"""Capture the replay fixtures (`mock_flight.json` / `mock_hotel.json`).

This is the one sanctioned way to (re)build the fixtures: it spends one
REAL SerpApi call per kind and records it in the lifetime ledger, saves
the raw SerpApi response verbatim into ``backend/data/``, then runs the
shapers over it so we know the fixture replays cleanly.

Run only when a fixture is actually missing/corrupt — the lifetime
budget is small (MAX_CALLS across the app's whole life).

    ../../venv/bin/python -m tests_dev.capture_fixtures          (from backend/)
    venv/bin/python -m backend.tests_dev.capture_fixtures        (from repo root)
"""
import json
import sys
from pathlib import Path

from backend.src.services import serp_service as svc  # noqa: E402


def daystamp(offset: int) -> str:
    import time
    d = time.localtime()
    return time.strftime("%Y-%m-%d", time.struct_time(
        (d.tm_year, d.tm_mon, d.tm_mday + offset, 0, 0, 0, 0, 0, -1)))


FLIGHT_PARAMS = {
    "engine": "google_flights", "hl": "en", "gl": "in", "currency": "INR",
    "type": 1, "departure_id": "DEL", "arrival_id": "BOM",
    "outbound_date": daystamp(9), "return_date": daystamp(14),
    "travel_class": 1, "adults": 2, "children": 0,  # 1 = economy (SerpApi int)
}

HOTEL_PARAMS = {
    "engine": "google_hotels", "hl": "en", "gl": "in", "currency": "INR",
    "q": "Goa", "check_in_date": daystamp(9), "check_out_date": daystamp(11),
    "adults": 2, "children": 0, "sort_by": "3",
}

SHAPE = {"flight": svc.shape_flight, "hotel": svc.shape_hotel}
PARAMS = {"flight": FLIGHT_PARAMS, "hotel": HOTEL_PARAMS}


def capture(kind: str) -> None:
    fixture = svc.FIXTURES[kind]
    raw = svc._serp_request(kind, PARAMS[kind])  # ledger + raw response
    payload = SHAPE[kind](raw)  # proves the raw response replays cleanly
    tmp = fixture.with_suffix(".tmp")
    tmp.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    import os
    os.replace(tmp, fixture)
    spot = {k: payload.get(k) for k in
            ("currency", "mock", "cached") if k in payload}
    if kind == "flight":
        spot["best"] = len(payload.get("best", []))
    else:
        spot["properties"] = len(payload.get("properties", []))
    print(f"{kind}: fixture captured -> {fixture.name} | shaped: {spot}")


def main() -> None:
    info = svc.budget()
    print("budget before:", info["used"], "used,", info["remaining"], "remaining")
    if info["remaining"] < len(KINDS := [k for k in ("flight", "hotel")]):
        sys.exit(f"need {len(KINDS)} calls free, only {info['remaining']} left — aborting")
    if not svc._api_key():
        sys.exit("SERP_API is not configured (.env) — aborting")
    try:
        for kind in KINDS:
            capture(kind)
    except Exception as exc:
        sys.exit(f"capture failed mid-run ({exc!r}) — ledger/fixture state is partial, check data/")
    print("budget after:", svc.budget()["used"], "used")


if __name__ == "__main__":
    main()
