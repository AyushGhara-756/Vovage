import re

from flask import Blueprint, jsonify, request

from ..services.analysis_services import analyze_repository
from ..services.github_services import RepositoryDownloadError
from ..services.noir_services import (
    NoirScanError,
    NoirTimeout,
    NoirUnavailable,
    get_noir_version,
)

analysis_bp = Blueprint("analysis", __name__, url_prefix="/api/analysis")

_OWNER_REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
_REF_PATTERN = re.compile(r"^[A-Za-z0-9_./-]+$")


def _error(message, status_code):
    return jsonify({"error": message}), status_code


def _valid_ref(ref):
    if not isinstance(ref, str) or not _REF_PATTERN.fullmatch(ref):
        return False

    return ".." not in ref.split("/")


@analysis_bp.get("/health")
def analysis_health():
    try:
        noir = get_noir_version()
    except NoirUnavailable as exc:
        return jsonify({
            "noir": {
                "available": False,
                "error": str(exc),
            }
        }), 503

    return jsonify({
        "noir": {
            "available": True,
            **noir,
        }
    }), 200


@analysis_bp.post("/scan")
def scan_repository():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return _error("Request body must be a JSON object.", 400)

    missing = [
        field
        for field in ("installation_id", "owner", "repo")
        if data.get(field) in (None, "")
    ]
    if missing:
        return _error(
            f"Missing required field(s): {', '.join(missing)}.",
            400,
        )

    installation_id = data["installation_id"]
    owner = data["owner"]
    repo = data["repo"]
    ref = data.get("ref") or None
    passive_scan = data.get("passive_scan", False)

    if (
        isinstance(installation_id, bool)
        or not isinstance(installation_id, int)
        or installation_id <= 0
    ):
        return _error("installation_id must be a positive integer.", 400)

    if (
        not isinstance(owner, str)
        or not _OWNER_REPO_PATTERN.fullmatch(owner)
        or ".." in owner
    ):
        return _error(
            "owner must contain only letters, numbers, '.', '_' or '-'.",
            400,
        )

    if (
        not isinstance(repo, str)
        or not _OWNER_REPO_PATTERN.fullmatch(repo)
        or ".." in repo
    ):
        return _error(
            "repo must contain only letters, numbers, '.', '_' or '-'.",
            400,
        )

    if ref is not None and not _valid_ref(ref):
        return _error("ref contains invalid characters.", 400)

    if not isinstance(passive_scan, bool):
        return _error("passive_scan must be a boolean.", 400)

    try:
        payload = analyze_repository(
            installation_id=installation_id,
            owner=owner,
            repo=repo,
            ref=ref,
            passive_scan=passive_scan,
        )
    except RepositoryDownloadError as exc:
        status_code = (
            exc.status_code
            if exc.status_code in (401, 403, 404, 413)
            else 502
        )
        return _error(str(exc), status_code)
    except NoirUnavailable as exc:
        return _error(str(exc), 503)
    except NoirTimeout as exc:
        return _error(str(exc), 504)
    except NoirScanError as exc:
        return _error(str(exc), 502)

    return jsonify(payload), 200
