from ...model.Hotels import load_artifacts, predict_adr, MONTHS
from flask import request, jsonify, Blueprint

model, scaler, meta = load_artifacts()

REQUIRED = ["hotel", "arrival_date_year", "arrival_date_month", "arrival_date_week_number",
            "arrival_date_day_of_month", "stays_in_weekend_nights", "stays_in_week_nights", "adults"]
ID_COLS = ["name", "email", "phone-number", "credit_card"]

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
