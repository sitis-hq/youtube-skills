"""Authorised HTTP to Google's YouTube APIs, the access token, and quota accounting.

Not a command: the scripts of this skill import it. Standard library only, so a step needs no
library attachment to read the APIs.

The token comes from `ai-integration oauth-token --connection YOUTUBE` at the moment of use and
lives only in this process's memory. It is never printed, logged or written to a file, and no error
message here carries a request header.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from ytskills.common import Refusal, note  # noqa: E402

DATA_API = "https://www.googleapis.com/youtube/v3/"
ANALYTICS_API = "https://youtubeanalytics.googleapis.com/v2/reports"
REPORTING_API = "https://youtubereporting.googleapis.com/v1/"

# Data API v3 cost in quota units per call, from
# https://developers.google.com/youtube/v3/determine_quota_cost (read 2026-11-04).
# The default project quota is 10,000 units a day. The Analytics and Reporting APIs do not draw on it.
UNITS = {"videos": 1, "channels": 1, "playlistItems": 1, "search": 100, "commentThreads": 1}


def run_command(argv: list[str]) -> tuple[int, str, str]:
    """The one place a subprocess is started for the token; tests replace it."""
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        raise Refusal(f"{argv[0]} is not on PATH: these scripts run inside a Sitis run, "
                      "where the worker provides it") from None
    return proc.returncode, proc.stdout, proc.stderr


def access_token(min_ttl: int = 300) -> str:
    argv = [os.environ.get("AI_INTEGRATION_BIN", "ai-integration"), "oauth-token",
            "--connection", "YOUTUBE", "--min-ttl", str(min_ttl)]
    code, out, err = run_command(argv)
    try:
        doc = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
    except json.JSONDecodeError:
        doc = {}
    data = doc.get("data") or {}
    if code == 0 and doc.get("success") and data.get("accessToken"):
        return data["accessToken"]
    error = doc.get("error") or {}
    message = error.get("message") or err.strip()[:300] or f"exit {code}"
    raise Refusal(f"no YouTube token: {message}. 'not given' means the recipe or step does not "
                  "declare YOUTUBE_REFRESH_TOKEN; 'not connected' or 'reconnect' means the owner "
                  "connects YouTube on the project's credentials page")


def http_request(method: str, url: str, headers: dict[str, str],
                 body: bytes | None = None) -> tuple[int, bytes]:
    """The one place the network is touched; tests replace it."""
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except urllib.error.URLError as e:
        raise Refusal(f"cannot reach {urllib.parse.urlsplit(url).netloc}: {e.reason}") from None


def _google_error(status: int, payload: bytes) -> tuple[str, str]:
    try:
        err = json.loads(payload).get("error", {})
    except (json.JSONDecodeError, AttributeError):
        return "", payload[:200].decode("utf-8", "replace")
    reasons = [e.get("reason", "") for e in err.get("errors", []) if isinstance(e, dict)]
    return (reasons[0] if reasons else str(err.get("status", ""))), str(err.get("message", ""))


class Client:
    """One run's view of the APIs: a token fetched once and renewed on 401, and the quota spent."""

    def __init__(self) -> None:
        self._token: str | None = None
        self.units = 0
        self.calls: dict[str, int] = {}

    def _auth(self, renew: bool = False) -> dict[str, str]:
        if self._token is None or renew:
            self._token = access_token()
        return {"Authorization": f"Bearer {self._token}"}

    def request(self, method: str, url: str, params: dict[str, Any] | None = None,
                body: Any = None, raw: bool = False) -> Any:
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            url = f"{url}?{urllib.parse.urlencode(clean, doseq=True)}"
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        status, payload = http_request(method, url, {**headers, **self._auth()}, data)
        if status == 401:
            status, payload = http_request(method, url, {**headers, **self._auth(renew=True)}, data)
        if status >= 400:
            reason, message = _google_error(status, payload)
            where = urllib.parse.urlsplit(url).path
            if reason in ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"):
                raise Refusal(f"{where}: {reason} — the API quota is spent; spent this run: "
                              f"{self.units} units. Data API quota resets at midnight Pacific time")
            if status == 403 and reason in ("insufficientPermissions", "ACCESS_TOKEN_SCOPE_INSUFFICIENT",
                                            "PERMISSION_DENIED", "forbidden"):
                raise Refusal(f"{where}: HTTP 403 {reason} — the connection lacks the scope this "
                              f"read needs ({message}); the owner reconnects YouTube with it")
            raise Refusal(f"{where}: HTTP {status} {reason} {message}".strip())
        if raw:
            return payload
        try:
            return json.loads(payload) if payload else {}
        except json.JSONDecodeError:
            raise Refusal(f"{urllib.parse.urlsplit(url).path}: the answer is not JSON") from None

    def data_api(self, resource: str, params: dict[str, Any]) -> dict[str, Any]:
        self._auth()  # no token, no call: nothing is spent and nothing should be counted
        units = UNITS.get(resource, 1)
        self.units += units
        self.calls[resource] = self.calls.get(resource, 0) + 1
        note(f"[quota] {resource}.list +{units} unit(s), {self.units} this run")
        return self.request("GET", DATA_API + resource, params)

    def quota(self) -> dict[str, Any]:
        return {"data_api_units": self.units, "calls": dict(self.calls),
                "note": "Data API units; the default daily quota is 10,000. Analytics and "
                        "Reporting API calls are not counted against it."}


def batches(items: list[str], size: int) -> list[list[str]]:
    return [items[i:i + size] for i in range(0, len(items), size)]
