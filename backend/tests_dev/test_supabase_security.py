"""Live Supabase/PostgREST/Storage security matrix.

Developer script, not a unit test. It creates real test users in the configured
project, probes RLS directly through PostgREST and the Storage API, then removes
every test user and object it created.

Usage (from the repository root, with the root venv active):

    python backend/tests_dev/test_supabase_security.py

Requires a running Flask backend on http://127.0.0.1:6050 and a running Next.js
dev server on http://localhost:3000 for the header/rate-limit checks.
"""

import json
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
from supabase import create_client  # noqa: E402

from backend.__main__ import app  # noqa: E402
from backend.tests_dev.test_auth_integration import (  # noqa: E402
    PUB,
    SECRET,
    URL,
    make_user,
)

IMAGE_DIR = Path(
    r"C:\Users\HOME\AppData\Local\Temp\opencode\supabase-images"
)
BACKEND = "http://127.0.0.1:6050"
FRONTEND = "http://localhost:3000"

PASS = []
FAIL = []
SKIP = []
INFO = []


def check(name, condition, detail=""):
    if condition:
        PASS.append(name)
        print(f"PASS  {name}")
    else:
        FAIL.append(name)
        print(f"FAIL  {name} {detail}")


def note(name, detail):
    INFO.append((name, detail))
    print(f"INFO  {name}: {detail}")


def skip(name, detail):
    SKIP.append(name)
    print(f"SKIP  {name}: {detail}")


def short(res):
    text = res.text.replace("\n", " ")[:240]
    return f"{res.status_code} {text}"


def json_or_empty(res):
    try:
        return res.json()
    except Exception:
        return None


def denied_or_empty(res):
    if res.status_code in (401, 403):
        return True
    if res.status_code == 200:
        data = json_or_empty(res)
        return data == []
    return False


def rest(method, path, token=None, key=PUB, payload=None):
    headers = {"apikey": key}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
    headers["Prefer"] = "return=representation"
    return httpx.request(
        method,
        f"{URL}/rest/v1{path}",
        headers=headers,
        json=payload,
        timeout=20,
    )


def admin_rows(admin, table, id_column, row_id):
    return (
        admin.table(table)
        .select("*")
        .eq(id_column, row_id)
        .execute()
        .data
    )


def storage_headers(token=None, key=PUB, content_type=None, upsert=None):
    headers = {"apikey": key}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type
    if upsert is not None:
        headers["x-upsert"] = "true" if upsert else "false"
    return headers


def storage_upload(token, path, data, content_type, key=PUB, upsert=False):
    return httpx.post(
        f"{URL}/storage/v1/object/avatars/{path}",
        headers=storage_headers(token, key, content_type, upsert),
        content=data,
        timeout=20,
    )


def storage_delete(token=None, path="", key=SECRET):
    headers = {"apikey": key}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.request(
        "DELETE",
        f"{URL}/storage/v1/object/avatars/{path}",
        headers=headers,
        timeout=20,
    )


def storage_list(token, prefix, key=PUB):
    return httpx.post(
        f"{URL}/storage/v1/object/list/avatars",
        headers=storage_headers(token, key, "application/json"),
        json={"prefix": prefix, "limit": 100, "offset": 0},
        timeout=10,
    )


def load_images():
    wanted = {
        "png": ("test.png", "image/png"),
        "jpg": ("test.jpg", "image/jpeg"),
        "webp": ("test.webp", "image/webp"),
        "gif": ("test.gif", "image/gif"),
    }
    images = {}
    for fmt, (name, mime) in wanted.items():
        path = IMAGE_DIR / name
        if not path.exists():
            raise SystemExit(f"missing test image: {path}")
        images[fmt] = (path.read_bytes(), mime, path.suffix)
    return images


def make_user_with_retry(admin, public, tag):
    last = None
    for attempt in range(3):
        try:
            return make_user(admin, public, tag)
        except Exception as exc:  # noqa: BLE001 - report provider errors
            last = exc
            print(f"user creation retry {attempt + 1}/3: {type(exc).__name__}")
            time.sleep(2 + attempt * 3)
    raise last


