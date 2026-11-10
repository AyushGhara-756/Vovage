from ...model.Hotels import load_artifacts, predict_adr, MONTHS
from flask import request, jsonify, Blueprint

from ..services import serp_service
from ..services.serp_service import SerpError, shape_hotel

import re

model, scaler, meta = load_artifacts()

REQUIRED = ["hotel", "arrival_date_year", "arrival_date_month", "arrival_date_week_number",
            "arrival_date_day_of_month", "stays_in_weekend_nights", "stays_in_week_nights", "adults"]
ID_COLS = ["name", "email", "phone-number", "credit_card"]

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SORTS = {"3", "8", "9", "13"}

hotels_bp = Blueprint("hotel", __name__, url_prefix="/api/hotel")
@hotels_bp.route("/options", methods=["GET"])
def options():
    """Dropdown values for the frontend (top categories seen in training)."""
    return jsonify({c: v for c, v in meta["top_values"].items() if c not in ID_COLS})


@hotels_bp.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "send JSON"}), 400

    rows = data if isinstance(data, list) else [data]

    for r in rows:
        missing = [c for c in REQUIRED if c not in r]
        if missing:
            return jsonify({"error": "missing fields", "fields": missing}), 400
        if r["arrival_date_month"] not in MONTHS:
            return jsonify({"error": "arrival_date_month must be a full month name, e.g. 'July'"}), 400

    try:
        price = predict_adr(model, scaler, meta, rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"adr": [round(float(p), 2) for p in price]})


@hotels_bp.route("/search", methods=["GET"])
def search():
    """Live Google Hotels board via SerpApi. 1 call (or cache/mock)."""
    args = request.args
    q = (args.get("q") or "").strip()
    check_in = (args.get("check_in_date") or "").strip()
    check_out = (args.get("check_out_date") or "").strip()

    if not q:
        return jsonify({"error": "q (location) is required"}), 400
    if not (_DATE.match(check_in) and _DATE.match(check_out)):
        return jsonify({"error": "dates must be YYYY-MM-DD"}), 400
    if check_out <= check_in:
        return jsonify({"error": "check_out_date must be after check_in_date"}), 400

    sort_by = (args.get("sort_by") or "3").strip()
    if sort_by and sort_by not in _SORTS:
        return jsonify({"error": "sort_by must be one of " + ", ".join(sorted(_SORTS))}), 400

    try:
        adults = min(8, max(1, int(args.get("adults", 2))))
        children = min(8, max(0, int(args.get("children", 0))))
    except ValueError:
        return jsonify({"error": "adults/children must be integers"}), 400

    params = {
        "engine": "google_hotels",
        "hl": "en",
        "gl": "in",
        "currency": "INR",
        "q": q,
        "check_in_date": check_in,
        "check_out_date": check_out,
        "adults": adults,
        "children": children,
    }
    if sort_by:
        params["sort_by"] = sort_by

    try:
        payload = serp_service.run_search("hotel", params, shape_hotel)
    except SerpError as e:
        return jsonify({"error": str(e)}), 502
    return jsonify(payload)
