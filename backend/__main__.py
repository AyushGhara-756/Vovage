# Dev entrypoint: python -m backend  (starts Flask on port 6050).
# The app itself lives in backend/app.py, shared with the Vercel
# service entrypoint (backend/api/index.py).
from .app import app

if __name__ == "__main__":
    app.run(port=6050)
