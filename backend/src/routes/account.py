"""Authenticated account endpoints: profile, preferences, avatar storage,
saved searches and search history.

Every operation runs with the caller's own access token against Supabase
PostgREST, so the existing RLS policies decide what the caller can see or
change. The only user id ever used is the verified token's `sub`.
"""

import json
import re
import uuid

import httpx
import supabase as supabase_lib
from flask import Blueprint, g, jsonify, request

from ..flask_auth import PUBLISHABLE_KEY, SECRET_KEY, SUPABASE_URL, require_auth

account_bp = Blueprint("account", __name__, url_prefix="/api/account")

_CURRENCIES = {"INR", "USD", "EUR", "GBP", "AED"}
_CABINS = {"economy", "premium_economy", "business", "first"}
_TRAVEL_TYPES = {"leisure", "business", "adventure", "family"}
_SEARCH_TYPES = {"flight", "hotel", "package"}
_AVATAR_BUCKET = "avatars"
_AVATAR_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"]
_PHONE_RE = re.compile(r"^\+[1-9][0-9]{7,14}$")
_MAX_PARAMS = 20000


@account_bp.before_request
def _require_account_config():
    if not (SUPABASE_URL and PUBLISHABLE_KEY):
        return jsonify({"error": "account service is not configured"}), 401


@account_bp.after_request
def _no_store(response):
    response.headers["Cache-Control"] = "no-store"
    return response


def _user_client():
    client = supabase_lib.create_client(SUPABASE_URL, PUBLISHABLE_KEY)
    client.postgrest.auth(g.access_token)
    return client


def _clean(value, limit=120):
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def _valid_id(value):
    try:
        uuid.UUID(str(value))
        return True
    except (TypeError, ValueError, AttributeError):
        return False


def _params_ok(params):
    if not isinstance(params, dict) or not params:
        return False
    try:
        return len(json.dumps(params)) <= _MAX_PARAMS
    except (TypeError, ValueError):
        return False


def _safe(fn):
    try:
        return fn(), None
    except Exception as exc:
        detail = str(getattr(exc, "message", exc) or exc)
        return None, detail


def _auth_user(access_token):
    """Ask GoTrue for the authoritative user record (email confirmation)."""
    if not (SUPABASE_URL and PUBLISHABLE_KEY):
        return None
    try:
        res = httpx.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "apikey": PUBLISHABLE_KEY,
                "Authorization": f"Bearer {access_token}",
            },
            timeout=10,
        )
        if res.status_code == 200:
            data = res.json()
            return data if isinstance(data, dict) else None
    except Exception:
        return None
    return None


def _first(client, table, column):
    rows, err = _safe(lambda: (
        client.table(table).select("*").eq(column, g.user_id).limit(1).execute()
    ).data)
    if err:
        return None, err
    return (rows[0] if rows else None), None


@account_bp.route("/me", methods=["GET"])
@require_auth
def me():
    client = _user_client()
    profile, p_err = _first(client, "profiles", "id")
    if p_err:
        return jsonify({"error": "could not load profile"}), 502

    preferences, pr_err = _first(client, "user_preferences", "user_id")
    if pr_err:
        return jsonify({"error": "could not load preferences"}), 502

    consents, c_err = _safe(lambda: (
        client.table("user_consents")
        .select("consent_type,policy_version,accepted_at")
        .eq("user_id", g.user_id)
        .execute()
    ).data)
    if c_err:
        return jsonify({"error": "could not load consents"}), 502

    claims = g.claims
    auth_user = _auth_user(g.access_token) or {}
    return jsonify({
        "user_id": g.user_id,
        "email": auth_user.get("email") or claims.get("email"),
        "email_verified": bool(auth_user.get("email_confirmed_at")),
        "profile": profile,
        "preferences": preferences,
        "consents": consents or [],
    })


