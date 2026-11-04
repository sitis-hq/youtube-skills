#!/usr/bin/env python3
# Derived from youtube-agent-skill, https://github.com/Jakeschincariol/youtube-agent-skill
# commit a2feb2104981a375ffd4f87ee04f4f5344ac43c6, skills/yt-viral/swipe.py.
# MIT licence, Copyright (c) 2026 Jake Schincariol; the text is in licenses/youtube-agent-skill.txt.
# Changed: argparse and JSON-only output; a downward mode for under-performers (--direction down
# and both); a channel whose median is 0 is reported instead of dividing every video to 0; reads
# youtube-data's video rows (channel_id, video_id) as well as the original shape; titles in another
# language than English are marked unsupported instead of being classified by number and "?"
# patterns alone; hooks.json sits next to this file instead of in a sibling skill.
"""Rank videos by how far each beat — or fell short of — its OWN channel's median views.

  swipe.py videos.json                         outliers upward, 1.5x the channel median or more
  swipe.py videos.json --direction down        under-performers, 0.5x or less
  swipe.py videos.json --direction both --min 2 --max 0.4

Raw view counts rank channel size, not ideas: 400k views on a channel whose median is 30k is the
thing worth studying, on a 2M-subscriber channel it is a normal day. So each video is scored as a
multiple of its channel's median, which needs at least four videos of that channel in the input;
thinner channels are listed, not ranked.

Input: a JSON list, or an object with `videos` — youtube-data's `data_api.py videos` / `uploads
--with-stats` output as it comes, or [{"channel", "title", "views", "url"}].

The formula is one of the 21 in hooks.json, matched against the TITLE: a judgement about the words
on screen, not about why the video worked. The patterns are English; a title in another language
gets "unsupported-language" rather than a guess from its digits and question marks.

Multiples compare views only, so an old video and a new one of the same channel are compared on
unequal time; candidates.py (views per day) is the age-fair measure.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from ytskills.common import Refusal, read_json, run, video_rows  # noqa: E402

HERE = Path(__file__).resolve().parent
MIN_PER_CHANNEL = 4


def load_formulas() -> list[dict[str, Any]]:
    with open(HERE / "hooks.json", encoding="utf-8") as fh:
        return json.load(fh)["hooks"]


def mostly_latin(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return True
    return sum(c.isascii() for c in letters) / len(letters) >= 0.8


def classify(title: str, formulas: list[dict[str, Any]], lang: str = "en") -> str:
    if lang.split("-")[0] != "en" or not mostly_latin(title):
        return "unsupported-language"
    scored = []
    for f in formulas:
        n = sum(1 for p in f["match"] if re.search(p, title, re.I))
        if n:
            scored.append((n, f["name"]))
    scored.sort(reverse=True)
    return scored[0][1] if scored else "Unclassified"


def channel_of(r: dict[str, Any]) -> str:
    return str(r.get("channel_id") or r.get("channel") or r.get("channel_title") or "?")


def score(rows: list[dict[str, Any]], formulas: list[dict[str, Any]], lang: str) -> dict[str, Any]:
    by: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by.setdefault(channel_of(r), []).append(r)
    scored, thin, zero = [], [], []
    for ch, vids in by.items():
        if len(vids) < MIN_PER_CHANNEL:
            thin.append({"channel": ch, "videos": len(vids)})
            continue
        med = statistics.median(float(v.get("views") or 0) for v in vids)
        if med <= 0:
            zero.append(ch)
            continue
        for v in vids:
            views = int(v.get("views") or 0)
            title = v.get("title") or ""
            url = v.get("url") or (f"https://www.youtube.com/watch?v={v['video_id']}" if v.get("video_id") else "")
            scored.append({"channel": ch, "channel_title": v.get("channel_title"),
                           "video_id": v.get("video_id"), "title": title, "views": views,
                           "median": round(med, 1), "multiple": round(views / med, 3),
                           "formula": classify(title, formulas, lang), "url": url})
    return {"scored": scored, "thin": thin, "zero": zero, "channels": len(by)}


def main(argv: list[str] | None = None) -> dict[str, Any]:
    p = argparse.ArgumentParser(prog="swipe.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("videos", help="a JSON file of videos")
    p.add_argument("--direction", choices=["up", "down", "both"], default="up")
    p.add_argument("--min", type=float, default=1.5, help="upward: multiple at or above this (1.5)")
    p.add_argument("--max", type=float, default=0.5, help="downward: multiple at or below this (0.5)")
    p.add_argument("--lang", default="en", help="the titles' language; formulas exist for en only")
    a = p.parse_args(argv)
    if a.direction in ("up", "both") and a.min <= 1:
        raise Refusal("--min must be above 1: a multiple of 1 is the median itself")
    if a.direction in ("down", "both") and not 0 <= a.max < 1:
        raise Refusal("--max must be within 0..1: below the median")
    rows = video_rows(read_json(a.videos))
    s = score(rows, load_formulas(), a.lang)
    up = sorted((r for r in s["scored"] if r["multiple"] >= a.min), key=lambda r: -r["multiple"])
    down = sorted((r for r in s["scored"] if r["multiple"] <= a.max), key=lambda r: r["multiple"])
    out: dict[str, Any] = {"ok": True, "videos": len(rows), "channels": s["channels"],
                           "rule": {"min_videos_per_channel": MIN_PER_CHANNEL,
                                    "multiple": "views / the channel's median views in this input"}}
    if a.direction in ("up", "both"):
        out["outliers_up"] = up
        out["rule"]["up_at_or_above"] = a.min
    if a.direction in ("down", "both"):
        out["outliers_down"] = down
        out["rule"]["down_at_or_below"] = a.max
    counts: dict[str, int] = {}
    for r in up if a.direction != "down" else down:
        counts[r["formula"]] = counts.get(r["formula"], 0) + 1
    out["formulas"] = dict(sorted(counts.items(), key=lambda x: -x[1]))
    out["skipped_thin_channels"] = s["thin"]
    out["skipped_zero_median_channels"] = s["zero"]
    return out


if __name__ == "__main__":
    sys.exit(run(main))
