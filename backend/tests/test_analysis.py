import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.src.services import noir_services
from backend.src.services.analysis_services import (
    _collect_files,
    _normalize_endpoints,
    _relative_path,
)


class PathNormalizationTests(unittest.TestCase):
    def test_relative_path_strips_repository_root(self):
        root = os.path.abspath("/tmp/checkout")

        self.assertEqual(
            _relative_path(os.path.join(root, "src", "app.py"), root),
            "src/app.py",
        )

    def test_relative_path_rejects_escape(self):
        root = os.path.abspath("/tmp/checkout")
        outside = os.path.abspath("/tmp/other/app.py")

        self.assertEqual(_relative_path(outside, root), outside)

    def test_normalize_endpoints_updates_handler_and_code_paths(self):
        root = os.path.abspath("/tmp/checkout")
        endpoints = [{
            "handler": {
                "path": os.path.join(root, "app.py"),
            },
            "details": {
                "code_paths": [{
                    "path": os.path.join(root, "routes.py"),
                }],
            },
        }]

        normalized = _normalize_endpoints(endpoints, root)

        self.assertEqual(normalized[0]["handler"]["path"], "app.py")
        self.assertEqual(
            normalized[0]["details"]["code_paths"][0]["path"],
            "routes.py",
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
