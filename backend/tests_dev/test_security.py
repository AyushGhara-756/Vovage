"""Unit checks for rate limiting and the SerpApi daily call cap.

Run from the repository root with the venv active:

    python -m unittest backend.tests_dev.test_security -v
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.src import security


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


class RateLimiterTests(unittest.TestCase):
    def test_allows_then_blocks(self):
        clock = FakeClock()
        limiter = security.RateLimiter(clock=clock)
        self.assertEqual(limiter.allow("ip-a", 2), (True, 0))
        self.assertEqual(limiter.allow("ip-a", 2), (True, 0))
        allowed, retry_after = limiter.allow("ip-a", 2)
        self.assertFalse(allowed)
        self.assertGreater(retry_after, 0)

    def test_isolates_keys(self):
        clock = FakeClock()
        limiter = security.RateLimiter(clock=clock)
        limiter.allow("ip-a", 1)
        self.assertFalse(limiter.allow("ip-a", 1)[0])
        self.assertTrue(limiter.allow("ip-b", 1)[0])

    def test_window_slides(self):
        clock = FakeClock()
        limiter = security.RateLimiter(clock=clock)
        limiter.allow("ip-a", 1)
        self.assertFalse(limiter.allow("ip-a", 1)[0])
        clock.advance(61)
        self.assertTrue(limiter.allow("ip-a", 1)[0])

    def test_reset_clears_state(self):
        clock = FakeClock()
        limiter = security.RateLimiter(clock=clock)
        limiter.allow("ip-a", 1)
        limiter.reset()
        self.assertTrue(limiter.allow("ip-a", 1)[0])


class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "serp_usage.json"
        self.patch = mock.patch.object(security, "USAGE_FILE", self.path)
        self.patch.start()
        self.env = mock.patch.dict(os.environ, {"SERP_DAILY_CALL_LIMIT": "2"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.patch.stop()
        self.tmp.cleanup()

    def test_quota_persists_and_blocks(self):
        security.reserve_serp_call()
        security.reserve_serp_call()
        with self.assertRaises(security.QuotaError):
            security.reserve_serp_call()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data["count"], 2)

    def test_quota_resets_on_new_day(self):
        security.reserve_serp_call()
        security.reserve_serp_call()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["date"] = "2000-01-01"
        self.path.write_text(json.dumps(data), encoding="utf-8")

        security.reserve_serp_call()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data["count"], 1)

    def test_zero_limit_disables_cap(self):
        os.environ["SERP_DAILY_CALL_LIMIT"] = "0"
        for _ in range(5):
            security.reserve_serp_call()
        self.assertFalse(self.path.exists())


class FlaskLimitTests(unittest.TestCase):
    def setUp(self):
        from backend.__main__ import app

        self.client = app.test_client()
        security.LIMITER.reset()

    def tearDown(self):
        security.LIMITER.reset()

    def test_account_requests_are_rate_limited(self):
        with mock.patch.dict(os.environ, {"RATE_LIMIT_ACCOUNT_PER_MINUTE": "1"}):
            first = self.client.get("/api/account/me")
            second = self.client.get("/api/account/me")
        self.assertEqual(first.status_code, 401)
        self.assertEqual(second.status_code, 429)
        self.assertIsNotNone(second.headers.get("Retry-After"))

    def test_forwarded_clients_are_isolated_behind_loopback(self):
        env = {"REMOTE_ADDR": "127.0.0.1"}
        with mock.patch.dict(os.environ, {"RATE_LIMIT_ACCOUNT_PER_MINUTE": "1"}):
            first = self.client.get(
                "/api/account/me",
                headers={"X-Forwarded-For": "203.0.113.1"},
                environ_base=env,
            )
            same = self.client.get(
                "/api/account/me",
                headers={"X-Forwarded-For": "203.0.113.1"},
                environ_base=env,
            )
            other = self.client.get(
                "/api/account/me",
                headers={"X-Forwarded-For": "203.0.113.2"},
                environ_base=env,
            )
        self.assertEqual(first.status_code, 401)
        self.assertEqual(same.status_code, 429)
        self.assertEqual(other.status_code, 401)


if __name__ == "__main__":
    unittest.main()
