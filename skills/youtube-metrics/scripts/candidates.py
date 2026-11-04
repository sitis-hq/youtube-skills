#!/usr/bin/env python3
"""Score candidate videos for the watchlist: views per day of age, against their channel's median.

  candidates.py found.json --source search [--baseline uploads.json ...] [--top 20] [--max-age-days 30]

Input files are youtube-data's `data_api.py videos` (or `uploads --with-stats`) output as it comes,
or lists of {"video_id", "channel_id", "title", "views", "published_at"}.

  views_per_day   views / age in days, age measured from published_at to the file's fetched_at
                  (else --as-of, else now) and never less than 1 day, so an hour-old upload does
                  not divide by almost nothing
  channel median  the median views_per_day of that channel's videos among the candidates and the
                  --baseline files (a channel's recent uploads: `data_api.py uploads --channel-id
                  UC... --max 20 --with-stats`); at least 4 videos, as swipe.py requires
  score           views_per_day / channel median: how many times faster than its channel's typical
                  video this one gathers views. Raw views rank channel size; this ranks the video.
                  No score without a median — those candidates are ranked after the scored ones
                  by views_per_day, and listed in `need_baseline` with the channels to fetch.

Each candidate carries the fields of a `watch` record (`record`) except `reason`, which is the
agent's sentence about why it is followed.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from ytskills.common import (Refusal, parse_date, parse_datetime, read_json, run,  # noqa: E402
                             video_rows)

MIN_PER_CHANNEL = 4


def load(paths: list[str], fallback: datetime) -> list[dict[str, Any]]:
    rows = []
    for path in paths:
        doc = read_json(path)
        ref = fallback
        if isinstance(doc, dict) and doc.get("fetched_at"):
            ref = parse_datetime(doc["fetched_at"], f"{path} fetched_at")
        for r in video_rows(doc):
            if r.get("video_id") and r.get("views") is not None and r.get("published_at"):
                age = (ref - parse_datetime(r["published_at"], "published_at")).total_seconds() / 86400
                rows.append({**r, "age_days": round(max(1.0, age), 3)})
    return rows


def main(argv: list[str] | None = None) -> dict[str, Any]:
    p = argparse.ArgumentParser(prog="candidates.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("candidates", nargs="+", help="files of candidate videos")
    p.add_argument("--source", required=True, help="how they were found: search, trends, competitor-list")
    p.add_argument("--baseline", action="append", default=[], help="more videos of the same channels, "
                                                                     "for the medians only; repeatable")
    p.add_argument("--as-of", help="the reference day when a file has no fetched_at (default now)")
    p.add_argument("--max-age-days", type=float, help="leave out older candidates")
    p.add_argument("--top", type=int, help="keep the best N")
    a = p.parse_args(argv)
    fallback = (datetime.combine(parse_date(a.as_of, "--as-of"), datetime.min.time(), timezone.utc)
                if a.as_of else datetime.now(timezone.utc))
    cands = load(a.candidates, fallback)
    if not cands:
        raise Refusal("no candidate has video_id, views and published_at")
    pool: dict[str, dict[str, Any]] = {r["video_id"]: r for r in load(a.baseline, fallback)}
    pool.update({r["video_id"]: r for r in cands})
    by_channel: dict[str, list[float]] = {}
    for r in pool.values():
        by_channel.setdefault(r.get("channel_id") or "?", []).append(r["views"] / r["age_days"])
    medians = {ch: statistics.median(v) for ch, v in by_channel.items() if len(v) >= MIN_PER_CHANNEL}

    out_rows = []
    seen = set()
    for r in cands:
        if r["video_id"] in seen or (a.max_age_days and r["age_days"] > a.max_age_days):
            continue
        seen.add(r["video_id"])
        ch = r.get("channel_id") or "?"
        vpd = r["views"] / r["age_days"]
        med = medians.get(ch)
        score = round(vpd / med, 3) if med else None
        row = {"video_id": r["video_id"], "channel_id": r.get("channel_id"),
               "channel_title": r.get("channel_title"), "title": r.get("title"),
               "published_at": r["published_at"], "views": int(r["views"]), "age_days": r["age_days"],
               "views_per_day": round(vpd, 3),
               "channel_median_views_per_day": round(med, 3) if med is not None else None,
               "channel_videos": len(by_channel.get(ch, [])), "score": score}
        record = {"video_id": r["video_id"], "channel_id": r.get("channel_id"), "source": a.source,
                  "published_at": r["published_at"], "views": int(r["views"]),
                  "views_per_day": round(vpd, 3)}
        if score is not None:
            record["score"] = score
        row["record"] = record
        out_rows.append(row)
    out_rows.sort(key=lambda x: (x["score"] is None, -(x["score"] or 0), -x["views_per_day"]))
    if a.top:
        out_rows = out_rows[:a.top]
    need = sorted({x["channel_id"] for x in out_rows if x["score"] is None and x["channel_id"]})
    return {"ok": True, "rule": {"views_per_day": "views / max(1, age in days)",
                                 "score": f"views_per_day / channel median views_per_day "
                                          f"(channel needs {MIN_PER_CHANNEL}+ videos in the input)"},
            "candidates": out_rows, "need_baseline": need}


if __name__ == "__main__":
    sys.exit(run(main))
