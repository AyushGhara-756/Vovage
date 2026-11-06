import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.src.services import noir_services
from backend.src.services.analysis_services import (
    _collect_files,
    _map_endpoints,
    _to_api_endpoint,
)


class EndpointMappingTests(unittest.TestCase):
    def test_maps_query_and_path_params(self):
        endpoint = {
            "url": "/users/{id}",
            "method": "GET",
            "params": [
                {"name": "id", "value": "", "param_type": "path"},
                {"name": "verbose", "value": "", "param_type": "query"},
            ],
        }

        self.assertEqual(
            _to_api_endpoint(endpoint),
            {
                "endpoint": "/users/{id}",
                "method": "GET",
                "params": ["id", "verbose"],
                "body": {},
            },
        )

    def test_maps_json_form_and_body_params(self):
        endpoint = {
            "url": "/users",
            "method": "POST",
            "params": [
                {"name": "email", "value": "", "param_type": "json"},
                {"name": "name", "value": "test", "param_type": "form"},
                {"name": "note", "value": "hello", "param_type": "body"},
            ],
        }

        result = _to_api_endpoint(endpoint)

        self.assertEqual(result["params"], [])
        self.assertEqual(
            result["body"],
            {
                "email": "",
                "name": "test",
                "note": "hello",
            },
        )

    def test_dedupes_params_and_ignores_non_body_duplicates(self):
        endpoint = {
            "url": "/users/{id}",
            "method": "GET",
            "params": [
                {"name": "id", "value": "", "param_type": "path"},
                {"name": "id", "value": "", "param_type": "query"},
                {"name": "page", "value": "", "param_type": "query"},
            ],
        }

        result = _to_api_endpoint(endpoint)

        self.assertEqual(result["params"], ["id", "page"])

    def test_accepts_patch_and_head(self):
        for method in ("PATCH", "HEAD"):
            endpoint = {
                "url": "/users",
                "method": method,
                "params": [],
            }

            self.assertEqual(_to_api_endpoint(endpoint)["method"], method)

    def test_uppercases_method(self):
        endpoint = {
            "url": "/users",
            "method": "post",
            "params": [],
        }

        self.assertEqual(_to_api_endpoint(endpoint)["method"], "POST")

    def test_skips_unsupported_methods(self):
        for method in ("QUERY", "SEND", "CLI", "TRACE"):
            endpoint = {
                "url": "/users",
                "method": method,
                "params": [],
            }

            self.assertIsNone(_to_api_endpoint(endpoint))

    def test_skips_malformed_endpoints(self):
        self.assertIsNone(_to_api_endpoint(None))
        self.assertIsNone(_to_api_endpoint({}))
        self.assertIsNone(_to_api_endpoint({"method": "GET"}))
        self.assertIsNone(_to_api_endpoint({"url": "/users"}))

    def test_map_endpoints_filters_unsupported_methods(self):
        endpoints = [
            {"url": "/get", "method": "GET", "params": []},
            {"url": "/query", "method": "QUERY", "params": []},
            {"url": "/post", "method": "POST", "params": []},
        ]

        mapped = _map_endpoints(endpoints)

        self.assertEqual(
            [endpoint["endpoint"] for endpoint in mapped],
            ["/get", "/post"],
        )

    def test_collect_files_skips_excluded_directories(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "app.py").write_text("")
            Path(root, "src").mkdir()
            Path(root, "src", "routes.py").write_text("")
            Path(root, "__pycache__").mkdir()
            Path(root, "__pycache__", "cached.pyc").write_text("")
            Path(root, "node_modules").mkdir()
            Path(root, "node_modules", "package.js").write_text("")

            self.assertEqual(
                _collect_files(root),
                ["app.py", "src/routes.py"],
            )


class NoirScanTests(unittest.TestCase):
    @staticmethod
    def _process(returncode=0, stdout="", stderr=""):
        process = Mock()
        process.returncode = returncode
        process.communicate.return_value = (stdout, stderr)
        return process

    @patch("backend.src.services.noir_services.subprocess.Popen")
    def test_parses_json_output(self, popen):
        popen.return_value = self._process(
            stdout='{"endpoints": [], "errors": []}'
        )

        result = noir_services.run_noir_scan("/tmp/repo")

        self.assertEqual(result["endpoints"], [])
        self.assertEqual(result["errors"], [])

    @patch("backend.src.services.noir_services.subprocess.Popen")
    def test_rejects_malformed_json(self, popen):
        popen.return_value = self._process(stdout="not json")

        with self.assertRaises(noir_services.NoirScanError):
            noir_services.run_noir_scan("/tmp/repo")

    @patch("backend.src.services.noir_services.subprocess.Popen")
    def test_rejects_non_zero_exit(self, popen):
        popen.return_value = self._process(
            returncode=2,
            stderr="analyzer failed",
        )

        with self.assertRaises(noir_services.NoirScanError):
            noir_services.run_noir_scan("/tmp/repo")

    @patch("backend.src.services.noir_services.subprocess.Popen")
    def test_passes_passive_scan_flag(self, popen):
        popen.return_value = self._process(
            stdout='{"endpoints": [], "errors": []}'
        )

        noir_services.run_noir_scan("/tmp/repo", passive_scan=True)

        command = popen.call_args.args[0]
        self.assertIn("-P", command)


if __name__ == "__main__":
    unittest.main()
