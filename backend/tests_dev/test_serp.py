"""Dev smoke test for the SerpApi layer.

Runs entirely on mock replays and local fixtures — zero real SerpApi
calls. urlopen is stubbed for the whole run so no code path can ever
reach the network, and the budget ledger is restored pristine at the end.
"""
import json
import shutil
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.__main__ import app  # noqa: E402
from backend.src.services import serp_service  # noqa: E402

STATE = serp_service.STATE_FILE
CACHE = serp_service.CACHE_DIR
client = app.test_client()
fails = []

# --- hard network guard: anything reaching here means the code tried the wire
def _no_network(url, timeout=0, **kw):
    raise RuntimeError(f"TEST GUARD: attempted network call -> {url}")

_orig_urlopen = serp_service.urllib.request.urlopen
serp_service.urllib.request.urlopen = _no_network


def check(name, cond, extra=""):
    print(("PASS" if cond else "FAIL"), name, extra if not cond else "")
    if not cond:
        fails.append(name)


try:
    # --- real budget untouched at start
    assert not STATE.exists(), "serp_state.json exists before any real call!"
    b = client.get("/api/serp/budget").get_json()
    check("budget starts clean", b == {"max": 5, "used": 0, "remaining": 5, "calls": []}, str(b))

    # --- IATA autocomplete (local, free)
    r = client.get("/api/flight/airports?q=del")
    hits = r.get_json()["results"]
    check("airports q=del has DEL", r.status_code == 200 and hits[0]["code"] == "DEL", str(hits[:2]))
    r = client.get("/api/flight/airports?q=mumbai")
    check("airports q=mumbai has BOM",
          any(h["code"] == "BOM" for h in r.get_json()["results"]))
    check("airports empty q", client.get("/api/flight/airports?q=").get_json()["results"] == [])

    # --- validation (no call, no money)
    r = client.get("/api/flight/search?origin=DEL&destination=DEL&outbound_date=2026-11-10&return_date=2026-11-14")
    check("flight search rejects same airports", r.status_code == 400)
    r = client.get("/api/flight/search?origin=DEL&destination=BOM&outbound_date=2026-13-99&return_date=2026-11-14")
    check("flight search rejects bad date", r.status_code == 400)
    r = client.get("/api/hotel/search?q=Bali&check_in_date=2026-11-10&check_out_date=2026-11-09")
    check("hotel search rejects inverted dates", r.status_code == 400)
    check("state still clean after validation", not STATE.exists())

    # --- mock replay flight (zero spend)
    r = client.get("/api/flight/search?origin=DEL&destination=BOM&outbound_date=2026-11-10"
                   "&return_date=2026-11-14&travel_class=economy&mock=1")
    fl = r.get_json()
    check("mock flight 200", r.status_code == 200, str(r.status_code))
    check("mock flight flag", fl.get("mock") is True and fl.get("cached") is False)
    check("mock flight best list", len(fl.get("best", [])) == 5, str(len(fl.get("best", []))))
    check("mock flight budget untouched", fl["budget"]["used"] == 0)
    check("mock flight currency honest", fl.get("currency") == "USD", str(fl.get("currency")))
    first = fl["best"][0]
    check("mock leg shape", first["legs"][0]["dep_code"] == "DEL" and first["price"] == 56,
          str(first)[:200])
    check("mock insights", fl["insights"]["low"] == 56 and len(fl["insights"]["history"]) > 0)

    # --- mock replay hotel (zero spend)
    r = client.get("/api/hotel/search?q=Bali Resorts&check_in_date=2026-11-10&check_out_date=2026-11-11&mock=1")
    ho = r.get_json()
    check("mock hotel 200", r.status_code == 200)
    check("mock hotel props", ho["count"] == 20 and len(ho["properties"]) == 20)
    p = ho["properties"][0]
    check("props shape", p["name"].startswith("The Anvaya") and p["price"] == 118
          and p["rating"] == 4.7 and len(p["images"]) > 0,
          str({k: p[k] for k in ("name", "price", "rating")}))
    check("deal badge exists", any(pp.get("deal") for pp in ho["properties"]))
    check("mock hotel budget untouched", ho["budget"]["used"] == 0)
    check("state still clean after mocks", not STATE.exists())

    # --- cache round-trip: seed with the exact params the route builds
    params = {
        "engine": "google_flights", "hl": "en", "gl": "in", "currency": "INR",
        "type": 1, "departure_id": "DEL", "arrival_id": "BOM",
        "outbound_date": "2026-12-01", "return_date": "2026-12-05",
        "travel_class": "economy", "adults": 2, "children": 0,
    }
    seeded = dict(serp_service.shape_flight(
        json.loads(serp_service.FIXTURES["flight"].read_text(encoding="utf-8"))))
    # mirror exactly what a real run persists after shaping
    seeded["mock"] = False
    seeded["currency"] = "INR"
    seeded["trip"] = {"origin": "DEL", "destination": "BOM",
                      "outbound_date": "2026-12-01", "return_date": "2026-12-05"}
    seeded["budget"] = serp_service.budget()
    seeded["fetched_on"] = serp_service._now()
    serp_service._cache_write(serp_service._params_key("flight", params), seeded)
    check("cache file seeded", CACHE.exists() and any(CACHE.iterdir()))

    r = client.get("/api/flight/search?origin=DEL&destination=BOM&outbound_date=2026-12-01&return_date=2026-12-05")
    got = r.get_json()
    check("cache hit served", r.status_code == 200 and got.get("cached") is True
          and got.get("mock") is False, str(r.status_code) + str(got)[:120])
    check("cache hit spends nothing", got.get("budget", {}).get("used") == 0 and not STATE.exists())
    check("cache trip echo", got["trip"]["origin"] == "DEL"
          and got["trip"]["return_date"] == "2026-12-05")

    # --- budget exhaustion guard (fake ledger, then cleaned up)
    STATE.write_text(json.dumps({"calls": [{"ts": 0, "kind": "test", "key": "x"}] * 5}),
                     encoding="utf-8")
    r = client.get("/api/flight/search?origin=DEL&destination=BOM&outbound_date=2026-11-10&return_date=2026-11-14")
    check("exhaustion -> 429", r.status_code == 429, str(r.status_code))
    check("429 message mentions budget", "budget" in r.get_json()["error"])
    r = client.get("/api/hotel/search?q=Bali&check_in_date=2026-11-10&check_out_date=2026-11-11")
    check("exhaustion -> 429 hotel", r.status_code == 429)
    b = client.get("/api/serp/budget").get_json()
    check("budget endpoint reports 0", b["remaining"] == 0 and b["used"] == 5)
    STATE.unlink()  # restore pristine budget
    print("state restored:", not STATE.exists())

    # --- real-path registration (stubbed network, schema only)
    class FakeResp:
        def __init__(self, payload): self.payload = payload
        def read(self): return json.dumps(self.payload).encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    fake_flight = json.loads(serp_service.FIXTURES["flight"].read_text(encoding="utf-8"))
    serp_service.urllib.request.urlopen = lambda url, timeout=0: FakeResp(fake_flight)
    r = client.get("/api/flight/search?origin=DEL&destination=BOM&outbound_date=2026-11-20&return_date=2026-11-24")
    got = r.get_json()
    check("real-path stub 200", r.status_code == 200, str(r.status_code) + str(got)[:120])
    b = serp_service.budget()
    check("ledger spent 1 of 5", b["used"] == 1 and b["remaining"] == 4, str(b))
    check("ledger logged flight", b["calls"][0]["kind"] == "flight")
    r = client.get("/api/flight/search?origin=DEL&destination=BOM&outbound_date=2026-11-20&return_date=2026-11-24")
    check("repeat from cache", r.get_json()["cached"] is True and serp_service.budget()["used"] == 1)
finally:
    serp_service.urllib.request.urlopen = _orig_urlopen
    STATE.unlink(missing_ok=True)
    shutil.rmtree(CACHE, ignore_errors=True)  # drop test seeds
    print("state cleaned:", not STATE.exists(), "| cache cleaned:", not CACHE.exists())

print()
print("RESULT:", "ALL PASS" if not fails else f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
