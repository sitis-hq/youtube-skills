#!/usr/bin/env python3
"""Call the DataForSEO API once and save the response body exactly as it came.

  dfs.py post /v3/serp/youtube/organic/live/advanced --data '{"keyword": "...", ...}' --out serp-x.json
  dfs.py post /v3/dataforseo_labs/google/keyword_overview/live --data-file body.json --out labs.json
  dfs.py get  /v3/keywords_data/google_trends/explore/tasks_ready --out ready.json

Why a script and not each step's own client: every step that measures demand needs the same four
things, and a client written inside a run gets some of them wrong:

  - the documented full response, never the trimmed `.ai` shape the MCP server returns by default
    (the other scripts here read only the full one);
  - the body saved to a file untouched, so numbers are read by scripts, never retyped;
  - one task per Live call (DataForSEO drops the rest of a Live POST);
  - the error codes told apart: a top-level code other than 20000 failed the whole call, a task's
    own code failed that task alone.

Credentials are the project's secret credentials DATAFORSEO_LOGIN (DATAFORSEO_USERNAME is read as
an alias, like the MCP server does) and DATAFORSEO_PASSWORD, from the run's environment. They are
never printed. When they are missing the script refuses and names them: the step declares them and
the run asks the owner.

`--data` takes one task object or a list of them; one object is wrapped in a list. The output file
must not exist yet unless --overwrite: a saved response is evidence of what was measured on a day.

Prints {"ok": true, "out", "status_code", "cost", "tasks": [{"id", "status_code", "status_message",
"result_count"}]}. A refusal or a failed call exits 2 with {"ok": false, "error"}; the body of a
failed call is still saved when it came back. Standard library only: Python 3.11.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from ytskills.common import Refusal, run  # noqa: E402

API_BASE = "https://api.dataforseo.com"
TIMEOUT_SECONDS = 180


def credentials() -> tuple[str, str]:
    login = os.environ.get("DATAFORSEO_LOGIN") or os.environ.get("DATAFORSEO_USERNAME")
    password = os.environ.get("DATAFORSEO_PASSWORD")
    missing = [name for name, value in (("DATAFORSEO_LOGIN", login), ("DATAFORSEO_PASSWORD", password))
               if not value]
    if missing:
        raise Refusal(f"missing credential(s) {', '.join(missing)}: the step must declare them; they are the "
                      "API login and password from app.dataforseo.com/api-access, not the account password")
    return login, password  # type: ignore[return-value]


def check_path(path: str) -> str:
    if not path.startswith("/v3/"):
        raise Refusal(f"path must start with /v3/, got {path!r}")
    if path.rstrip("/").endswith(".ai"):
        raise Refusal("the .ai shape is trimmed and undocumented; call the path without .ai")
    return path


def tasks_body(data: str | None, data_file: str | None, path: str) -> list[dict[str, Any]]:
    if (data is None) == (data_file is None):
        raise Refusal("post needs exactly one of --data or --data-file")
    try:
        text = data if data is not None else Path(data_file).read_text(encoding="utf-8")  # type: ignore[arg-type]
        body = json.loads(text)
    except json.JSONDecodeError as e:
        raise Refusal(f"the request body is not JSON: {e}") from None
    except OSError as e:
        raise Refusal(f"cannot read --data-file: {e}") from None
    tasks = [body] if isinstance(body, dict) else body
    if not isinstance(tasks, list) or not tasks or not all(isinstance(t, dict) for t in tasks):
        raise Refusal("the request body must be a task object or a non-empty list of task objects")
    if "/live" in path and len(tasks) > 1:
        raise Refusal(f"a Live endpoint takes one task per call, got {len(tasks)}; make one call per task")
    return tasks


def call(method: str, path: str, tasks: list[dict[str, Any]] | None) -> tuple[int, bytes]:
    login, password = credentials()
    token = base64.b64encode(f"{login}:{password}".encode()).decode()
    req = urllib.request.Request(
        API_BASE + path, method=method,
        data=json.dumps(tasks).encode() if tasks is not None else None,
        headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except (urllib.error.URLError, TimeoutError) as e:
        raise Refusal(f"DataForSEO did not answer: {e}") from None


def summary(doc: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for task in doc.get("tasks") or []:
        result = task.get("result")
        out.append({"id": task.get("id"), "status_code": task.get("status_code"),
                    "status_message": task.get("status_message"),
                    "result_count": len(result) if isinstance(result, list) else 0})
    return out


def main_run(argv: list[str] | None) -> dict[str, Any]:
    p = argparse.ArgumentParser(description="Call DataForSEO once and save the response as it came.")
    p.add_argument("method", choices=["post", "get"])
    p.add_argument("path", help="API path, e.g. /v3/serp/youtube/organic/live/advanced")
    p.add_argument("--data", help="the task object, or a list of them, as JSON (post)")
    p.add_argument("--data-file", help="a file holding the task object or list (post)")
    p.add_argument("--out", required=True, help="where the response body is saved, exactly as it came")
    p.add_argument("--overwrite", action="store_true", help="replace an existing --out file")
    a = p.parse_args(argv)
    path = check_path(a.path)
    out = Path(a.out)
    if out.exists() and not a.overwrite:
        raise Refusal(f"{out} exists; a saved response is not replaced without --overwrite")
    if a.method == "get" and (a.data is not None or a.data_file is not None):
        raise Refusal("get takes no request body")
    tasks = tasks_body(a.data, a.data_file, path) if a.method == "post" else None

    http_status, body = call(a.method.upper(), path, tasks)
    if body:
        try:
            out.write_bytes(body)
        except OSError as e:
            raise Refusal(f"cannot save the response to {out}: {e}") from None
    try:
        doc = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise Refusal(f"HTTP {http_status}: the answer is not JSON (saved to {out if body else 'nowhere'})") from None
    if not isinstance(doc, dict):
        raise Refusal(f"HTTP {http_status}: unexpected answer shape (saved to {out})")
    code = doc.get("status_code")
    if code != 20000:
        # 40100 unauthorised, 40200 balance empty, 40202 rate limit: nothing in this call was measured.
        raise Refusal(f"DataForSEO error {code}: {doc.get('status_message')} (HTTP {http_status}; body saved to {out})")
    tasks_out = summary(doc)
    return {"ok": True, "out": str(out), "status_code": code, "cost": doc.get("cost"), "tasks": tasks_out,
            "failed_tasks": sum(1 for t in tasks_out if t["status_code"] != 20000)}


def main(argv: list[str] | None = None) -> int:
    return run(main_run, argv)


if __name__ == "__main__":
    sys.exit(main())
