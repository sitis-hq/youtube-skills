#!/usr/bin/env python3
"""Growth velocity and anomaly flags of videos, from dated view-count snapshots.

  velocity.py snapshot-2026-11-01.json snapshot-2026-11-02.json ... [--min-abs 20]

Each file is one day's snapshot: youtube-data's `data_api.py videos` output as it comes
({"as_of": "YYYY-MM-DD", "videos": [{"video_id", "views", "published_at"}, ...]}), or a list of rows
that each carry `as_of`. Later files win for the same day. Each video gets the fields of a
`velocity` record (`record`), ready for `records.py write velocity`.

views_per_day — the views gained between the last two snapshots, divided by the days between them.
  A count that went down (YouTube removes invalid views) gives 0, with views_delta showing the fall.
  With a single snapshot there is no gain to measure: the record then carries the lifetime average
  views / age in days and source "views-per-age", so a reader can tell the proxy from a measurement.

anomaly — the latest rate against the video's own history:
  baseline  the median of its earlier daily rates (up to the last 14 intervals before the latest),
            when there are at least 3 of them;
  spike     latest >= 2 x baseline  and  latest - baseline >= --min-abs views/day;
  drop      latest <= 0.5 x baseline  and  baseline - latest >= --min-abs views/day;
  none      otherwise.
  With fewer than 3 earlier intervals the baseline is the lifetime average (views / age) at the
  previous snapshot, for videos at least 7 days old, and only a spike is flagged: nearly every
  video's daily views fall below its lifetime average once its launch days are over, so a drop
  against that average is the normal decay, not news. Younger videos, and those without
  published_at, get none.
The median keeps one odd day of the history from moving the baseline; --min-abs keeps a video going
from 2 to 5 views a day from reading as a spike. Both factors are this skill's choice, stated here
and tested, not a YouTube figure.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from ytskills.common import Refusal, parse_date, parse_datetime, read_json, run, video_rows  # noqa: E402

SPIKE_FACTOR = 2.0
DROP_FACTOR = 0.5
MIN_BASELINE_INTERVALS = 3
MAX_BASELINE_INTERVALS = 14
PROXY_MIN_AGE_DAYS = 7


def load_snapshots(paths: list[str]) -> dict[str, dict[str, Any]]:
    """video_id -> {"history": {date: views}, "published_at": str|None}."""
    videos: dict[str, dict[str, Any]] = {}
    for path in paths:
        doc = read_json(path)
        file_day = doc.get("as_of") if isinstance(doc, dict) else None
        for r in video_rows(doc):
            day_raw = r.get("as_of") or file_day
            if not day_raw:
                raise Refusal(f"{path}: a row of {r.get('video_id')} has no as_of, and neither has the file")
            if r.get("video_id") is None or r.get("views") is None:
                continue  # a video whose count is hidden or that came back without stats
            v = videos.setdefault(r["video_id"], {"history": {}, "published_at": None})
            v["history"][parse_date(day_raw, f"{path} as_of")] = int(r["views"])
            v["published_at"] = r.get("published_at") or v["published_at"]
    return videos


def age_days(published_at: str | None, on: date) -> int | None:
    if not published_at:
        return None
    return max(1, (on - parse_datetime(published_at, "published_at").date()).days)


def rule(min_abs: float) -> dict[str, Any]:
    return {"spike": f"latest >= {SPIKE_FACTOR} x baseline and latest - baseline >= {min_abs:g}",
            "drop": f"latest <= {DROP_FACTOR} x baseline and baseline - latest >= {min_abs:g}",
            "baseline": f"median of up to {MAX_BASELINE_INTERVALS} earlier daily rates, at least "
                        f"{MIN_BASELINE_INTERVALS}; else lifetime views/age (spike only, age >= "
                        f"{PROXY_MIN_AGE_DAYS} days)",
            "unit": "views per day"}


def flag(latest: float, baseline: float | None, min_abs: float, drops: bool) -> str:
    if baseline is None:
        return "none"
    if latest >= SPIKE_FACTOR * baseline and latest - baseline >= min_abs:
        return "spike"
    if drops and latest <= DROP_FACTOR * baseline and baseline - latest >= min_abs:
        return "drop"
    return "none"


def analyse(video_id: str, v: dict[str, Any], latest_day: date, min_abs: float) -> dict[str, Any]:
    hist = sorted(v["history"].items())
    if hist[-1][0] != latest_day:
        return {"video_id": video_id, "skipped": f"absent from the latest snapshot ({latest_day})"}
    day, views = hist[-1]
    out: dict[str, Any] = {"video_id": video_id, "as_of": day.isoformat(), "views": views,
                           "snapshots": len(hist)}
    if len(hist) == 1:
        age = age_days(v["published_at"], day)
        if age is None:
            return {**out, "skipped": "one snapshot and no published_at: nothing to measure"}
        vpd = round(views / age, 3)
        out.update(views_per_day=vpd, basis="views-per-age", age_days=age, baseline_views_per_day=None,
                   anomaly="none")
        out["record"] = {"video_id": video_id, "as_of": out["as_of"], "views_per_day": vpd,
                         "anomaly": "none", "source": "views-per-age"}
        return out
    rates = []
    for (d0, v0), (d1, v1) in zip(hist, hist[1:]):
        rates.append((v1 - v0) / (d1 - d0).days)
    latest_raw = rates[-1]
    latest = max(0.0, latest_raw)
    earlier = [max(0.0, r) for r in rates[:-1]][-MAX_BASELINE_INTERVALS:]
    if len(earlier) >= MIN_BASELINE_INTERVALS:
        baseline, basis, drops = statistics.median(earlier), f"own history ({len(earlier)} intervals)", True
    else:
        prev_day, prev_views = hist[-2]
        age = age_days(v["published_at"], prev_day)
        if age is not None and age >= PROXY_MIN_AGE_DAYS:
            baseline, basis, drops = prev_views / age, "lifetime views/age (spike only)", False
        else:
            baseline, basis, drops = None, "none: too little history and too young or undated", False
    anomaly = flag(latest, baseline, min_abs, drops)
    out.update(views_per_day=round(latest, 3), views_delta=hist[-1][1] - hist[-2][1],
               days=(hist[-1][0] - hist[-2][0]).days, basis="snapshots",
               baseline_views_per_day=round(baseline, 3) if baseline is not None else None,
               baseline_basis=basis, anomaly=anomaly)
    if latest_raw < 0:
        out["note"] = "the view count went down; YouTube removes views it judges invalid"
    out["record"] = {"video_id": video_id, "as_of": out["as_of"], "views_per_day": round(latest, 3),
                     "anomaly": anomaly, "source": "data-api"}
    return out


def main(argv: list[str] | None = None) -> dict[str, Any]:
    p = argparse.ArgumentParser(prog="velocity.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("snapshots", nargs="+", help="dated snapshot files, in any order")
    p.add_argument("--min-abs", type=float, default=20.0,
                   help="least change in views/day that can be an anomaly (default 20)")
    a = p.parse_args(argv)
    videos = load_snapshots(a.snapshots)
    if not videos:
        raise Refusal("the snapshots hold no video with a view count")
    latest_day = max(d for v in videos.values() for d in v["history"])
    results = [analyse(vid, v, latest_day, a.min_abs) for vid, v in sorted(videos.items())]
    done = [r for r in results if "record" in r]
    return {"ok": True, "as_of": latest_day.isoformat(), "rule": rule(a.min_abs),
            "summary": {"videos": len(done), "spike": sum(r["anomaly"] == "spike" for r in done),
                        "drop": sum(r["anomaly"] == "drop" for r in done),
                        "skipped": len(results) - len(done)},
            "videos": results}


if __name__ == "__main__":
    sys.exit(run(main))
