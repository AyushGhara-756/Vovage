"""SerpApi integration (Google Flights + Google Hotels).

Ground rules baked into this module:

- The app may spend **MAX_CALLS** real SerpApi calls in its entire
  lifetime. The ledger lives in ``backend/data/serp_state.json`` and
  survives server restarts; once spent, no request path can spend more.
- Every successful real search is cached (params-keyed JSON under
  ``backend/data/serp_cache/``) — identical repeat searches are served
  from disk and cost nothing.
- ``mock=True`` replays the captured fixtures in ``backend/data/``
  (zero cost, never touches the ledger).
- Airport autocomplete is served from the local IATA dataset — it
  never spends a call.
"""

import hashlib
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# project root (backend/src/services -> up 3)
ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "backend" / "data"

STATE_FILE = DATA_DIR / "serp_state.json"
CACHE_DIR = DATA_DIR / "serp_cache"
IATA_FILE = DATA_DIR / "iata-airport_codes.json"
FIXTURES = {
    "flight": DATA_DIR / "mock_flight.json",
    "hotel": DATA_DIR / "mock_hotel.json",
}

MAX_CALLS = 5
API_URL = "https://serpapi.com/search.json"
TIMEOUT = 60

_IATA_WARNED = False  # one-time warning flag for a missing/corrupt dataset


class SerpError(Exception):
    """Raised for anything wrong with a SerpApi round-trip."""


class BudgetExhausted(SerpError):
    """The lifetime call budget is spent; only cache/mock remain."""


# ------------------------------------------------------------------ state

def _load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"calls": []}
    except (json.JSONDecodeError, OSError):
        return {"calls": []}


def _save_state(state):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


def budget():
    """Calls spent vs the lifetime allowance."""
    calls = _load_state().get("calls", [])
    return {
        "max": MAX_CALLS,
        "used": len(calls),
        "remaining": max(0, MAX_CALLS - len(calls)),
        "calls": calls[-5:],
    }


def _api_key():
    key = os.environ.get("SERP_API") or os.environ.get("SERPAPI_KEY")
    if not key and (ROOT / ".env").exists():
        for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line.startswith("SERP_API="):
                key = line.split("=", 1)[1].strip()
                break
    if not key:
        raise SerpError("SERP_API is not configured (.env)")
    return key


# ------------------------------------------------------------------ cache

def _params_key(kind, params):
    blob = urllib.parse.urlencode(sorted((k, str(v)) for k, v in params.items()))
    return hashlib.sha1(f"{kind}|{blob}".encode("utf-8")).hexdigest()[:24]


def _cache_read(key):
    path = CACHE_DIR / f"{key}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _cache_write(key, payload):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = (CACHE_DIR / f"{key}.json").with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, CACHE_DIR / f"{key}.json")
    except OSError:
        pass  # cache is best-effort


# ------------------------------------------------------------------ engine

def _now():
    return time.strftime("%Y-%m-%d %H:%M", time.localtime())


def _serp_request(kind, params):
    info = budget()
    if info["remaining"] <= 0:
        raise BudgetExhausted(
            f"lifetime SerpApi budget spent ({MAX_CALLS}/{MAX_CALLS}) — "
            "only cached results remain"
        )

    query = dict(params)
    query["api_key"] = _api_key()
    url = f"{API_URL}?{urllib.parse.urlencode(query)}"

    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            body = json.loads(exc.read().decode("utf-8"))
            detail = str(body.get("error", ""))
        except Exception:
            pass
        raise SerpError(f"serpapi returned HTTP {exc.code}"
                        + (f" — {detail}" if detail else "")) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SerpError("could not reach serpapi") from exc

    if isinstance(raw, dict) and raw.get("error"):
        raise SerpError(str(raw["error"]))

    # a successful, billable search — spend exactly one call
    state = _load_state()
    state.setdefault("calls", []).append(
        {"ts": int(time.time()), "kind": kind, "key": _params_key(kind, params)}
    )
    _save_state(state)
    return raw


