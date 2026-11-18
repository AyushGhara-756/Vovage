"""Request throttling and provider-quota guards.

Dependency-free so it can run in any Flask worker. The sliding-window
limiter is per process; the daily SerpApi budget is stored on disk so it
survives restarts and is shared by workers using the same data dir.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

USAGE_FILE = (
    Path(__file__).resolve().parents[2] / "backend" / "data" / "serp_usage.json"
)


class QuotaError(Exception):
    """Raised when the SerpApi daily call budget is exhausted."""


def _int_env(name, default):
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


class RateLimiter:
    """Sliding-window counter keyed by an arbitrary string."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key, limit, window=60.0):
        if limit <= 0:
            return True, 0
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= window:
                hits.popleft()
            if len(hits) >= limit:
                retry_after = max(1, int(window - (now - hits[0]) + 0.999))
                return False, retry_after
            hits.append(now)
            if len(self._hits) > 10000:
                cutoff = now - window
                for key in [k for k, q in self._hits.items() if not q or q[-1] < cutoff]:
                    del self._hits[key]
            return True, 0

    def reset(self):
        with self._lock:
            self._hits.clear()


LIMITER = RateLimiter()


def client_key():
    from flask import request

    remote = request.remote_addr or "unknown"
    trusted = _int_env("TRUST_PROXY", 0) == 1 or remote in {"127.0.0.1", "::1"}
    if trusted:
        for header in ("X-Forwarded-For", "X-Real-IP"):
            value = request.headers.get(header, "")
            candidate = value.split(",")[0].strip()
            if candidate:
                return candidate
    return remote


def rate_limit(bucket, per_minute):
    from flask import jsonify, request

    if request.method == "OPTIONS":
        return None
    allowed, retry_after = LIMITER.allow(f"{bucket}:{client_key()}", per_minute)
    if allowed:
        return None
    response = jsonify({"error": "Too many requests. Please slow down and try again."})
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    return response


ROUTE_LIMITS = (
    ("/api/flight/search", "RATE_LIMIT_SEARCH_PER_MINUTE", 20, "search"),
    ("/api/hotel/search", "RATE_LIMIT_SEARCH_PER_MINUTE", 20, "search"),
    ("/api/package/search", "RATE_LIMIT_SEARCH_PER_MINUTE", 20, "search"),
    ("/api/flight/predict", "RATE_LIMIT_PREDICT_PER_MINUTE", 60, "predict"),
    ("/api/hotel/predict", "RATE_LIMIT_PREDICT_PER_MINUTE", 60, "predict"),
    ("/api/account", "RATE_LIMIT_ACCOUNT_PER_MINUTE", 60, "account"),
)


def install(app):
    from flask import request

    @app.before_request
    def _enforce_limits():
        path = request.path or ""
        for prefix, env_name, default, bucket in ROUTE_LIMITS:
            if path.startswith(prefix):
                return rate_limit(bucket, _int_env(env_name, default))
        if path.startswith("/api/"):
            return rate_limit("api", _int_env("RATE_LIMIT_API_PER_MINUTE", 120))
        return None


def _daily_limit():
    return _int_env("SERP_DAILY_CALL_LIMIT", 200)


def _today():
    return time.strftime("%Y-%m-%d", time.localtime())


_QUOTA_LOCK = threading.Lock()


def reserve_serp_call():
    """Reserve one live SerpApi call for today, or raise QuotaError."""
    limit = _daily_limit()
    if limit <= 0:
        return
    with _QUOTA_LOCK:
        data = {}
        try:
            data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            data = {}
        today = _today()
        if data.get("date") != today:
            data = {"date": today, "count": 0}
        try:
            count = int(data.get("count", 0))
        except (TypeError, ValueError):
            count = 0
        if count >= limit:
            raise QuotaError(
                f"daily search budget ({limit}) reached — try again tomorrow"
            )
        data["count"] = count + 1
        try:
            USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = USAGE_FILE.with_suffix(f".{os.getpid()}.tmp")
            tmp.write_text(json.dumps(data), encoding="utf-8")
            os.replace(tmp, USAGE_FILE)
        except OSError:
            pass  # never block a search because the counter could not be saved
