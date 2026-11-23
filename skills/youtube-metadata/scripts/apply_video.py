#!/usr/bin/env python3
"""Change a published video's metadata or custom thumbnail through the Data API, each under an intent.

  apply_video.py metadata --video-id ID --desired meta.json [--dry-run]
      Bring the video's snippet to a desired state. The file holds only the fields to set, out of:
      title, description, tags (a list), defaultLanguage. The script reads the whole snippet, merges
      the desired fields into it and sends the whole snippet back (videos.update deletes every
      property the request leaves out), then re-reads and checks every desired field. Nothing
      differs → no claim, no write. Key: metadata:video:<id>:<digest of the desired state>.

  apply_video.py thumbnail --video-id ID --image thumb.jpg
      thumbnails.set. The file is checked first (JPEG or PNG, at least 640 px wide, at most 50 MB).
      Key: thumbnail:video:<id>:<digest of the file>. The API cannot read a custom image back, so
      the 2xx answer is the evidence and the output says to look at the watch page.

Not here: thumbnail A/B tests (Studio only: youtube-studio/references/ab-test.md).

Failure semantics, re-reads that wait for YouTube's read side, and the token: exactly as
youtube-channel-setup's apply_channel.py, whose client this script uses. A 4xx means YouTube refused
and nothing changed → the intent is failed; a missing scope adds "fallback": "studio". A 5xx, a lost
answer or a re-read that does not show the change → the claim stays open and "uncertain": do not
retry, check on YouTube. A claim already committed → skipped and said so.

Data API v3 reference read 2026-11-23:
  https://developers.google.com/youtube/v3/docs/videos/update — PUT, part=snippet; id, and with a
    snippet also snippet.title and snippet.categoryId, are required; settable snippet fields
    include categoryId, defaultLanguage, description, tags[], title; a property the request leaves
    out that has a value is deleted; 50 units. videos.list costs 1 unit.
  https://developers.google.com/youtube/v3/docs/thumbnails/set — POST to the upload URL with
    videoId; image/jpeg or image/png, at most 50 MB; about 50 units. YouTube Help 72431 (read
    2026-11-04, as youtube-thumbnail-check states it): 16:9, at least 640 px wide.

All output is JSON on stdout; a refusal exits 2 with {"ok": false, "error": ...}.
Standard library only: Python 3.11.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SETUP_SCRIPTS = HERE.parents[1] / "youtube-channel-setup" / "scripts"
sys.path.insert(0, str(SETUP_SCRIPTS))
try:
    # One Data API client, one failure rule, one re-read rule for every write the set makes.
    import apply_channel as ac  # noqa: E402
except ImportError:  # pragma: no cover - only when the tree is incomplete
    print(json.dumps({"ok": False, "error": f"youtube-channel-setup's apply_channel.py is missing at {SETUP_SCRIPTS}"}))
    sys.exit(2)

intent = ac.intent
ApiError = ac.ApiError
Refusal = ac.Refusal

FIELDS = ("title", "description", "tags", "defaultLanguage")
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
THUMB_MIN_WIDTH = 640
THUMB_BYTES = 50 * 1024 * 1024
# No Studio playbook edits a video's details: without the scope the change is the owner's, by hand.
PLAYBOOK = "none: ask the owner to make the change on the video's details page in Studio"

ac.COST.update({"videos.list": 1, "videos.update": 50, "thumbnails.set": 50})


def check_video_id(video_id: str) -> str:
    if not VIDEO_ID.match(video_id or ""):
        raise Refusal(f"--video-id must be an 11-character video id, got {video_id!r}")
    return video_id


def load_desired(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as fh:
            desired = json.load(fh)
    except OSError as e:
        raise Refusal(f"cannot read {path}: {e.strerror}") from None
    except json.JSONDecodeError as e:
        raise Refusal(f"{path} is not JSON: {e}") from None
    if not isinstance(desired, dict) or not desired:
        raise Refusal(f"{path} must hold an object with at least one of: {', '.join(FIELDS)}")
    unknown = set(desired) - set(FIELDS)
    if unknown:
        raise Refusal(f"{path}: fields this script does not set: {sorted(unknown)}; allowed: {', '.join(FIELDS)}")
    for name in ("title", "description", "defaultLanguage"):
        if name in desired and not isinstance(desired[name], str):
            raise Refusal(f"{name} must be text")
    if "title" in desired and not desired["title"].strip():
        raise Refusal("a video's title cannot be empty")
    if "tags" in desired and (not isinstance(desired["tags"], list)
                              or not all(isinstance(t, str) and t.strip() for t in desired["tags"])):
        raise Refusal("tags must be a list of non-empty texts")
    return desired


def read_snippet(client: Any, video_id: str) -> dict[str, Any]:
    page = client.call("videos.list", "GET", ac.API + "videos", {"part": "snippet", "id": video_id})
    items = page.get("items") or []
    if not items:
        raise Refusal(f"video {video_id} was not found, or this connection cannot see it")
    return items[0].get("snippet") or {}


def same(name: str, a: Any, b: Any) -> bool:
    if name == "tags":
        return [t.strip() for t in (a or [])] == [t.strip() for t in (b or [])]
    return (a or "") == (b or "")


def diff(current: dict[str, Any], desired: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"field": k, "from": current.get(k), "to": v} for k, v in desired.items() if not same(k, current.get(k), v)]


def apply_metadata(client: Any, ids_fn, video_id: str, desired_path: str, dry_run: bool) -> dict[str, Any]:
    desired = load_desired(desired_path)
    key = intent.build_key("metadata", video_id=video_id, state_file=desired_path)
    snippet = read_snippet(client, video_id)
    changes = diff(snippet, desired)
    if not changes:
        return {"ok": True, "changed": False, "key": key, "units_used": client.units}
    if dry_run:
        return {"ok": True, "dry_run": True, "changed": True, "key": key, "diff": changes,
                "units_used": client.units}
    ids = ids_fn()
    claimed = intent.claim(key, ids)
    if not claimed["act"]:
        out = ac._skipped(key, claimed, client)
        out["diff"] = changes
        return out
    # The whole snippet goes back, read-only parts removed: what YouTube holds now, with only the
    # desired fields replaced. categoryId and title come along, which the update requires.
    merged = {k: v for k, v in snippet.items()
              if k not in ("publishedAt", "channelId", "channelTitle", "thumbnails", "localized",
                           "liveBroadcastContent", "defaultAudioLanguage")}
    merged.update(desired)
    body = json.dumps({"id": video_id, "snippet": merged}).encode("utf-8")
    try:
        client.call("videos.update", "PUT", ac.API + "videos", {"part": "snippet"}, body, "application/json")
    except ApiError as e:
        return ac._api_failure(key, ids, e, client, diff=changes)
    try:
        _, left, tries = ac.reread(lambda: read_snippet(client, video_id), lambda after: diff(after, desired))
    except (ApiError, Refusal) as e:
        return ac._uncertain(key, client, f"the re-read failed: {e}", diff=changes)
    if left:
        return ac._uncertain(key, client, f"{tries} re-reads do not show every desired field", diff=changes,
                             not_applied=left)
    intent.commit(key, ids, {"diff": changes})
    return {"ok": True, "changed": True, "acted": True, "key": key, "diff": changes, "units_used": client.units}


def check_thumbnail(path: str) -> dict[str, Any]:
    info = ac.image_info(path)
    if info["width"] < THUMB_MIN_WIDTH:
        raise Refusal(f"{path} is {info['width']} px wide; a thumbnail needs at least {THUMB_MIN_WIDTH}")
    if info["bytes"] > THUMB_BYTES:
        raise Refusal(f"{path} is {info['bytes']} bytes; thumbnails.set takes at most {THUMB_BYTES}")
    return info


def apply_thumbnail(client: Any, ids_fn, video_id: str, image: str) -> dict[str, Any]:
    info = check_thumbnail(image)
    key = intent.build_key("thumbnail", video_id=video_id, file=image)
    # A read, so before the claim: a video this connection cannot see changes nothing.
    read_snippet(client, video_id)
    ids = ids_fn()
    claimed = intent.claim(key, ids)
    if not claimed["act"]:
        return ac._skipped(key, claimed, client)
    try:
        client.call("thumbnails.set", "POST", ac.UPLOAD + "thumbnails/set", {"videoId": video_id, "uploadType": "media"},
                    info["data"], info["mime"])
    except ApiError as e:
        return ac._api_failure(key, ids, e, client)
    # The Data API has no read that shows which custom image is live: the 2xx answer is the evidence.
    intent.commit(key, ids, {"file_bytes": info["bytes"]})
    return {"ok": True, "acted": True, "key": key, "units_used": client.units,
            "say": "Set. The API cannot read the image back: look at the video's watch page."}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="apply_video.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)
    m = sub.add_parser("metadata", help="bring a video's snippet to a desired state")
    m.add_argument("--desired", required=True, help="JSON object with any of: " + ", ".join(FIELDS))
    m.add_argument("--dry-run", action="store_true", help="print the diff only; no claim, no write")
    t = sub.add_parser("thumbnail", help="set a video's custom thumbnail")
    t.add_argument("--image", required=True, help="JPEG or PNG, >= 640 px wide, <= 50 MB")
    for sp in sub.choices.values():
        sp.add_argument("--video-id", required=True, help="the video (11 characters)")
        sp.add_argument("--spec-template-id", help="this run's Process id")
        sp.add_argument("--project-id", help="this run's Project id")
        sp.add_argument("--connection", default="YOUTUBE", help="the OAuth connection name (default YOUTUBE)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    client = ac.Client(args.connection)

    def ids_fn() -> dict[str, str]:
        return intent.run_ids(args.spec_template_id, args.project_id)

    try:
        video_id = check_video_id(args.video_id)
        if args.command == "metadata":
            out = apply_metadata(client, ids_fn, video_id, args.desired, args.dry_run)
        else:
            out = apply_thumbnail(client, ids_fn, video_id, args.image)
    except ApiError as e:
        # Only reads happen outside a claim, so nothing changed.
        out = {"ok": False, "error": str(e), "units_used": client.units}
        if e.scope_missing:
            out.update(fallback="studio", playbook=PLAYBOOK)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2
    except (Refusal, intent.Refusal) as e:
        print(json.dumps({"ok": False, "error": str(e), "units_used": client.units}, ensure_ascii=False))
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
