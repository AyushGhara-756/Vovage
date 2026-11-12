"""Supabase JWT verification + auth middleware for protected endpoints.

Tokens arrive as `Authorization: Bearer <access_token>`. Verification:
- ES256/RS256 asymmetric signing keys are fetched from the project's
  published JWKS (`/auth/v1/.well-known/jwks.json`) and verified with
  PyJWT (signature, issuer, audience, expiry, issued-at).
- Legacy HS256 tokens are only accepted when SUPABASE_JWT_SECRET is
  configured for the project; otherwise they are rejected.
The verified `sub` claim is the only user id this backend ever trusts.
"""

import os
import time
from functools import wraps
from pathlib import Path

import jwt
from jwt import PyJWKClient
from flask import g, jsonify, request

ROOT = Path(__file__).resolve().parents[2]

SUPABASE_URL = ""
PUBLISHABLE_KEY = ""
JWT_SECRET = ""
SECRET_KEY = ""

_JWK_CLIENT = None
_JWK_LOADED_AT = 0.0
_JWK_TTL = 600.0


def _load_env():
    global SUPABASE_URL, PUBLISHABLE_KEY, JWT_SECRET, SECRET_KEY
    env = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            env[key.strip()] = value
    SUPABASE_URL = (
        os.environ.get("SUPABASE_URL")
        or env.get("SUPABASE_URL")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
        or env.get("NEXT_PUBLIC_SUPABASE_URL")
        or ""
    ).rstrip("/")
    PUBLISHABLE_KEY = os.environ.get(
        "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"
    ) or env.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY") or ""
    JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET") or env.get("SUPABASE_JWT_SECRET") or ""
    SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY") or env.get("SUPABASE_SECRET_KEY") or ""


_load_env()


class AuthError(Exception):
    def __init__(self, message, status=401):
        super().__init__(message)
        self.status = status


def _jwk_client():
    global _JWK_CLIENT, _JWK_LOADED_AT
    now = time.time()
    if _JWK_CLIENT is None or now - _JWK_LOADED_AT > _JWK_TTL:
        if not SUPABASE_URL:
            raise AuthError("auth service is not configured", 401)
        _JWK_CLIENT = PyJWKClient(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json", cache_keys=True)
        _JWK_LOADED_AT = now
    return _JWK_CLIENT


def _alg_of(token):
    header = jwt.get_unverified_header(token)
    return header.get("alg")


def verify_access_token(token):
    """Verify a Supabase access token and return its claims, or raise AuthError."""
    if not token:
        raise AuthError("missing bearer token")

    try:
        alg = _alg_of(token)
    except jwt.PyJWTError as exc:
        raise AuthError("malformed authorization token") from exc

    if alg not in ("HS256", "ES256", "RS256"):
        raise AuthError("token signing method is not accepted")

    if alg == "HS256":
        if not JWT_SECRET:
            raise AuthError("token signing method is not accepted")
        key = JWT_SECRET
        algorithms = ["HS256"]
    else:
        try:
            signing_key = _jwk_client().get_signing_key_from_jwt(token)
        except Exception as exc:
            raise AuthError("could not verify token signature") from exc
        key = signing_key.key
        algorithms = [alg]

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience="authenticated",
            issuer=f"{SUPABASE_URL}/auth/v1",
            leeway=30,
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("session expired — sign in again") from exc
    except jwt.InvalidAudienceError as exc:
        raise AuthError("token audience is not accepted") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("invalid authorization token") from exc

    if claims.get("role") != "authenticated":
        raise AuthError("insufficient permissions", 403)
    if not claims.get("sub"):
        raise AuthError("invalid authorization token")
    return claims


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        token = header[7:].strip() if header.startswith("Bearer ") else ""
        try:
            claims = verify_access_token(token)
        except AuthError as exc:
            return jsonify({"error": str(exc)}), exc.status
        except Exception:
            return jsonify({"error": "authentication failed"}), 401
        g.user_id = claims["sub"]
        g.access_token = token
        g.claims = claims
        return fn(*args, **kwargs)

    return wrapper
