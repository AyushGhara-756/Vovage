# Vercel serverless entrypoint for the Flask API.
# Vercel's Python runtime imports this module and serves the module-level
# `app` (WSGI) for every request routed to it by vercel.json.
import sys
from pathlib import Path

# repo root: backend/api/index.py -> up 2
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.__main__ import app  # noqa: E402,F401