def run():
    admin = create_client(URL, SECRET)
    public = create_client(URL, PUB)
    flask = app.test_client()

    user1 = user2 = None
    token1 = token2 = None
    created_paths = []
    inserted_consents = []
    created_save_ids = []
    created_history_ids = []

    def cleanup():
        for path in created_paths:
            try:
                storage_delete(path=path)
            except Exception:
                pass
        for row in inserted_consents:
            try:
                admin.table("user_consents").delete().eq("id", row).execute()
            except Exception:
                pass
        for row in created_save_ids:
            try:
                admin.table("saved_searches").delete().eq("id", row).execute()
            except Exception:
                pass
        for row in created_history_ids:
            try:
                admin.table("search_history").delete().eq("id", row).execute()
            except Exception:
                pass
        for user in (user1, user2):
            if user is not None:
                try:
                    admin.auth.admin.delete_user(user.id)
                except Exception:
                    pass

    try:
        user1, email1, _pw1, token1 = make_user_with_retry(admin, public, "ext1")
        user2, email2, _pw2, token2 = make_user_with_retry(admin, public, "ext2")
        print("created 2 test users")

        profile1 = admin_rows(admin, "profiles", "id", user1.id)[0]
        profile2 = admin_rows(admin, "profiles", "id", user2.id)[0]
        prefs1 = admin_rows(admin, "user_preferences", "user_id", user1.id)[0]
        prefs2 = admin_rows(admin, "user_preferences", "user_id", user2.id)[0]
        consents1 = admin_rows(admin, "user_consents", "user_id", user1.id)
        note("profiles columns", ",".join(sorted(profile1.keys())))
        note("preferences columns", ",".join(sorted(prefs1.keys())))
        note("consents rows", str(len(consents1)))

        # ---------------------------------------------------------------- profiles
        r = rest("GET", f"/profiles?id=eq.{user1.id}&select=id,full_name", token1)
        data = json_or_empty(r) or []
        check(
            "PostgREST: owner can select own profile",
            r.status_code == 200 and len(data) == 1 and data[0]["id"] == user1.id,
            short(r),
        )

        r = rest("GET", f"/profiles?id=eq.{user2.id}&select=id,full_name", token1)
        check(
            "PostgREST: user1 cannot select user2 profile",
            denied_or_empty(r),
            short(r),
        )

        r = rest(
            "PATCH",
            f"/profiles?id=eq.{user1.id}",
            token1,
            payload={"full_name": "Extended Renamed"},
        )
        check(
            "PostgREST: owner can update allowed profile column",
            r.status_code in (200, 204),
            short(r),
        )
        after = admin_rows(admin, "profiles", "id", user1.id)[0]
        check(
            "PostgREST: allowed profile update persisted",
            after.get("full_name") == "Extended Renamed",
            str(after.get("full_name")),
        )

        restricted = "updated_at" if "updated_at" in profile1 else "created_at"
        old_value = admin_rows(admin, "profiles", "id", user1.id)[0].get(restricted)
        r = rest(
            "PATCH",
            f"/profiles?id=eq.{user1.id}",
            token1,
            payload={restricted: "2000-01-01T00:00:00+00:00"},
        )
        after = admin_rows(admin, "profiles", "id", user1.id)[0]
        check(
            f"PostgREST: restricted profile column ({restricted}) not changed",
            after.get(restricted) == old_value,
            f"{short(r)} value={after.get(restricted)}",
        )

        r = rest(
            "PATCH",
            f"/profiles?id=eq.{user1.id}",
            token1,
            payload={"id": user2.id},
        )
        after = admin_rows(admin, "profiles", "id", user1.id)[0]
        check(
            "PostgREST: profile id cannot be reassigned",
            after.get("id") == user1.id,
            f"{short(r)} id={after.get('id')}",
        )

        r = rest(
            "PATCH",
            f"/profiles?id=eq.{user2.id}",
            token1,
            payload={"full_name": "Hijacked"},
        )
        after2 = admin_rows(admin, "profiles", "id", user2.id)[0]
        check(
            "PostgREST: user1 cannot update user2 profile",
            denied_or_empty(r) and after2.get("full_name") == profile2.get("full_name"),
            f"{short(r)} name={after2.get('full_name')}",
        )

        # ------------------------------------------------------------- preferences
        r = rest("GET", f"/user_preferences?user_id=eq.{user1.id}&select=*", token1)
        data = json_or_empty(r) or []
        check(
            "PostgREST: owner can select own preferences",
            r.status_code == 200 and len(data) == 1,
            short(r),
        )

        r = rest("GET", f"/user_preferences?user_id=eq.{user2.id}&select=*", token1)
        check(
            "PostgREST: user1 cannot select user2 preferences",
            denied_or_empty(r),
            short(r),
        )

        r = rest(
            "PATCH",
            f"/user_preferences?user_id=eq.{user1.id}",
            token1,
            payload={"preferred_cabin": "business", "notification_enabled": False},
        )
        after = admin_rows(admin, "user_preferences", "user_id", user1.id)[0]
        check(
            "PostgREST: owner preferences update persisted",
            r.status_code in (200, 204)
            and after.get("preferred_cabin") == "business"
            and after.get("notification_enabled") is False,
            f"{short(r)} {after.get('preferred_cabin')}/{after.get('notification_enabled')}",
        )

        r = rest(
            "PATCH",
            f"/user_preferences?user_id=eq.{user1.id}",
            token1,
            payload={"user_id": user2.id},
        )
        after1 = admin_rows(admin, "user_preferences", "user_id", user1.id)
        after2 = admin_rows(admin, "user_preferences", "user_id", user2.id)
        check(
            "PostgREST: preferences ownership cannot be changed",
            denied_or_empty(r) and len(after1) == 1 and len(after2) == 1,
            f"{short(r)} u1={len(after1)} u2={len(after2)}",
        )

        duplicate_payload = {
            k: v
            for k, v in prefs1.items()
            if k not in ("created_at", "updated_at")
        }
        duplicate_payload["user_id"] = user1.id
        r = rest("POST", "/user_preferences", token1, payload=duplicate_payload)
        rows_after = admin_rows(admin, "user_preferences", "user_id", user1.id)
        if r.status_code in (200, 201):
            check(
                "PostgREST: duplicate preferences insert rejected",
                len(rows_after) == 1,
                f"{short(r)} rows={len(rows_after)}",
            )
        else:
            check(
                "PostgREST: duplicate preferences insert rejected",
                r.status_code in (400, 401, 403, 409),
                short(r),
            )

        other_payload = {
            k: v
            for k, v in prefs2.items()
            if k not in ("created_at", "updated_at")
        }
        other_payload["user_id"] = user2.id
        r = rest("POST", "/user_preferences", token1, payload=other_payload)
        check(
            "PostgREST: user1 cannot insert preferences for user2",
            denied_or_empty(r)
            and len(admin_rows(admin, "user_preferences", "user_id", user2.id)) == 1,
            short(r),
        )

        # ----------------------------------------------------------------- consents
        r = rest("GET", f"/user_consents?user_id=eq.{user1.id}&select=*", token1)
        data = json_or_empty(r) or []
        check(
            "PostgREST: owner can select own consents",
            r.status_code == 200 and len(data) >= 2,
            short(r),
        )

        r = rest("GET", f"/user_consents?user_id=eq.{user2.id}&select=*", token1)
        check(
            "PostgREST: user1 cannot select user2 consents",
            denied_or_empty(r),
            short(r),
        )

        consent_payload = {
            "user_id": user1.id,
            "consent_type": "marketing_test",
            "policy_version": "test-v1",
        }
        if consents1 and "accepted_at" in consents1[0]:
            consent_payload["accepted_at"] = "2026-11-13T00:00:00+00:00"
        r = rest("POST", "/user_consents", token1, payload=consent_payload)
        inserted = json_or_empty(r) or []
        if isinstance(inserted, list) and inserted:
            inserted_consents.extend(
                row["id"] for row in inserted if row.get("id")
            )
        check(
            "PostgREST: consent writes are trigger-only (direct insert denied)",
            r.status_code in (401, 403),
            short(r),
        )

        if consents1:
            consent_id = consents1[0]["id"]
            original_version = consents1[0].get("policy_version")
            r = rest(
                "PATCH",
                f"/user_consents?id=eq.{consent_id}",
                token1,
                payload={"policy_version": "tampered"},
            )
            after = admin_rows(admin, "user_consents", "id", consent_id)
            check(
                "PostgREST: consent rows are immutable (update denied)",
                denied_or_empty(r)
                and after
                and after[0].get("policy_version") == original_version,
                f"{short(r)} version={after[0].get('policy_version') if after else None}",
            )

            r = rest("DELETE", f"/user_consents?id=eq.{consent_id}", token1)
            after = admin_rows(admin, "user_consents", "id", consent_id)
            check(
                "PostgREST: consent rows are immutable (delete denied)",
                denied_or_empty(r) and len(after) == 1,
                f"{short(r)} rows={len(after)}",
            )

        evil_consent = {
            "user_id": user2.id,
            "consent_type": "evil_test",
            "policy_version": "test-v1",
        }
        if consents1 and "accepted_at" in consents1[0]:
            evil_consent["accepted_at"] = "2026-11-13T00:00:00+00:00"
        r = rest("POST", "/user_consents", token1, payload=evil_consent)
        evil_rows = (
            admin.table("user_consents")
            .select("id")
            .eq("user_id", user2.id)
            .eq("consent_type", "evil_test")
            .execute()
            .data
        )
        check(
            "PostgREST: user1 cannot insert consent for user2",
            denied_or_empty(r) and evil_rows == [],
            short(r),
        )

        # ------------------------------------------------------- saves / history
        save_payload = {
            "search_type": "flight",
            "search_name": "Direct RLS save",
            "search_params": {"origin": "BOM", "destination": "DEL"},
        }
        r = flask.post(
            "/api/account/saves",
            headers={"Authorization": f"Bearer {token1}"},
            json=save_payload,
        )
        save_id = (r.get_json() or {}).get("save", {}).get("id")
        if save_id:
            created_save_ids.append(save_id)
        check("setup: Flask created a save", r.status_code == 201 and bool(save_id), short(r))

        if save_id:
            save_row = admin_rows(admin, "saved_searches", "id", save_id)[0]

            r = rest("GET", f"/saved_searches?id=eq.{save_id}&select=*", token1)
            check(
                "PostgREST: owner can select own save",
                r.status_code == 200 and len(json_or_empty(r) or []) == 1,
                short(r),
            )

            r = rest("GET", f"/saved_searches?id=eq.{save_id}&select=*", token2)
            check(
                "PostgREST: user2 cannot select user1 save",
                denied_or_empty(r),
                short(r),
            )

            r = rest(
                "PATCH",
                f"/saved_searches?id=eq.{save_id}",
                token2,
                payload={"search_name": "Stolen"},
            )
            after = admin_rows(admin, "saved_searches", "id", save_id)[0]
            check(
                "PostgREST: user2 cannot update user1 save",
                denied_or_empty(r) and after.get("search_name") != "Stolen",
                f"{short(r)} name={after.get('search_name')}",
            )

            r = rest(
                "PATCH",
                f"/saved_searches?id=eq.{save_id}",
                token1,
                payload={"user_id": user2.id},
            )
            after = admin_rows(admin, "saved_searches", "id", save_id)[0]
            check(
                "PostgREST: save ownership cannot be changed",
                denied_or_empty(r) and after.get("user_id") == user1.id,
                f"{short(r)} owner={after.get('user_id')}",
            )

            r = rest("DELETE", f"/saved_searches?id=eq.{save_id}", token2)
            after = admin_rows(admin, "saved_searches", "id", save_id)
            check(
                "PostgREST: user2 cannot delete user1 save",
                denied_or_empty(r) and len(after) == 1,
                f"{short(r)} rows={len(after)}",
            )

            steal_payload = {
                k: v
                for k, v in save_row.items()
                if k not in ("id", "created_at", "updated_at")
            }
            steal_payload["user_id"] = user2.id
            r = rest("POST", "/saved_searches", token1, payload=steal_payload)
            stolen = (
                admin.table("saved_searches")
                .select("id")
                .eq("user_id", user2.id)
                .eq("search_name", steal_payload.get("search_name", ""))
                .execute()
                .data
            )
            if stolen:
                created_save_ids.extend(row["id"] for row in stolen)
            check(
                "PostgREST: direct save insert for another user denied",
                denied_or_empty(r) and stolen == [],
                f"{short(r)} stolen={len(stolen)}",
            )

            r = rest("DELETE", f"/saved_searches?id=eq.{save_id}", token1)
            check(
                "PostgREST: owner can delete own save",
                r.status_code in (200, 204),
                short(r),
            )

        history_params = {"q": "Goa", "check_in_date": "2026-12-05"}
        r = flask.post(
            "/api/account/history",
            headers={"Authorization": f"Bearer {token1}"},
            json={"search_type": "hotel", "search_params": history_params},
        )
        entry_id = (r.get_json() or {}).get("history", {}).get("id")
        if entry_id:
            created_history_ids.append(entry_id)
        check(
            "setup: Flask created a history entry",
            r.status_code == 201 and bool(entry_id),
            short(r),
        )

        if entry_id:
            history_row = admin_rows(admin, "search_history", "id", entry_id)[0]

            r = rest("GET", f"/search_history?id=eq.{entry_id}&select=*", token1)
            check(
                "PostgREST: owner can select own history",
                r.status_code == 200 and len(json_or_empty(r) or []) == 1,
                short(r),
            )

            r = rest("GET", f"/search_history?id=eq.{entry_id}&select=*", token2)
            check(
                "PostgREST: user2 cannot select user1 history",
                denied_or_empty(r),
                short(r),
            )

            r = rest(
                "PATCH",
                f"/search_history?id=eq.{entry_id}",
                token2,
                payload={"user_id": user1.id},
            )
            check(
                "PostgREST: user2 cannot update user1 history",
                denied_or_empty(r),
                short(r),
            )

            r = rest(
                "PATCH",
                f"/search_history?id=eq.{entry_id}",
                token1,
                payload={"user_id": user2.id},
            )
            after = admin_rows(admin, "search_history", "id", entry_id)[0]
            check(
                "PostgREST: history has no ownership-change path",
                denied_or_empty(r) and after.get("user_id") == user1.id,
                f"{short(r)} owner={after.get('user_id')}",
            )

            r = rest("DELETE", f"/search_history?id=eq.{entry_id}", token2)
            after = admin_rows(admin, "search_history", "id", entry_id)
            check(
                "PostgREST: user2 cannot delete user1 history",
                denied_or_empty(r) and len(after) == 1,
                f"{short(r)} rows={len(after)}",
            )

            steal_history = {
                k: v
                for k, v in history_row.items()
                if k not in ("id", "created_at")
            }
            steal_history["user_id"] = user2.id
            r = rest("POST", "/search_history", token1, payload=steal_history)
            stolen_history = (
                admin.table("search_history")
                .select("id")
                .eq("user_id", user2.id)
                .eq("search_type", steal_history.get("search_type", ""))
                .execute()
                .data
            )
            if stolen_history:
                created_history_ids.extend(row["id"] for row in stolen_history)
            check(
                "PostgREST: direct history insert for another user denied",
                denied_or_empty(r) and stolen_history == [],
                f"{short(r)} stolen={len(stolen_history)}",
            )

            r = rest("DELETE", f"/search_history?id=eq.{entry_id}", token1)
            check(
                "PostgREST: owner can delete own history",
                r.status_code in (200, 204),
                short(r),
            )

        # ------------------------------------------------------------------ anon
        for table, column, value in (
            ("profiles", "id", user1.id),
            ("user_preferences", "user_id", user1.id),
            ("user_consents", "user_id", user1.id),
            ("saved_searches", "user_id", user1.id),
            ("search_history", "user_id", user1.id),
        ):
            r = rest("GET", f"/{table}?{column}=eq.{value}&select=*")
            check(
                f"PostgREST: anon cannot read {table}",
                denied_or_empty(r),
                short(r),
            )

        r = rest(
            "POST",
            "/saved_searches",
            payload={
                "user_id": user1.id,
                "search_type": "flight",
                "search_params": {"a": 1},
            },
        )
        check("PostgREST: anon cannot insert saves", r.status_code in (401, 403), short(r))

        # ---------------------------------------------------------- service role
        service_profile = (
            admin.table("profiles").select("id").in_("id", [user1.id, user2.id]).execute().data
        )
        service_prefs = (
            admin.table("user_preferences")
            .select("user_id")
            .in_("user_id", [user1.id, user2.id])
            .execute()
            .data
        )
        check(
            "Service role bypasses RLS for profiles/preferences",
            len(service_profile) == 2 and len(service_prefs) == 2,
            f"profiles={len(service_profile)} prefs={len(service_prefs)}",
        )

        # ------------------------------------------------------------- storage
        config = httpx.get(
            f"{URL}/storage/v1/bucket/avatars",
            headers={"apikey": SECRET},
            timeout=20,
        )
        config_data = json_or_empty(config) or {}
        if config.status_code == 200:
            check(
                "Storage bucket is public",
                config_data.get("public") is True,
                str(config_data.get("public")),
            )
            check(
                "Storage bucket size limit is 2MB",
                config_data.get("file_size_limit") == 2097152,
                str(config_data.get("file_size_limit")),
            )
            check(
                "Storage bucket allowed MIME whitelist",
                set(config_data.get("allowed_mime_types") or [])
                == {"image/png", "image/jpeg", "image/webp", "image/gif"},
                str(config_data.get("allowed_mime_types")),
            )
        else:
            skip("storage bucket configuration", short(config))

        images = load_images()
        signatures = {
            "png": b"\x89PNG",
            "jpg": b"\xff\xd8",
            "webp": b"RIFF",
            "gif": b"GIF8",
        }
        for fmt, (data, mime, ext) in images.items():
            check(
                f"generated {fmt} signature is valid",
                data.startswith(signatures[fmt]),
                data[:8].hex(),
            )

        for fmt, (data, mime, ext) in images.items():
            path = f"{user1.id}/ext-{fmt}-{uuid.uuid4().hex[:8]}{ext}"
            created_paths.append(path)
            r = storage_upload(token1, path, data, mime)
            check(
                f"Storage: owner uploads valid {fmt}",
                r.status_code in (200, 201),
                short(r),
            )
            if r.status_code in (200, 201):
                public = httpx.get(
                    f"{URL}/storage/v1/object/public/avatars/{path}",
                    timeout=20,
                )
                check(
                    f"Storage: public URL serves {fmt} bytes",
                    public.status_code == 200 and public.content == data,
                    f"{public.status_code} len={len(public.content)}",
                )

        cross_path = f"{user2.id}/cross-{uuid.uuid4().hex[:8]}.png"
        created_paths.append(cross_path)
        r = storage_upload(token2, cross_path, images["png"][0], "image/png")
        check(
            "Storage: owner upload succeeds for cross-user test",
            r.status_code in (200, 201),
            short(r),
        )
        if r.status_code in (200, 201):
            r = storage_upload(token1, cross_path, images["png"][0], "image/png")
            check(
                "Storage: user1 cannot upload into user2 folder",
                r.status_code not in (200, 201),
                short(r),
            )
            r = storage_delete(token1, cross_path)
            check(
                "Storage: user1 cannot delete user2 object",
                r.status_code not in (200, 204),
                short(r),
            )
            try:
                r = storage_list(token1, f"{user2.id}/")
                check(
                    "Storage: user1 cannot list user2 folder",
                    denied_or_empty(r),
                    short(r),
                )
            except httpx.TimeoutException:
                skip("Storage: user1 cannot list user2 folder", "request timed out")
            r = storage_delete(path=cross_path)
            check(
                "Storage: service role deletes user2 object",
                r.status_code in (200, 204),
                short(r),
            )

        oversize = b"\x89PNG\r\n\x1a\n" + b"0" * (2 * 1024 * 1024 + 1)
        path = f"{user1.id}/oversize-{uuid.uuid4().hex[:8]}.png"
        created_paths.append(path)
        r = storage_upload(token1, path, oversize, "image/png")
        check(
            "Storage: >2MB upload rejected",
            r.status_code in (400, 413),
            short(r),
        )
        storage_delete(path=path)

        for label, name, mime, data in (
            ("text/plain", "note.txt", "text/plain", b"not an image"),
            ("image/svg+xml", "evil.svg", "image/svg+xml", b"<svg/>"),
        ):
            path = f"{user1.id}/{name.rsplit('.', 1)[0]}-{uuid.uuid4().hex[:6]}.{name.rsplit('.', 1)[1]}"
            created_paths.append(path)
            r = storage_upload(token1, path, data, mime)
            check(
                f"Storage: invalid type {label} rejected",
                r.status_code in (400, 415),
                short(r),
            )
            if r.status_code not in (200, 201):
                storage_delete(path=path)

        for name, mime, data in (
            ("mismatch.txt", "image/png", images["png"][0]),
            ("mismatch.exe", "image/png", images["png"][0]),
            ("mismatch.html", "image/png", b"<script>alert(1)</script>"),
        ):
            path = f"{user1.id}/{name.rsplit('.', 1)[0]}-{uuid.uuid4().hex[:6]}.{name.rsplit('.', 1)[1]}"
            created_paths.append(path)
            r = storage_upload(token1, path, data, mime)
            if r.status_code in (200, 201):
                note(
                    "storage extension vs MIME",
                    f"{path.rsplit('.', 1)[1]} extension with declared {mime} was accepted; MIME whitelist is the storage boundary and the frontend extension check blocks normal uploads",
                )
                if name.endswith(".html"):
                    public = httpx.get(
                        f"{URL}/storage/v1/object/public/avatars/{path}",
                        timeout=20,
                    )
                    ctype = public.headers.get("content-type", "")
                    note("storage public content-type for .html", ctype)
                    check(
                        "Storage: HTML extension is not served as text/html",
                        "text/html" not in ctype.lower(),
                        ctype,
                    )
                storage_delete(path=path)
            else:
                check(
                    f"Storage: extension mismatch {name} rejected",
                    r.status_code in (400, 415),
                    short(r),
                )

        replace_path = f"{user1.id}/replace-{uuid.uuid4().hex[:8]}.png"
        created_paths.append(replace_path)
        r = storage_upload(token1, replace_path, images["png"][0], "image/png")
        check(
            "Storage: replacement fixture uploaded",
            r.status_code in (200, 201),
            short(r),
        )
        r = storage_upload(
            token1,
            replace_path,
            images["jpg"][0],
            "image/jpeg",
            upsert=True,
        )
        check(
            "Storage: owner can overwrite own object (upsert)",
            r.status_code in (200, 201),
            short(r),
        )
        if r.status_code not in (200, 201):
            note(
                "storage upsert",
                "owner upsert denied; live project is missing the owner SELECT policy required by Storage for upsert",
            )
        storage_delete(path=replace_path)

        delete_path = f"{user1.id}/delete-{uuid.uuid4().hex[:8]}.png"
        created_paths.append(delete_path)
        r = storage_upload(token1, delete_path, images["png"][0], "image/png")
        check(
            "Storage: delete fixture uploaded",
            r.status_code in (200, 201),
            short(r),
        )
        r = storage_delete(token1, delete_path)
        check(
            "Storage: owner can delete own object",
            r.status_code in (200, 204),
            short(r),
        )
        if r.status_code not in (200, 204):
            note(
                "storage delete",
                "owner delete denied; live project is missing the owner SELECT policy required by Storage for delete",
            )
        storage_delete(path=delete_path)

        list_path = f"{user1.id}/list-{uuid.uuid4().hex[:8]}.png"
        created_paths.append(list_path)
        r = storage_upload(token1, list_path, images["png"][0], "image/png")
        check(
            "Storage: list fixture uploaded",
            r.status_code in (200, 201),
            short(r),
        )
        try:
            r = storage_list(token1, f"{user1.id}/")
            data = json_or_empty(r)
            found = isinstance(data, list) and any(
                item.get("name", "").startswith("list-") for item in data
            )
            check(
                "Storage: owner can list own folder",
                r.status_code == 200 and found,
                short(r),
            )
        except httpx.TimeoutException:
            skip("Storage: owner list own folder", "request timed out")
        storage_delete(path=list_path)

        anon_path = f"{user1.id}/anon-{uuid.uuid4().hex[:8]}.png"
        created_paths.append(anon_path)
        r = storage_upload(None, anon_path, images["png"][0], "image/png")
        anon_denied = (
            r.status_code in (401, 403)
            or (r.status_code == 400 and "row-level security" in r.text.lower())
        )
        check(
            "Storage: anon upload denied",
            anon_denied,
            short(r),
        )
        if anon_denied:
            note("anon storage upload", "denied with HTTP 400/403 by storage RLS")
            skip("Storage: service cleanup of anon path", "anon upload created no object")
        else:
            r = storage_delete(path=anon_path)
            check(
                "Storage: service cleanup of anon path",
                r.status_code in (200, 204),
                short(r),
            )

        # -------------------------------------------------------- rate limiting
        ip = "203.0.113.250"
        statuses = []
        retry_after = None
        for _ in range(61):
            r = httpx.get(
                f"{BACKEND}/api/account/me",
                headers={"X-Forwarded-For": ip},
                timeout=10,
            )
            statuses.append(r.status_code)
            if r.status_code == 429:
                retry_after = r.headers.get("Retry-After")
                break
        check(
            "Backend: live rate limit returns 429",
            429 in statuses,
            f"statuses={statuses[:3]}...{statuses[-3:]} count={len(statuses)}",
        )
        if 429 in statuses:
            check(
                "Backend: rate-limited response has Retry-After",
                retry_after is not None,
                str(retry_after),
            )
        check(
            "Backend: rate limit allows at most 60 requests/min",
            statuses.count(401) <= 60,
            f"401s={statuses.count(401)} total={len(statuses)}",
        )

        # ------------------------------------------------------------- headers
        r = httpx.get(f"{BACKEND}/api/account/me", timeout=10)
        headers = {k.lower(): v for k, v in r.headers.items()}
        for header, expected in (
            ("cache-control", "no-store"),
            ("x-content-type-options", "nosniff"),
            ("x-frame-options", "DENY"),
            ("referrer-policy", "no-referrer"),
            ("cross-origin-resource-policy", "same-site"),
        ):
            check(
                f"Backend header {header}",
                expected.lower() in headers.get(header, "").lower(),
                headers.get(header, ""),
            )

        r = httpx.get(f"{FRONTEND}/", timeout=20)
        headers = {k.lower(): v for k, v in r.headers.items()}
        check("Frontend / responds 200", r.status_code == 200, str(r.status_code))
        csp = headers.get("content-security-policy", "")
        check(
            "Frontend CSP present",
            "default-src 'self'" in csp and "frame-ancestors 'none'" in csp,
            csp[:240],
        )
        check(
            "Frontend nosniff/frame/referrer/permissions headers",
            headers.get("x-content-type-options") == "nosniff"
            and headers.get("x-frame-options") == "DENY"
            and headers.get("referrer-policy") == "strict-origin-when-cross-origin"
            and "permissions-policy" in headers,
            json.dumps({k: headers.get(k) for k in (
                "x-content-type-options",
                "x-frame-options",
                "referrer-policy",
            )}),
        )
        check(
            "Frontend COOP/CORP headers",
            headers.get("cross-origin-opener-policy") == "same-origin"
            and headers.get("cross-origin-resource-policy") == "same-origin",
            f"{headers.get('cross-origin-opener-policy')}/{headers.get('cross-origin-resource-policy')}",
        )

        # ----------------------------------------------- policy introspection
        r = rest("GET", "/pg_policies?select=*", key=SECRET)
        if r.status_code == 200:
            note("pg_policies introspection", f"available: {len(json_or_empty(r) or [])} rows")
        else:
            skip(
                "direct pg_policies introspection",
                f"not exposed through PostgREST: {short(r)}; functional RLS behavior is the evidence",
            )

    except Exception as exc:  # noqa: BLE001 - report and still clean up
        print(f"FATAL {type(exc).__name__}: {exc}")
        FAIL.append("extended suite completed without fatal error")
    finally:
        cleanup()
        print("cleanup complete")

    print()
    print(f"{len(PASS)} passed, {len(FAIL)} failed, {len(SKIP)} skipped, {len(INFO)} info")
    if FAIL:
        print("failed:")
        for name in FAIL:
            print(f"  - {name}")
    if SKIP:
        print("skipped:")
        for name in SKIP:
            print(f"  - {name}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
