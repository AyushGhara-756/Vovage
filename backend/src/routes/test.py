from flask import Blueprint

test_bp = Blueprint("test", __name__, url_prefix="/api/test")

@test_bp.get("/")
def test():
    return {"api":"live"}, 200
