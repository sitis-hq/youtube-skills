#!/usr/bin/env python3
"""Fresh comments for triage, and the API actions on them behind an intent reservation.

  comments.py fetch --channel-id UC... --since 2026-11-03 [--handled-file handled.json]
      New comment threads on the channel's videos since a day (newest first), minus what the
      channel already handled: comments in `replied` records, the channel's own comments, and
      threads the channel has already answered by hand. Prints a triage-ready list.

  comments.py reply --comment-id ID --video-id ID --text-file reply.txt
      Post a reply with the Data API (comments.insert) under the intent key reply:comment:<id>:
      claim → insert → commit, so a repeated run cannot reply twice. Prints the fields of the
      `replied` record to write next.

  comments.py hide --comment-id ID --video-id ID
      Reject a comment (comments.setModerationStatus, rejected) under hide:comment:<id>. Rejection
      cannot be undone: YouTube does not move a rejected comment back to published.

All output is JSON on stdout; a refusal exits 2 with {"ok": false, "error": ...}. A failure that
the Data API cannot get past (a missing scope) carries "fallback": "studio" and names the playbook.

The access token comes from `ai-integration oauth-token` at the moment of use and is never printed
or written. Quota (Data API v3 reference, read 2026-11-04): commentThreads.list and comments.list
1 unit a page; comments.insert and comments.setModerationStatus 50 units each.

Standard library only: Python 3.11. The intent helper is youtube-studio's scripts/intent.py.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
STUDIO_SCRIPTS = HERE.parents[1] / "youtube-studio" / "scripts"
sys.path.insert(0, str(STUDIO_SCRIPTS))
try:
    import intent  # noqa: E402
except ImportError:  # pragma: no cover - only when the tree is incomplete
    print(json.dumps({"ok": False, "error": f"youtube-studio's intent.py is missing at {STUDIO_SCRIPTS}"}))
    sys.exit(2)

API = "https://www.googleapis.com/youtube/v3/"
COST = {"commentThreads.list": 1, "comments.list": 1, "comments.insert": 50, "comments.setModerationStatus": 50}
STUDIO_PLAYBOOK = "youtube-studio/references/comment-actions.md"


class Refusal(Exception):
    pass


class ApiError(Exception):
    """A Data API answer other than success. status None means the request may not have arrived
    or its answer was lost — the action's outcome is unknown."""

    def __init__(self, status: int | None, reason: str, message: str):
        super().__init__(f"{status or 'no answer'} {reason}: {message}")
        self.status, self.reason, self.message = status, reason, message

    @property
    def certain_not_done(self) -> bool:
        # A 4xx answer is YouTube refusing the request: nothing was created. A 5xx or a lost answer
        # may hide a success, so the claim stays as it is (at-most-once).
        return self.status is not None and 400 <= self.status < 500

    @property
    def scope_missing(self) -> bool:
        return self.status in (401, 403) and self.reason in (
            "insufficientPermissions", "ACCESS_TOKEN_SCOPE_INSUFFICIENT", "forbidden", "authError")


# ── the network, behind two functions the tests replace ─────────────────────────────────────────


