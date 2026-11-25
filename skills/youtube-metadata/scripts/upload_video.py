#!/usr/bin/env python3
"""Upload a video file to the channel through the Data API, once, resumable across runs.

  upload_video.py start --file mix.mp4 --meta meta.json
      Claims the upload's intent (key upload:video:<digest of the file>, the same key
      `intent.py key upload --file` gives) and opens a resumable upload session. No byte of the
      video is sent. Prints {"session_uri", "size", "key"}: STORE the session uri where the next
      run finds it (the recipe's own record) BEFORE `send`. A refused or failed session start
      creates no video, so it fails the intent and a later run may start again.

  upload_video.py send --file mix.mp4 --session <session uri>
      First asks YouTube how much of the file the session holds (an empty PUT with
      Content-Range bytes */<size>): all of it → the upload already finished, take the video id;
      part of it → send the rest; the session is gone (404/410) → outcome unknown. Then sends the
      file in 64 MiB pieces, asking again after a lost answer or a 5xx. A finished upload commits the
      intent with the video id. Asking a session what it holds is a check, not a second upload, so
      resuming an open claim this way keeps the at-most-once rule (CONTRACT.md, rule 7).

meta.json (snippet and status of videos.insert):
  {"title": "…", "description": "…", "tags": ["…"], "categoryId": "10",
   "defaultLanguage": "en", "defaultAudioLanguage": "en",
   "publishAt": "2026-12-05T15:00:00Z",          # private until then; omit with "privacy" to set it
   "privacy": "private",                          # private (default with publishAt), unlisted, public
   "selfDeclaredMadeForKids": false,              # required: YouTube asks every upload
   "containsSyntheticMedia": false}               # optional: the altered or synthetic content label

Checks before the claim: title 1–100 characters without < or >, description at most 5000 bytes
without < or >, tags at most 500 characters together, publishAt in the future and only with
privacy private, the file readable and a video.

Data API v3 reference read 2026-11-25:
  https://developers.google.com/youtube/v3/docs/videos/insert — POST
    /upload/youtube/v3/videos?uploadType=resumable&part=snippet,status; status.publishAt needs
    privacyStatus private; selfDeclaredMadeForKids and containsSyntheticMedia are status fields.
  https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol — the session
    URI is the Location header of the start; 308 Resume Incomplete with a Range header while
    incomplete; 200/201 with the video resource when done; a status request is a PUT with an
    empty body and Content-Range: bytes */<size>; pieces are multiples of 256 KiB.
  Uploads longer than 15 minutes need a channel whose status.longUploadsStatus is allowed
  (youtube-data: data_api.py channels --mine says it as long_uploads).

All output is JSON on stdout; a refusal exits 2 with {"ok": false, ...}. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SETUP_SCRIPTS = HERE.parents[1] / "youtube-channel-setup" / "scripts"
sys.path.insert(0, str(SETUP_SCRIPTS))
try:
    import apply_channel as ac  # noqa: E402 — the set's one token and intent client
except ImportError:  # pragma: no cover
    print(json.dumps({"ok": False, "error": f"youtube-channel-setup's apply_channel.py is missing at {SETUP_SCRIPTS}"}))
    sys.exit(2)

intent = ac.intent
Refusal = ac.Refusal
START = "https://www.googleapis.com/upload/youtube/v3/videos"
PIECE = 64 * 1024 * 1024  # a multiple of 256 KiB, as the protocol requires
CHECKS_AFTER_LOSS = (5, 30, 120)  # seconds before asking the session again; tests replace SLEEP
SLEEP = time.sleep
# videos.insert: 1 unit of its own "Video Uploads" bucket, 100 uploads a day — not the 10 000
# units the reads share (determine_quota_cost, read 2026-11-25).
UPLOAD_UNITS = 1
SAY_UNCERTAIN = ("Outcome unknown — do not upload again. Check the channel's videos in Studio and tell "
                 "the owner; a later run asks the stored session first.")


# ── the network, behind one function the tests replace ──────────────────────────────────────────


def http(method: str, url: str, headers: dict[str, str], body: bytes | None) -> tuple[int, dict[str, str], bytes]:
    """Status, headers (lower-case names) and body. A lost answer raises ac.ApiError(None, …)."""
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ac.ApiError(None, "network", str(e)) from None


def _token(connection: str) -> str:
    return ac.access_token(connection)


# ── checks ──────────────────────────────────────────────────────────────────────────────────────


def check_file(path: str) -> int:
    p = Path(path)
    if not p.is_file():
        raise Refusal(f"no such file: {path}")
    size = p.stat().st_size
    if size == 0:
        raise Refusal(f"{path} is empty")
    with p.open("rb") as fh:
        head = fh.read(12)
    if head[4:8] != b"ftyp":
        raise Refusal(f"{path} is not an MP4/MOV video (no ftyp box)")
    return size


def load_meta(path: str) -> dict[str, Any]:
    try:
        meta = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise Refusal(f"cannot read {path}: {e}") from None
    if not isinstance(meta, dict):
        raise Refusal(f"{path} must hold a JSON object")
    title, desc = str(meta.get("title") or ""), str(meta.get("description") or "")
    problems = []
    if not 1 <= len(title) <= 100:
        problems.append("title must be 1–100 characters")
    if len(desc.encode("utf-8")) > 5000:
        problems.append("description is over 5000 bytes")
    if any(c in title + desc for c in "<>"):
        problems.append("title and description may not contain < or >")
    tags = meta.get("tags") or []
    if not isinstance(tags, list) or sum(len(str(t)) + (2 if " " in str(t) else 0) for t in tags) + max(len(tags) - 1, 0) > 500:
        problems.append("tags must be a list of at most 500 characters together")
    if not isinstance(meta.get("selfDeclaredMadeForKids"), bool):
        problems.append("selfDeclaredMadeForKids must be true or false (YouTube asks every upload)")
    if "containsSyntheticMedia" in meta and not isinstance(meta["containsSyntheticMedia"], bool):
        problems.append("containsSyntheticMedia must be true or false")
    privacy = meta.get("privacy") or ("private" if meta.get("publishAt") else None)
    if privacy not in ("private", "unlisted", "public"):
        problems.append("set publishAt, or privacy to private, unlisted or public")
    if meta.get("publishAt"):
        try:
            at = datetime.fromisoformat(str(meta["publishAt"]).replace("Z", "+00:00"))
            if at.tzinfo is None or at <= datetime.now(timezone.utc):
                problems.append("publishAt must be in the future and carry a time zone")
        except ValueError:
            problems.append(f"publishAt is not an ISO date-time: {meta['publishAt']!r}")
        if privacy != "private":
            problems.append("publishAt works only with privacy private")
    if problems:
        raise Refusal(f"{path}: " + "; ".join(problems))
    meta["privacy"] = privacy
    return meta


def resource(meta: dict[str, Any]) -> dict[str, Any]:
    snippet = {"title": meta["title"], "description": meta.get("description", ""),
               "tags": meta.get("tags") or [], "categoryId": str(meta.get("categoryId") or "10")}
    for k in ("defaultLanguage", "defaultAudioLanguage"):
        if meta.get(k):
            snippet[k] = meta[k]
    status: dict[str, Any] = {"privacyStatus": meta["privacy"],
                              "selfDeclaredMadeForKids": meta["selfDeclaredMadeForKids"]}
    if meta.get("publishAt"):
        status["publishAt"] = meta["publishAt"]
    if "containsSyntheticMedia" in meta:
        status["containsSyntheticMedia"] = meta["containsSyntheticMedia"]
    return {"snippet": snippet, "status": status}


def _error(status: int, raw: bytes) -> ac.ApiError:
    try:
        err = json.loads(raw).get("error", {})
    except (json.JSONDecodeError, ValueError, AttributeError):
        err = {}
    reason = (err.get("errors") or [{}])[0].get("reason") or err.get("status") or "error"
    return ac.ApiError(status, reason, err.get("message") or raw[:200].decode("utf-8", "replace"))


# ── start ───────────────────────────────────────────────────────────────────────────────────────


def start(connection: str, ids_fn, file: str, meta_path: str) -> dict[str, Any]:
    size = check_file(file)
    meta = load_meta(meta_path)
    key = intent.build_key("upload", file=file)
    ids = ids_fn()
    claimed = intent.claim(key, ids)
    if not claimed["act"]:
        out = {"ok": claimed.get("status") == "committed", "key": key, "acted": False, "claim": claimed}
        if claimed.get("status") == "claimed":
            out["say"] = ("The upload was started earlier. If its session uri was stored, run `send` with it; "
                          "if none was stored, the outcome is unknown: " + SAY_UNCERTAIN)
        else:
            out["say"] = claimed["say"]
        return out
    body = json.dumps(resource(meta)).encode("utf-8")
    headers = {"Authorization": f"Bearer {_token(connection)}", "Content-Type": "application/json; charset=UTF-8",
               "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": "video/mp4"}
    url = START + "?" + urllib.parse.urlencode({"uploadType": "resumable", "part": "snippet,status"})
    try:
        status, hdrs, raw = http("POST", url, headers, body)
    except ac.ApiError as e:
        # A session that was never opened holds no bytes, and a video exists only once all bytes
        # arrive: a failed start certainly uploaded nothing.
        intent.fail(key, ids, f"the upload session did not open: {e}")
        return {"ok": False, "key": key, "intent": "failed", "error": str(e)}
    if status != 200 or not hdrs.get("location"):
        e = _error(status, raw)
        intent.fail(key, ids, f"the upload session did not open: {e}")
        out = {"ok": False, "key": key, "intent": "failed", "error": str(e)}
        if e.scope_missing:
            out["say"] = "The connection lacks the upload scope: reconnect YouTube with youtube.upload."
        return out
    return {"ok": True, "key": key, "acted": True, "session_uri": hdrs["location"], "size": size,
            "say": "Session open, nothing sent. Store session_uri now, then run send."}


# ── send ────────────────────────────────────────────────────────────────────────────────────────


def _held(hdrs: dict[str, str]) -> int:
    """Bytes the session holds, from a 308's Range header ('bytes=0-N'); none → 0."""
    rng = hdrs.get("range")
    if not rng:
        return 0
    try:
        return int(rng.split("-")[-1]) + 1
    except ValueError:
        raise Refusal(f"the session answered an unreadable Range: {rng!r}") from None


