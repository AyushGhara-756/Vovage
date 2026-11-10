"""Dev smoke test for the packages layer.

Pure logic tests run over synthetic shaped payloads; the route tests
exercise the live path with a stubbed urlopen (no real SerpApi calls)
and a scratch cache dir, restored pristine at the end.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.__main__ import app  # noqa: E402
from backend.src.services import serp_service  # noqa: E402
from backend.src.services.package_service import (  # noqa: E402
    PackageError, build_packages,
)

client = app.test_client()
fails = []

# --- redirect the cache to a scratch dir so the real one is never touched
_cache_backup = serp_service.CACHE_DIR
serp_service.CACHE_DIR = Path(tempfile.mkdtemp(prefix="vovage-test-cache-"))

_orig_urlopen = serp_service.urllib.request.urlopen


def check(name, cond, extra=""):
    print(("PASS" if cond else "FAIL"), name, extra if not cond else "")
    if not cond:
        fails.append(name)


def fare(price, name="IndiGo"):
    return {
        "price": price,
        "legs": [{"dep_code": "DEL", "dep_time": "2026-11-18 08:45",
                  "arr_code": "GOI", "arr_time": "2026-11-18 11:10",
                  "airline": name, "logo": "", "duration": 145}],
        "layovers": [],
        "duration": 145, "logo": "", "carbon": None, "token": "t",
    }


def stay(name, total_price, rating, class_num=3, per_night=None):
    return {
        "name": name, "type": "hotel", "link": "http://x", "rating": rating,
        "reviews": 100, "class_num": class_num, "amenities": ["A", "B"],
        "images": [{"thumb": "t.jpg", "full": "f.jpg"}], "nearby": [],
        "price": per_night, "total_price": total_price,
    }


FLIGHT = {"currency": "INR", "best": [fare(5000), fare(9000)],
          "selected": [], "others": [],
          "trip": {"origin": "DEL", "destination": "GOI"}}

HOTEL = {"currency": "INR", "q": "Goa", "count": 3, "properties": [
    stay("Budget Inn", 6000, 4.0, 2),
    stay("Lux Palace", 20000, 4.9, 5),
    stay("Mid Cozy", 9000, 4.6, 3),
]}


def put(q, guests=2, budget=20000, nights=None, **kw):
    return build_packages(FLIGHT, HOTEL, budget,
                          nights=nights if nights is not None else 2,
                          adults=guests, children=kw.get("children", 0))


try:
    # ---------------- pure logic ----------------
    p = put("GOI")
    check("three tiers", [x["tier"] for x in p["packages"]]
          == ["saver", "balanced", "comfort"], str(p["packages"]))
    saver = p["packages"][0]
    check("saver total = flight + hotel",
          saver["total"] == 2 * 5000 + 6000
          and saver["breakdown"]["flight"] == 10000
          and saver["breakdown"]["hotel"] == 6000, str(saver))
    check("saver within budget", saver["within_budget"] and saver["headroom"] == 4000)
    balanced = p["packages"][1]
    check("balanced picks highest rated that fits",
          balanced["stay"]["name"] == "Mid Cozy"
          and balanced["breakdown"]["hotel"] == 9000,
          str(balanced["stay"]))
    comfort = p["packages"][2]
    check("comfort picks best rated overall",
          comfort["stay"]["name"] == "Lux Palace"
          and comfort["breakdown"]["hotel"] == 20000,
          str(comfort["stay"]))
    check("comfort flagged over budget",
          not comfort["within_budget"] and comfort["over_by"]
          == comfort["total"] - p["budget"], str(comfort["total"]))

    # children multiply the fare like adults
    pc = put("GOI", guests=2, children=1)
    check("children count as travellers",
          pc["packages"][0]["breakdown"]["flight"] == 3 * 5000,
          str(pc["packages"][0]))

    # per-night fallback: property without total_price
    night_hotel = {"currency": "INR", "q": "Goa", "count": 1, "properties": [
        stay("Nightly Only", None, 4.2, 3, per_night=2000),
    ]}
    pn = build_packages(FLIGHT, night_hotel, 20000, nights=3, adults=2)
    check("nightly fallback = rate × nights",
          pn["packages"][0]["breakdown"]["hotel"] == 6000
          and pn["packages"][0]["stay"]["per_night_estimate"] is True,
          str(pn["packages"][0]))

    # tight budget: nothing fits, balanced tier vanishes
    pt = put("GOI", budget=4000)
    check("tight budget drops balanced tier",
          [x["tier"] for x in pt["packages"]] == ["saver", "comfort"],
          str(pt["packages"]))

    # empty boards raise
    try:
        build_packages({"best": [], "selected": [], "others": []}, HOTEL, 100, nights=2)
        check("no fares raises", False)
    except PackageError:
        check("no fares raises", True)
    try:
        build_packages(FLIGHT, {"properties": []}, 100, nights=2)
        check("no stays raises", False)
    except PackageError:
        check("no stays raises", True)

    # ---------------- route validation (no network) ----------------
    base = "/api/package/search?origin=DEL&destination=GOI&q=Goa&outbound_date=2026-11-18&return_date=2026-11-20"

    r = client.get(base + "&budget=0")
    check("rejects zero budget", r.status_code == 400, str(r.status_code))
    r = client.get("/api/package/search?origin=DEL&destination=GOI&q=Goa&outbound_date=2026-11-20&return_date=2026-11-18&budget=1000")
    check("rejects inverted dates", r.status_code == 400)
    r = client.get(base.replace("outbound_date=2026-11-18", "outbound_date=bad") + "&budget=100")
    check("rejects bad date", r.status_code == 400)
    r = client.get("/api/package/search?origin=DEL&destination=GOI&outbound_date=2026-11-18&return_date=2026-11-20&budget=100")
    check("rejects missing q", r.status_code == 400)
    r = client.get(base + "&budget=abc")
    check("rejects non-numeric budget", r.status_code == 400)
    r = client.get(base + "&budget=1000&feed=replay")
    check("feed param is inert", r.status_code in (200, 502), str(r.status_code))

    # ---------------- live route, uncached: two stubbed network calls ----------------
    shaped_flight = dict(FLIGHT)
    shaped_flight.update(cached=False, fetched_on="2026-11-10 09:00")
    shaped_hotel = dict(HOTEL)
    shaped_hotel.update(cached=False, fetched_on="2026-11-10 09:00")

    class FakeResp:
        def __init__(self, payload): self.payload = payload
        def read(self): return json.dumps(self.payload).encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    # serve a shaped payload straight back (cache-write persists it verbatim)
    serp_service._cache_write(
        serp_service._params_key("flight", {
            "engine": "google_flights", "hl": "en", "gl": "in", "currency": "INR",
            "type": 1, "departure_id": "DEL", "arrival_id": "GOI",
            "outbound_date": "2026-11-18", "return_date": "2026-11-20",
            "travel_class": 1, "adults": 2, "children": 0,
        }), shaped_flight)
    serp_service._cache_write(
        serp_service._params_key("hotel", {
            "engine": "google_hotels", "hl": "en", "gl": "in", "currency": "INR",
            "q": "Goa", "check_in_date": "2026-11-18", "check_out_date": "2026-11-20",
            "adults": 2, "children": 0, "sort_by": "3",
        }), shaped_hotel)

    calls = {"n": 0}
    def counting_urlopen(url, timeout=0):
        calls["n"] += 1
        return FakeResp({})
    serp_service.urllib.request.urlopen = counting_urlopen

    r = client.get(base + "&budget=60000&adults=2&cabin=economy")
    check("package route 200", r.status_code == 200,
          str(r.status_code) + " " + str(r.get_json())[:160])
    if r.status_code == 200:
        body = r.get_json()
        check("tiers present", len(body["packages"]) >= 2, str(len(body["packages"])))
        check("boards flagged cached, no mock key",
              body["boards"]["flight"]["cached"] is True
              and body["boards"]["hotel"]["cached"] is True
              and "mock" not in body["boards"]["flight"], str(body["boards"]))
        check("cache-first made zero network calls", calls["n"] == 0, str(calls["n"]))
        check("budget key is the trip ceiling (not a ledger)",
              body["budget"] == 60000, str(body.get("budget")))
        check("nights match dates", body["nights"] == 2, str(body["nights"]))
        check("trip budget echoed", body["trip_budget"] == 60000)
        check("currency honest", body["currency"] == "INR", str(body["currency"]))

    # repeat request — still zero network
    r = client.get(base + "&budget=60000")
    check("repeat served from cache", r.status_code == 200 and calls["n"] == 0,
          f"{r.status_code} net={calls['n']}")
finally:
    serp_service.urllib.request.urlopen = _orig_urlopen
    shutil.rmtree(serp_service.CACHE_DIR, ignore_errors=True)
    serp_service.CACHE_DIR = _cache_backup
    print("urlopen restored; cache scratch cleaned; real cache untouched")

print()
print("RESULT:", "ALL PASS" if not fails else f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
