import json
import os
import signal
import subprocess

from dotenv import load_dotenv

load_dotenv()

NOIR_BIN = os.getenv("NOIR_BIN", "noir")
NOIR_TIMEOUT = int(os.getenv("NOIR_TIMEOUT", "180"))
NOIR_VERSION_TIMEOUT = 10


class NoirError(Exception):
    """Base class for Noir integration errors."""


class NoirUnavailable(NoirError):
    """Raised when the Noir binary cannot be executed."""


class NoirTimeout(NoirError):
    """Raised when a Noir command exceeds the configured timeout."""


class NoirScanError(NoirError):
    """Raised when Noir returns an error or malformed output."""


def _truncate(text, limit=2000):
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def get_noir_version():
    try:
        process = subprocess.run(
            [NOIR_BIN, "version"],
            capture_output=True,
            text=True,
            timeout=NOIR_VERSION_TIMEOUT,
        )
    except FileNotFoundError as exc:
        raise NoirUnavailable(
            f"Noir binary not found at '{NOIR_BIN}'. Set NOIR_BIN to its path."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise NoirUnavailable(
            "Noir did not respond to 'noir version'."
        ) from exc

    if process.returncode != 0:
        detail = _truncate(process.stderr or process.stdout)
        raise NoirUnavailable(
            f"Noir is not available: {detail or 'unknown error'}"
        )

    version = process.stdout.strip() or process.stderr.strip()
    return {"version": version}


def run_noir_scan(repo_path, passive_scan=False):
    command = [
        NOIR_BIN,
        "scan",
        str(repo_path),
        "-f",
        "json",
        "--no-log",
        "--no-color",
        "--no-spinner",
    ]

    if passive_scan:
        command.append("-P")

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        raise NoirUnavailable(
            f"Noir binary not found at '{NOIR_BIN}'. Set NOIR_BIN to its path."
        ) from exc

    try:
        stdout, stderr = process.communicate(timeout=NOIR_TIMEOUT)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

        process.communicate()
        raise NoirTimeout(
            f"Noir scan exceeded the {NOIR_TIMEOUT}s timeout."
        ) from None

    if process.returncode != 0:
        detail = _truncate(stderr or stdout)
        raise NoirScanError(
            f"Noir scan failed with exit code {process.returncode}: "
            f"{detail or 'unknown error'}"
        )

    output = stdout.strip()
    if not output:
        detail = _truncate(stderr)
        raise NoirScanError(
            f"Noir produced no JSON output. {detail}".strip()
        )

    try:
        result = json.loads(output)
    except json.JSONDecodeError as exc:
        raise NoirScanError(
            "Noir produced output that was not valid JSON."
        ) from exc

    if not isinstance(result, dict) or "endpoints" not in result:
        raise NoirScanError(
            "Noir output did not contain an 'endpoints' field."
        )

    return result
