#!/usr/bin/env python3
"""Each channel's normal: the median views of its latest long-form uploads, and its subscribers.

  channel_baselines.py --serp F [--serp F2 ...] [--top 20] --out baselines.json
  channel_baselines.py --channel-id UC... [--channel-id UC... ...] --out baselines.json
  options: --max-videos 30  --sleep 1.0  --refresh

A video is a breakout when it beats its own channel's median, not when its view count is large:
400k views is ordinary for a big channel and extraordinary for a channel whose videos get 500. So
niche research (youtube-demand niches.py) needs every ranking channel's median, and before the
channel is connected there is no Data API. yt-dlp reads the same public pages a viewer sees: the
channel's Videos tab (long-form only; Shorts sit on their own tab) gives each upload's view count,
and the tab's header gives the subscriber count YouTube shows. No token is used.

The median is over the latest --max-videos uploads as they are now, without dividing by age: recent
uploads have had less time, which lowers the median a little, so a multiple read against it errs
towards calling more breakouts. A channel with fewer than 5 uploads read has no median a reader
should trust; niches.py skips it.

The output file is written after every channel and read back on the next run: channels already in
it are skipped (unless --refresh), so a long run that stops can be continued. When YouTube answers
429 (too many requests) the script stops at once, keeps what it has, and says so; run it again
later with the same arguments.

Prints {"ok": true, "out", "read", "skipped", "failed", "stopped"}. A refusal exits 2.
Standard library and the yt-dlp CLI from the shelf: Python 3.11.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[3] / "lib"))
# The SERP is parsed exactly as youtube-demand reads it for competition, so both see the same top.
sys.path.insert(0, str(HERE.parents[2] / "youtube-demand" / "scripts"))

import yt_competition  # noqa: E402
from ytskills.common import Refusal, run  # noqa: E402

CHANNEL_ID = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
MIN_VIDEOS_FOR_MEDIAN = 5
RATE_LIMITED = re.compile(r"\b429\b|Too Many Requests|rate.?limit", re.I)


def run_ytdlp(argv: list[str]) -> tuple[int, str, str]:
    """The one place yt-dlp is started; tests replace it. Returns (code, stdout, stderr tail)."""
    exe = shutil.which("yt-dlp")
    if not exe:
        raise Refusal("yt-dlp is not on PATH: attach the yt-dlp CLI from the shelf to this step")
    proc = subprocess.run([exe, *argv], capture_output=True, text=True, timeout=180)
    return proc.returncode, proc.stdout, (proc.stderr or "")[-600:]


def channels_from_serp(paths: list[str], top: int) -> list[str]:
    seen: dict[str, None] = {}
    for path in paths:
        try:
            tasks = yt_competition.serp_tasks(yt_competition.load_json(path), path)
        except yt_competition.Refusal as e:
            raise Refusal(str(e)) from None
        for task in tasks:
            for v in yt_competition.videos_from_serp(task["items"])[:top]:
                cid = v.get("channel_id")
                # A collaboration shows as "X and 2 more" with no single channel id; it has no baseline.
                if cid and CHANNEL_ID.match(cid):
                    seen.setdefault(cid)
    return list(seen)


def baseline(channel_id: str, max_videos: int) -> dict[str, Any]:
    code, out, err = run_ytdlp(["--flat-playlist", "--playlist-end", str(max_videos), "-J", "--no-warnings",
                                f"https://www.youtube.com/channel/{channel_id}/videos"])
    if code != 0:
        return {"error": err.strip() or f"yt-dlp exited {code}"}
    try:
        doc = json.loads(out)
    except json.JSONDecodeError:
        return {"error": "yt-dlp did not return JSON"}
    views = [int(e["view_count"]) for e in doc.get("entries") or []
             if isinstance(e, dict) and isinstance(e.get("view_count"), (int, float))]
    subs = doc.get("channel_follower_count")
    row: dict[str, Any] = {"title": doc.get("channel") or doc.get("uploader"),
                           "subscribers": int(subs) if isinstance(subs, (int, float)) else None,
                           "videos_read": len(views),
                           "median_views": statistics.median(views) if views else None,
                           "views": views}
    if len(views) < MIN_VIDEOS_FOR_MEDIAN:
        row["note"] = f"fewer than {MIN_VIDEOS_FOR_MEDIAN} uploads read: no trustworthy median"
    return row


def load_existing(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise Refusal(f"{path} exists but cannot be read back ({e}); move it away or pass another --out") from None
    if not isinstance(doc, dict) or not isinstance(doc.get("channels"), dict):
        raise Refusal(f"{path} is not a channel_baselines output; pass another --out")
    return doc


def main(argv: list[str] | None = None) -> dict[str, Any]:
    p = argparse.ArgumentParser(prog="channel_baselines.py", description=__doc__.split("\n\n")[0])
    p.add_argument("--serp", action="append", default=[], help="DataForSEO YouTube SERP response (repeatable)")
    p.add_argument("--channel-id", action="append", default=[], help="a channel id UC... (repeatable)")
    p.add_argument("--top", type=int, default=yt_competition.TOP, help="top results read per SERP (default 20)")
    p.add_argument("--max-videos", type=int, default=30, help="latest uploads read per channel (default 30)")
    p.add_argument("--sleep", type=float, default=1.0, help="seconds between channels (default 1.0)")
    p.add_argument("--out", required=True, help="baselines file; read back and extended on the next run")
    p.add_argument("--refresh", action="store_true", help="read channels already in --out again")
    a = p.parse_args(argv)
    if not a.serp and not a.channel_id:
        raise Refusal("pass --serp FILE or --channel-id UC...")
    bad = [c for c in a.channel_id if not CHANNEL_ID.match(c)]
    if bad:
        raise Refusal(f"not channel ids: {bad}")
    if a.max_videos < MIN_VIDEOS_FOR_MEDIAN or a.top < 1 or a.sleep < 0:
        raise Refusal(f"--max-videos must be at least {MIN_VIDEOS_FOR_MEDIAN}, --top at least 1, --sleep not negative")

    wanted = list(dict.fromkeys([*a.channel_id, *channels_from_serp(a.serp, a.top)]))
    out = Path(a.out)
    doc = load_existing(out) or {"channels": {}, "failed": {}}
    doc.update({"max_videos": a.max_videos, "source": "yt-dlp, the channel's public Videos tab"})
    doc.setdefault("failed", {})
    read = skipped = 0
    stopped = None
    for n, cid in enumerate(wanted):
        if cid in doc["channels"] and not a.refresh:
            skipped += 1
            continue
        if read and a.sleep:
            time.sleep(a.sleep)
        row = baseline(cid, a.max_videos)
        if "error" in row:
            if RATE_LIMITED.search(row["error"]):
                stopped = (f"YouTube answered 429 after {read} channel(s); {len(wanted) - n} left. "
                           "Run again later with the same arguments: done channels are kept.")
                break
            doc["failed"][cid] = row["error"][-300:]
        else:
            row["read_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            doc["channels"][cid] = row
            doc["failed"].pop(cid, None)
            read += 1
        try:
            out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError as e:
            raise Refusal(f"cannot write {out}: {e}") from None
    if not out.exists():
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "out": str(out), "wanted": len(wanted), "read": read, "skipped": skipped,
            "failed": len(doc["failed"]), "stopped": stopped,
            "note": "median_views is over the latest uploads as they are now; channels with fewer than "
                    f"{MIN_VIDEOS_FOR_MEDIAN} uploads carry a note and are skipped by niches.py"}


if __name__ == "__main__":
    sys.exit(run(main))