def access_token(connection: str) -> str:
    cmd = [os.environ.get("AI_INTEGRATION_BIN", "ai-integration"), "oauth-token",
           "--connection", connection, "--field", "accessToken"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise Refusal(f"{cmd[0]} is not on PATH — this works only inside a Sitis run") from None
    token = proc.stdout.strip()
    if proc.returncode != 0 or not token or token.startswith("{"):
        # The verb prints its error as JSON; pass its message on, never the token.
        try:
            msg = json.loads(token).get("error", {}).get("message", "")
        except (json.JSONDecodeError, AttributeError):
            msg = proc.stderr.strip()[:300]
        raise Refusal(f"no access token for connection {connection}: {msg or 'empty answer'}")
    return token


def http(method: str, endpoint: str, params: dict[str, Any], body: dict[str, Any] | None,
         token: str) -> dict[str, Any]:
    url = API + endpoint + "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read()).get("error", {})
        except (json.JSONDecodeError, ValueError):
            err = {}
        reason = (err.get("errors") or [{}])[0].get("reason") or err.get("status") or "error"
        raise ApiError(e.code, reason, err.get("message") or str(e)) from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ApiError(None, "network", str(e)) from None


class Client:
    def __init__(self, connection: str):
        self.connection = connection
        self.token: str | None = None
        self.units = 0

    def call(self, name: str, method: str, endpoint: str, params: dict[str, Any],
             body: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.token is None:
            self.token = access_token(self.connection)
        # Counted before the call: a refused request still spends its quota.
        self.units += COST[name]
        return http(method, endpoint, params, body, self.token)


# ── fetch ──────────────────────────────────────────────────────────────────────────────────────


def handled_ids(raw: Any) -> set[str]:
    """Comment ids from what the step read back: `replied:<id>:<action>` keys, records, or bare ids.
    Any action counts: a comment the channel answered, hid or reported is handled."""
    if isinstance(raw, dict):
        raw = raw.get("records") or raw.get("items") or raw.get("keys") or []
    if not isinstance(raw, list):
        raise Refusal("the handled file must hold a JSON list of replied keys")
    out = set()
    for item in raw:
        key = item.get("key") if isinstance(item, dict) else item
        if not isinstance(key, str):
            continue
        out.add(key.split(":")[1] if key.startswith("replied:") else key)
    return out


def _parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _item(c: dict[str, Any], video_id: str, thread_id: str, parent: str | None,
          reply_count: int | None) -> dict[str, Any]:
    s = c["snippet"]
    item = {
        "comment_id": c["id"],
        "thread_id": thread_id,
        "parent_id": parent,
        "is_reply": parent is not None,
        "video_id": video_id,
        "author": s.get("authorDisplayName"),
        "author_channel_id": (s.get("authorChannelId") or {}).get("value"),
        "text": s.get("textOriginal") or s.get("textDisplay") or "",
        "published_at": s.get("publishedAt"),
        "likes": s.get("likeCount", 0),
        "moderation_status": s.get("moderationStatus", "published"),
    }
    if reply_count is not None:
        item["reply_count"] = reply_count
    return item


def fetch(client: Client, channel_id: str, since: str, handled: set[str], max_pages: int,
          statuses: list[str], full_replies: bool) -> dict[str, Any]:
    since_at = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
    items: list[dict[str, Any]] = []
    dropped = {"handled": 0, "own": 0, "answered_by_channel": 0}
    truncated = False
    for status in statuses:
        token: str | None = None
        pages = 0
        reached_since = False
        while not reached_since:
            if pages >= max_pages:
                truncated = True
                break
            params = {"part": "snippet,replies", "allThreadsRelatedToChannelId": channel_id,
                      "maxResults": 100, "order": "time", "textFormat": "plainText",
                      "moderationStatus": status}
            if token:
                params["pageToken"] = token
            page = client.call("commentThreads.list", "GET", "commentThreads", params)
            pages += 1
            for thread in page.get("items", []):
                ts = thread["snippet"]
                top = ts["topLevelComment"]
                if _parse_time(top["snippet"]["publishedAt"]) < since_at:
                    # order=time: every later thread is older still.
                    reached_since = True
                    break
                video_id = ts.get("videoId") or top["snippet"].get("videoId")
                if not video_id:
                    continue  # a channel-level discussion, not a video comment
                replies = (thread.get("replies") or {}).get("comments", [])
                total = ts.get("totalReplyCount", 0)
                if full_replies and total > len(replies):
                    replies = list_replies(client, top["id"])
                own_replies = [r for r in replies
                               if (r["snippet"].get("authorChannelId") or {}).get("value") == channel_id]
                last_own = max((_parse_time(r["snippet"]["publishedAt"]) for r in own_replies), default=None)
                author = (top["snippet"].get("authorChannelId") or {}).get("value")
                if author == channel_id:
                    dropped["own"] += 1
                elif top["id"] in handled:
                    dropped["handled"] += 1
                elif last_own is not None:
                    # The owner answered by hand (or a record was lost): replying again doubles it.
                    dropped["answered_by_channel"] += 1
                else:
                    items.append(_item(top, video_id, thread["id"], None, total))
                for r in replies:
                    rs = r["snippet"]
                    at = _parse_time(rs["publishedAt"])
                    if (rs.get("authorChannelId") or {}).get("value") == channel_id:
                        continue
                    if at < since_at or r["id"] in handled:
                        continue
                    if last_own is not None and at <= last_own:
                        # Before the channel's last word in this thread: already part of what it answered.
                        dropped["answered_by_channel"] += 1
                        continue
                    items.append(_item(r, video_id, thread["id"], top["id"], None))
            token = page.get("nextPageToken")
            if not token:
                break
    items.sort(key=lambda i: i["published_at"] or "", reverse=True)
    return {"ok": True, "channel_id": channel_id, "since": since, "count": len(items),
            "dropped": dropped, "truncated": truncated, "units_used": client.units, "items": items}


def list_replies(client: Client, parent_id: str, max_pages: int = 5) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    token = None
    for _ in range(max_pages):
        params = {"part": "snippet", "parentId": parent_id, "maxResults": 100, "textFormat": "plainText"}
        if token:
            params["pageToken"] = token
        page = client.call("comments.list", "GET", "comments", params)
        out.extend(page.get("items", []))
        token = page.get("nextPageToken")
        if not token:
            break
    return out


# ── actions behind an intent ───────────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _api_failure(key: str, ids: dict[str, str], e: ApiError, client: Client) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False, "key": key, "error": str(e), "units_used": client.units}
    if e.certain_not_done:
        intent.fail(key, ids, f"Data API refused: {e}")
        out["intent"] = "failed"
        if e.scope_missing:
            out.update(fallback="studio", playbook=STUDIO_PLAYBOOK,
                       say="The connection cannot do this through the API; do it in Studio under a new claim.")
    else:
        # The request may have gone through: at-most-once leaves the claim in flight.
        out.update(intent="claimed", uncertain=True,
                   say="Outcome unknown — do not retry. Check the comment on YouTube and tell the owner.")
    return out


def reply(client: Client, ids: dict[str, str], comment_id: str, video_id: str, text: str) -> dict[str, Any]:
    if not text.strip():
        raise Refusal("the reply text is empty")
    key = intent.build_key("reply", comment_id=comment_id)
    claimed = intent.claim(key, ids)
    if not claimed["act"]:
        return {"ok": True, "key": key, "acted": False, "claim": claimed,
                "say": claimed["say"] + " If the replied record is missing, write it from claim.result."}
    # Replies are one level deep: a reply to a reply goes into the top-level comment's thread.
    parent = comment_id.split(".", 1)[0]
    try:
        made = client.call("comments.insert", "POST", "comments", {"part": "snippet"},
                           {"snippet": {"parentId": parent, "textOriginal": text}})
    except ApiError as e:
        return _api_failure(key, ids, e, client)
    reply_id = made.get("id")
    if not reply_id:
        # YouTube answered 2xx without the new comment: it may exist. Leave the claim in flight.
        return {"ok": False, "key": key, "intent": "claimed", "uncertain": True, "units_used": client.units,
                "error": "comments.insert answered without an id",
                "say": "Outcome unknown — do not retry. Check the comment on YouTube and tell the owner."}
    at = _now()
    intent.commit(key, ids, {"reply_id": reply_id, "at": at})
    record = {"comment_id": comment_id, "video_id": video_id, "action": "reply", "at": at,
              "reply_id": reply_id, "source": "community"}
    return {"ok": True, "key": key, "acted": True, "reply_id": reply_id, "units_used": client.units,
            "record": record, "say": "Write the replied record with these fields through records.py."}


def hide(client: Client, ids: dict[str, str], comment_id: str, video_id: str) -> dict[str, Any]:
    key = intent.build_key("hide", comment_id=comment_id)
    claimed = intent.claim(key, ids)
    if not claimed["act"]:
        return {"ok": True, "key": key, "acted": False, "claim": claimed}
    try:
        client.call("comments.setModerationStatus", "POST", "comments/setModerationStatus",
                    {"id": comment_id, "moderationStatus": "rejected"})
    except ApiError as e:
        return _api_failure(key, ids, e, client)
    at = _now()
    intent.commit(key, ids, {"at": at})
    record = {"comment_id": comment_id, "video_id": video_id, "action": "hide", "at": at, "source": "community"}
    return {"ok": True, "key": key, "acted": True, "units_used": client.units, "record": record}


# ── command line ───────────────────────────────────────────────────────────────────────────────


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="comments.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)

    f = sub.add_parser("fetch", help="fresh comments since a day, minus what was handled")
    f.add_argument("--channel-id", required=True, help="the channel (profile record's channel_id)")
    f.add_argument("--since", required=True, help="YYYY-MM-DD, UTC; overlap with the last run is harmless")
    f.add_argument("--handled-file", help="JSON list of replied:<commentId>:<action> keys the step read back")
    f.add_argument("--max-pages", type=int, default=10, help="page budget per status, 1 unit each (default 10)")
    f.add_argument("--include-held", action="store_true",
                   help="also read held-for-review and likely-spam threads (for hide/report triage)")
    f.add_argument("--full-replies", action="store_true",
                   help="read every reply of a thread with more than the inline ones (1 unit a page)")

    for name, help_text in (("reply", "post a reply through the Data API under an intent"),
                            ("hide", "reject a comment (irreversible) under an intent")):
        a = sub.add_parser(name, help=help_text)
        a.add_argument("--comment-id", required=True)
        a.add_argument("--video-id", required=True)
        if name == "reply":
            a.add_argument("--text-file", help="the reply text, UTF-8 (preferred: no shell quoting)")
            a.add_argument("--text", help="the reply text inline")
        a.add_argument("--spec-template-id", help="this run's Process id")
        a.add_argument("--project-id", help="this run's Project id")

    for sp in sub.choices.values():
        sp.add_argument("--connection", default="YOUTUBE", help="the OAuth connection name (default YOUTUBE)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    client = Client(args.connection)
    try:
        if args.command == "fetch":
            if not re.match(r"^UC[A-Za-z0-9_-]{22}$", args.channel_id):
                raise Refusal(f"--channel-id must be a UC… channel id, got {args.channel_id!r}")
            try:
                since = date.fromisoformat(args.since).isoformat()
            except ValueError:
                raise Refusal(f"--since must be YYYY-MM-DD, got {args.since!r}") from None
            handled: set[str] = set()
            if args.handled_file:
                try:
                    with open(args.handled_file, encoding="utf-8") as fh:
                        handled = handled_ids(json.load(fh))
                except OSError as e:
                    raise Refusal(f"cannot read {args.handled_file}: {e.strerror}") from None
                except json.JSONDecodeError as e:
                    raise Refusal(f"{args.handled_file} is not JSON: {e}") from None
            statuses = ["published"] + (["heldForReview", "likelySpam"] if args.include_held else [])
            try:
                out = fetch(client, args.channel_id, since, handled, max(1, args.max_pages), statuses,
                            args.full_replies)
            except ApiError as e:
                out = {"ok": False, "error": str(e), "units_used": client.units}
                if e.scope_missing:
                    out.update(fallback="studio", playbook=STUDIO_PLAYBOOK)
                print(json.dumps(out, ensure_ascii=False, indent=2))
                return 2
        else:
            if not re.match(r"^[A-Za-z0-9_-]{11}$", args.video_id):
                raise Refusal(f"--video-id must be an 11-character video id, got {args.video_id!r}")
            ids = intent.run_ids(args.spec_template_id, args.project_id)
            if args.command == "reply":
                text = args.text
                if args.text_file:
                    try:
                        text = Path(args.text_file).read_text(encoding="utf-8").strip()
                    except OSError as e:
                        raise Refusal(f"cannot read {args.text_file}: {e.strerror}") from None
                if text is None:
                    raise Refusal("reply needs --text-file (or --text)")
                out = reply(client, ids, args.comment_id, args.video_id, text)
            else:
                out = hide(client, ids, args.comment_id, args.video_id)
    except (Refusal, intent.Refusal) as e:
        print(json.dumps({"ok": False, "error": str(e), "units_used": client.units}, ensure_ascii=False))
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
