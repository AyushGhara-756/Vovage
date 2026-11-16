"""Live Supabase + Flask + Next.js auth integration checks.

This is a developer script, not a unit test: it creates real (confirmed or
unconfirmed) users in the configured Supabase project, exercises the Flask
account API with their JWTs, optionally exercises the Next.js callback and
proxy routes, then deletes the test users again.

Usage (from the repository root, with the root venv active):

    python backend/tests_dev/test_auth_integration.py
    python backend/tests_dev/test_auth_integration.py --frontend http://localhost:3000

The optional --frontend run also verifies real signup/recovery token hashes
through `/auth/callback`; it does not click a real inbox link.
"""

import argparse
import base64
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supabase import create_client  # noqa: E402
from backend.__main__ import app  # noqa: E402

PASS = []
FAIL = []
SKIP = []


def check(name, condition, detail=""):
    if condition:
        PASS.append(name)
        print(f"PASS  {name}")
    else:
        FAIL.append(name)
        print(f"FAIL  {name} {detail}")


def read_env():
    values = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            values[key.strip()] = value
    return values


ENV = read_env()


def env(key):
    return os.environ.get(key) or ENV.get(key) or ""


URL = (env("NEXT_PUBLIC_SUPABASE_URL") or env("SUPABASE_URL")).rstrip("/")
PUB = env("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
SECRET = env("SUPABASE_SECRET_KEY")


def body(res):
    try:
        return res.get_json()
    except Exception:
        return {}


def auth(token):
    return {"Authorization": f"Bearer {token}"}


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZQmcAAAAASUVORK5CYII="
)


def storage_upload(token, path, data):
    return httpx.post(
        f"{URL}/storage/v1/object/avatars/{path}",
        headers={
            "apikey": PUB,
            "Authorization": f"Bearer {token}",
            "Content-Type": "image/png",
            "x-upsert": "true",
        },
        content=data,
        timeout=20,
    )


def storage_delete(token, path):
    return httpx.request(
        "DELETE",
        f"{URL}/storage/v1/object/avatars/{path}",
        headers={"apikey": PUB, "Authorization": f"Bearer {token}"},
        timeout=20,
    )


def make_user(admin, public, tag, confirmed=True):
    email = f"vovage.test.{tag}.{int(time.time())}.{uuid.uuid4().hex[:6]}@example.com"
    password = "Vovage!Test" + uuid.uuid4().hex[:10]
    user = admin.auth.admin.create_user({
        "email": email,
        "password": password,
        "email_confirm": confirmed,
        "user_metadata": {
            "full_name": f"Vovage Test {tag}",
            "phone_number": None,
            "home_city": "Test City",
            "home_airport": "Test Airport",
            "preferred_currency": "INR",
            "terms_accepted": True,
            "terms_version": "v1.0",
            "privacy_version": "v1.0",
        },
    }).user
    token = None
    if confirmed:
        token = public.auth.sign_in_with_password(
            {"email": email, "password": password}
        ).session.access_token
    return user, email, password, token


