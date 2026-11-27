import base64
import http.client
import json
import urllib.parse
import urllib.request

from django.conf import settings

LANGUAGE_IDS = {"PYTHON": 71, "JAVA": 62, "C": 50}
ACCEPTED, TIME_LIMIT, COMPILE_ERROR = 3, 5, 6
RUNTIME_ERRORS = range(7, 13)
MAX_REPLY_BYTES = 1_000_000
CLIENT_NAME = "Codemm/1.0"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class Judge0Error(Exception):
    """Judge0 is switched off, unreachable or failed internally."""


def is_configured():
    return bool(settings.JUDGE0_URL)


def _check_url(url):
    """Student code only travels over HTTPS, except to a Judge0 on this computer."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" and not (parts.scheme == "http" and parts.hostname in LOCAL_HOSTS):
        raise Judge0Error("Code checking is misconfigured: JUDGE0_URL must use https.")


def _encode(text):
    return base64.b64encode(text.encode()).decode()


def _decode(text):
    return base64.b64decode(text).decode(errors="replace") if text else ""


def run(language, source_code, stdin, time_limit_ms):
    """Run code once and return {"status": id, "stdout": str, "error": str, "time_ms": int or None}."""
    if not is_configured():
        raise Judge0Error("Code checking isn't set up yet.")
    _check_url(settings.JUDGE0_URL)
    body = json.dumps({
        "language_id": LANGUAGE_IDS[language],
        "source_code": _encode(source_code),
        "stdin": _encode(stdin),
        "cpu_time_limit": time_limit_ms / 1000,
    }).encode()
    request = urllib.request.Request(
        f"{settings.JUDGE0_URL}/submissions?base64_encoded=true&wait=true",
        data=body, headers={"Content-Type": "application/json", "User-Agent": CLIENT_NAME}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read(MAX_REPLY_BYTES + 1)
    except (OSError, http.client.HTTPException) as error:
        raise Judge0Error("The code checker couldn't be reached. Try again in a minute.") from error
    if len(raw) > MAX_REPLY_BYTES:
        raise Judge0Error("The program printed too much output.")
    try:
        data = json.loads(raw)
        status = (data.get("status") or {}).get("id")
        if status not in (ACCEPTED, TIME_LIMIT, COMPILE_ERROR, *RUNTIME_ERRORS):
            raise ValueError("Unexpected checker status")
        time = data.get("time")
        return {
            "status": status,
            "stdout": _decode(data.get("stdout")),
            "error": _decode(data.get("compile_output")) or _decode(data.get("stderr")),
            "time_ms": round(float(time) * 1000) if time else None,
        }
    except (ValueError, TypeError, AttributeError, OverflowError) as error:
        raise Judge0Error("The code checker had a problem. Try again in a minute.") from error
