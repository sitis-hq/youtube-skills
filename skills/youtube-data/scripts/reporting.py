#!/usr/bin/env python3
"""Thumbnail impressions and impression CTR of own videos, from the YouTube Reporting API.

  reporting.py jobs                                   the reporting jobs of the connected channel
  reporting.py ensure-job                             create the two reach jobs that are missing
                                                      (first data in ~48 h)
  reporting.py reach --ctr-scale fraction|percent|unknown [--since DATE] [--id ID ...] [--all-days]
                                                      per video and day: impressions and CTR as
                                                      `studio` record fields
  reporting.py sources --ctr-scale fraction|percent|unknown [--since DATE] [--id ID ...]
                       [--published videos.json --first-days N]
                                                      per video and traffic source, summed over
                                                      the period (or over each video's first N
                                                      days): impressions and CTR

The Analytics API has no thumbnail impressions or CTR. The Reporting API has them in the reach
reports. `channel_reach_basic_a1` has date, channel_id, video_id, video_thumbnail_impressions,
video_thumbnail_impressions_ctr; `channel_reach_combined_a1` adds traffic_source_type,
traffic_source_detail, operating_system and device_type. It is a bulk API: a job is created once,
YouTube then writes one CSV per day about two days later, plus reports covering the 30 days before
the job was created; standard reports are kept 60 days, historical ones 30. So a job that does not
exist loses its days for good, and `ensure-job` creates both on the day a channel is connected.
Read from developers.google.com/youtube/reporting on 2026-11-04 and 2026-11-23.

`sources` sums the combined report over its period per video and traffic source. Browse features
(type 3) are split by traffic_source_detail, because YouTube's own control group — the
subscriptions feed — is one of its details; the docs do not list the detail values, so they come
out exactly as the file writes them and the reader names the subscriptions one from what it sees.
With --published (a JSON list of {video_id, published_at}, as data_api.py uploads writes it) and
--first-days N, each video counts only its first N days, so videos of different ages compare; a
video whose first days are older than the reports the API still keeps is marked `partial`.

A file read under `percent` whose largest raw CTR is at most 1 may hold fractions: the output then
carries `scale_warning`, since a fraction read as a percent passes every range check.

The docs call video_thumbnail_impressions_ctr "the percentage of impressions that resulted in a
click" and define it as clicks / impressions, without saying whether the file holds 0.045 or 4.5.
Until one real file has been compared with Studio, the scale is the caller's statement
(--ctr-scale), not this script's guess; a value that contradicts it is refused. `unknown` keeps
impressions, which do not depend on the scale, leaves CTR out of every record, and reports the
largest raw CTR value read (`ctr_raw_max`): above 1 proves the file holds percent.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

import _yt  # noqa: E402
from ytskills.common import Refusal, parse_date, run  # noqa: E402

REACH = "channel_reach_basic_a1"
COMBINED = "channel_reach_combined_a1"
JOB_NAMES = {REACH: "sitis reach", COMBINED: "sitis reach by source"}

# traffic_source_type codes, from developers.google.com/youtube/reporting/v1/reports/dimensions
# read 2026-11-23.
TRAFFIC_SOURCES = {
    "0": "direct or unknown", "1": "YouTube advertising", "3": "browse features", "4": "YouTube channels",
    "5": "YouTube search", "7": "suggested videos", "8": "other YouTube features", "9": "external",
    "11": "video cards and annotations", "14": "playlists", "17": "notifications", "18": "playlist pages",
    "19": "programming from claimed content", "20": "interactive video endscreen", "23": "stories",
    "24": "Shorts", "25": "product pages", "26": "hashtag pages", "27": "sound pages",
    "28": "live redirect", "29": "podcasts", "30": "remixed video", "31": "vertical live feed",
    "32": "related video",
}
BROWSE = "3"


def list_jobs(client: _yt.Client) -> list[dict[str, Any]]:
    return client.request("GET", _yt.REPORTING_API + "jobs").get("jobs", [])


def job_of(client: _yt.Client, report_type: str) -> dict[str, Any] | None:
    return next((j for j in list_jobs(client) if j.get("reportTypeId") == report_type), None)


def reach_job(client: _yt.Client) -> dict[str, Any] | None:
    return job_of(client, REACH)


def cmd_jobs(client: _yt.Client, a: argparse.Namespace) -> dict[str, Any]:
    return {"ok": True, "jobs": list_jobs(client)}


def cmd_ensure_job(client: _yt.Client, a: argparse.Namespace) -> dict[str, Any]:
    existing = {j.get("reportTypeId"): j for j in list_jobs(client)}
    jobs, created = {}, []
    for report_type, name in JOB_NAMES.items():
        if report_type in existing:
            jobs[report_type] = existing[report_type]
            continue
        jobs[report_type] = client.request("POST", _yt.REPORTING_API + "jobs",
                                           body={"reportTypeId": report_type, "name": name})
        created.append(report_type)
    out: dict[str, Any] = {"ok": True, "created": created, "jobs": jobs}
    if created:
        out["note"] = ("the first reports of a new job appear about 48 hours from now, with the "
                       "30 days before today")
    return out


def read_row(r: dict[str, str], scale: str) -> dict[str, Any]:
    """One reach row of either report: impressions, and CTR under the stated scale."""
    try:
        impressions = int(float(r["video_thumbnail_impressions"] or 0))
        raw = float(r["video_thumbnail_impressions_ctr"] or 0)
    except (KeyError, ValueError):
        raise Refusal("a reach report lacks video_thumbnail_impressions / _ctr columns; "
                      f"its header is {list(r)}") from None
    ctr: float | None = raw / 100 if scale == "percent" else raw
    if scale == "unknown":
        ctr = None
    elif not 0 <= ctr <= 1:
        raise Refusal(f"CTR {r['video_thumbnail_impressions_ctr']} for {r.get('video_id')} is "
                      f"not a {scale} — --ctr-scale is wrong for this file")
    d = r.get("date", "")
    day = f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 and d.isdigit() else d
    return {"video_id": r.get("video_id"), "date": day, "impressions": impressions, "ctr": ctr, "ctr_raw": raw}


def parse_reach_csv(text: str, scale: str) -> list[dict[str, Any]]:
    return [read_row(r, scale) for r in csv.DictReader(io.StringIO(text))]


def aggregate(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Several rows of one video and day add up; CTR is weighted by impressions, because the mean
    of rates would let a ten-impression row count as much as a ten-thousand one."""
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        k = (r["video_id"], r["date"])
        agg = out.setdefault(k, {"impressions": 0, "clicks": 0.0})
        agg["impressions"] += r["impressions"]
        if r["ctr"] is not None:
            agg["clicks"] += r["impressions"] * r["ctr"]
    return out


