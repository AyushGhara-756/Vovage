from flask import Blueprint, jsonify

from ..services import serp_service

serp_bp = Blueprint("serp", __name__, url_prefix="/api/serp")


@serp_bp.route("/budget", methods=["GET"])
def budget():
    """Lifetime SerpApi call ledger — read-only, spends nothing."""
    return jsonify(serp_service.budget())