def run_search(kind, params, shape, mock=False):
    """Execute (or replay/cache) a SerpApi search and return the shaped payload."""
    if mock:
        fixture = FIXTURES[kind]
        try:
            raw = json.loads(fixture.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
            raise SerpError(f"replay fixture {fixture.name} is missing") from exc
        payload = shape(raw)
        payload["mock"] = True
        payload["cached"] = False
        payload["fetched_on"] = _now()
        payload["currency"] = (payload.get("currency")
                               or raw.get("search_parameters", {}).get("currency")
                               or "USD")
        payload["budget"] = budget()  # replay spends nothing
        return payload

    key = _params_key(kind, params)
    cached = _cache_read(key)
    if cached is not None:
        cached["cached"] = True
        cached["budget"] = budget()  # serve from disk, no spend
        return cached

    raw = _serp_request(kind, params)
    payload = shape(raw)
    payload["mock"] = False
    payload["cached"] = False
    payload["fetched_on"] = _now()
    payload["budget"] = budget()
    _cache_write(key, payload)
    return payload


# ------------------------------------------------------------------ shaping

def _leg(flight):
    dep = flight.get("departure_airport") or {}
    arr = flight.get("arrival_airport") or {}
    return {
        "dep_code": dep.get("id"),
        "dep_name": dep.get("name"),
        "dep_time": dep.get("time"),
        "arr_code": arr.get("id"),
        "arr_name": arr.get("name"),
        "arr_time": arr.get("time"),
        "duration": flight.get("duration"),
        "airplane": flight.get("airplane"),
        "airline": flight.get("airline"),
        "logo": flight.get("airline_logo"),
        "cabin": flight.get("travel_class"),
        "flight": flight.get("flight_number"),
        "legroom": flight.get("legroom"),
        "overnight": bool(flight.get("overnight")),
    }


def _option(item):
    lays = item.get("layovers") or []
    return {
        "price": item.get("price"),
        "legs": [_leg(x) for x in (item.get("flights") or [])],
        "layovers": [
            {
                "duration": l.get("duration"),
                "name": l.get("name"),
                "overnight": bool(l.get("overnight")),
            }
            for l in lays
        ],
        "duration": item.get("total_duration"),
        "logo": item.get("airline_logo"),
        "carbon": (item.get("carbon_emissions") or {}).get("difference_percent"),
        "token": item.get("booking_token") or "",
    }


def _insights(pi):
    if not pi:
        return None
    return {
        "low": pi.get("lowest_price"),
        "level": pi.get("price_level"),
        "range": pi.get("typical_price_range") or [],
        "history": pi.get("price_history") or [],
    }


def shape_flight(raw):
    """Round-trip boards: departure_flights / return_flights / selected_flights.
    One-way boards: best_flights / other_flights. Whichever exist get shaped."""
    insights = _insights(raw.get("price_insights"))
    return {
        "currency": raw.get("search_parameters", {}).get("currency"),
        "insights": insights,
        "departures": [_option(o) for o in (raw.get("departure_flights") or [])],
        "returns": [_option(o) for o in (raw.get("return_flights") or [])],
        "selected": [_option(o) for o in (raw.get("selected_flights") or [])],
        "best": [_option(o) for o in (raw.get("best_flights") or [])],
        "others": [_option(o) for o in (raw.get("other_flights") or [])],
        "trip": {
            "origin": raw.get("search_parameters", {}).get("departure_id"),
            "destination": raw.get("search_parameters", {}).get("arrival_id"),
            "outbound_date": raw.get("search_parameters", {}).get("outbound_date"),
            "return_date": raw.get("search_parameters", {}).get("return_date"),
        },
    }


def _stay_card(p):
    rate = p.get("rate_per_night") or {}
    total = p.get("total_rate") or {}
    images = [
        {"thumb": i.get("thumbnail"), "full": i.get("original_image")}
        for i in (p.get("images") or [])
        if i.get("thumbnail") or i.get("original_image")
    ]
    nearby = []
    for n in (p.get("nearby_places") or [])[:4]:
        tr = (n.get("transportations") or [{}])[0]
        nearby.append({
            "name": n.get("name"),
            "by": f"{tr.get('type', '')} {tr.get('duration', '')}".strip() or None,
        })
    return {
        "name": p.get("name"),
        "type": p.get("type"),
        "link": p.get("link"),
        "hotel_class": p.get("hotel_class"),
        "class_num": p.get("extracted_hotel_class"),
        "rating": p.get("overall_rating"),
        "reviews": p.get("reviews"),
        "location_rating": p.get("location_rating"),
        "check_in_time": p.get("check_in_time"),
        "check_out_time": p.get("check_out_time"),
        "price": rate.get("extracted_lowest"),
        "price_display": rate.get("lowest"),
        "unit_price": rate.get("extracted_display_price"),
        "total_price": total.get("extracted_lowest"),
        "total_display": total.get("lowest"),
        "deal": p.get("deal"),
        "deal_description": p.get("deal_description"),
        "amenities": (p.get("amenities") or [])[:8],
        "images": images,
        "nearby": nearby,
        "desc": p.get("description"),
        "coords": p.get("gps_coordinates"),
    }


def shape_hotel(raw):
    props = raw.get("properties") or []
    return {
        "currency": raw.get("search_parameters", {}).get("currency"),
        "q": raw.get("search_parameters", {}).get("q"),
        "count": len(props),
        "properties": [_stay_card(p) for p in props],
    }


# ------------------------------------------------------------------ iata

_AIRPORT_INDEX = None


def _airport_index():
    global _AIRPORT_INDEX, _IATA_WARNED
    if _AIRPORT_INDEX is None:
        try:
            raw = json.loads(IATA_FILE.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
            if not _IATA_WARNED:
                logging.getLogger(__name__).warning(
                    "airport dataset %s is unreadable (%s) — "
                    "airport autocomplete will return no results",
                    IATA_FILE, exc,
                )
                _IATA_WARNED = True
            _AIRPORT_INDEX = []
        else:
            _AIRPORT_INDEX = [
                r for r in raw
                if r.get("iata_code") and len(r["iata_code"]) == 3
            ]
    return _AIRPORT_INDEX


def search_airports(q, limit=8):
    """Local IATA lookup — name / city / code prefix. Zero SerpApi calls."""
    query = (q or "").strip().lower()
    if not query:
        return []
    code_q = query.upper()
    scored = []
    for r in _airport_index():
        code = r.get("iata_code", "")
        name = (r.get("name") or "").lower()
        city = (r.get("municipality") or "").lower()
        if code.startswith(code_q):
            score = 3
        elif city and query in city:
            score = 2
        elif query in name:
            score = 1
        else:
            continue
        scored.append((score, code, r))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [
        {
            "code": code,
            "name": r.get("name"),
            "city": r.get("municipality"),
            "country": (r.get("iso_country") or ""),
        }
        for _, code, r in scored[:limit]
    ]
