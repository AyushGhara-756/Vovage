import contextlib
import os
import tarfile
import tempfile
import time
from urllib.parse import quote

import jwt
import requests
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("GITHUB_APP_ID")
MAX_REPO_ARCHIVE_BYTES = int(
    os.getenv("MAX_REPO_ARCHIVE_BYTES", str(200 * 1024 * 1024))
)


class RepositoryDownloadError(Exception):
    """Raised when a repository cannot be downloaded or extracted."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def _get_private_key():
    private_key_path = os.getenv("GITHUB_PRIVATE_KEY_PATH")

    if not private_key_path:
        raise RuntimeError("GITHUB_PRIVATE_KEY_PATH is not set.")

    with open(private_key_path, "r") as file:
        return file.read()


def generate_jwt():
    now = int(time.time())

    payload = {
        "iat": now - 60,
        "exp": now + 600,
        "iss": APP_ID
    }

    return jwt.encode(payload, _get_private_key(), algorithm="RS256")


def get_installation_id():
    token = generate_jwt()

    response = requests.get(
        "https://api.github.com/app/installations",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json"
        }
    )

    print("Status:", response.status_code)
    response.raise_for_status()

    installations = response.json()

    if not installations:
        print("No installations found.")
        return None

    for installation in installations:
        print(
            "Account:",
            installation["account"]["login"],
            "| Installation ID:",
            installation["id"]
        )


def get_access_token(installation_id):
    token = generate_jwt()

    response = requests.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json"
        }
    )

    response.raise_for_status()

    return response.json()["token"]


def get_repo_files(installation_id, owner, repo):
    token = get_access_token(installation_id)

    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"

    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json"
        }
    )

    response.raise_for_status()

    files = response.json()["tree"]

    _file = []
    for file in files:
        if file["type"] == "blob":
            # print(file["path"])
            _file.append(file["path"])
    return _file

# def get_dependency_graph(installation_id, owner, repo):
#     token = get_access_token(installation_id)

#     url = f"https://api.github.com/repos/{owner}/{repo}/dependency-graph/sbom"

#     response = requests.get(
#         url,
#         headers={
#             "Authorization": f"Bearer {token}",
#             "Accept": "application/vnd.github+json"
#         }
#     )

#     response.raise_for_status()
#     sbom = response.json()

#     for package in sbom["sbom"]["packages"]:
#         name = package.get("name", "")
#         version = package.get("versionInfo", "unknown")

#         if name:
#             print(f"{name} : {version}")


def _github_error(exc, owner, repo):
    response = getattr(exc, "response", None)
    status_code = response.status_code if response is not None else None

    if status_code == 404:
        return (
            f"Repository {owner}/{repo} was not found or the GitHub App "
            "does not have access to it.",
            404,
        )

    if status_code in (401, 403):
        return (
            f"GitHub denied access to {owner}/{repo} (status {status_code}).",
            status_code,
        )

    status_label = status_code if status_code is not None else "unknown"
    return (
        f"GitHub request failed for {owner}/{repo} (status {status_label}).",
        status_code,
    )


def _find_repository_root(extract_root):
    entries = [
        entry
        for entry in os.listdir(extract_root)
        if not entry.startswith(".")
    ]

    if len(entries) == 1:
        candidate = os.path.join(extract_root, entries[0])
        if os.path.isdir(candidate):
            return candidate

    return extract_root


@contextlib.contextmanager
def downloaded_repository(installation_id, owner, repo, ref=None):
    """Yield an extracted repository checkout and clean it up afterwards."""
    try:
        token = get_access_token(installation_id)
    except requests.HTTPError as exc:
        message, status_code = _github_error(exc, owner, repo)
        raise RepositoryDownloadError(message, status_code) from exc
    except requests.RequestException as exc:
        raise RepositoryDownloadError(
            f"Could not authenticate with GitHub for {owner}/{repo}: {exc}"
        ) from exc

    ref_path = f"/{quote(ref, safe='')}" if ref else ""
    url = f"https://api.github.com/repos/{owner}/{repo}/tarball{ref_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    with tempfile.TemporaryDirectory(prefix="vovage-repo-") as tmp_dir:
        archive_path = os.path.join(tmp_dir, "repository.tar.gz")

        try:
            with requests.get(
                url,
                headers=headers,
                stream=True,
                timeout=(10, 120),
            ) as response:
                response.raise_for_status()

                downloaded = 0
                with open(archive_path, "wb") as archive:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue

                        downloaded += len(chunk)
                        if downloaded > MAX_REPO_ARCHIVE_BYTES:
                            raise RepositoryDownloadError(
                                f"Repository archive for {owner}/{repo} exceeds "
                                f"the {MAX_REPO_ARCHIVE_BYTES} byte limit.",
                                413,
                            )

                        archive.write(chunk)
        except requests.HTTPError as exc:
            message, status_code = _github_error(exc, owner, repo)
            raise RepositoryDownloadError(message, status_code) from exc
        except requests.RequestException as exc:
            raise RepositoryDownloadError(
                f"Could not download {owner}/{repo} from GitHub: {exc}"
            ) from exc

        extract_root = os.path.join(tmp_dir, "checkout")
        os.makedirs(extract_root, exist_ok=True)

        try:
            with tarfile.open(archive_path, "r:gz") as archive:
                archive.extractall(extract_root, filter="data")
        except (tarfile.TarError, OSError) as exc:
            raise RepositoryDownloadError(
                f"Could not extract the archive for {owner}/{repo}."
            ) from exc

        yield _find_repository_root(extract_root)


if __name__ == "__main__":
    get_installation_id()
