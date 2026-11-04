#!/usr/bin/env python3
"""Thumbnail impressions and impression CTR of own videos, from the YouTube Reporting API.

  reporting.py jobs                                   the reporting jobs of the connected channel
  reporting.py ensure-job                             create the reach job once (first data in ~48 h)
  reporting.py reach --ctr-scale fraction|percent [--since DATE] [--id ID ...] [--all-days]
                                                      per video and day: impressions and CTR as
                                                      `studio` record fields

The Analytics API has no thumbnail impressions or CTR. The Reporting API has them in the reach
reports (`channel_reach_basic_a1`: date, channel_id, video_id, video_thumbnail_impressions,
video_thumbnail_impressions_ctr). It is a bulk API: a job is created once, YouTube then writes one
CSV per day about two days later, plus 30 days of history at creation; standard reports are kept
60 days, historical ones 30. Read from developers.google.com/youtube/reporting on 2026-11-04.

The docs call video_thumbnail_impressions_ctr "the percentage of impressions that resulted in a
click" and define it as clicks / impressions, without saying whether the file holds 0.045 or 4.5.
Until one real file has been compared with Studio, the scale is the caller's statement
(--ctr-scale), not this script's guess; a value that contradicts it is refused.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

import _yt  # noqa: E402
from ytskills.common import Refusal, parse_date, run  # noqa: E402

REACH = "channel_reach_basic_a1"


def list_jobs(client: _yt.Client) -> list[dict[str, Any]]:
    return client.request("GET", _yt.REPORTING_API + "jobs").get("jobs", [])


def reach_job(client: _yt.Client) -> dict[str, Any] | None:
    return next((j for j in list_jobs(client) if j.get("reportTypeId") == REACH), None)


def cmd_jobs(client: _yt.Client, a: argparse.Namespace) -> dict[str, Any]:
    return {"ok": True, "jobs": list_jobs(client)}


def cmd_ensure_job(client: _yt.Client, a: argparse.Namespace) -> dict[str, Any]:
    job = reach_job(client)
    if job:
        return {"ok": True, "created": False, "job": job}
    job = client.request("POST", _yt.REPORTING_API + "jobs",
                         body={"reportTypeId": REACH, "name": "sitis reach"})
    return {"ok": True, "created": True, "job": job,
            "note": "the first reports appear about 48 hours from now, with 30 days of history"}


def parse_reach_csv(text: str, scale: str) -> list[dict[str, Any]]:
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        try:
            impressions = int(float(r["video_thumbnail_impressions"] or 0))
            ctr = float(r["video_thumbnail_impressions_ctr"] or 0)
        except (KeyError, ValueError):
            raise Refusal("a reach report lacks video_thumbnail_impressions / _ctr columns; "
                          f"its header is {list(r)}") from None
        if scale == "percent":
            ctr /= 100
        if not 0 <= ctr <= 1:
            raise Refusal(f"CTR {r['video_thumbnail_impressions_ctr']} for {r.get('video_id')} is "
                          f"not a {scale} — --ctr-scale is wrong for this file")
        d = r.get("date", "")
        day = f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 and d.isdigit() else d
        rows.append({"video_id": r.get("video_id"), "date": day, "impressions": impressions, "ctr": ctr})
    return rows


def aggregate(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Several rows of one video and day add up; CTR is weighted by impressions, because the mean
    of rates would let a ten-impression row count as much as a ten-thousand one."""
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        k = (r["video_id"], r["date"])
        agg = out.setdefault(k, {"impressions": 0, "clicks": 0.0})
        agg["impressions"] += r["impressions"]
        agg["clicks"] += r["impressions"] * r["ctr"]
    return out


def cmd_reach(client: _yt.Client, a: argparse.Namespace) -> dict[str, Any]:
    job = reach_job(client)
    if not job:
        raise Refusal(f"no {REACH} job yet: run `reporting.py ensure-job` once; data follows in ~48 h")
    params: dict[str, Any] = {}
    if a.since:
        params["startTimeAtOrAfter"] = f"{parse_date(a.since, '--since').isoformat()}T00:00:00Z"
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
    rows: list[dict[str, Any]] = []
    for rep in sorted(latest.values(), key=lambda r: r["startTime"]):
        payload = client.request("GET", rep["downloadUrl"], raw=True)
        rows += parse_reach_csv(payload.decode("utf-8-sig"), a.ctr_scale)
    wanted = {x.strip() for v in (a.id or []) for x in v.split(",") if x.strip()}
    if wanted:
        rows = [r for r in rows if r["video_id"] in wanted]
    agg = aggregate(rows)
    records = []
    for (vid, day), v in sorted(agg.items()):
        ctr = round(v["clicks"] / v["impressions"], 6) if v["impressions"] else 0.0
        records.append({"video_id": vid, "as_of": day, "available": True,
                        "impressions": v["impressions"], "ctr": ctr, "source": "reporting-api"})
    if not a.all_days:
        newest: dict[str, dict[str, Any]] = {}
        for r in records:
            newest[r["video_id"]] = r  # sorted by day, so the last one is the newest
        records = list(newest.values())
    days = sorted({r["as_of"] for r in records})
    latest_day = days[-1] if days else None
    missing = [{"video_id": v, "as_of": latest_day, "available": False, "source": "reporting-api"}
               for v in sorted(wanted - {r["video_id"] for r in records})] if latest_day else []
    return {"ok": True, "reports_read": len(latest), "records": records + missing,
            "units": {"ctr": "a fraction 0..1, as the studio record wants"},
            "note": "each element is the fields of a `studio` record; videos asked for with no row "
                    "come back available=false"}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="reporting.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("jobs", help="list reporting jobs")
    sub.add_parser("ensure-job", help=f"create the {REACH} job when it is missing")
    r = sub.add_parser("reach", help="impressions and CTR per video and day")
    r.add_argument("--ctr-scale", required=True, choices=["fraction", "percent"],
                   help="how the file writes CTR; see the module help")
    r.add_argument("--since", help="only reports for days from this date")
    r.add_argument("--id", action="append", help="only these videos; repeatable or a comma list")
    r.add_argument("--all-days", action="store_true", help="every day, not only each video's newest")
    return p


COMMANDS = {"jobs": cmd_jobs, "ensure-job": cmd_ensure_job, "reach": cmd_reach}


def main(argv: list[str] | None = None) -> dict[str, Any]:
    a = parser().parse_args(argv)
    client = _yt.Client()
    out = COMMANDS[a.command](client, a)
    out["quota"] = client.quota()
    return out


if __name__ == "__main__":
    sys.exit(run(main))
