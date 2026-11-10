"""Dev smoke test for the live-only SerpApi layer.

Runs entirely on a stubbed urlopen — no code path can ever reach the
network, and the real cache dir is restored pristine at the end.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.__main__ import app  # noqa: E402
from backend.src.services import serp_service  # noqa: E402

client = app.test_client()
fails = []

# --- redirect the cache to a scratch dir so the real one is never touched
_cache_backup = serp_service.CACHE_DIR
serp_service.CACHE_DIR = Path(tempfile.mkdtemp(prefix="vovage-test-cache-"))

# --- hard network guard: anything reaching here means the code tried the wire
def _no_network(url, timeout=0, **kw):
    raise RuntimeError(f"TEST GUARD: attempted network call -> {url}")

_orig_urlopen = serp_service.urllib.request.urlopen
serp_service.urllib.request.urlopen = _no_network


def check(name, cond, extra=""):
    print(("PASS" if cond else "FAIL"), name, extra if not cond else "")
    if not cond:
        fails.append(name)


def raw_flight():
    """A minimal realistic Google Flights response."""
    return {
        "search_parameters": {
            "departure_id": "DEL", "arrival_id": "BOM",
            "outbound_date": "2026-11-20", "return_date": "2026-11-24",
            "currency": "INR",
        },
        "price_insights": {
            "lowest_price": 4120, "price_level": "low",
            "typical_price_range": [3800, 6100],
            "price_history": [[1760000000, 4800], [1760100000, 4120]],
        },
        "best_flights": [{
            "price": 4120, "total_duration": 7350,
            "flights": [{
                "departure_airport": {"id": "DEL", "name": "Delhi",
                                      "time": "2026-11-20 08:30"},
                "arrival_airport": {"id": "BOM", "name": "Mumbai",
                                    "time": "2026-11-20 10:35"},
                "duration": 7500, "airline": "Vistara",
                "airline_logo": "x.png", "travel_class": "Economy",
                "flight_number": "UK 931",
            }],
            "layovers": [],
            "booking_token": "tok-1",
        }],
        "other_flights": [],
    }


try:
    # --- IATA autocomplete (local, free, no network)
    r = client.get("/api/flight/airports?q=del")
    hits = r.get_json()["results"]
    check("airports q=del has DEL", r.status_code == 200 and hits[0]["code"] == "DEL", str(hits[:2]))
    r = client.get("/api/flight/airports?q=mumbai")
    check("airports q=mumbai has BOM",
          any(h["code"] == "BOM" for h in r.get_json()["results"]))
    check("airports empty q", client.get("/api/flight/airports?q=").get_json()["results"] == [])

    # --- validation (no network)
    r = client.get("/api/flight/search?origin=DEL&destination=DEL&outbound_date=2026-11-10&return_date=2026-11-14")
    check("flight search rejects same airports", r.status_code == 400)
    r = client.get("/api/flight/search?origin=DEL&destination=BOM&outbound_date=2026-13-99&return_date=2026-11-14")
    check("flight search rejects bad date", r.status_code == 400)
    r = client.get("/api/flight/search?origin=DEL&destination=BOM&outbound_date=2026-11-14&return_date=2026-11-10")
    check("flight search rejects inverted dates", r.status_code == 400)
    r = client.get("/api/hotel/search?q=Bali&check_in_date=2026-11-10&check_out_date=2026-11-09")
    check("hotel search rejects inverted dates", r.status_code == 400)

    # --- live path (stubbed network, schema only)
    class FakeResp:
        def __init__(self, payload): self.payload = payload
        def read(self): return json.dumps(self.payload).encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    serp_service.urllib.request.urlopen = lambda url, timeout=0: FakeResp(raw_flight())
    r = client.get("/api/flight/search?origin=DEL&destination=BOM&outbound_date=2026-11-20&return_date=2026-11-24")
    got = r.get_json()
    check("live-path stub 200", r.status_code == 200, str(r.status_code) + str(got)[:160])
    check("flagged live (not cached)",
          got.get("cached") is False and "mock" not in got, str(got)[:120])
    best = got.get("best", [])
    check("live best list", len(best) > 0, str(len(best)))
    if best:
        first = best[0]
        check("leg shape",
              bool(first.get("price")) and bool(first.get("legs"))
              and first["legs"][0].get("dep_code"),
              str(first)[:200])
    check("currency sane",
          isinstance(got.get("currency"), str) and len(got.get("currency", "")) == 3,
          str(got.get("currency")))
    check("insights shaped", bool(got.get("insights")), str(got.get("insights"))[:120])
    check("no budget key in payload", "budget" not in got)

    # --- repeat search is served from cache, never the wire
    calls = {"n": 0}
    def counting_urlopen(url, timeout=0):
        calls["n"] += 1
        return FakeResp(raw_flight())
    serp_service.urllib.request.urlopen = counting_urlopen
    r = client.get("/api/flight/search?origin=DEL&destination=BOM&outbound_date=2026-11-20&return_date=2026-11-24")
    got2 = r.get_json()
    check("repeat from cache", r.status_code == 200 and got2["cached"] is True)
    check("cache hit made zero network calls", calls["n"] == 0, str(calls["n"]))
    check("cache trip echo", got2["trip"]["origin"] == "DEL"
          and got2["trip"]["return_date"] == "2026-11-24")

    # --- no mock/backdoor anywhere
    r = client.get("/api/flight/search?origin=DEL&destination=BOM&outbound_date=2026-12-01&return_date=2026-12-05&mock=1")
    check("mock param is inert (still live path)",
          r.status_code == 200 and r.get_json()["cached"] is False and calls["n"] == 1,
          str(r.status_code))
finally:
    serp_service.urllib.request.urlopen = _orig_urlopen
    shutil.rmtree(serp_service.CACHE_DIR, ignore_errors=True)
    serp_service.CACHE_DIR = _cache_backup
    print("urlopen restored; cache scratch cleaned; real cache untouched")

print()
print("RESULT:", "ALL PASS" if not fails else f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
