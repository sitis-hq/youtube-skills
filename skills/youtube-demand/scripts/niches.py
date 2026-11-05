#!/usr/bin/env python3
"""Rank niche candidates by demand AND competition, from saved DataForSEO responses.

A niche that many people watch is not the same as a niche a new channel can enter: the most watched
sub-genres are held by the biggest channels. So a niche is scored on both sides, with the tiers the
idea score uses (lib/ytskills/scoring.py), and the output says which numbers were measured.

  niches.py --serp F [--serp F2 ...] [--labs F ...] [--trends F ...] [--anchor TERM]
            [--channels F] [--top 20] [--as-of YYYY-MM-DD]

  --serp     /v3/serp/youtube/organic/live/advanced, one task per niche term. Every niche is a SERP
             term; Labs or Trends terms with no SERP are listed in `warnings` and not ranked.
  --labs     keyword_overview for the same terms -> volume (Google web) and kd_web
  --trends   Trends explore, "type": "youtube", up to 5 terms a request -> yt_interest
  --anchor   one term put into EVERY Trends request. Each request is rescaled so the anchor reads the
             same as in the first one; that makes indices of different requests comparable. Without
             it, indices from more than one request are not used for demand (a warning says so).
  --channels youtube-data `channels` output: subscriber counts, the authority part of competition

Per niche:
  demand       0-5: max(volume tier, interest tier); none measured -> the niche is not scored
  competition  yt_competition 0..1 over the top results, with its parts (yt_competition.py)
  opportunity  5 * (1 - yt_competition)
  niche_score  0-100 from demand and opportunity, in the idea score's ratio between them
  overlap      videos the niche's top results share with each other niche. Two terms whose results
               are mostly the same videos are one audience, not two niches: see `same_results`.
  now          the median views per day of age of the top results, and the top three videos —
               what the niche pulls today, reported for the reader and not scored twice (it is
               already inside competition's traffic part).

Prints {"ok": true, "niches": [...ranked], "same_results": [...], ...}. A refusal exits 2.
Standard library only: Python 3.11.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "lib"))
sys.path.insert(0, str(HERE))

import normalize  # noqa: E402
import yt_competition  # noqa: E402
from ytskills import scoring  # noqa: E402
from ytskills.common import Refusal, run as run_main  # noqa: E402

SAME_RESULTS_SHARE = 0.5   # half of the smaller top list shared: the two queries surface one audience


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
    """yt_interest per term on one scale, whether it is comparable across terms, and the cost."""
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
    if not batches:
        return {}, True, cost
    if len(batches) == 1:
        return batches[0], True, cost
    if not anchor:
        warnings.append(f"Trends came in {len(batches)} requests without an --anchor: their indices are on "
                        "different scales, so yt_interest is reported but not used for demand")
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
            warnings.append(f"the anchor reads 0 in Trends request {i + 1}; its terms cannot be rescaled and "
                            "are left out of demand")
            comparable = False
            continue
        factor = reference / b[key]
        for k, v in b.items():
            # Rescaled values may pass 100: the scale is the first request's, not each request's own.
            merged.setdefault(k, round(v * factor, 1))
    return merged, comparable, cost


def run(argv: list[str] | None = None) -> dict[str, Any]:
    p = argparse.ArgumentParser(description="Rank niche candidates by demand and competition (see the file's docstring).")
    p.add_argument("--serp", action="append", default=[], help="YouTube organic SERP response, one task per niche term (repeatable)")
    p.add_argument("--labs", action="append", default=[], help="Labs keyword_overview response for the same terms (repeatable)")
    p.add_argument("--trends", action="append", default=[], help="Trends explore response, type=youtube (repeatable)")
    p.add_argument("--anchor", help="the term present in every Trends request, to put them on one scale")
    p.add_argument("--channels", action="append", default=[], help="youtube-data `channels` output for subscriber counts")
    p.add_argument("--top", type=int, default=yt_competition.TOP, help="top results read per niche (default 20)")
    p.add_argument("--as-of", help="count ages to this day, YYYY-MM-DD (default: each SERP's datetime)")
    a = p.parse_args(argv)
    if not a.serp:
        raise Refusal("pass --serp: every niche is a term with its YouTube results")
    if a.top < 1:
        raise Refusal("--top must be at least 1")
    fixed_now = _as_of_now(a.as_of)

    errors: list[dict[str, Any]] = []
    warnings: list[str] = []
    labs, cost = labs_metrics(a.labs, errors)
    interest, interest_comparable, trends_cost = trends_interest(a.trends, a.anchor, errors, warnings)
    cost += trends_cost
    try:
        subs = yt_competition.subscribers_from(a.channels)
    except yt_competition.Refusal as e:
        raise Refusal(str(e)) from None

    niches: dict[str, dict[str, Any]] = {}
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
            if not term or term in niches:
                if term:
                    warnings.append(f"{term!r} has more than one SERP; the first one is used")
                continue
            now = fixed_now or yt_competition.parse_when(task["datetime"]) or datetime.now(timezone.utc)
            videos = yt_competition.videos_from_serp(task["items"])[:a.top]
            comp = yt_competition.score(term, videos, now, subs, a.top)
            top_ids[term] = {v["video_id"] for v in videos if v.get("video_id")}
            ranked = []
            for v in videos:
                age = yt_competition.age_days(v, now)
                if age is not None and isinstance(v.get("views"), (int, float)):
                    ranked.append({"video_id": v.get("video_id"), "title": v.get("title"),
                                   "channel_id": v.get("channel_id"),
                                   "views_per_day": round(v["views"] / max(age, 1.0), 1)})
            ranked.sort(key=lambda r: -r["views_per_day"])
            niches[term] = {"term": term, "competition": comp, "top_videos": ranked[:3]}

    if not niches:
        raise Refusal("no successful SERP task in the input")
    for extra in sorted((set(labs) | set(interest)) - set(niches) - {normalize.term_key(a.anchor or "")}):
        warnings.append(f"{extra!r} has Labs or Trends data but no SERP; it is not ranked as a niche")

    out = []
    for term, n in niches.items():
        comp = n["competition"]
        volume = labs.get(term, {}).get("volume")
        kd_web = labs.get(term, {}).get("kd_web")
        yt_interest = interest.get(term)
        dem = scoring.demand(volume, yt_interest if interest_comparable else None)
        opp = scoring.opportunity(comp["yt_competition"] if comp["n_videos"] else None, kd_web)
        overlaps = []
        for other, ids in top_ids.items():
            if other == term or not top_ids[term] or not ids:
                continue
            shared = len(top_ids[term] & ids)
            if shared:
                overlaps.append({"term": other, "shared_videos": shared,
                                 "share": round(shared / min(len(top_ids[term]), len(ids)), 3)})
        overlaps.sort(key=lambda o: -o["share"])
        row: dict[str, Any] = {
            "term": term,
            "niche_score": round(scoring.measured_score(dem[0], opp[0]), 1) if dem and opp else None,
            "demand": {"tier": dem[0] if dem else None, "basis": dem[1] if dem else None,
                       "volume": volume, "yt_interest": yt_interest, "kd_web": kd_web},
            "opportunity": {"value": round(opp[0], 2) if opp else None, "basis": opp[1] if opp else None},
            "competition": {k: comp.get(k) for k in ("yt_competition", "confidence", "components", "weights",
                                                      "n_videos", "median_subscribers", "subscribers_known")},
            "now": {"median_views_per_day": comp.get("median_views_per_day"),
                    "median_age_days": comp.get("median_age_days"),
                    "shorts_share": comp.get("shorts_share"), "top_videos": n["top_videos"]},
            "overlap": overlaps,
        }
        if not dem:
            row["unscored"] = "no demand measured: pass --labs (keyword_overview) or --trends for this term"
        elif not opp:
            row["unscored"] = "no competition: the SERP had no videos and Labs has no kd_web"
        out.append(row)
    out.sort(key=lambda r: (r["niche_score"] is None, -(r["niche_score"] or 0), r["term"]))
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
    if not any(r["competition"]["subscribers_known"] for r in out):
        warnings.append("no subscriber counts: competition is traffic and targeting only (pass --channels "
                        "from youtube-data once the channel is connected)")

    return {"ok": True, "as_of": a.as_of, "niches": out, "same_results": same,
            "interest_comparable": interest_comparable, "cost_usd": round(cost, 6),
            "errors": errors, "warnings": warnings,
            "note": "niche_score weighs measured demand against measured competition (0-100); "
                    "volume is Google web search volume, yt_interest a relative index; terms in "
                    "same_results surface mostly the same videos and are one audience"}


def _run_reading(argv: list[str] | None) -> dict[str, Any]:
    try:
        return run(argv)
    except OSError as e:
        raise Refusal(f"cannot read input: {e}") from None


def main(argv: list[str] | None = None) -> int:
    return run_main(_run_reading, argv)


if __name__ == "__main__":
    sys.exit(main())
