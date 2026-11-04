#!/usr/bin/env python3
"""Turn a YouTube Studio Analytics export (Advanced mode, Reach) into `studio` record fields.

Studio exports impressions and impression click-through rate per video as CSV, with the rate in
percent ("Impressions click-through rate (%)": 4.5 means 4.5 %). The `studio` record stores a
fraction (0.045), and records.py refuses a percentage rather than guess — so the conversion is done
here, once, from the column header, not by the agent in its head.

  studio_reach.py --csv "Table data.csv" --as-of 2026-11-03 [--video ID ...]

Prints {"ok": true, "rows": [...], "skipped": [...]}: each row carries exactly the fields of
`records.py write studio`. A video passed with --video that the export does not carry gets a row
with available=false, because "no data" is written, not skipped (youtube-records).

Standard library only: Python 3.11.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date
from typing import Any

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


class Refusal(Exception):
    pass


def _norm(header: str) -> str:
    return re.sub(r"\s+", " ", header.strip().lower())


def find_columns(headers: list[str]) -> dict[str, Any]:
    """Locate the id, impressions and CTR columns; say whether the CTR column is in percent."""
    normed = [_norm(h) for h in headers]
    cols: dict[str, Any] = {}
    for i, h in enumerate(normed):
        if h in ("content", "video", "video id") and "id" not in cols:
            cols["id"] = i
        elif "click-through" in h or "click through" in h or h.endswith("ctr") or "ctr (" in h:
            cols["ctr"] = i
            cols["ctr_percent"] = "%" in h
        elif h.startswith("impressions") and "impressions" not in cols:
            cols["impressions"] = i
    missing = [n for n in ("id", "impressions", "ctr") if n not in cols]
    if missing:
        raise Refusal(f"the export has no {', '.join(missing)} column; headers: {headers}")
    return cols


def _number(text: str) -> float | None:
    text = text.strip().replace(" ", "").replace(",", "").rstrip("%")
    if text in ("", "—", "-", "–"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse(rows: list[list[str]], as_of: str, expected: list[str], ctr_unit: str | None) -> dict[str, Any]:
    if not rows:
        raise Refusal("the export is empty")
    cols = find_columns(rows[0])
    percent = cols["ctr_percent"] if ctr_unit is None else ctr_unit == "percent"
    if ctr_unit is None and not cols["ctr_percent"]:
        # A header without "%" could be either scale; a wrong guess is a 100x error downstream.
        raise Refusal("the CTR column does not say its unit; pass --ctr-unit percent or fraction")
    out: dict[str, dict[str, Any]] = {}
    skipped: list[dict[str, str]] = []
    for line in rows[1:]:
        if len(line) <= max(cols["id"], cols["impressions"], cols["ctr"]):
            continue
        vid = line[cols["id"]].strip()
        if not VIDEO_ID.match(vid):
            # The "Total" row and channel-level lines are not videos.
            skipped.append({"value": vid, "why": "not a video id"})
            continue
        impressions = _number(line[cols["impressions"]])
        ctr = _number(line[cols["ctr"]])
        row: dict[str, Any] = {"video_id": vid, "as_of": as_of, "source": "studio-export"}
        if impressions is None or ctr is None:
            row["available"] = False
        else:
            fraction = ctr / 100 if percent else ctr
            if not 0 <= fraction <= 1:
                raise Refusal(f"{vid}: CTR {ctr} is outside 0..1 as a fraction — check --ctr-unit")
            row.update(available=True, impressions=int(round(impressions)), ctr=round(fraction, 6))
        out[vid] = row
    for vid in expected:
        if vid not in out:
            out[vid] = {"video_id": vid, "as_of": as_of, "available": False, "source": "studio-export"}
    return {"ok": True, "as_of": as_of, "ctr_unit_read": "percent" if percent else "fraction",
            "rows": list(out.values()), "skipped": skipped}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="studio_reach.py", description=__doc__.split("\n\n")[0])
    p.add_argument("--csv", required=True, help="the exported table (Table data.csv)")
    p.add_argument("--as-of", required=True, help="the day the numbers describe, YYYY-MM-DD")
    p.add_argument("--video", action="append", default=[],
                   help="a video that must get a row; missing from the export → available=false")
    p.add_argument("--ctr-unit", choices=("percent", "fraction"),
                   help="only when the CTR header does not show %%")
    args = p.parse_args(argv)
    try:
        try:
            as_of = date.fromisoformat(args.as_of).isoformat()
        except ValueError:
            raise Refusal(f"--as-of must be YYYY-MM-DD, got {args.as_of!r}") from None
        for vid in args.video:
            if not VIDEO_ID.match(vid):
                raise Refusal(f"--video {vid!r} is not an 11-character video id")
        try:
            with open(args.csv, encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.reader(fh))
        except OSError as e:
            raise Refusal(f"cannot read {args.csv}: {e.strerror}") from None
        out = parse(rows, as_of, args.video, args.ctr_unit)
    except Refusal as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
