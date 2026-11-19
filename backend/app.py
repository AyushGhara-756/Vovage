# Flask app assembly. Shared by:
#   - backend/__main__.py   (dev: python -m backend)
#   - backend/api/index.py  (Vercel service entrypoint)
# Imports are dual-mode: relative when imported inside the `backend` package
# (dev), absolute when backend/ itself is on sys.path (deployed service root).
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS

try:
    from .src.routes.flights import flight_bp
    from .src.routes.hotels import hotels_bp
    from .src.routes.packages import package_bp
    from .src.routes.account import account_bp
except ImportError:  # backend/ is on sys.path (service-root layout)
    from src.routes.flights import flight_bp
    from src.routes.hotels import hotels_bp
    from src.routes.packages import package_bp
    from src.routes.account import account_bp

# repo root .env (dev); a no-op on Vercel where env vars come from the dashboard
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

app = Flask(__name__)

FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000").split(",")
    if origin.strip()
]
CORS(
    app,
    resources={r"/api/*": {"origins": FRONTEND_ORIGINS}},
    supports_credentials=False,
    allow_headers=["Authorization", "Content-Type"],
    methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
)

@app.before_request
def _redirect_root_api_paths():
    from flask import request, redirect
    path = request.path.rstrip("/")
    qs = request.query_string.decode()
    target = None
    if path == "/flight/options":
        target = "/api/flight/options"
    elif path == "/flight/predict":
        target = "/api/flight/predict"
    elif path == "/flight/airports":
        target = "/api/flight/airports"
    elif path == "/flight/search":
        target = "/api/flight/search"
    elif path == "/hotel/options":
        target = "/api/hotel/options"
    elif path == "/hotel/predict":
        target = "/api/hotel/predict"
    elif path == "/hotel/search":
        target = "/api/hotel/search"
    elif path == "/package/search":
        target = "/api/package/search"
    elif path == "/account/me":
        target = "/api/account/me"
    if target:
        resp = redirect(target + ("?" + qs if qs else ""), code=308)
        origin = request.headers.get("Origin", "")
        if origin in FRONTEND_ORIGINS:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        return resp

app.register_blueprint(flight_bp)
app.register_blueprint(hotels_bp)
app.register_blueprint(package_bp)
app.register_blueprint(account_bp)
