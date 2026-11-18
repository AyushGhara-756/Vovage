import re

from flask import Blueprint, request, jsonify

from ..services.flight_service import predict as predict_price, flight_service
from ..services import serp_service
from ..services.serp_service import SerpError, shape_flight

flight_bp = Blueprint("flight", __name__, url_prefix="/api/flight")

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CABINS = ["economy", "premium_economy", "business", "first"]
# SerpApi wants an integer travel_class, not the human string
_CLASS_ID = {"economy": 1, "premium_economy": 2, "business": 3, "first": 4}


@flight_bp.route("/options", methods=["GET"])
def options():
    """Dropdown values + ranges for the frontend."""
    meta = flight_service.meta
    return jsonify({
        "options": meta["options"],
        "duration_range": [meta["duration_min"], meta["duration_max"]],
        "days_left_range": [meta["days_left_min"], meta["days_left_max"]],
    })


@flight_bp.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True)

    if not data or not (isinstance(data, dict) or isinstance(data, list)):
        return jsonify({"error": "send a JSON body"}), 400

    try:
        prices = predict_price(data)
        return jsonify({"predicted_price": [round(float(p), 2) for p in prices]})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@flight_bp.route("/airports", methods=["GET"])
def airports():
    """Local IATA autocomplete — name / city / code. Spends no SerpApi calls."""
    query = request.args.get("q", "")
    try:
        limit = min(12, max(1, int(request.args.get("limit", 8))))
    except ValueError:
        limit = 8
    return jsonify({"results": serp_service.search_airports(query, limit)})


@flight_bp.route("/search", methods=["GET"])
def search():
    """Live Google Flights search via SerpApi (cache-first).

    With return_date: round trip. Without it: one-way."""
    args = request.args
    origin = (args.get("origin") or "").strip().upper()
    destination = (args.get("destination") or "").strip().upper()
    outbound = (args.get("outbound_date") or "").strip()
    return_date = (args.get("return_date") or "").strip()

    if not (origin and destination and outbound):
        return jsonify({
            "error": "origin, destination and outbound_date are required",
        }), 400
    if origin == destination:
        return jsonify({"error": "origin and destination must differ"}), 400
    if not _DATE.match(outbound) or (return_date and not _DATE.match(return_date)):
        return jsonify({"error": "dates must be YYYY-MM-DD"}), 400
    if return_date and return_date < outbound:
        return jsonify({"error": "return_date cannot precede outbound_date"}), 400

    cabin = (args.get("travel_class") or "economy").strip().lower()
    if cabin not in _CABINS:
        return jsonify({"error": "travel_class must be one of " + ", ".join(_CABINS)}), 400

    try:
        adults = min(8, max(1, int(args.get("adults", 2))))
        children = min(8, max(0, int(args.get("children", 0))))
    except ValueError:
        return jsonify({"error": "adults/children must be integers"}), 400

    params = {
        "engine": "google_flights",
        "hl": "en",
        "gl": "in",
        "currency": "INR",
        "type": 1 if return_date else 2,  # round trip vs one-way
        "departure_id": origin,
        "arrival_id": destination,
        "outbound_date": outbound,
        "travel_class": _CLASS_ID[cabin],
        "adults": adults,
        "children": children,
    }
    if return_date:
        params["return_date"] = return_date

    try:
        payload = serp_service.run_search("flight", params, shape_flight)
    except SerpError as e:
        return jsonify({"error": str(e)}), 502

    # SerpApi's option price is the total for every passenger in the search.
    # Boards display a per-traveller fare, so attach the split alongside the
    # true total and record the party size the prices were computed for.
    travellers = adults + children
    payload["travellers"] = travellers
    for board in ("departures", "returns", "selected", "best", "others"):
        for opt in payload.get(board) or []:
            if opt.get("price") is not None:
                opt["price_per_traveller"] = round(opt["price"] / travellers, 2)

    return jsonify(payload)