@account_bp.route("/me", methods=["PATCH"])
@require_auth
def update_me():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "send a JSON body"}), 400

    profile_updates = {}
    for field, limit in (
        ("full_name", 120),
        ("phone_number", 32),
        ("home_city", 120),
        ("home_airport", 120),
    ):
        if field not in body:
            continue
        value = _clean(body.get(field), limit)
        if field == "full_name" and not value:
            return jsonify({"error": "full_name cannot be empty"}), 400
        if field == "phone_number" and value:
            value = re.sub(r"[\s()\-]", "", value)
            if not _PHONE_RE.match(value):
                return jsonify({"error": "phone_number must be E.164, e.g. +919876543210"}), 400
        profile_updates[field] = value

    if "preferred_currency" in body:
        currency = _clean(body.get("preferred_currency"), 8)
        currency = currency.upper() if currency else None
        if currency and currency not in _CURRENCIES:
            return jsonify({"error": "unsupported currency"}), 400
        profile_updates["preferred_currency"] = currency or "INR"

    if "avatar_url" in body:
        avatar = _clean(body.get("avatar_url"), 400)
        if avatar and not avatar.startswith("https://"):
            return jsonify({"error": "avatar_url must be an https URL"}), 400
        profile_updates["avatar_url"] = avatar

    prefs_updates = {}
    if "preferred_travel_type" in body:
        value = _clean(body.get("preferred_travel_type"), 24)
        value = value.lower() if value else None
        if value and value not in _TRAVEL_TYPES:
            return jsonify({"error": "unsupported travel type"}), 400
        prefs_updates["preferred_travel_type"] = value

    if "preferred_cabin" in body:
        value = _clean(body.get("preferred_cabin"), 24)
        value = value.lower() if value else None
        if value and value not in _CABINS:
            return jsonify({"error": "unsupported cabin"}), 400
        prefs_updates["preferred_cabin"] = value

    if "preferred_hotel_rating" in body:
        rating = body.get("preferred_hotel_rating")
        if isinstance(rating, bool) or not isinstance(rating, int):
            return jsonify({"error": "preferred_hotel_rating must be a whole number"}), 400
        prefs_updates["preferred_hotel_rating"] = max(0, min(5, rating))

    if "notification_enabled" in body:
        enabled = body.get("notification_enabled")
        if not isinstance(enabled, bool):
            return jsonify({"error": "notification_enabled must be true or false"}), 400
        prefs_updates["notification_enabled"] = enabled

    if not profile_updates and not prefs_updates:
        return jsonify({"error": "nothing to update"}), 400

    client = _user_client()
    if profile_updates:
        existing, err = _safe(lambda: (
            client.table("profiles").select("id").eq("id", g.user_id)
            .limit(1).execute()
        ).data)
        if err:
            return jsonify({"error": "could not load profile"}), 502
        if not existing:
            return jsonify({"error": "profile not found"}), 404
        _, err = _safe(lambda: (
            client.table("profiles").update(profile_updates)
            .eq("id", g.user_id).execute()
        ))
        if err:
            return jsonify({"error": "profile update failed"}), 502

    if prefs_updates:
        existing, err = _safe(lambda: (
            client.table("user_preferences").select("user_id")
            .eq("user_id", g.user_id).limit(1).execute()
        ).data)
        if err:
            return jsonify({"error": "could not load preferences"}), 502
        if not existing:
            return jsonify({"error": "preferences not found"}), 404
        _, err = _safe(lambda: (
            client.table("user_preferences").update(prefs_updates)
            .eq("user_id", g.user_id).execute()
        ))
        if err:
            return jsonify({"error": "preferences update failed"}), 502

    return me()


@account_bp.route("/avatar/bucket", methods=["POST"])
@require_auth
def ensure_avatar_bucket():
    """Isolated privileged op: creates the public avatars bucket if absent.

    Only authenticated callers can reach it; the secret key never leaves the
    server and is never returned or logged.
    """
    if not SECRET_KEY:
        return jsonify({"error": "avatar storage is not configured"}), 503

    url = f"{SUPABASE_URL}/storage/v1/bucket"
    headers = {
        "apikey": SECRET_KEY,
        "Authorization": f"Bearer {SECRET_KEY}",
        "Content-Type": "application/json",
    }
    try:
        res = httpx.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            buckets = res.json()
            if any(b.get("name") == _AVATAR_BUCKET for b in buckets):
                return jsonify({"bucket": _AVATAR_BUCKET, "created": False})
        create = httpx.post(
            url,
            headers=headers,
            json={
                "name": _AVATAR_BUCKET,
                "public": True,
                "file_size_limit": 2097152,
                "allowed_mime_types": _AVATAR_TYPES,
            },
            timeout=15,
        )
        if create.status_code in (200, 201) or "Duplicate" in create.text:
            return jsonify({"bucket": _AVATAR_BUCKET, "created": True})
        return jsonify({"error": "could not prepare avatar storage"}), 502
    except Exception:
        return jsonify({"error": "could not prepare avatar storage"}), 502


@account_bp.route("/saves", methods=["GET"])
@require_auth
def list_saves():
    client = _user_client()
    rows, err = _safe(lambda: (
        client.table("saved_searches").select("*")
        .eq("user_id", g.user_id).order("created_at", desc=True).execute()
    ).data)
    if err:
        return jsonify({"error": "could not load saved searches"}), 502
    return jsonify({"saves": rows or []})


@account_bp.route("/saves", methods=["POST"])
@require_auth
def create_save():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "send a JSON body"}), 400
    search_type = _clean(body.get("search_type"), 16)
    search_type = search_type.lower() if search_type else None
    if search_type not in _SEARCH_TYPES:
        return jsonify({"error": "search_type must be flight, hotel or package"}), 400
    name = _clean(body.get("search_name"), 80)
    params = body.get("search_params")
    if not _params_ok(params):
        return jsonify({"error": "search_params must be a non-empty JSON object"}), 400

    client = _user_client()
    row, err = _safe(lambda: (
        client.table("saved_searches").insert({
            "user_id": g.user_id,
            "search_type": search_type,
            "search_name": name or "Untitled search",
            "search_params": params,
        }).execute()
    ).data)
    if err or not row:
        return jsonify({"error": "could not save search"}), 502
    return jsonify({"save": row[0]}), 201


