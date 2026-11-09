from flask import Blueprint, request, jsonify
from ..services.flight_service import predict as predict_price

flight_bp = Blueprint("flight", __name__, url_prefix="/api/flight")

@flight_bp.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True)

    if not data or "features" not in data:
        return jsonify({"error": "features required"}), 400

    try:
        price = predict_price(data["features"])

        return jsonify({
            "predicted_price": round(price, 2)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400
