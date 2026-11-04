#!/usr/bin/env python3
# Derived from youtube-agent-skill, https://github.com/Jakeschincariol/youtube-agent-skill
# commit a2feb2104981a375ffd4f87ee04f4f5344ac43c6, skills/yt-retention/retention.py.
# MIT licence, Copyright (c) 2026 Jake Schincariol; the text is in licenses/youtube-agent-skill.txt.
# Changed: the axis unit is stated (--axis percent|ratio|seconds) instead of guessed from
# max(x) <= 100.5, which read the API's 0.01..1.0 ratio as percent and Shorts under 100 s in
# seconds as percent (upstream PR #126); the watching value can be a ratio (--watch-unit); argparse
# replaces hand parsing, so --duration's value is no longer taken for the CSV path; --transcript
# without a way to place cliffs in seconds is refused instead of silently ignored; the transcript
# is read by lib/ytskills/subtitles (clean yt-dlp captions); JSON-only output; the "healthy under
# 25 %" verdict was dropped — it had no source.
"""Find where viewers leave a video, from its audience-retention curve.

  retention.py curve.csv --axis percent --duration 613
  retention.py curve.csv --axis percent --duration 613 --transcript video.srt
  retention.py studio-export.csv --axis seconds          a Short exported from Studio in seconds

The CSV's first two numeric columns are read: a position and the share still watching. State the
position's unit: `percent` of the video (0..100; youtube-data's analytics.py retention writes this),
`ratio` (0..1, the Analytics API's elapsedVideoTimeRatio as it comes) or `seconds`. The share is a
percentage unless --watch-unit ratio (the API's audienceWatchRatio as it comes; it can pass 1 where
viewers rewatch).

Three numbers, because they are three different problems:
  hook_leak   percentage points lost in the first --hook-seconds (30)
  cliffs      the five steepest single drops of more than 0.8 points — moments people left at
  slide       the mean loss per axis unit after the hook — the steady bleed of the middle

With --transcript (srt, vtt or whisper json) each cliff carries what was said within 4 s of it.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from ytskills import subtitles  # noqa: E402
from ytskills.common import Refusal, parse_duration, run  # noqa: E402

CLIFF_POINTS = 0.8
NEAR_SECONDS = 4.0


def load_csv(path: str) -> list[tuple[float, float]]:
    rows = []
    try:
        fh = open(path, newline="", encoding="utf-8-sig", errors="replace")
    except OSError as e:
        raise Refusal(f"cannot read {path}: {e.strerror}") from None
    with fh:
        for r in csv.reader(fh):
            vals = []
            for c in r:
                c = c.strip().replace("%", "").replace(",", "")
                try:
                    vals.append(float(c))
                except ValueError:
                    pass
            if len(vals) >= 2:
                rows.append((vals[0], vals[1]))
    return sorted(rows)


def analyse(rows: list[tuple[float, float]], axis: str, watch_unit: str, duration: float | None,
            hook_seconds: float = 30.0) -> dict[str, Any]:
    if len(rows) < 8:
        raise Refusal(f"only {len(rows)} data points; at least 8 are needed")
    xs = [x for x, _ in rows]
    if axis == "ratio":
        if max(xs) > 1.0001:
            raise Refusal(f"--axis ratio but positions reach {max(xs)}; is it percent or seconds?")
        rows = [(x * 100, y) for x, y in rows]
    elif axis == "percent" and max(xs) > 100.5:
        raise Refusal(f"--axis percent but positions reach {max(xs)}; is it seconds?")
    elif axis == "seconds" and duration and max(xs) > duration * 1.05:
        raise Refusal(f"positions reach {max(xs)} s, beyond --duration {duration} s")
    if watch_unit == "ratio":
        rows = [(x, y * 100) for x, y in rows]
    elif max(y for _, y in rows) <= 1.5:
        raise Refusal("every watching value is 1.5 or less — that is a ratio; pass --watch-unit ratio")
    xs = [x for x, _ in rows]
    ys = [y for _, y in rows]
    seconds_axis = axis == "seconds"

    def at_seconds(x: float) -> float | None:
        if seconds_axis:
            return x
        return x / 100.0 * duration if duration else None

    def at_percent(x: float) -> float | None:
        if not seconds_axis:
            return x
        return x / duration * 100 if duration else None

    if seconds_axis:
        cutoff, hook_basis = hook_seconds, f"first {hook_seconds:g} s"
    elif duration:
        cutoff, hook_basis = hook_seconds / duration * 100, f"first {hook_seconds:g} s"
    else:
        cutoff, hook_basis = 10.0, "first 10 % of the video (no --duration given)"
    start = ys[0] or 100.0
    hook_end = min((y for x, y in rows if x <= cutoff), default=start)
    drops = []
    for i in range(1, len(rows)):
        d = ys[i - 1] - ys[i]
        span = (xs[i] - xs[i - 1]) or 1
        drops.append((d / span, xs[i - 1], xs[i], d))
    steepest = sorted(drops, reverse=True)
    cliffs = []
    for _, x0, x1, d in steepest[:5]:
        if d <= CLIFF_POINTS:
            continue
        s, pc = at_seconds(x0), at_percent(x0)
        cliffs.append({"from": round(x0, 3), "to": round(x1, 3), "lost": round(d, 2),
                       "at_seconds": round(s, 1) if s is not None else None,
                       "at_percent": round(pc, 2) if pc is not None else None})
    middle = [r for r, x0, _, _ in drops if x0 > cutoff]
    return {
        "points": len(rows), "start": round(start, 2), "end": round(ys[-1], 2),
        "hook_window": hook_basis, "hook_leak": round(start - hook_end, 2),
        "cliffs": cliffs,
        "slide": round(sum(middle) / len(middle), 4) if middle else 0.0,
        "units": {"start/end/hook_leak/lost": "percentage points of the viewers who started",
                  "slide": "points lost per second" if seconds_axis else "points lost per 1 % of the video",
                  "from/to": "seconds" if seconds_axis else "percent of the video"},
    }


def attach_transcript(result: dict[str, Any], path: str) -> None:
    if not Path(path).exists():
        raise Refusal(f"no transcript file {path}")
    cues = subtitles.load(path)
    for c in result["cliffs"]:
        t = c["at_seconds"]
        near = [txt for s, e, txt in cues if s <= t + NEAR_SECONDS and e >= t - NEAR_SECONDS]
        c["said"] = " ".join(near)[:200]


def main(argv: list[str] | None = None) -> dict[str, Any]:
    p = argparse.ArgumentParser(prog="retention.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("csv", help="the retention curve")
    p.add_argument("--axis", required=True, choices=["percent", "ratio", "seconds"],
                   help="the unit of the position column")
    p.add_argument("--watch-unit", choices=["percent", "ratio"], default="percent",
                   help="the unit of the watching column (default percent)")
    p.add_argument("--duration", help="the video's length, seconds or ISO 8601; needed to place "
                                      "percent positions in seconds")
    p.add_argument("--hook-seconds", type=float, default=30.0, help="the hook window (default 30)")
    p.add_argument("--transcript", help="srt, vtt or whisper json of the video")
    a = p.parse_args(argv)
    duration = parse_duration(a.duration, "--duration") if a.duration else None
    if a.transcript and a.axis != "seconds" and not duration:
        raise Refusal("--transcript needs --duration when the axis is percent or ratio: without it "
                      "no cliff can be placed in the transcript")
    result = analyse(load_csv(a.csv), a.axis, a.watch_unit, duration, a.hook_seconds)
    if a.transcript:
        attach_transcript(result, a.transcript)
    return {"ok": True, "csv": a.csv, "duration_s": duration, **result}


if __name__ == "__main__":
    sys.exit(run(main))