def run_backend_checks(admin, public):
    client = app.test_client()
    user1 = user2 = None
    storage_path = None
    try:
        user1, email1, _pw1, token1 = make_user(admin, public, "a")
        user2, email2, _pw2, token2 = make_user(admin, public, "b")
        print(f"created users: {email1[:12]}..., {email2[:12]}...")

        profile = admin.table("profiles").select("*").eq("id", user1.id).execute().data
        prefs = admin.table("user_preferences").select("*").eq("user_id", user1.id).execute().data
        consents = admin.table("user_consents").select("*").eq("user_id", user1.id).execute().data
        check("trigger created profile", len(profile) == 1)
        check("trigger created preferences", len(prefs) == 1)
        check("trigger recorded consents", len(consents) >= 2)
        if profile:
            check("profile name from metadata", profile[0].get("full_name") == "Vovage Test a")
        if consents:
            types = {c.get("consent_type") for c in consents}
            check("consent types terms/privacy", {"terms", "privacy_policy"}.issubset(types), str(types))

        res = client.get("/api/account/me")
        check("GET /me without token is 401", res.status_code == 401, str(res.status_code))

        res = client.get("/api/account/me", headers=auth("not-a-jwt"))
        check("GET /me with garbage token is 401", res.status_code == 401, str(res.status_code))

        tampered = token1[:-4] + ("AAAA" if not token1.endswith("AAAA") else "BBBB")
        res = client.get("/api/account/me", headers=auth(tampered))
        check("GET /me with tampered token is 401", res.status_code == 401, str(res.status_code))

        res = client.get("/api/account/me", headers=auth(token1))
        data = body(res)
        check("GET /me authorized is 200", res.status_code == 200, str(res.status_code) + " " + json.dumps(data)[:300])
        check("GET /me returns own email", data.get("email") == email1)
        check("GET /me email verified", data.get("email_verified") is True)
        check("GET /me includes profile", isinstance(data.get("profile"), dict))
        check("GET /me includes preferences", isinstance(data.get("preferences"), dict))
        check("GET /me includes consents", isinstance(data.get("consents"), list) and len(data["consents"]) >= 2)
        check("GET /me user id matches token", data.get("user_id") == user1.id)

        updates = {
            "full_name": "Vovage Renamed",
            "phone_number": "+91 98765 43210",
            "home_city": "Mumbai",
            "home_airport": "BOM",
            "preferred_currency": "USD",
            "avatar_url": "https://example.com/avatar.png",
            "preferred_travel_type": "leisure",
            "preferred_cabin": "business",
            "preferred_hotel_rating": 4,
            "notification_enabled": False,
        }
        res = client.patch("/api/account/me", headers=auth(token1), json=updates)
        data = body(res)
        check("PATCH /me valid is 200", res.status_code == 200, str(res.status_code) + " " + json.dumps(data)[:300])
        if res.status_code == 200:
            check("PATCH /me persisted profile name", data["profile"]["full_name"] == "Vovage Renamed")
            check("PATCH /me persisted currency", data["profile"]["preferred_currency"] == "USD")
            check("PATCH /me persisted rating", data["preferences"]["preferred_hotel_rating"] == 4)
            check("PATCH /me persisted notifications", data["preferences"]["notification_enabled"] is False)

        for label, payload in (
            ("bad currency", {"preferred_currency": "XXX"}),
            ("bad rating type", {"preferred_hotel_rating": 3.5}),
            ("empty update", {}),
            ("bad avatar", {"avatar_url": "http://example.com/x.png"}),
            ("bad phone", {"phone_number": "abc"}),
            ("bad travel type", {"preferred_travel_type": "space"}),
        ):
            res = client.patch("/api/account/me", headers=auth(token1), json=payload)
            check(f"PATCH /me rejects {label}", res.status_code == 400, str(res.status_code) + " " + json.dumps(body(res))[:200])

        save_params = {"origin": "BOM", "destination": "DEL", "outbound_date": "2026-12-01"}
        res = client.post("/api/account/saves", headers=auth(token1), json={"search_type": "flight", "search_name": "BOM to DEL", "search_params": save_params})
        data = body(res)
        check("POST /saves is 201", res.status_code == 201, str(res.status_code) + " " + json.dumps(data)[:300])
        save_id = (data.get("save") or {}).get("id")

        res = client.post("/api/account/saves", headers=auth(token1), json={"search_type": "bus", "search_params": save_params})
        check("POST /saves rejects bad type", res.status_code == 400, str(res.status_code))

        res = client.get("/api/account/saves", headers=auth(token1))
        saves = body(res).get("saves") or []
        check("GET /saves lists own save", res.status_code == 200 and any(s.get("id") == save_id for s in saves), str(res.status_code))

        res = client.patch(f"/api/account/saves/{save_id}", headers=auth(token1), json={"search_name": "Renamed route"})
        data = body(res)
        check("PATCH /saves renames", res.status_code == 200 and data.get("save", {}).get("search_name") == "Renamed route", str(res.status_code) + " " + json.dumps(data)[:300])

        res = client.patch(f"/api/account/saves/{save_id}", headers=auth(token2), json={"search_name": "stolen"})
        check("PATCH other user's save is 404", res.status_code == 404, str(res.status_code))

        res = client.delete(f"/api/account/saves/{save_id}", headers=auth(token2))
        check("DELETE other user's save is 404", res.status_code == 404, str(res.status_code))

        res = client.delete("/api/account/saves/not-a-uuid", headers=auth(token1))
        check("DELETE bad save id is 400", res.status_code == 400, str(res.status_code))

        res = client.delete(f"/api/account/saves/{save_id}", headers=auth(token1))
        check("DELETE own save is 200", res.status_code == 200, str(res.status_code) + " " + json.dumps(body(res))[:200])

        res = client.get("/api/account/saves", headers=auth(token1))
        check("GET /saves empty after delete", body(res).get("saves") == [])

        hist_params = {"q": "Goa", "check_in_date": "2026-12-05"}
        res = client.post("/api/account/history", headers=auth(token1), json={"search_type": "hotel", "search_params": hist_params})
        data = body(res)
        check("POST /history is 201", res.status_code == 201, str(res.status_code) + " " + json.dumps(data)[:300])
        entry_id = (data.get("history") or {}).get("id")

        res = client.get("/api/account/history", headers=auth(token1))
        hist = body(res).get("history") or []
        check("GET /history lists own entry", res.status_code == 200 and any(h.get("id") == entry_id for h in hist), str(res.status_code))

        res = client.delete(f"/api/account/history/{entry_id}", headers=auth(token2))
        check("DELETE other user's history is 404", res.status_code == 404, str(res.status_code))

        res = client.delete(f"/api/account/history/{entry_id}", headers=auth(token1))
        check("DELETE own history entry is 200", res.status_code == 200, str(res.status_code))

        client.post("/api/account/history", headers=auth(token1), json={"search_type": "flight", "search_params": save_params})
        res = client.delete("/api/account/history", headers=auth(token1))
        check("DELETE /history clears all", res.status_code == 200, str(res.status_code))
        res = client.get("/api/account/history", headers=auth(token1))
        check("GET /history empty after clear", body(res).get("history") == [])

        res = client.post("/api/account/avatar/bucket", headers=auth(token1))
        data = body(res)
        check("POST /avatar/bucket is 200", res.status_code == 200, str(res.status_code) + " " + json.dumps(data)[:200])
        res = client.post("/api/account/avatar/bucket", headers=auth(token1))
        check("POST /avatar/bucket idempotent", res.status_code == 200 and body(res).get("created") is False, str(res.status_code))

        storage_path = f"{user1.id}/integration-{uuid.uuid4().hex[:8]}.png"
        uploaded = storage_upload(token1, storage_path, PNG_1X1)
        storage_rls_missing = (
            uploaded.status_code in (400, 403)
            and "row-level security" in uploaded.text.lower()
        )
        if storage_rls_missing:
            SKIP.append("avatar upload (storage RLS policies not applied)")
            print(
                "SKIP  avatar checks: storage RLS policies are not applied. Run the "
                "storage policy SQL in README 'Authentication & account data' and rerun."
            )
        else:
            check(
                "avatar upload works in own folder",
                uploaded.status_code in (200, 201),
                f"{uploaded.status_code} {uploaded.text[:200]}",
            )
        if uploaded.status_code in (200, 201):
            public_read = httpx.get(
                f"{URL}/storage/v1/object/public/avatars/{storage_path}",
                timeout=20,
            )
            check(
                "avatar public URL serves the uploaded image",
                public_read.status_code == 200 and public_read.content == PNG_1X1,
                str(public_read.status_code),
            )
            other_upload = storage_upload(token2, storage_path, PNG_1X1)
            check(
                "other user cannot overwrite avatar",
                other_upload.status_code not in (200, 201),
                f"{other_upload.status_code} {other_upload.text[:200]}",
            )
            other_delete = storage_delete(token2, storage_path)
            check(
                "other user cannot delete avatar",
                other_delete.status_code not in (200, 204),
                f"{other_delete.status_code} {other_delete.text[:200]}",
            )
            own_delete = storage_delete(token1, storage_path)
            check(
                "owner can delete avatar",
                own_delete.status_code in (200, 204),
                f"{own_delete.status_code} {own_delete.text[:200]}",
            )

        res = client.get("/api/account/me", headers=auth(token2))
        data = body(res)
        check("second user sees own profile", res.status_code == 200 and data.get("profile", {}).get("full_name") == "Vovage Test b")

        res = client.patch(
            "/api/account/me",
            headers=auth(token2),
            json={
                "id": user1.id,
                "user_id": user1.id,
                "full_name": "Spoof Attempt",
                "email": "attacker@example.com",
                "role": "service_role",
            },
        )
        check("PATCH /me ignores supplied ids/email/role", res.status_code == 200, str(res.status_code))
        p1 = admin.table("profiles").select("full_name").eq("id", user1.id).single().execute().data
        p2 = admin.table("profiles").select("full_name").eq("id", user2.id).single().execute().data
        check("profile spoof did not change other user", p1.get("full_name") == "Vovage Renamed", str(p1))
        check("profile spoof changed own user only", p2.get("full_name") == "Spoof Attempt", str(p2))
        u2 = admin.auth.admin.get_user_by_id(user2.id).user
        check("email cannot be changed through profile API", u2.email == email2)

        res = client.post(
            "/api/account/saves",
            headers=auth(token2),
            json={
                "user_id": user1.id,
                "search_type": "hotel",
                "search_name": "User2 hotel",
                "search_params": {"q": "Goa"},
            },
        )
        save2_id = (body(res).get("save") or {}).get("id")
        check("POST /saves ignores supplied user_id", res.status_code == 201, str(res.status_code))
        row = admin.table("saved_searches").select("user_id").eq("id", save2_id).single().execute().data
        check("save row owned by token user", row.get("user_id") == user2.id)
        res1 = client.get("/api/account/saves", headers=auth(token1))
        res2 = client.get("/api/account/saves", headers=auth(token2))
        check("user1 cannot see user2 save", not any(s.get("id") == save2_id for s in (body(res1).get("saves") or [])))
        check("user2 can see own save", any(s.get("id") == save2_id for s in (body(res2).get("saves") or [])))

        res = client.post(
            "/api/account/history",
            headers=auth(token2),
            json={
                "user_id": user1.id,
                "search_type": "hotel",
                "search_params": {"q": "Goa"},
            },
        )
        entry2_id = (body(res).get("history") or {}).get("id")
        check("POST /history ignores supplied user_id", res.status_code == 201, str(res.status_code))
        row = admin.table("search_history").select("user_id").eq("id", entry2_id).single().execute().data
        check("history row owned by token user", row.get("user_id") == user2.id)
        res1 = client.get("/api/account/history", headers=auth(token1))
        check("user1 cannot see user2 history", not any(h.get("id") == entry2_id for h in (body(res1).get("history") or [])))

        for label, method, path, payload in (
            ("GET /saves", "get", "/api/account/saves", None),
            ("GET /history", "get", "/api/account/history", None),
            ("POST /saves", "post", "/api/account/saves", {"search_type": "flight", "search_params": {"a": 1}}),
            ("POST /history", "post", "/api/account/history", {"search_type": "flight", "search_params": {"a": 1}}),
            ("POST /avatar/bucket", "post", "/api/account/avatar/bucket", {}),
        ):
            res = client.get(path) if method == "get" else client.post(path, json=payload)
            check(f"{label} without token is 401", res.status_code == 401, str(res.status_code))

        pre = client.options(
            "/api/account/me",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        check("CORS allows frontend origin", pre.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000", str(pre.headers.get("Access-Control-Allow-Origin")))
        pre = client.options(
            "/api/account/me",
            headers={
                "Origin": "http://evil.example",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        check("CORS blocks other origin", pre.headers.get("Access-Control-Allow-Origin") is None, str(pre.headers.get("Access-Control-Allow-Origin")))
    finally:
        if storage_path:
            try:
                httpx.request(
                    "DELETE",
                    f"{URL}/storage/v1/object/avatars/{storage_path}",
                    headers={
                        "apikey": SECRET,
                        "Authorization": f"Bearer {SECRET}",
                    },
                    timeout=20,
                )
            except Exception:
                pass
        for user in (user1, user2):
            if user is not None:
                try:
                    admin.auth.admin.delete_user(user.id)
                except Exception as exc:
                    print("cleanup warning:", type(exc).__name__)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(opener, url):
    request = urllib.request.Request(url, headers={"User-Agent": "vovage-auth-test"})
    try:
        with opener.open(request, timeout=60) as res:
            return res.status, res.headers, res.read(4000)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read(4000)


def run_frontend_checks(base, admin, public):
    base = base.rstrip("/")
    anonymous = urllib.request.build_opener(NoRedirect)
    status, headers, _ = fetch(anonymous, f"{base}/profile")
    location = headers.get("Location") or ""
    check(
        "frontend /profile redirects signed-out",
        status in (307, 308)
        and "/signin" in location
        and "next=%2Fprofile" in location,
        f"{status} {location}",
    )
    status, _headers, _ = fetch(anonymous, f"{base}/signin")
    check("frontend /signin renders", status == 200, str(status))

    for label, path in (
        ("missing token", "/auth/callback"),
        ("external next", "/auth/callback?next=https://evil.example"),
        ("protocol-relative next", "/auth/callback?next=//evil.example"),
        ("provider error", "/auth/callback?error=access_denied&error_description=Link+expired"),
    ):
        status, headers, _ = fetch(anonymous, f"{base}{path}")
        location = headers.get("Location") or ""
        check(
            f"frontend callback {label} redirects to signin",
            status in (307, 308)
            and "/signin?verify_error=" in location
            and "evil.example" not in location,
            f"{status} {location}",
        )

    signup_user = None
    recovery_user = None
    try:
        signup_user, email, password, _token = make_user(admin, public, "verify", confirmed=False)
        link = admin.auth.admin.generate_link({
            "type": "signup",
            "email": email,
            "password": password,
            "options": {"redirect_to": f"{base}/auth/callback?next=/profile"},
        })
        token_hash = link.properties.hashed_token
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPCookieProcessor(jar))
        status, headers, _ = fetch(
            opener,
            f"{base}/auth/callback?token_hash={urllib.parse.quote(token_hash)}&type=signup&next=%2Fprofile",
        )
        location = headers.get("Location") or ""
        parsed = urllib.parse.urlparse(location)
        check(
            "signup token hash verifies and redirects to profile",
            status in (307, 308)
            and parsed.path == "/profile"
            and "1" in urllib.parse.parse_qs(parsed.query).get("verified", []),
            f"{status} {location}",
        )
        check("signup callback sets session cookies", len(jar) > 0, str(len(jar)))
        status, _headers, _ = fetch(opener, f"{base}/profile")
        check("verified session can open /profile", status == 200, str(status))

        recovery_user, email, _password, _token = make_user(admin, public, "recovery")
        link = admin.auth.admin.generate_link({
            "type": "recovery",
            "email": email,
            "options": {"redirect_to": f"{base}/auth/callback?next=/auth/update-password"},
        })
        token_hash = link.properties.hashed_token
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPCookieProcessor(jar))
        status, headers, _ = fetch(
            opener,
            f"{base}/auth/callback?token_hash={urllib.parse.quote(token_hash)}&type=recovery&next=%2Fauth%2Fupdate-password",
        )
        location = headers.get("Location") or ""
        parsed = urllib.parse.urlparse(location)
        check(
            "recovery token hash redirects to update-password",
            status in (307, 308)
            and parsed.path == "/auth/update-password"
            and "1" not in urllib.parse.parse_qs(parsed.query).get("verified", []),
            f"{status} {location}",
        )
        check("recovery callback sets session cookies", len(jar) > 0, str(len(jar)))
        status, _headers, _ = fetch(opener, f"{base}/auth/update-password")
        check("recovery session can open /auth/update-password", status == 200, str(status))
        status, _headers, _ = fetch(opener, f"{base}/profile")
        check("recovery session can open /profile", status == 200, str(status))
    finally:
        for user in (signup_user, recovery_user):
            if user is not None:
                try:
                    admin.auth.admin.delete_user(user.id)
                except Exception as exc:
                    print("cleanup warning:", type(exc).__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--frontend",
        help="Base URL of a running Next.js server, e.g. http://localhost:3000",
    )
    args = parser.parse_args()

    if not (URL and PUB and SECRET):
        print("Missing Supabase env vars (NEXT_PUBLIC_SUPABASE_URL, "
              "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY, SUPABASE_SECRET_KEY).")
        return 2

    admin = create_client(URL, SECRET)
    public = create_client(URL, PUB)

    run_backend_checks(admin, public)
    if args.frontend:
        run_frontend_checks(args.frontend, admin, public)
    else:
        print("SKIP  frontend checks (pass --frontend http://localhost:3000)")

    skipped = f", {len(SKIP)} skipped" if SKIP else ""
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed{skipped}")
    if SKIP:
        print("skipped:", ", ".join(SKIP))
    if FAIL:
        print("failed:", ", ".join(FAIL))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