def _ask(session: str, size: int, token: str) -> tuple[str, Any]:
    status, hdrs, raw = http("PUT", session, {"Authorization": f"Bearer {token}", "Content-Length": "0",
                                              "Content-Range": f"bytes */{size}"}, b"")
    if status in (200, 201):
        return "done", json.loads(raw)
    if status == 308:
        return "partial", _held(hdrs)
    if status in (404, 410):
        return "gone", None
    raise _error(status, raw)


def send(connection: str, ids_fn, file: str, session: str) -> dict[str, Any]:
    size = check_file(file)
    key = intent.build_key("upload", file=file)
    ids = ids_fn()
    if not session.startswith("https://"):
        raise Refusal("--session must be the https session uri that start printed")
    token = _token(connection)
    sent_from = None
    troubles = 0

    def uncertain(error: str) -> dict[str, Any]:
        return {"ok": False, "key": key, "intent": "claimed", "uncertain": True, "error": error, "say": SAY_UNCERTAIN}

    while True:
        # Every failure — a lost answer, a 5xx, a refreshed token — is followed by asking the session
        # again, and all of them together are bounded: a session that keeps failing is reported.
        if troubles > len(CHECKS_AFTER_LOSS):
            return uncertain("the session kept failing; last state unknown")
        try:
            state, value = _ask(session, size, token)
        except ac.ApiError as e:
            if e.status == 401:
                token, troubles = _token(connection), troubles + 1
                continue
            if e.status is None or e.status >= 500:
                SLEEP(CHECKS_AFTER_LOSS[min(troubles, len(CHECKS_AFTER_LOSS) - 1)])
                troubles += 1
                continue
            return uncertain(str(e))
        if state == "done":
            video_id = value.get("id")
            if not video_id:
                return uncertain("the finished upload answered without a video id")
            try:
                intent.commit(key, ids, {"video_id": video_id})
            except (Refusal, intent.Refusal):
                # Already committed by an earlier send of the same session: the upload stands once.
                pass
            return {"ok": True, "key": key, "video_id": video_id, "size": size, "resumed_at": sent_from,
                    "upload_units_used": UPLOAD_UNITS, "privacy": (value.get("status") or {}).get("privacyStatus"),
                    "publish_at": (value.get("status") or {}).get("publishAt"),
                    "say": "Uploaded. YouTube processes it next; set the thumbnail with apply_video.py thumbnail."}
        if state == "gone":
            return uncertain("the upload session is gone (404/410): it expired or was cancelled")
        offset = value
        if sent_from is None:
            sent_from = offset
        end = min(offset + PIECE, size) - 1
        with open(file, "rb") as fh:
            fh.seek(offset)
            piece = fh.read(end - offset + 1)
        try:
            status, hdrs, raw = http("PUT", session, {"Authorization": f"Bearer {token}",
                                                      "Content-Length": str(len(piece)),
                                                      "Content-Range": f"bytes {offset}-{end}/{size}"}, piece)
        except ac.ApiError:
            SLEEP(CHECKS_AFTER_LOSS[min(troubles, len(CHECKS_AFTER_LOSS) - 1)])
            troubles += 1
            continue  # the next round asks the session what it holds
        if status in (200, 201, 308):
            troubles = 0
            continue  # the next round reads the state, so one rule handles every answer
        if status == 401:
            token, troubles = _token(connection), troubles + 1
            continue
        if status >= 500:
            SLEEP(CHECKS_AFTER_LOSS[min(troubles, len(CHECKS_AFTER_LOSS) - 1)])
            troubles += 1
            continue
        return uncertain(str(_error(status, raw)))


# ── entry ───────────────────────────────────────────────────────────────────────────────────────


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="upload_video.py", description=__doc__.split("\n\n")[0])
    p.add_argument("--connection", default=os.environ.get("YOUTUBE_CONNECTION", "YOUTUBE"))
    p.add_argument("--spec-template-id")
    p.add_argument("--project-id")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("start", help="claim the upload and open a session; sends nothing")
    s.add_argument("--file", required=True)
    s.add_argument("--meta", required=True, help="snippet and status as JSON (see the module docstring)")
    d = sub.add_parser("send", help="send the file through a stored session, resuming where it stopped")
    d.add_argument("--file", required=True)
    d.add_argument("--session", required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    a = parser().parse_args(argv)

    def ids_fn() -> dict[str, str]:
        return intent.run_ids(a.spec_template_id, a.project_id)

    try:
        out = start(a.connection, ids_fn, a.file, a.meta) if a.command == "start" else \
            send(a.connection, ids_fn, a.file, a.session)
    except (Refusal, intent.Refusal) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
