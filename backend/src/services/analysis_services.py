import os

from .github_services import downloaded_repository
from .noir_services import run_noir_scan

EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "venv",
    ".venv",
    "env",
}


def _relative_path(path, repo_root):
    try:
        relative = os.path.relpath(path, repo_root)
    except ValueError:
        return path

    relative = relative.replace(os.sep, "/")
    if relative == ".." or relative.startswith("../"):
        return path

    return relative


def _normalize_endpoints(endpoints, repo_root):
    for endpoint in endpoints:
        handler = endpoint.get("handler")
        if isinstance(handler, dict) and handler.get("path"):
            handler["path"] = _relative_path(handler["path"], repo_root)

        details = endpoint.get("details")
        if isinstance(details, dict):
            for code_path in details.get("code_paths") or []:
                if isinstance(code_path, dict) and code_path.get("path"):
                    code_path["path"] = _relative_path(
                        code_path["path"], repo_root
                    )

    return endpoints


def _collect_files(repo_root):
    files = []

    for current_root, dirs, filenames in os.walk(repo_root, followlinks=False):
        dirs[:] = [name for name in dirs if name not in EXCLUDED_DIRS]

        for filename in filenames:
            absolute_path = os.path.join(current_root, filename)
            relative = os.path.relpath(absolute_path, repo_root)
            files.append(relative.replace(os.sep, "/"))

    return sorted(files)


def analyze_repository(
    installation_id,
    owner,
    repo,
    ref=None,
    passive_scan=False,
):
    with downloaded_repository(
        installation_id,
        owner,
        repo,
        ref=ref,
    ) as repo_root:
        scan_result = run_noir_scan(repo_root, passive_scan=passive_scan)
        endpoints = _normalize_endpoints(
            scan_result.get("endpoints", []),
            repo_root,
        )
        files = _collect_files(repo_root)

    return {
        "repository": {
            "owner": owner,
            "repo": repo,
            "ref": ref,
        },
        "summary": {
            "file_count": len(files),
            "endpoint_count": len(endpoints),
        },
        "files": files,
        "endpoints": endpoints,
        "passive_results": scan_result.get("passive_results", []),
        "errors": scan_result.get("errors", []),
    }
