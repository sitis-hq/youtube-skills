#!/usr/bin/env python3
"""Read the YouTube Analytics API (v2 reports.query) for the connected channel.

  analytics.py video-metrics --id ID ... --start D --end D    per-video views, watch time, AVD, APV, subs
  analytics.py channel       --start D --end D [--by day]     channel totals for a period
  analytics.py traffic       [--id ID] --start D --end D      views by traffic source type
  analytics.py retention     --id ID --start D --end D --duration S --csv OUT
                             the retention curve, written as the two-column CSV retention.py reads
  analytics.py query         --metrics a,b [--dimensions d] [--filters f] --start D --end D

There is no thumbnail-impressions or impression-CTR metric in this API: those come from the
Reporting API's reach reports (reporting.py) or a Studio export. `query` refuses the names that do
not exist here rather than letting the API answer with a bare 400.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

import _yt  # noqa: E402
from ytskills.common import Refusal, parse_date, parse_duration, run  # noqa: E402

# Names agents and upstream scripts ask for that the Analytics API does not have (metrics page
# https://developers.google.com/youtube/analytics/metrics read 2026-11-04).
NOT_IN_ANALYTICS = {
    "impressions": "here it is the old name of adImpressions — ad impressions, a monetary metric, "
                   "not thumbnail impressions",
    "impressionClickThroughRate": "no such metric; thumbnail CTR is video_thumbnail_impressions_ctr "
                                  "in the Reporting API reach reports (reporting.py) or Studio",
    "impressionsClickThroughRate": "no such metric; see reporting.py",
    "videoThumbnailImpressions": "no such metric; the Reporting API has video_thumbnail_impressions",
    "videoThumbnailImpressionsClickRate": "no such metric; see reporting.py",
    "ctr": "no such metric; see reporting.py",
}

VIDEO_METRICS = ["views", "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage",
                 "subscribersGained", "subscribersLost", "likes", "comments", "shares"]
CHANNEL_METRICS = VIDEO_METRICS


def rows_of(answer: dict[str, Any]) -> list[dict[str, Any]]:
    names = [h["name"] for h in answer.get("columnHeaders", [])]
    return [dict(zip(names, r)) for r in answer.get("rows", []) or []]


def period(a: argparse.Namespace) -> dict[str, str]:
    end = parse_date(a.end, "--end") if a.end else date.today()
    start = parse_date(a.start, "--start") if a.start else end - timedelta(days=a.days - 1)
    if start > end:
        raise Refusal(f"--start {start} is after --end {end}")
    return {"startDate": start.isoformat(), "endDate": end.isoformat()}


def report(client: _yt.Client, a: argparse.Namespace, **params: Any) -> list[dict[str, Any]]:
    for m in str(params.get("metrics", "")).split(","):
        if m in NOT_IN_ANALYTICS:
            raise Refusal(f"metric {m!r}: {NOT_IN_ANALYTICS[m]}")
    client.calls["analytics.reports.query"] = client.calls.get("analytics.reports.query", 0) + 1
    return rows_of(client.request("GET", _yt.ANALYTICS_API, {"ids": "channel==MINE", **period(a), **params}))


def ids_of(a: argparse.Namespace) -> list[str]:
    return [x.strip() for v in (a.id or []) for x in v.split(",") if x.strip()]


def cmd_video_metrics(client: _yt.Client, a: argparse.Namespace) -> dict[str, Any]:
    ids = ids_of(a)
    if not ids:
        raise Refusal("pass --id for each video")
    rows: list[dict[str, Any]] = []
    # The video dimension takes at most 200 rows per answer and needs a sort.
    for batch in _yt.batches(ids, 200):
        rows += report(client, a, dimensions="video", metrics=",".join(VIDEO_METRICS),
                       filters="video==" + ",".join(batch), sort="-views", maxResults=200)
    seen = {r["video"] for r in rows}
    return {"ok": True, **period(a), "units": UNITS_NOTE, "videos": rows,
            # A video with no views in the period has no row; that is zero, not an error.
            "no_rows": [i for i in ids if i not in seen]}


def cmd_channel(client: _yt.Client, a: argparse.Namespace) -> dict[str, Any]:
    params: dict[str, Any] = {"metrics": ",".join(CHANNEL_METRICS)}
    if a.by:
        params.update(dimensions=a.by, sort=a.by)
    return {"ok": True, **period(a), "units": UNITS_NOTE, "rows": report(client, a, **params)}


def cmd_traffic(client: _yt.Client, a: argparse.Namespace) -> dict[str, Any]:
    params: dict[str, Any] = {"dimensions": "insightTrafficSourceType",
                              "metrics": "views,estimatedMinutesWatched", "sort": "-views"}
    ids = ids_of(a)
    if ids:
        params["filters"] = "video==" + ",".join(ids[:200])
    rows = report(client, a, **params)
    total = sum(r.get("views", 0) or 0 for r in rows)
    for r in rows:
        r["share"] = round((r.get("views", 0) or 0) / total, 4) if total else None
    return {"ok": True, **period(a), "videos": ids or "channel", "rows": rows,
            "units": {"share": "fraction of the period's views, 0..1",
                      "estimatedMinutesWatched": "minutes"}}


def retention_csv(rows: list[dict[str, Any]], path: str) -> int:
    """Write the curve as retention.py reads it: position in percent of the video (the API's ratio
    0.01..1.0 times 100) and percent still watching (audienceWatchRatio times 100; above 100 where
    viewers rewatch)."""
    points = sorted((float(r["elapsedVideoTimeRatio"]), float(r["audienceWatchRatio"])) for r in rows)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["position_percent", "watching_percent"])
        for x, y in points:
            w.writerow([round(x * 100, 3), round(y * 100, 3)])
    return len(points)


def cmd_retention(client: _yt.Client, a: argparse.Namespace) -> dict[str, Any]:
    ids = ids_of(a)
    if len(ids) != 1:
        raise Refusal("the retention report takes exactly one --id")
    duration = parse_duration(a.duration, "--duration")
    params: dict[str, Any] = {"dimensions": "elapsedVideoTimeRatio",
                              "metrics": "audienceWatchRatio,relativeRetentionPerformance",
                              "filters": f"video=={ids[0]}" + (f";audienceType=={a.audience_type}"
                                                               if a.audience_type else ""),
                              "sort": "elapsedVideoTimeRatio"}
    rows = report(client, a, **params)
    if not rows:
        return {"ok": True, "available": False, "video_id": ids[0], **period(a),
                "reason": "the API returned no retention points — too few views in the period, "
                          "or the video is not this channel's"}
    n = retention_csv(rows, a.csv)
    rel = [float(r["relativeRetentionPerformance"]) for r in rows
           if r.get("relativeRetentionPerformance") is not None]
    here = Path(__file__).resolve()
    retention_py = here.parents[2] / "youtube-metrics" / "scripts" / "retention.py"
    return {
        "ok": True, "available": True, "video_id": ids[0], **period(a), "points": n, "csv": a.csv,
        "duration_s": duration,
        "relative_retention_mean": round(sum(rel) / len(rel), 3) if rel else None,
        "units": {"csv": "position_percent 0..100 of the video, watching_percent (100 = every "
                         "viewer who started; above 100 means rewatching)",
                  "relative_retention_mean": "0..1 against videos of similar length; 0.5 is the median"},
        "next": f"python3 {retention_py} {a.csv} --axis percent --duration {duration:g}",
    }


def cmd_query(client: _yt.Client, a: argparse.Namespace) -> dict[str, Any]:
    params = {"metrics": a.metrics, "dimensions": a.dimensions, "filters": a.filters,
              "sort": a.sort, "maxResults": a.max_results, "currency": a.currency}
    return {"ok": True, **period(a), "rows": report(client, a, **params)}


UNITS_NOTE = {
    "estimatedMinutesWatched": "minutes",
    "averageViewDuration": "seconds",
    "averageViewPercentage": "percent 0..100 of the video (the docs do not state the scale; "
                             "values come back like 41.7)",
}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="analytics.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    def with_period(sp: argparse.ArgumentParser) -> argparse.ArgumentParser:
        sp.add_argument("--start", help="first day YYYY-MM-DD (or use --days)")
        sp.add_argument("--end", help="last day YYYY-MM-DD (default today; the API lags 2-3 days)")
        sp.add_argument("--days", type=int, default=28, help="period length when --start is absent")
        return sp

    vm = with_period(sub.add_parser("video-metrics", help="per-video metrics for a period"))
    vm.add_argument("--id", action="append", help="a video id or a comma list; repeatable")
    ch = with_period(sub.add_parser("channel", help="channel totals for a period"))
    ch.add_argument("--by", choices=["day", "month"], help="split by day or month")
    tr = with_period(sub.add_parser("traffic", help="views by traffic source type"))
    tr.add_argument("--id", action="append", help="limit to these videos (default: the channel)")
    rt = with_period(sub.add_parser("retention", help="the retention curve of one video"))
    rt.add_argument("--id", action="append", required=True)
    rt.add_argument("--duration", required=True,
                    help="the video's length, seconds or ISO 8601 (videos' duration_s); retention.py "
                         "needs it to turn percent positions into seconds")
    rt.add_argument("--csv", required=True, help="where to write the curve")
    rt.add_argument("--audience-type", choices=["ORGANIC", "AD_INSTREAM", "AD_INDISPLAY"])
    q = with_period(sub.add_parser("query", help="any other report"))
    q.add_argument("--metrics", required=True)
    q.add_argument("--dimensions")
    q.add_argument("--filters")
    q.add_argument("--sort")
    q.add_argument("--max-results", type=int)
    q.add_argument("--currency", help="for revenue metrics, e.g. USD")
    return p


COMMANDS = {"video-metrics": cmd_video_metrics, "channel": cmd_channel, "traffic": cmd_traffic,
            "retention": cmd_retention, "query": cmd_query}


def main(argv: list[str] | None = None) -> dict[str, Any]:
    a = parser().parse_args(argv)
    client = _yt.Client()
    out = COMMANDS[a.command](client, a)
    out["quota"] = client.quota()
    return out


if __name__ == "__main__":
    sys.exit(run(main))
