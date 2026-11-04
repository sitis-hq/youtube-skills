#!/usr/bin/env python3
"""How far a channel is from the YouTube Partner Program thresholds, on a given day.

  ypp.py --subscribers 812 --watch-hours 2950 --shorts-views 1200000 --uploads-90d 5 [--on 2026-11-04]

Inputs are the channel's own counts: subscribers; public long-form watch hours over the last 365
days; public Shorts-feed views over the last 90 days; public uploads over the last 90 days. The
Analytics API gives estimatedMinutesWatched / 60 for all videos, which overstates the qualified
hours (Shorts-feed watch time, and private, unlisted or deleted videos do not count) — treat the
answer as a bound, and Studio's Earn tab as the truth.

Thresholds, dated by when they apply (each with its source and the day it was read):
  revenue sharing (ads), applications before 2027-02-01: 1,000 subscribers and either 4,000 watch
    hours in 12 months or 10,000,000 Shorts views in 90 days
    — support.google.com/youtube/answer/72851, read 2026-11-04
  revenue sharing, applications from 2027-02-01: 1,000 subscribers and either 8,000 watch hours or
    20,000,000 Shorts views; existing partners unaffected
    — YouTube's announcement as reported by The Next Web, 2026-08-10, read 2026-11-04; YouTube's
      help page did not yet show it
  fan funding (memberships, Super Chat, Shopping; not ad revenue): 500 subscribers, 3 public uploads
    in 90 days, and either 3,000 watch hours in 12 months or 3,000,000 Shorts views in 90 days;
    not offered in every country — announced 2023-06-13, unchanged in the 2026-08-10 report, read
    2026-11-04
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from ytskills.common import Refusal, parse_date, run  # noqa: E402

CHANGE_2027 = date(2027, 2, 1)


def tiers(on: date) -> list[dict[str, Any]]:
    later = on >= CHANGE_2027
    return [
        {"tier": "revenue-sharing", "subscribers": 1000, "uploads_90d": None,
         "watch_hours": 8000 if later else 4000, "shorts_views": 20_000_000 if later else 10_000_000,
         "source": ("The Next Web 2026-08-10 reporting YouTube, effective 2027-02-01" if later
                    else "support.google.com/youtube/answer/72851"),
         "read": "2026-11-04"},
        {"tier": "fan-funding", "subscribers": 500, "uploads_90d": 3, "watch_hours": 3000,
         "shorts_views": 3_000_000,
         "source": "YouTube expansion of 2023-06-13; unchanged per The Next Web 2026-08-10",
         "read": "2026-11-04", "note": "not available in every country"},
    ]


def assess(t: dict[str, Any], subs: int, hours: float | None, shorts: int | None,
           uploads: int | None) -> dict[str, Any]:
    missing: dict[str, Any] = {}
    unknown = []
    if subs < t["subscribers"]:
        missing["subscribers"] = t["subscribers"] - subs
    if t["uploads_90d"] is not None:
        if uploads is None:
            unknown.append("uploads_90d")
        elif uploads < t["uploads_90d"]:
            missing["uploads_90d"] = t["uploads_90d"] - uploads
    long_ok = hours is not None and hours >= t["watch_hours"]
    shorts_ok = shorts is not None and shorts >= t["shorts_views"]
    if not (long_ok or shorts_ok):
        if hours is None and shorts is None:
            unknown.append("watch_hours or shorts_views")
        else:
            missing["either"] = {
                "watch_hours": round(t["watch_hours"] - hours, 1) if hours is not None else "unknown",
                "shorts_views": t["shorts_views"] - shorts if shorts is not None else "unknown"}
    met = not missing and not unknown
    return {**t, "met": met if not unknown else None, "missing": missing, "unknown": unknown,
            "route": ("watch-hours" if long_ok else "shorts" if shorts_ok else None)}


def main(argv: list[str] | None = None) -> dict[str, Any]:
    p = argparse.ArgumentParser(prog="ypp.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--subscribers", type=int, required=True)
    p.add_argument("--watch-hours", type=float, help="public long-form watch hours, last 365 days")
    p.add_argument("--shorts-views", type=int, help="public Shorts-feed views, last 90 days")
    p.add_argument("--uploads-90d", type=int, help="public uploads, last 90 days")
    p.add_argument("--on", help="the day of the application (default today)")
    a = p.parse_args(argv)
    if a.subscribers < 0 or (a.watch_hours or 0) < 0 or (a.shorts_views or 0) < 0:
        raise Refusal("counts cannot be negative")
    on = parse_date(a.on, "--on") if a.on else date.today()
    result = [assess(t, a.subscribers, a.watch_hours, a.shorts_views, a.uploads_90d) for t in tiers(on)]
    out: dict[str, Any] = {"ok": True, "on": on.isoformat(), "tiers": result}
    if on < CHANGE_2027:
        out["upcoming"] = {"from": CHANGE_2027.isoformat(),
                           "revenue_sharing": {"watch_hours": 8000, "shorts_views": 20_000_000}}
    return out


if __name__ == "__main__":
    sys.exit(run(main))
