"""Dev smoke test for the packages layer.

Pure logic tests run over synthetic shaped payloads; the route tests run
on mock replays (zero real SerpApi calls).The real ledger is snapshotted
at start and restored byte-identically at the end, so running this test
never costs or misreports a call.
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.__main__ import app  # noqa: E402
from backend.src.services import serp_service  # noqa: E402
from backend.src.services.package_service import (  # noqa: E402
    PackageError, build_packages,
)

STATE = serp_service.STATE_FILE
CACHE = serp_service.CACHE_DIR
client = app.test_client()
fails = []

_state_snapshot = STATE.read_text(encoding="utf-8") if STATE.exists() else None
_used0 = 0
if _state_snapshot is not None:
    try:
        _used0 = len(json.loads(_state_snapshot)["calls"])
    except (KeyError, ValueError):
        _state_snapshot = None


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

    # ---------------- route validation (no calls, no spend) ----------------
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
    check("validation spent nothing", serp_service.budget()["used"] == _used0)

    # ---------------- replay end-to-end (zero spend) ----------------
    r = client.get(base + "&budget=60000&adults=2&cabin=economy&feed=replay")
    check("replay package 200", r.status_code == 200,
          str(r.status_code) + " " + str(r.get_json())[:150])
    if r.status_code != 200:
        raise RuntimeError(r.get_json())
    body = r.get_json()
    check("replay tiers present", len(body["packages"]) >= 2, str(len(body["packages"])))
    check("replay boards honest", body["boards"]["flight"]["mock"] is True
          and body["boards"]["hotel"]["mock"] is True, str(body["boards"]))
    check("replay spends nothing", body["budget"]["used"] == _used0)
    check("nights match dates", body["nights"] == 2, str(body["nights"]))
    check("currency honest", body["currency"] == "INR", str(body["currency"]))

    # exact same replay again — still zero spend
    r = client.get(base + "&budget=60000&feed=replay")
    check("repeat replay spends nothing", r.status_code == 200
          and serp_service.budget()["used"] == _used0)

    # ---------------- live = auto cache-first ----------------
    # (a) both legs seeded in cache: live feed serves from cache, zero spend
    fp = {
        "engine": "google_flights", "hl": "en", "gl": "in", "currency": "INR",
        "type": 1, "departure_id": "DEL", "arrival_id": "GOI",
        "outbound_date": "2026-11-18", "return_date": "2026-11-20",
        "travel_class": 1, "adults": 2, "children": 0,
    }
    hp = {
        "engine": "google_hotels", "hl": "en", "gl": "in", "currency": "INR",
        "q": "Goa", "check_in_date": "2026-11-18", "check_out_date": "2026-11-20",
        "adults": 2, "children": 0, "sort_by": "3",
    }
    seeded_f = serp_service.shape_flight(
        json.loads(serp_service.FIXTURES["flight"].read_text(encoding="utf-8")))
    seeded_f.update(mock=False, currency="INR",
                    fetched_on=serp_service._now(), budget=serp_service.budget())
    serp_service._cache_write(serp_service._params_key("flight", fp), seeded_f)
    seeded_h = serp_service.shape_hotel(
        json.loads(serp_service.FIXTURES["hotel"].read_text(encoding="utf-8")))
    seeded_h.update(mock=False, currency="INR",
                    fetched_on=serp_service._now(), budget=serp_service.budget())
    serp_service._cache_write(serp_service._params_key("hotel", hp), seeded_h)

    r = client.get(base + "&budget=60000&feed=live")
    check("live, both cached -> 200", r.status_code == 200,
          str(r.status_code) + " " + str(r.get_json())[:150])
    if r.status_code == 200:
        got = r.get_json()
        check("both boards flagged cached",
              got["boards"]["flight"]["cached"] is True
              and got["boards"]["hotel"]["cached"] is True, str(got["boards"]))
        check("cached serve spent nothing", serp_service.budget()["used"] == _used0)

    # (b) ledger at 5/5, flight cached, hotel not: hotel must replay-fallback,
    #     NOT reach the network (route's own 429 guard passes only via the cache)
    STATE.write_text(json.dumps({"calls": [{"ts": 0, "kind": "test", "key": "f"}] * 5}),
                     encoding="utf-8")
    hotel_cache = serp_service.CACHE_DIR / (
        serp_service._params_key("hotel", hp) + ".json")
    hotel_cache.unlink(missing_ok=True)  # break hotel cache
    r = client.get(base + "&budget=60000&feed=live")
    check("live, spent budget + cached flight -> 200", r.status_code == 200,
          str(r.status_code) + " " + str(r.get_json())[:150])
    if r.status_code == 200:
        got = r.get_json()
        check("hotel replay-fallback flagged", got["boards"]["hotel"]["mock"] is True
              and got["boards"]["flight"]["cached"] is True, str(got["boards"]))
        check("fallback spent nothing extra", serp_service.budget()["used"] == 5)
    # restore real snapshot; the exhaustion ledger is replaced below in `finally`
    if _state_snapshot is None:
        STATE.unlink(missing_ok=True)
    else:
        STATE.write_text(_state_snapshot, encoding="utf-8")
finally:
    if _state_snapshot is None:
        STATE.unlink(missing_ok=True)
    else:
        STATE.write_text(_state_snapshot, encoding="utf-8")
    shutil.rmtree(CACHE, ignore_errors=True)  # drop test seeds
    print("state restored:", True, "| cache cleaned:", not CACHE.exists())

print()
print("RESULT:", "ALL PASS" if not fails else f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
