#!/usr/bin/env python3
"""Rank niche candidates by how open each one is to a new channel, with demand as a floor.

  niches.py --serp F [--serp F2 ...] --baselines baselines.json [--demand-floor 10000]
            [--labs F ...] [--trends F ... --anchor TERM] [--top 20] [--as-of YYYY-MM-DD]

What makes a niche hard is not its popularity. YouTube matches videos to each viewer, and gives new
channels a slot on the home page; a popular niche whose top is spread over many channels and keeps
taking new videos is the best case, because its demand is proven. A niche is hard when a few
incumbents hold the top, when the top is old, and when small channels never break through. Those
three are measured here, over the niche term's YouTube top results:

  breakouts      the share of the top videos that come from channels under 100k subscribers and have
                 at least 3x their own channel's median views. Needs channel medians: youtube-data
                 channel_baselines.py. 3x the channel's median is the outlier line of
                 youtube-strategy thresholds.md (Paddy Galloway: "3 or 4 times more than the average
                 at minimum on a channel"); 100k is the line between established and large channels
                 in the same file. Videos whose channel has fewer than 5 uploads read are left out.
  concentration  the share of the top videos held by the three channels with most of them
  freshness      the share of the top videos published in the last 365 days

  openness       0-100: the mean of breakouts, 1 - concentration and freshness, equal weights (ours).
                 When fewer than half of the top videos have a channel median, breakouts is left out,
                 the mean is of the other two, and `confidence` is "low".
  demand         the median views of the top videos: what the best in the niche get. A niche under
                 --demand-floor (default 10,000, ours) is listed below the others as too small to
                 rank on openness: an open niche nobody watches is not an opportunity.

Ranking: niches at or over the floor by openness, ties by demand; then those under the floor; then
those that could not be measured. `same_results` names term pairs whose top results are at least half
the same videos: one audience, not two niches.

Search numbers are reported under `search` and do not rank: Labs volume and kd_web (--labs), the
Trends YouTube index (--trends; pass --anchor, a term put into every request, so indices of different
requests share the first request's scale), and yt_competition, our heuristic for the fight over
the search results. They tell how much a niche is searched, which matters for search-led formats and
little for browse-led ones.

Prints {"ok": true, "niches": [...ranked], "same_results": [...], ...}. A refusal exits 2.
Standard library only: Python 3.11.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "lib"))
sys.path.insert(0, str(HERE))

import normalize  # noqa: E402
import yt_competition  # noqa: E402
from ytskills.common import Refusal, run as run_main  # noqa: E402

BREAKOUT_MULTIPLE = 3.0          # youtube-strategy thresholds.md: outlier line
SMALL_CHANNEL_BELOW = 100_000    # thresholds.md: under "large"
MIN_VIDEOS_FOR_MEDIAN = 5        # channel_baselines.py: fewer gives no trustworthy median
FRESH_DAYS = 365
DEMAND_FLOOR = 10_000            # ours: median views of the top results
SAME_RESULTS_SHARE = 0.5         # half of the smaller top list shared: one audience


def _load(path: str) -> dict[str, Any]:
    try:
        return normalize.load(path)
    except normalize.Refusal as e:
        raise Refusal(str(e)) from None


def _as_of_now(as_of: str | None) -> datetime | None:
    if not as_of:
        return None
    try:
        d = date.fromisoformat(as_of)
    except ValueError:
        raise Refusal(f"--as-of must be YYYY-MM-DD, got {as_of!r}") from None
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc) + timedelta(hours=12)


def load_baselines(path: str | None) -> dict[str, dict[str, Any]]:
    if not path:
        return {}
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise Refusal(f"cannot read --baselines: {e}") from None
    channels = doc.get("channels") if isinstance(doc, dict) else None
    if not isinstance(channels, dict):
        raise Refusal("--baselines is not youtube-data channel_baselines.py output (no 'channels')")
    return channels


def labs_metrics(paths: list[str], errors: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], float]:
    out: dict[str, dict[str, Any]] = {}
    cost = 0.0
    for path in paths:
        doc = _load(path)
        cost += float(doc.get("cost") or 0)
        for result in normalize.results(doc, path, errors):
            for entry in normalize.labs_entries(result):
                row = normalize.labs_row(entry) if isinstance(entry, dict) else None
                if row:
                    out.setdefault(normalize.term_key(row["term"]), row)
    return out, cost


def trends_interest(paths: list[str], anchor: str | None, errors: list[dict[str, Any]],
                    warnings: list[str]) -> tuple[dict[str, float], bool, float]:
    """yt_interest per term on one scale, whether it compares across terms, and the cost."""
    batches: list[dict[str, float]] = []
    cost = 0.0
    for path in paths:
        doc = _load(path)
        try:
            normalize.require_youtube_trends(doc, path)
        except normalize.Refusal as e:
            raise Refusal(str(e)) from None
        cost += float(doc.get("cost") or 0)
        for result in normalize.results(doc, path, errors):
            values = normalize.trends(result, [], [], warnings)
            if values:
                batches.append({normalize.term_key(k): float(v) for k, v in values.items()})
    if len(batches) <= 1:
        return (batches[0] if batches else {}), True, cost
    if not anchor:
        warnings.append(f"Trends came in {len(batches)} requests without an --anchor: their indices are on "
                        "different scales and do not compare across requests")
        merged: dict[str, float] = {}
        for b in batches:
            for k, v in b.items():
                merged.setdefault(k, v)
        return merged, False, cost
    key = normalize.term_key(anchor)
    missing = [i + 1 for i, b in enumerate(batches) if key not in b]
    if missing:
        raise Refusal(f"--anchor {anchor!r} is not in Trends request(s) {missing}: put the anchor term into "
                      "every request, or the requests cannot be put on one scale")
    reference = batches[0][key]
    merged = {}
    comparable = True
    for i, b in enumerate(batches):
        if b[key] <= 0:
            warnings.append(f"the anchor reads 0 in Trends request {i + 1}; its terms cannot be rescaled")
            comparable = False
            continue
        for k, v in b.items():
            # Rescaled values may pass 100: the scale is the first request's, not each request's own.
            merged.setdefault(k, round(v * reference / b[key], 1))
    return merged, comparable, cost


def openness(videos: list[dict[str, Any]], now: datetime,
             baselines: dict[str, dict[str, Any]]) -> dict[str, Any]:
    n = len(videos)
    by_channel = Counter(v.get("channel_id") or f"?{i}" for i, v in enumerate(videos))
    top3 = sum(c for _, c in by_channel.most_common(3)) / n
    ages = [a for a in (yt_competition.age_days(v, now) for v in videos) if a is not None]
    fresh = sum(a <= FRESH_DAYS for a in ages) / len(ages) if ages else None

    measured, breakouts = 0, []
    for v in videos:
        b = baselines.get(v.get("channel_id") or "")
        views = v.get("views")
        if not b or not isinstance(views, (int, float)) or (b.get("videos_read") or 0) < MIN_VIDEOS_FOR_MEDIAN \
                or not b.get("median_views"):
            continue
        measured += 1
        multiple = views / b["median_views"]
        subs = b.get("subscribers")
        if multiple >= BREAKOUT_MULTIPLE and subs is not None and subs < SMALL_CHANNEL_BELOW:
            breakouts.append({"video_id": v.get("video_id"), "title": v.get("title"), "channel": b.get("title"),
                              "subscribers": subs, "views": views, "channel_median": b["median_views"],
                              "multiple": round(multiple, 1)})
    coverage = measured / n
    breakout_share = len(breakouts) / measured if measured else None
    parts = {"breakouts": breakout_share if coverage >= 0.5 else None,
             "spread": 1 - top3, "freshness": fresh}
    used = [v for v in parts.values() if v is not None]
    breakouts.sort(key=lambda b: -b["multiple"])
    return {
        "openness": round(100 * statistics.fmean(used), 1) if used else None,
        "confidence": "normal" if parts["breakouts"] is not None and fresh is not None else "low",
        "parts": {k: (round(v, 3) if v is not None else None) for k, v in parts.items()},
        "top3_channel_share": round(top3, 3),
        "distinct_channels": len(by_channel),
        "fresh_share": round(fresh, 3) if fresh is not None else None,
        "breakout_share": round(breakout_share, 3) if breakout_share is not None else None,
        "baseline_coverage": round(coverage, 3),
        "breakouts": breakouts[:5],
    }


def run(argv: list[str] | None = None) -> dict[str, Any]:
    p = argparse.ArgumentParser(description="Rank niche candidates by openness to a new channel (see the file's docstring).")
    p.add_argument("--serp", action="append", default=[], help="YouTube organic SERP response, one task per niche term (repeatable)")
    p.add_argument("--baselines", help="youtube-data channel_baselines.py output for the channels in the SERPs")
    p.add_argument("--demand-floor", type=float, default=DEMAND_FLOOR,
                   help=f"median views of the top results a niche needs to be ranked on openness (default {DEMAND_FLOOR})")
    p.add_argument("--labs", action="append", default=[], help="Labs keyword_overview response for the same terms (repeatable)")
    p.add_argument("--trends", action="append", default=[], help="Trends explore response, type=youtube (repeatable)")
    p.add_argument("--anchor", help="the term present in every Trends request, to put them on one scale")
    p.add_argument("--top", type=int, default=yt_competition.TOP, help="top results read per niche (default 20)")
    p.add_argument("--as-of", help="count ages to this day, YYYY-MM-DD (default: each SERP's datetime)")
    a = p.parse_args(argv)
    if not a.serp:
        raise Refusal("pass --serp: every niche is a term with its YouTube results")
    if a.top < 1 or a.demand_floor < 0:
        raise Refusal("--top must be at least 1 and --demand-floor not negative")
    fixed_now = _as_of_now(a.as_of)
    baselines = load_baselines(a.baselines)

    errors: list[dict[str, Any]] = []
    warnings: list[str] = []
    labs, cost = labs_metrics(a.labs, errors)
    interest, interest_comparable, trends_cost = trends_interest(a.trends, a.anchor, errors, warnings)
    cost += trends_cost
    subs = {cid: b["subscribers"] for cid, b in baselines.items() if isinstance(b.get("subscribers"), int)}

    out: list[dict[str, Any]] = []
    top_ids: dict[str, set[str]] = {}
    for path in a.serp:
        doc = _load(path)
        cost += float(doc.get("cost") or 0)
        try:
            tasks = yt_competition.serp_tasks(doc, path)
        except yt_competition.Refusal as e:
            raise Refusal(str(e)) from None
        for task in tasks:
            term = normalize.term_key(task["keyword"] or "")
            if not term or term in top_ids:
                if term:
                    warnings.append(f"{term!r} has more than one SERP; the first one is used")
                continue
            now = fixed_now or yt_competition.parse_when(task["datetime"]) or datetime.now(timezone.utc)
            videos = yt_competition.videos_from_serp(task["items"])[:a.top]
            top_ids[term] = {v["video_id"] for v in videos if v.get("video_id")}
            comp = yt_competition.score(term, videos, now, subs, a.top)
            row: dict[str, Any] = {"term": term, "n_videos": len(videos)}
            if not videos:
                row["unmeasured"] = "no videos in the results"
            else:
                row.update(openness(videos, now, baselines))
                row["demand"] = {"median_views": comp.get("median_views"),
                                 "median_views_per_day": comp.get("median_views_per_day"),
                                 "below_floor": (comp.get("median_views") or 0) < a.demand_floor}
            row["search"] = {"volume": labs.get(term, {}).get("volume"), "kd_web": labs.get(term, {}).get("kd_web"),
                             "yt_interest": interest.get(term),
                             "yt_competition": comp.get("yt_competition") if videos else None,
                             "yt_competition_parts": comp.get("components")}
            out.append(row)

    if not out:
        raise Refusal("no successful SERP task in the input")
    if not baselines:
        warnings.append("no --baselines: breakouts cannot be measured, openness is spread and freshness only "
                        "(run youtube-data channel_baselines.py on the same SERP files)")
    for extra in sorted((set(labs) | set(interest)) - set(top_ids) - {normalize.term_key(a.anchor or "")}):
        warnings.append(f"{extra!r} has Labs or Trends data but no SERP; it is not ranked as a niche")

    for row in out:
        overlaps = []
        mine = top_ids[row["term"]]
        for other, ids in top_ids.items():
            if other != row["term"] and mine and ids and mine & ids:
                shared = len(mine & ids)
                overlaps.append({"term": other, "shared_videos": shared, "share": round(shared / min(len(mine), len(ids)), 3)})
        row["overlap"] = sorted(overlaps, key=lambda o: -o["share"])

    def order(r: dict[str, Any]) -> tuple:
        if r.get("openness") is None:
            return (2, 0, 0, r["term"])
        return (1 if r["demand"]["below_floor"] else 0, -r["openness"], -(r["demand"]["median_views"] or 0), r["term"])
    out.sort(key=order)
    for i, r in enumerate(out, 1):
        r["rank"] = i

    same = []
    terms = sorted(top_ids)
    for i, t1 in enumerate(terms):
        for t2 in terms[i + 1:]:
            if top_ids[t1] and top_ids[t2]:
                shared = len(top_ids[t1] & top_ids[t2])
                share = shared / min(len(top_ids[t1]), len(top_ids[t2]))
                if share >= SAME_RESULTS_SHARE:
                    same.append({"terms": [t1, t2], "shared_videos": shared, "share": round(share, 3)})
    same.sort(key=lambda s: -s["share"])

    return {"ok": True, "as_of": a.as_of, "niches": out, "same_results": same,
            "rules": {"breakout": f">= {BREAKOUT_MULTIPLE:g}x the channel's median, channel under {SMALL_CHANNEL_BELOW:,} subscribers",
                      "fresh": f"published within {FRESH_DAYS} days", "demand_floor": a.demand_floor,
                      "openness": "mean of breakouts, 1 - top-3 channel share, freshness; equal weights (ours)"},
            "interest_comparable": interest_comparable, "cost_usd": round(cost, 6),
            "errors": errors, "warnings": warnings,
            "note": "ranked by openness among niches at or over the demand floor; search numbers are reported, "
                    "not ranked; terms in same_results surface mostly the same videos and are one audience"}


def _run_reading(argv: list[str] | None) -> dict[str, Any]:
    try:
        return run(argv)
    except OSError as e:
        raise Refusal(f"cannot read input: {e}") from None


def main(argv: list[str] | None = None) -> int:
    return run_main(_run_reading, argv)


if __name__ == "__main__":
    sys.exit(main())
