"""Unit checks that the account API fails closed (401) on auth misconfiguration.

Run from the repository root with the venv active:

    python -m unittest backend.tests_dev.test_auth_fail_closed -v
"""

import unittest
from unittest import mock

from backend.__main__ import app
from backend.src import flask_auth
from backend.src.routes import account

VERIFIED_CLAIMS = {
    "sub": "00000000-0000-0000-0000-000000000000",
    "role": "authenticated",
}


class FailClosedTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def _get_saves(self):
        return self.client.get(
            "/api/account/saves",
            headers={"Authorization": "Bearer synthetic-token"},
        )

    def test_missing_publishable_key_returns_401(self):
        with mock.patch.object(
            flask_auth, "verify_access_token", return_value=VERIFIED_CLAIMS
        ), mock.patch.object(
            account, "SUPABASE_URL", "https://example.supabase.co"
        ), mock.patch.object(
            account, "PUBLISHABLE_KEY", ""
        ):
            res = self._get_saves()
        self.assertEqual(res.status_code, 401)

    def test_missing_project_url_returns_401(self):
        with mock.patch.object(
            flask_auth, "verify_access_token", return_value=VERIFIED_CLAIMS
        ), mock.patch.object(account, "SUPABASE_URL", ""), mock.patch.object(
            account, "PUBLISHABLE_KEY", "publishable-key"
        ):
            res = self._get_saves()
        self.assertEqual(res.status_code, 401)

    def test_jwks_misconfiguration_fails_closed_with_401(self):
        with mock.patch.object(flask_auth, "SUPABASE_URL", ""):
            previous = flask_auth._JWK_CLIENT
            flask_auth._JWK_CLIENT = None
            try:
                with self.assertRaises(flask_auth.AuthError) as caught:
                    flask_auth._jwk_client()
            finally:
                flask_auth._JWK_CLIENT = previous
        self.assertEqual(caught.exception.status, 401)


if __name__ == "__main__":
    unittest.main()
