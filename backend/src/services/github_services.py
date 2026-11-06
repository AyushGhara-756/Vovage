import os
import time
import jwt
import requests
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("GITHUB_APP_ID")
PRIVATE_KEY_PATH = os.getenv("GITHUB_PRIVATE_KEY_PATH")

with open(PRIVATE_KEY_PATH, "r") as file:
    PRIVATE_KEY = file.read()


def generate_jwt():
    now = int(time.time())

    payload = {
        "iat": now - 60,
        "exp": now + 600,
        "iss": APP_ID
    }

    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")


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

if __name__ == "__main__":
    get_installation_id()