def read_reports(client: _yt.Client, report_type: str, since: str | None) -> list[str]:
    """The CSV text of every day the job holds from `since`, one version per day."""
    job = job_of(client, report_type)
    if not job:
        raise Refusal(f"no {report_type} job yet: run `reporting.py ensure-job` once; data follows in ~48 h")
    params: dict[str, Any] = {}
    if since:
        params["startTimeAtOrAfter"] = f"{parse_date(since, '--since').isoformat()}T00:00:00Z"
    reports, token = [], None
    while True:
        page = client.request("GET", f"{_yt.REPORTING_API}jobs/{job['id']}/reports",
                              {**params, "pageToken": token})
        reports += page.get("reports", [])
        token = page.get("nextPageToken")
        if not token:
            break
    # A backfill reissues a day under a new id; the newest createTime for a startTime wins.
    latest: dict[str, dict[str, Any]] = {}
    for rep in reports:
        prev = latest.get(rep["startTime"])
        if prev is None or rep.get("createTime", "") > prev.get("createTime", ""):
            latest[rep["startTime"]] = rep
    return [client.request("GET", rep["downloadUrl"], raw=True).decode("utf-8-sig")
            for rep in sorted(latest.values(), key=lambda r: r["startTime"])]


def wanted_ids(a: argparse.Namespace) -> set[str]:
    return {x.strip() for v in (a.id or []) for x in v.split(",") if x.strip()}


def cmd_reach(client: _yt.Client, a: argparse.Namespace) -> dict[str, Any]:
    texts = read_reports(client, REACH, a.since)
    rows: list[dict[str, Any]] = []
    for text in texts:
        rows += parse_reach_csv(text, a.ctr_scale)
    wanted = wanted_ids(a)
    if wanted:
        rows = [r for r in rows if r["video_id"] in wanted]
    agg = aggregate(rows)
    records = []
    for (vid, day), v in sorted(agg.items()):
        record = {"video_id": vid, "as_of": day, "available": True, "impressions": v["impressions"],
                  "source": "reporting-api"}
        if a.ctr_scale != "unknown":
            record["ctr"] = round(v["clicks"] / v["impressions"], 6) if v["impressions"] else 0.0
        records.append(record)
    if not a.all_days:
        newest: dict[str, dict[str, Any]] = {}
        for r in records:
            newest[r["video_id"]] = r  # sorted by day, so the last one is the newest
        records = list(newest.values())
    days = sorted({r["as_of"] for r in records})
    latest_day = days[-1] if days else None
    missing = [{"video_id": v, "as_of": latest_day, "available": False, "source": "reporting-api"}
               for v in sorted(wanted - {r["video_id"] for r in records})] if latest_day else []
    out_units = ({"ctr": "left out: the scale is unknown"} if a.ctr_scale == "unknown"
                 else {"ctr": "a fraction 0..1, as the studio record wants"})
    return {"ok": True, "reports_read": len(texts), "records": records + missing,
            "ctr_raw_max": max((r["ctr_raw"] for r in rows), default=None),
            "units": out_units,
            "note": "each element is the fields of a `studio` record; videos asked for with no row "
                    "come back available=false"}