@account_bp.route("/saves/<save_id>", methods=["PATCH"])
@require_auth
def update_save(save_id):
    if not _valid_id(save_id):
        return jsonify({"error": "invalid saved search id"}), 400
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "send a JSON body"}), 400
    updates = {}
    if "search_name" in body:
        updates["search_name"] = _clean(body.get("search_name"), 80) or "Untitled search"
    if "search_params" in body:
        if not _params_ok(body.get("search_params")):
            return jsonify({"error": "search_params must be a non-empty JSON object"}), 400
        updates["search_params"] = body["search_params"]
    if not updates:
        return jsonify({"error": "nothing to update"}), 400

    client = _user_client()
    existing, err = _safe(lambda: (
        client.table("saved_searches").select("id")
        .eq("id", save_id).eq("user_id", g.user_id).limit(1).execute()
    ).data)
    if err:
        return jsonify({"error": "could not load saved search"}), 502
    if not existing:
        return jsonify({"error": "saved search not found"}), 404

    row, err = _safe(lambda: (
        client.table("saved_searches").update(updates)
        .eq("id", save_id).eq("user_id", g.user_id).execute()
    ).data)
    if err or not row:
        return jsonify({"error": "could not update saved search"}), 502
    return jsonify({"save": row[0]})


@account_bp.route("/saves/<save_id>", methods=["DELETE"])
@require_auth
def delete_save(save_id):
    if not _valid_id(save_id):
        return jsonify({"error": "invalid saved search id"}), 400
    client = _user_client()
    existing, err = _safe(lambda: (
        client.table("saved_searches").select("id")
        .eq("id", save_id).eq("user_id", g.user_id).limit(1).execute()
    ).data)
    if err:
        return jsonify({"error": "could not load saved search"}), 502
    if not existing:
        return jsonify({"error": "saved search not found"}), 404

    _, err = _safe(lambda: (
        client.table("saved_searches").delete()
        .eq("id", save_id).eq("user_id", g.user_id).execute()
    ))
    if err:
        return jsonify({"error": "could not delete saved search"}), 502
    return jsonify({"deleted": save_id})


@account_bp.route("/history", methods=["GET"])
@require_auth
def list_history():
    client = _user_client()
    rows, err = _safe(lambda: (
        client.table("search_history").select("*")
        .eq("user_id", g.user_id).order("searched_at", desc=True)
        .limit(50).execute()
    ).data)
    if err:
        return jsonify({"error": "could not load history"}), 502
    return jsonify({"history": rows or []})


@account_bp.route("/history", methods=["POST"])
@require_auth
def record_history():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "send a JSON body"}), 400
    search_type = _clean(body.get("search_type"), 16)
    search_type = search_type.lower() if search_type else None
    if search_type not in _SEARCH_TYPES:
        return jsonify({"error": "search_type must be flight, hotel or package"}), 400
    params = body.get("search_params")
    if not _params_ok(params):
        return jsonify({"error": "search_params must be a non-empty JSON object"}), 400

    client = _user_client()
    row, err = _safe(lambda: (
        client.table("search_history").insert({
            "user_id": g.user_id,
            "search_type": search_type,
            "search_params": params,
        }).execute()
    ).data)
    if err or not row:
        return jsonify({"error": "could not record search history"}), 502
    return jsonify({"history": row[0]}), 201


@account_bp.route("/history/<entry_id>", methods=["DELETE"])
@require_auth
def delete_history(entry_id):
    if not _valid_id(entry_id):
        return jsonify({"error": "invalid history id"}), 400
    client = _user_client()
    existing, err = _safe(lambda: (
        client.table("search_history").select("id")
        .eq("id", entry_id).eq("user_id", g.user_id).limit(1).execute()
    ).data)
    if err:
        return jsonify({"error": "could not load history entry"}), 502
    if not existing:
        return jsonify({"error": "history entry not found"}), 404

    _, err = _safe(lambda: (
        client.table("search_history").delete()
        .eq("id", entry_id).eq("user_id", g.user_id).execute()
    ))
    if err:
        return jsonify({"error": "could not delete history entry"}), 502
    return jsonify({"deleted": entry_id})


@account_bp.route("/history", methods=["DELETE"])
@require_auth
def clear_history():
    client = _user_client()
    _, err = _safe(lambda: (
        client.table("search_history").delete()
        .eq("user_id", g.user_id).execute()
    ))
    if err:
        return jsonify({"error": "could not clear history"}), 502
    return jsonify({"cleared": True})
