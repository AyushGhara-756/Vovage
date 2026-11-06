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

SUPPORTED_METHODS = {
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
}

BODY_PARAM_TYPES = {"json", "form", "body"}


def _to_api_endpoint(endpoint):
    if not isinstance(endpoint, dict):
        return None

    url = endpoint.get("url")
    method = endpoint.get("method")

    if not isinstance(url, str) or not url:
        return None

    if not isinstance(method, str):
        return None

    method = method.upper()
    if method not in SUPPORTED_METHODS:
        return None

    params = []
    body = {}
    seen_params = set()

    for param in endpoint.get("params") or []:
        if not isinstance(param, dict):
            continue

        name = param.get("name")
        if not isinstance(name, str) or not name:
            continue

        param_type = param.get("param_type", "")
        param_type = param_type.lower() if isinstance(param_type, str) else ""

        if param_type in BODY_PARAM_TYPES:
            value = param.get("value")
            body[name] = "" if value is None else value
            continue

        if name not in seen_params:
            seen_params.add(name)
            params.append(name)

    return {
        "endpoint": url,
        "method": method,
        "params": params,
        "body": body,
    }


def _map_endpoints(endpoints):
    mapped = []

    for endpoint in endpoints or []:
        converted = _to_api_endpoint(endpoint)
        if converted is not None:
            mapped.append(converted)

    return mapped


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
        endpoints = _map_endpoints(scan_result.get("endpoints", []))
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
