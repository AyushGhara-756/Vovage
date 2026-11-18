import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from .src.routes.flights import flight_bp
from .src.routes.hotels import hotels_bp
from .src.routes.packages import package_bp
from .src.routes.account import account_bp
from .src.security import QuotaError, install as install_security

APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV in {"production", "prod"}
HOST = os.environ.get("HOST", "127.0.0.1").strip() or "127.0.0.1"
try:
    PORT = int(os.environ.get("PORT", "6050"))
except ValueError:
    PORT = 6050

app = Flask(__name__)

FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000").split(",")
    if origin.strip()
]
if IS_PRODUCTION and (
    not FRONTEND_ORIGINS
    or any(o == "*" or not o.startswith("https://") for o in FRONTEND_ORIGINS)
):
    raise RuntimeError(
        "FRONTEND_ORIGIN must be a comma-separated list of https origins in production"
    )

CORS(
    app,
    resources={r"/api/account/*": {"origins": FRONTEND_ORIGINS}},
    supports_credentials=False,
    allow_headers=["Authorization", "Content-Type"],
    methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
)

install_security(app)


@app.after_request
def _security_headers(response):
    if request.path.startswith("/api/"):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.errorhandler(QuotaError)
def _quota_exhausted(exc):
    response = jsonify({"error": str(exc)})
    response.status_code = 429
    response.headers["Retry-After"] = "3600"
    return response


app.register_blueprint(flight_bp)
app.register_blueprint(hotels_bp)
app.register_blueprint(package_bp)
app.register_blueprint(account_bp)


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if IS_PRODUCTION and debug:
        raise SystemExit("FLASK_DEBUG must be disabled in production")
    app.run(host=HOST, port=PORT, debug=debug)
