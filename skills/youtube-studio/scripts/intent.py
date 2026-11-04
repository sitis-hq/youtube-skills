#!/usr/bin/env python3
"""At-most-once guard for irreversible YouTube actions: a reply, a pin, a post, a settings change.

The agent is not deterministic and a run can be repeated, so the action itself is made idempotent:
before acting, the step claims an intent key in the recipe's memory; only a fresh claim may act;
after the action is verified the claim is committed, or failed when the action certainly did not
happen. The key comes from the INTENTION (which comment, which post, which video), never from the
run, so a repeated run meets the same key and skips.

Commands (JSON on stdout; a refusal exits 2 with {"ok": false, "error": ...}):

  intent.py key VERB --part value ...     the key for an intention (see `intent.py key --help`)
  intent.py claim  --key K                claim before acting; "act": true only on a fresh claim
  intent.py commit --key K [--result-file F | --result JSON]
                                          the action happened and was verified
  intent.py fail   --key K --reason TEXT  the action certainly did NOT happen; a later run may retry

claim/commit/fail need the run's ids: --spec-template-id and --project-id, or the "Process id" and
"Project id" lines of current-task.md in the working directory.

Wraps `ai-integration claim-intent / commit-intent / fail-intent` (see their --help). The claim lives in
the recipe's memory as the record `claim:<key>`, so no record kind may start with `claim:`.
Standard library only: Python 3.11.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date
from typing import Any, Callable

COMMENT_ID = r"[A-Za-z0-9_-]{10,}(?:\.[A-Za-z0-9_-]{10,})?"
VIDEO_ID = r"[A-Za-z0-9_-]{11}"
DATE = r"\d{4}-\d{2}-\d{2}"
SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
SHA = r"[0-9a-f]{12}"


class Refusal(Exception):
    """A value or an answer this helper does not accept; the message says which and why."""


# ── keys ───────────────────────────────────────────────────────────────────────────────────────


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not slug:
        raise Refusal(f"cannot make a key from {text!r}: it has no latin letters or digits")
    return slug[:60].rstrip("-")


def digest_file(path: str) -> str:
    # The content, not the file name, is the intention: the same banner uploaded under another name
    # is the same action, and a new design is a new one.
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:12]
    except OSError as e:
        raise Refusal(f"cannot read {path}: {e.strerror}") from None


def digest_state(path: str) -> str:
    # Canonical JSON, so key order and whitespace in the desired state do not make a new intention.
    # A file, because JSON on a command line loses its quotes in the shell layers of a run.
    try:
        with open(path, encoding="utf-8") as fh:
            value = json.load(fh)
    except OSError as e:
        raise Refusal(f"cannot read {path}: {e.strerror}") from None
    except json.JSONDecodeError as e:
        raise Refusal(f"the desired state in {path} is not JSON: {e}") from None
    canonical = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def _check(pattern: str, what: str) -> Callable[[str], str]:
    rx = re.compile(f"^{pattern}$")

    def parse(value: str) -> str:
        value = str(value).strip()
        if not rx.match(value):
            raise Refusal(f"{what} looks wrong: {value!r}")
        return value

    return parse


def _date(value: str) -> str:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError:
        raise Refusal(f"date must be YYYY-MM-DD, got {value!r}") from None


_comment = _check(COMMENT_ID, "comment id")
_video = _check(VIDEO_ID, "video id (11 characters)")
_part = _check("(banner|avatar|watermark)", "branding part (banner, avatar or watermark)")
_area = _check("(channel|upload-defaults|home-tab)", "settings area (channel, upload-defaults or home-tab)")

# Each verb: its parts (flag → parser), how the key is formed, and the pattern a stored key matches.
# A key that does not come from here is refused by claim/commit/fail: a hand-made key that differs
# by one character from yesterday's is a second action, and nothing else would notice.
VERBS: dict[str, dict[str, Any]] = {
    "reply": {"parts": {"comment_id": _comment}, "doc": "a reply to a comment",
              "make": lambda p: f"reply:comment:{p['comment_id']}",
              "pattern": f"reply:comment:{COMMENT_ID}"},
    "pin": {"parts": {"comment_id": _comment}, "doc": "pinning a comment (Studio)",
            "make": lambda p: f"pin:comment:{p['comment_id']}",
            "pattern": f"pin:comment:{COMMENT_ID}"},
    "heart": {"parts": {"comment_id": _comment}, "doc": "a creator heart on a comment (Studio)",
              "make": lambda p: f"heart:comment:{p['comment_id']}",
              "pattern": f"heart:comment:{COMMENT_ID}"},
    "hide": {"parts": {"comment_id": _comment}, "doc": "rejecting a comment (cannot be undone)",
             "make": lambda p: f"hide:comment:{p['comment_id']}",
             "pattern": f"hide:comment:{COMMENT_ID}"},
    "report": {"parts": {"comment_id": _comment}, "doc": "reporting a comment to YouTube (Studio)",
               "make": lambda p: f"report:comment:{p['comment_id']}",
               "pattern": f"report:comment:{COMMENT_ID}"},
    "post": {"parts": {"date": _date, "title": str}, "doc": "a community post or poll; title = its topic",
             "make": lambda p: f"post:community:{p['date']}:{slugify(p['title'])}",
             "pattern": f"post:community:{DATE}:{SLUG}"},
    "ab": {"parts": {"video_id": _video, "date": _date}, "doc": "starting a Studio A/B test on a video",
           "make": lambda p: f"ab:video:{p['video_id']}:{p['date']}",
           "pattern": f"ab:video:{VIDEO_ID}:{DATE}"},
    "thumbnail": {"parts": {"video_id": _video, "file": digest_file}, "doc": "setting a video's thumbnail",
                  "make": lambda p: f"thumbnail:video:{p['video_id']}:{p['file']}",
                  "pattern": f"thumbnail:video:{VIDEO_ID}:{SHA}"},
    "branding": {"parts": {"part": _part, "file": digest_file}, "doc": "uploading a banner, avatar or watermark",
                 "make": lambda p: f"branding:{p['part']}:{p['file']}",
                 "pattern": f"branding:(banner|avatar|watermark):{SHA}"},
    "settings": {"parts": {"area": _area, "state_file": digest_state},
                 "doc": "applying a desired state (JSON) to channel settings, upload defaults or the home tab",
                 "make": lambda p: f"settings:{p['area']}:{p['state_file']}",
                 "pattern": f"settings:(channel|upload-defaults|home-tab):{SHA}"},
    "metadata": {"parts": {"video_id": _video, "state_file": digest_state},
                 "doc": "changing a video's title, description or tags to a desired state (JSON)",
                 "make": lambda p: f"metadata:video:{p['video_id']}:{p['state_file']}",
                 "pattern": f"metadata:video:{VIDEO_ID}:{SHA}"},
}
KEY_PATTERNS = [re.compile(f"^{v['pattern']}$") for v in VERBS.values()]


def build_key(verb: str, **parts: str) -> str:
    if verb not in VERBS:
        raise Refusal(f"unknown verb {verb!r}; known: {', '.join(VERBS)}")
    spec = VERBS[verb]
    parsed = {}
    for name, parse in spec["parts"].items():
        if parts.get(name) in (None, ""):
            raise Refusal(f"the key of {verb} needs --{name.replace('_', '-')}")
        parsed[name] = parse(parts[name])
    return spec["make"](parsed)


def check_key(key: str) -> str:
    key = key.strip()
    if not any(p.match(key) for p in KEY_PATTERNS):
        raise Refusal(f"{key!r} is not a key this helper builds; get it from `intent.py key`")
    return key


# ── the platform ───────────────────────────────────────────────────────────────────────────────

ID_LINES = {
    "spec_template_id": re.compile(r"^Process id.*?`([0-9a-f-]{36})`", re.M),
    "project_id": re.compile(r"^Project id.*?`([0-9a-f-]{36})`", re.M),
}


def run_ids(spec_template_id: str | None = None, project_id: str | None = None,
            task_file: str = "current-task.md") -> dict[str, str]:
    ids = {"spec_template_id": spec_template_id, "project_id": project_id}
    if not all(ids.values()):
        try:
            with open(task_file, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            text = ""
        for name, pattern in ID_LINES.items():
            if not ids[name]:
                m = pattern.search(text)
                ids[name] = m.group(1) if m else None
    missing = [f"--{n.replace('_', '-')}" for n, v in ids.items() if not v]
    if missing:
        raise Refusal(f"needs {' and '.join(missing)} (or the lines in {task_file})")
    return ids  # type: ignore[return-value]


def call_platform(argv: list[str]) -> dict[str, Any]:
    """Run one ai-integration verb; return its `data`. Tests replace the binary, not this function."""
    cmd = [os.environ.get("AI_INTEGRATION_BIN", "ai-integration"), *argv]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise Refusal(f"{cmd[0]} is not on PATH — this works only inside a Sitis run") from None
    try:
        out = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        out = {}
    if proc.returncode != 0 or not out.get("success"):
        err = out.get("error") or {}
        raise Refusal(f"ai-integration {argv[0]} refused (exit {proc.returncode}): "
                      f"{err.get('message') or (proc.stdout or proc.stderr).strip()[:400]}")
    return out.get("data") or {}


def _scope(ids: dict[str, str], key: str) -> list[str]:
    return ["--spec-template-id", ids["spec_template_id"], "--project-id", ids["project_id"], "--intent-key", key]


def claim(key: str, ids: dict[str, str]) -> dict[str, Any]:
    key = check_key(key)
    data = call_platform(["claim-intent", *_scope(ids, key)])
    outcome, status = data.get("outcome"), data.get("status")
    out: dict[str, Any] = {"ok": True, "key": key, "outcome": outcome, "status": status}
    if outcome == "fresh":
        out.update(act=True, say="Claimed. Act once, verify the result on YouTube, then commit; "
                                 "fail only if it certainly did not happen.")
    elif outcome == "exists" and status == "committed":
        out.update(act=False, result=data.get("result"),
                   say="Already done by an earlier run — skip it and say so.")
    elif outcome == "exists" and status == "claimed":
        # At-most-once: a claim that was never confirmed may or may not have acted. Acting again
        # could double it; the owner or a later check settles it, not a retry.
        out.update(act=False, say="Claimed earlier but never confirmed: it may have happened. Do not act; "
                                  "check on YouTube and report it to the owner.")
    else:
        out.update(act=False, result=data.get("result"), reason=data.get("reason"),
                   say=f"Unexpected claim answer ({outcome}/{status}) — do not act; report it.")
    return out


def commit(key: str, ids: dict[str, str], result: Any = None) -> dict[str, Any]:
    key = check_key(key)
    argv = ["commit-intent", *_scope(ids, key)]
    path = None
    if result is not None:
        # A file, not --result: JSON through the layers of a shell loses its quotes (the verb's help).
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False)
            path = fh.name
        argv += ["--result-file", path]
    try:
        data = call_platform(argv)
    finally:
        if path:
            os.unlink(path)
    if data.get("outcome") != "committed":
        raise Refusal(f"commit of {key} answered {data.get('outcome')!r}: there was no claim to commit")
    return {"ok": True, "key": key, "outcome": "committed"}


def fail(key: str, ids: dict[str, str], reason: str) -> dict[str, Any]:
    key = check_key(key)
    if not reason.strip():
        raise Refusal("--reason is empty: say why the action did not happen")
    data = call_platform(["fail-intent", *_scope(ids, key), "--reason", reason])
    if data.get("outcome") != "failed":
        raise Refusal(f"fail of {key} answered {data.get('outcome')!r}: there was no claim to fail")
    return {"ok": True, "key": key, "outcome": "failed"}


# ── command line ───────────────────────────────────────────────────────────────────────────────


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="intent.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)

    kp = sub.add_parser("key", help="build the key of an intention")
    verbs = kp.add_subparsers(dest="verb", required=True, metavar="VERB")
    for name, spec in VERBS.items():
        vp = verbs.add_parser(name, help=spec["doc"])
        for part in spec["parts"]:
            helps = {"file": "path of the image; its content forms the key",
                     "state_file": "a JSON file with the desired state; its canonical form forms the key",
                     "title": "the post's topic in a few words"}
            vp.add_argument("--" + part.replace("_", "-"), dest=part, required=True, help=helps.get(part))

    for name, help_text in (("claim", "claim before acting"), ("commit", "the action happened and was verified"),
                            ("fail", "the action certainly did not happen")):
        cp = sub.add_parser(name, help=help_text)
        cp.add_argument("--key", required=True, help="the key from `intent.py key`")
        cp.add_argument("--spec-template-id", help="this run's Process id")
        cp.add_argument("--project-id", help="this run's Project id")
        if name == "commit":
            cp.add_argument("--result", help="JSON to journal with the claim, e.g. the new reply's id")
            cp.add_argument("--result-file", help="the same, from a file (preferred)")
        if name == "fail":
            cp.add_argument("--reason", required=True, help="why it did not happen")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "key":
            parts = {k: v for k, v in vars(args).items() if k not in ("command", "verb")}
            out: dict[str, Any] = {"ok": True, "key": build_key(args.verb, **parts)}
        else:
            ids = run_ids(args.spec_template_id, args.project_id)
            if args.command == "claim":
                out = claim(args.key, ids)
            elif args.command == "fail":
                out = fail(args.key, ids, args.reason)
            else:
                raw = args.result
                if args.result_file:
                    try:
                        with open(args.result_file, encoding="utf-8") as fh:
                            raw = fh.read()
                    except OSError as e:
                        raise Refusal(f"cannot read {args.result_file}: {e.strerror}") from None
                result = None
                if raw:
                    try:
                        result = json.loads(raw)
                    except json.JSONDecodeError as e:
                        raise Refusal(f"the result is not JSON: {e}") from None
                out = commit(args.key, ids, result)
    except Refusal as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
