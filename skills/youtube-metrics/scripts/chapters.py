#!/usr/bin/env python3
# Derived from youtube-agent-skill, https://github.com/Jakeschincariol/youtube-agent-skill
# commit a2feb2104981a375ffd4f87ee04f4f5344ac43c6, skills/yt-chapters/chapters.py.
# MIT licence, Copyright (c) 2026 Jake Schincariol; the text is in licenses/youtube-agent-skill.txt.
# Changed: a `validate` command checks the chapter block of an existing description (the drafting
# was all upstream had); YouTube's rules carry their source; the transcript reader is
# lib/ytskills/subtitles; vocabulary is read in any script, and the English stop words apply only
# to --lang en; argparse and JSON-only output.
"""YouTube chapters: check a description's chapter block, or draft one from a transcript.

  chapters.py validate --description-file desc.txt [--duration 613]
  chapters.py draft video.srt [--target 7] [--lang en]

YouTube's rules for chapters written in the description (support.google.com/youtube/answer/9884579,
read 2026-11-04): the first timestamp is 00:00, there are at least three, in ascending order, and
each chapter is at least 10 seconds long. A block that breaks one does not become chapters, and
YouTube does not say so — hence the check.

Draft boundaries come from pauses and from how much the vocabulary changes across them; the titles
are the frequent words of each section, to be rewritten, not published.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from ytskills import subtitles  # noqa: E402
from ytskills.common import Refusal, parse_duration, run  # noqa: E402

MIN_SECONDS = 10.0
MIN_COUNT = 3
STOP = set("the a an of for to in on and or is are was were be been with this that it as at by from "
           "you your i my we our they them he she but so if then than there here what which who how "
           "when where why not no yes do does did just really very like about into over out up down "
           "can could will would should have has had get got make made go going went one two".split())
STAMP = re.compile(r"^\s*[-•*]?\s*\(?((?:\d{1,2}:)?\d{1,2}:\d{2})\)?\s*[-–—:|]?\s*(.*)$")


def mmss(t: float) -> str:
    t = int(t)
    h, m, s = t // 3600, (t % 3600) // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def validate(text: str, duration: float | None) -> dict[str, Any]:
    chapters = []
    for line in text.splitlines():
        m = STAMP.match(line)
        if m:
            chapters.append({"start": subtitles.parse_ts(m.group(1)), "label": m.group(1),
                             "title": m.group(2).strip()})
    problems = []
    if not chapters:
        return {"valid": False, "chapters": [], "problems": ["no timestamp lines found"]}
    if chapters[0]["start"] != 0:
        problems.append(f"the first timestamp is {chapters[0]['label']}, not 00:00")
    if len(chapters) < MIN_COUNT:
        problems.append(f"{len(chapters)} timestamp(s); at least {MIN_COUNT} are needed")
    for i, c in enumerate(chapters):
        end = chapters[i + 1]["start"] if i + 1 < len(chapters) else duration
        if i + 1 < len(chapters) and end <= c["start"]:
            problems.append(f"{chapters[i + 1]['label']} is not after {c['label']}")
        c["seconds"] = round(end - c["start"], 2) if end is not None else None
        if c["seconds"] is not None and 0 < c["seconds"] < MIN_SECONDS:
            problems.append(f"{c['label']} lasts {c['seconds']:g} s; the minimum is {MIN_SECONDS:g}")
        if not c["title"]:
            problems.append(f"{c['label']} has no title")
    out: dict[str, Any] = {"valid": not problems, "chapters": chapters, "problems": problems}
    if duration is None:
        out["note"] = "the last chapter's length is unchecked without --duration"
    return out


def keywords(text: str, english: bool) -> set[str]:
    found = re.findall(r"[^\W\d_][\w']{3,}", text.lower())
    return {w for w in found if not (english and w in STOP)}


def draft(cues: list[subtitles.Cue], target: int, english: bool) -> dict[str, Any]:
    if len(cues) < 6:
        raise Refusal("too few cues to chapter")
    dur = cues[-1][1]
    cand = []
    for i in range(1, len(cues)):
        gap = cues[i][0] - cues[i - 1][1]
        kb = keywords(" ".join(c[2] for c in cues[max(0, i - 12):i]), english)
        ka = keywords(" ".join(c[2] for c in cues[i:i + 12]), english)
        shift = 1 - (len(kb & ka) / len(kb | ka)) if (kb | ka) else 0
        cand.append((gap * 1.6 + shift * 3.2, cues[i][0]))
    cand.sort(reverse=True)
    picked = [0.0]
    for _, t in cand:
        if len(picked) >= target:
            break
        if all(abs(t - p) >= MIN_SECONDS for p in picked) and dur - t >= MIN_SECONDS:
            picked.append(t)
    picked.sort()
    chapters = []
    for n, t in enumerate(picked):
        end = picked[n + 1] if n + 1 < len(picked) else dur
        text = " ".join(c[2] for c in cues if c[0] >= t and c[1] <= end)
        kw = sorted(keywords(text, english), key=lambda w: (-text.lower().count(w), w))
        chapters.append({"start": round(t, 2), "label": mmss(t),
                         "draft_title": " ".join(w.capitalize() for w in kw[:3]) or "Section",
                         "seconds": round(end - t, 2)})
    ok = len(chapters) >= MIN_COUNT and chapters[0]["start"] == 0 and all(
        c["seconds"] >= MIN_SECONDS for c in chapters)
    return {"valid": ok, "chapters": chapters,
            "block": "\n".join(f"{c['label']} {c['draft_title']}" for c in chapters)}


def main(argv: list[str] | None = None) -> dict[str, Any]:
    p = argparse.ArgumentParser(prog="chapters.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    v = sub.add_parser("validate", help="check the chapter block of a description")
    v.add_argument("--description-file", required=True)
    v.add_argument("--duration", help="the video's length, to check the last chapter")
    d = sub.add_parser("draft", help="draft chapters from a timed transcript")
    d.add_argument("transcript")
    d.add_argument("--target", type=int, default=7, help="how many chapters at most (default 7)")
    d.add_argument("--lang", default="en")
    a = p.parse_args(argv)
    if a.command == "validate":
        try:
            text = Path(a.description_file).read_text(encoding="utf-8")
        except OSError as e:
            raise Refusal(f"cannot read {a.description_file}: {e.strerror}") from None
        duration = parse_duration(a.duration, "--duration") if a.duration else None
        return {"ok": True, **validate(text, duration)}
    if not Path(a.transcript).exists():
        raise Refusal(f"no file {a.transcript}")
    english = a.lang.split("-")[0] == "en"
    out = {"ok": True, **draft(subtitles.load(a.transcript), max(MIN_COUNT, a.target), english)}
    if not english:
        out["unsupported"] = ["stop words: draft titles may hold common words of the language"]
    return out


if __name__ == "__main__":
    sys.exit(run(main))
