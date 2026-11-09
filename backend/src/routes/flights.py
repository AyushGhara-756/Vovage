from flask import Blueprint, request, jsonify
from ..services.flight_service import predict as predict_price, flight_service

flight_bp = Blueprint("flight", __name__, url_prefix="/api/flight")


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
