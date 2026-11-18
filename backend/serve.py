"""Production entrypoint. Run from the repository root:

    python -m backend.serve
"""

from waitress import serve

from backend.__main__ import HOST, PORT, app

if __name__ == "__main__":
    serve(app, host=HOST, port=PORT, threads=8)