def source_of(r: dict[str, str]) -> str:
    code = (r.get("traffic_source_type") or "").strip()
    name = TRAFFIC_SOURCES.get(code, f"type {code}")
    if code == BROWSE:
        return f"{name}: {(r.get('traffic_source_detail') or '').strip() or '(no detail)'}"
    return name


def load_published(path: str) -> dict[str, str]:
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise Refusal(f"cannot read {path}: {e}") from None
    rows = doc.get("videos", doc) if isinstance(doc, dict) else doc
    out = {}
    for r in rows if isinstance(rows, list) else []:
        vid, when = (r or {}).get("video_id") or (r or {}).get("id"), (r or {}).get("published_at")
        if vid and when:
            out[vid] = str(when)[:10]
    if not out:
        raise Refusal(f"{path} holds no video_id with published_at")
    return out


def cmd_sources(client: _yt.Client, a: argparse.Namespace) -> dict[str, Any]:
    if bool(a.published) != bool(a.first_days):
        raise Refusal("--published and --first-days go together")
    published = load_published(a.published) if a.published else {}
    texts = read_reports(client, COMBINED, a.since)
    wanted = wanted_ids(a)
    sums: dict[tuple[str, str], dict[str, Any]] = {}
    raw_max: float | None = None
    days: set[str] = set()
    for text in texts:
        for r in csv.DictReader(io.StringIO(text)):
            if "traffic_source_type" not in r:
                raise Refusal(f"a combined reach report lacks traffic_source_type; its header is {list(r)}")
            if wanted and r.get("video_id") not in wanted:
                continue
            one = read_row(r, a.ctr_scale)
            if published:
                start = published.get(one["video_id"])
                if not start:
                    continue
                if one["date"] >= (date.fromisoformat(start) + timedelta(days=a.first_days)).isoformat():
                    continue
            raw_max = one["ctr_raw"] if raw_max is None else max(raw_max, one["ctr_raw"])
            days.add(one["date"])
            agg = sums.setdefault((one["video_id"], source_of(r)), {"impressions": 0, "clicks": 0.0})
            agg["impressions"] += one["impressions"]
            if one["ctr"] is not None:
                agg["clicks"] += one["impressions"] * one["ctr"]
    rows = []
    for (video_id, source), v in sorted(sums.items()):
        row: dict[str, Any] = {"video_id": video_id, "traffic_source": source, "impressions": v["impressions"]}
        if a.ctr_scale != "unknown":
            row["ctr"] = round(v["clicks"] / v["impressions"], 6) if v["impressions"] else None
        rows.append(row)
    span = sorted(days)
    if published and span:
        for row in rows:
            row["partial"] = published[row["video_id"]] < span[0]
    out: dict[str, Any] = {}
    if a.ctr_scale == "percent" and raw_max is not None and raw_max <= 1 and len(rows) >= 5:
        out["scale_warning"] = (f"every raw CTR is at most {raw_max}: this file may hold fractions; "
                                "check the scale before trusting CTR")
    return {"ok": True, "reports_read": len(texts), "period": [span[0], span[-1]] if span else None,
            "rows": rows, "ctr_raw_max": raw_max, **out,
            "units": ({"ctr": "left out: the scale is unknown"} if a.ctr_scale == "unknown"
                      else {"ctr": "a fraction 0..1, weighted by impressions over the period"}),
            "note": "summed over operating systems and devices; browse features are split by the "
                    "detail the file gives; reports older than 60 days are gone from the API"}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="reporting.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("jobs", help="list reporting jobs")
    sub.add_parser("ensure-job", help=f"create the {REACH} and {COMBINED} jobs that are missing")
    r = sub.add_parser("reach", help="impressions and CTR per video and day")
    s = sub.add_parser("sources", help="impressions and CTR per video and traffic source over a period")
    for sp in (r, s):
        sp.add_argument("--ctr-scale", required=True, choices=["fraction", "percent", "unknown"],
                        help="how the file writes CTR; unknown leaves CTR out (see the module help)")
        sp.add_argument("--since", help="only reports for days from this date")
        sp.add_argument("--id", action="append", help="only these videos; repeatable or a comma list")
    s.add_argument("--published", help="JSON list of {video_id, published_at}; with --first-days")
    s.add_argument("--first-days", type=int, help="count each video's first N days only")
    r.add_argument("--all-days", action="store_true", help="every day, not only each video's newest")
    return p


COMMANDS = {"jobs": cmd_jobs, "ensure-job": cmd_ensure_job, "reach": cmd_reach, "sources": cmd_sources}


def main(argv: list[str] | None = None) -> dict[str, Any]:
    a = parser().parse_args(argv)
    client = _yt.Client()
    out = COMMANDS[a.command](client, a)
    out["quota"] = client.quota()
    return out


if __name__ == "__main__":
    sys.exit(run(main))
