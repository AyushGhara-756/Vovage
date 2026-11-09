"""Package board — one flight board + one hotel board, priced as tiers.

Spend policy (efficient by construction):

- ``feed=replay`` (default): both boards replay fixtures — zero cost.
- ``feed=live``: both boards go through ``run_search``, which is
  cache-first — identical params are served from disk at zero cost and
  only a genuine cache miss spends a call.
- If the lifetime budget runs dry between the two boards (or when fewer
  than the needed calls remain and neither board is cached), the hotel
  board silently falls back to a fixture replay and the per-board tags
  say so. A hard 429 only fires when the flight leg itself can't be
  served without spending and the budget is spent.
"""
import re
from datetime import date

from flask import Blueprint, jsonify, request

from ..services import serp_service
from ..services.package_service import PackageError, build_packages
from ..services.serp_service import SerpError, BudgetExhausted, shape_flight, shape_hotel
from .flights import _CABINS, _CLASS_ID, _truthy, _DATE

package_bp = Blueprint("package", __name__, url_prefix="/api/package")

_MAX_NIGHTS = 30


def _params_flight(origin, destination, outbound, ret, cabin_id, adults, children):
    return {
        "engine": "google_flights", "hl": "en", "gl": "in", "currency": "INR",
        "type": 1, "departure_id": origin, "arrival_id": destination,
        "outbound_date": outbound, "return_date": ret,
        "travel_class": cabin_id, "adults": adults, "children": children,
    }


def _params_hotel(q, check_in, check_out, adults, children):
    return {
        "engine": "google_hotels", "hl": "en", "gl": "in", "currency": "INR",
        "q": q, "check_in_date": check_in, "check_out_date": check_out,
        "adults": adults, "children": children, "sort_by": "3",
    }


def _cached(kind, params):
    return serp_service._cache_read(serp_service._params_key(kind, params)) is not None


@package_bp.route("/search", methods=["GET"])
def search():
    """Three package tiers from one flight + one hotel board."""
    args = request.args
    origin = (args.get("origin") or "").strip().upper()
    destination = (args.get("destination") or "").strip().upper()
    q = (args.get("q") or "").strip()
    outbound = (args.get("outbound_date") or "").strip()
    ret = (args.get("return_date") or "").strip()
    feed = (args.get("feed") or "replay").strip().lower()
    if feed not in ("live", "replay"):
        return jsonify({"error": 'feed must be "live" or "replay"'}), 400

    if not (origin and destination and outbound and ret and q):
        return jsonify({"error":
                        "origin, destination, q, outbound_date and return_date "
                        "are required"}), 400
    if origin == destination:
        return jsonify({"error": "origin and destination must differ"}), 400
    if not (_DATE.match(outbound) and _DATE.match(ret)):
        return jsonify({"error": "dates must be YYYY-MM-DD"}), 400
    if ret <= outbound:
        return jsonify({"error": "return_date must be after outbound_date"}), 400
    nights = (date.fromisoformat(ret) - date.fromisoformat(outbound)).days
    if nights > _MAX_NIGHTS:
        return jsonify({"error": f"trips longer than {_MAX_NIGHTS} nights aren't supported"}), 400

    budget_raw = args.get("budget", "")
    try:
        budget = int(float(budget_raw))
    except ValueError:
        return jsonify({"error": "budget must be a number of rupees"}), 400
    if budget <= 0:
        return jsonify({"error": "budget must be a positive number of rupees"}), 400

    cabin = (args.get("cabin") or "economy").strip().lower()
    if cabin not in _CABINS:
        return jsonify({"error": "cabin must be one of " + ", ".join(_CABINS)}), 400

    try:
        adults = min(8, max(1, int(args.get("adults", 2))))
        children = min(8, max(0, int(args.get("children", 0))))
    except ValueError:
        return jsonify({"error": "adults/children must be integers"}), 400

    fparams = _params_flight(origin, destination, outbound, ret,
                             _CLASS_ID[cabin], adults, children)
    hparams = _params_hotel(q, outbound, ret, adults, children)
    mock = _truthy(args.get("mock", ""))

    try:
        if feed == "replay":
            flight = serp_service.run_search("flight", fparams, shape_flight, mock=True)
            hotel = serp_service.run_search("hotel", hparams, shape_hotel, mock=True)
        else:
            # hard stop only when nothing cached can serve the flight leg
            if (serp_service.budget()["remaining"] <= 0
                    and not _cached("flight", fparams) and not _cached("hotel", hparams)):
                return jsonify({
                    "error": "lifetime serpapi budget is spent — "
                             "switch the feed to REPLAY (cached results stay available)",
                    "budget": serp_service.budget(),
                }), 429
            flight = serp_service.run_search("flight", fparams, shape_flight, mock=False)
            # hotel leg: replay instead of spending the last remaining call
            remaining = serp_service.budget()["remaining"]
            replay_hotel = mock or (
                remaining < 1 and not _cached("hotel", hparams))
            hotel = serp_service.run_search("hotel", hparams, shape_hotel, mock=replay_hotel)
    except BudgetExhausted as e:
        return jsonify({"error": str(e), "budget": serp_service.budget()}), 429
    except SerpError as e:
        return jsonify({"error": str(e)}), 502

    try:
        payload = build_packages(flight, hotel, budget,
                                 nights=nights, adults=adults, children=children)
    except PackageError as e:
        return jsonify({"error": str(e)}), 409

    payload["boards"] = {
        "flight": {k: flight[k] for k in ("mock", "cached", "fetched_on")},
        "hotel": {k: hotel[k] for k in ("mock", "cached", "fetched_on")},
    }
    # ``budget`` is the trip ceiling the packs were priced against; the
    # lifetime SerpApi ledger rides along under the same key as other boards.
    payload["trip_budget"] = budget
    payload["budget"] = serp_service.budget()
    return jsonify(payload)
