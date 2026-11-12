"""SerpApi no-results errors should surface as friendly user messages.

Run from the repository root with the venv active:

    python -m unittest backend.tests_dev.test_serp_no_results -v
"""

import json
import unittest
from unittest import mock

from backend.src.services import serp_service


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def call(kind, error):
    with mock.patch.object(
        serp_service.urllib.request, "urlopen",
        return_value=FakeResponse({"error": error}),
    ), mock.patch.object(serp_service, "_api_key", return_value="test-key"):
        with unittest.TestCase().assertRaises(serp_service.SerpError) as caught:
            serp_service._serp_request(kind, {"engine": "test"})
    return str(caught.exception)


class SerpNoResultsTests(unittest.TestCase):
    def test_flight_no_results_is_friendly(self):
        message = call(
            "flight",
            "Google Flights hasn't returned any results for this query.",
        )
        self.assertEqual(
            message,
            "No flights were found for that route and dates. "
            "Try nearby airports or different dates.",
        )

    def test_hotel_no_results_is_friendly(self):
        message = call(
            "hotel",
            "Google Hotels hasn't returned any results for this query.",
        )
        self.assertEqual(
            message,
            "No stays were found for that destination and dates. "
            "Try another place or different dates.",
        )

    def test_other_serpapi_errors_are_preserved(self):
        message = call("flight", "Invalid API key.")
        self.assertEqual(message, "Invalid API key.")


if __name__ == "__main__":
    unittest.main()
