from flask import Blueprint, request
from ..services.github_services import get_repo_files
structure_bp = Blueprint("structure", __name__, url_prefix="/api/structure/")

@structure_bp.post("/files")
def get_files():
    data = request.get_json() or {}
    files = get_repo_files(
        179208968,
        "Omat100",
        "VoyageTest"
    )
    return {
        "files": [
            f"{file}" for file in files
        ]
    }


