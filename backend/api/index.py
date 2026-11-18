# Vercel service entrypoint for the Flask API (service root: backend/).
# Vercel's Python runtime imports this module and serves the module-level
# `app` (WSGI) for every request routed to it by vercel.json.
import sys
from pathlib import Path

# service root: backend/api/index.py -> backend/
BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app import app  # noqa: E402,F401  (backend/app.py)
