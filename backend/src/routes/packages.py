"""Package board — one flight board + one hotel board, priced as tiers.

Both boards are live SerpApi searches through ``run_search``, which is
cache-first — identical params are served from disk at zero network
cost and only a genuine cache miss reaches the API.
"""
import re
from datetime import date

from flask import Blueprint, jsonify, request

from ..services.package_service import PackageError, build_packages
from ..services.serp_service import SerpError, run_search, shape_flight, shape_hotel
from .flights import _CABINS, _CLASS_ID, _DATE

package_bp = Blueprint("package", __name__, url_prefix="/api/package")

_MAX_NIGHTS = 30


@package_bp.route("/search", methods=["GET"])
def search():
    """Three package tiers from one flight + one hotel board (live)."""
    args = request.args
    origin = (args.get("origin") or "").strip().upper()
    destination = (args.get("destination") or "").strip().upper()
    q = (args.get("q") or "").strip()
    outbound = (args.get("outbound_date") or "").strip()
    ret = (args.get("return_date") or "").strip()

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

    fparams = {
        "engine": "google_flights", "hl": "en", "gl": "in", "currency": "INR",
        "type": 1, "departure_id": origin, "arrival_id": destination,
        "outbound_date": outbound, "return_date": ret,
        "travel_class": _CLASS_ID[cabin], "adults": adults, "children": children,
    }
    hparams = {
        "engine": "google_hotels", "hl": "en", "gl": "in", "currency": "INR",
        "q": q, "check_in_date": outbound, "check_out_date": ret,
        "adults": adults, "children": children, "sort_by": "3",
    }

    try:
        flight = run_search("flight", fparams, shape_flight)
        hotel = run_search("hotel", hparams, shape_hotel)
    except SerpError as e:
        return jsonify({"error": str(e)}), 502

    try:
        payload = build_packages(flight, hotel, budget,
                                 nights=nights, adults=adults, children=children)
    except PackageError as e:
        return jsonify({"error": str(e)}), 409

    payload["boards"] = {
        "flight": {k: flight[k] for k in ("cached", "fetched_on")},
        "hotel": {k: hotel[k] for k in ("cached", "fetched_on")},
    }
    # ``trip_budget`` is the ceiling the packages were priced against.
    payload["trip_budget"] = budget
    return jsonify(payload)
