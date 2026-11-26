import base64
import json
import urllib.error
import urllib.request

from django.conf import settings

LANGUAGE_IDS = {"PYTHON": 71, "JAVA": 62, "C": 50}
ACCEPTED, TIME_LIMIT, COMPILE_ERROR = 3, 5, 6
RUNTIME_ERRORS = range(7, 13)


class Judge0Error(Exception):
    """Judge0 is switched off, unreachable or failed internally."""


def is_configured():
    return bool(settings.JUDGE0_URL)


def _encode(text):
    return base64.b64encode(text.encode()).decode()


def _decode(text):
    return base64.b64decode(text).decode(errors="replace") if text else ""


def run(language, source_code, stdin, time_limit_ms):
    """Run code once and return {"status": id, "stdout": str, "error": str, "time_ms": int or None}."""
    if not is_configured():
        raise Judge0Error("Code checking isn't set up yet.")
    body = json.dumps({
        "language_id": LANGUAGE_IDS[language],
        "source_code": _encode(source_code),
        "stdin": _encode(stdin),
        "cpu_time_limit": time_limit_ms / 1000,
    }).encode()
    request = urllib.request.Request(
        f"{settings.JUDGE0_URL}/submissions?base64_encoded=true&wait=true",
        data=body, headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        raise Judge0Error("The code checker couldn't be reached. Try again in a minute.") from error
    status = (data.get("status") or {}).get("id")
    if status not in (ACCEPTED, TIME_LIMIT, COMPILE_ERROR, *RUNTIME_ERRORS):
        raise Judge0Error("The code checker had a problem. Try again in a minute.")
    time = data.get("time")
    return {
        "status": status,
        "stdout": _decode(data.get("stdout")),
        "error": _decode(data.get("compile_output")) or _decode(data.get("stderr")),
        "time_ms": round(float(time) * 1000) if time else None,
    }
