#!/usr/bin/env python3
# Derived from youtube-agent-skill, https://github.com/Jakeschincariol/youtube-agent-skill
# commit a2feb2104981a375ffd4f87ee04f4f5344ac43c6, skills/yt-edit/deadair.py.
# MIT licence, Copyright (c) 2026 Jake Schincariol; the text is in licenses/youtube-agent-skill.txt.
# Changed: the transcript reader moved to lib/ytskills/subtitles (shared with retention.py and
# chapters.py, and cleaned of yt-dlp caption markup); argparse and JSON-only output; restarts are
# compared on words of any script, not only [a-z], so a non-English restart is found and a
# non-English line no longer reads as empty; filler words are English and the output says so for
# another --lang instead of finding none in silence.
"""Dead air, filler and restarted sentences in a timed transcript — an edit list, not an edit.

  deadair.py video.srt [--floor 0.45] [--lang en]

  DEAD    gaps between spoken cues longer than the floor (seconds); the middle of each is cut
  FILLER  cues that are only filler ("um", "so yeah", "basically") — English words
  REPEAT  a sentence restarted: the first five words of a cue repeat the last spoken cue's

Nothing touches media. Auto-captions time their cues loosely, so DEAD on them is approximate.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from ytskills import subtitles  # noqa: E402
from ytskills.common import Refusal, run  # noqa: E402

FILLER_ONLY = re.compile(r"^[\s,.-]*((um+|uh+|er+|ah+|so|okay|ok|right|yeah|like|anyway|basically|"
                         r"actually|you know|i mean|let me see|hold on)[\s,.-]*)+$", re.I)


def norm(t: str) -> list[str]:
    return re.findall(r"[^\W_]+", t.lower())


def cuts_of(cues: list[subtitles.Cue], floor: float, english: bool) -> list[dict[str, Any]]:
    def filler(t: str) -> bool:
        return english and bool(FILLER_ONLY.match(t))

    cuts = []
    for i, (s, e, t) in enumerate(cues):
        if filler(t):
            cuts.append({"kind": "FILLER", "start": s, "end": e, "why": t.strip()[:48]})
        if i:
            gap = s - cues[i - 1][1]
            if gap > floor:
                keep = floor / 2
                cuts.append({"kind": "DEAD", "start": round(cues[i - 1][1] + keep, 3),
                             "end": round(s - keep, 3), "why": f"{gap:.2f}s gap"})
        # A restart is compared with the last cue that was speech: most retakes have an "um"
        # between the two attempts, and the literal previous cue would miss them.
        if t.strip() and not filler(t):
            j = i - 1
            while j >= 0 and (filler(cues[j][2]) or not cues[j][2].strip()):
                j -= 1
            if j >= 0:
                a1, b1 = norm(cues[j][2])[:5], norm(t)[:5]
                if len(a1) >= 3 and a1 == b1:
                    cuts.append({"kind": "REPEAT", "start": cues[j][0], "end": cues[j][1],
                                 "why": f'restart of "{" ".join(a1)}"'})
    cuts = [c for c in cuts if c["end"] > c["start"]]
    cuts.sort(key=lambda c: c["start"])
    return cuts


def main(argv: list[str] | None = None) -> dict[str, Any]:
    p = argparse.ArgumentParser(prog="deadair.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("transcript", help="srt, vtt or whisper json")
    p.add_argument("--floor", type=float, default=0.45, help="the longest pause kept, seconds")
    p.add_argument("--lang", default="en", help="the spoken language; filler words exist for en")
    a = p.parse_args(argv)
    if not Path(a.transcript).exists():
        raise Refusal(f"no file {a.transcript}")
    cues = subtitles.load(a.transcript)
    if not cues:
        raise Refusal("no cues found — is this an srt, vtt or whisper json?")
    english = a.lang.split("-")[0] == "en"
    cuts = cuts_of(cues, a.floor, english)
    dur = cues[-1][1]
    removed = sum(c["end"] - c["start"] for c in cuts)
    out = {"ok": True, "source": a.transcript, "duration": dur, "cues": len(cues), "cuts": cuts,
           "removed": round(removed, 3), "out": round(dur - removed, 3)}
    if not english:
        out["unsupported"] = ["FILLER: the filler words are English"]
    return out


if __name__ == "__main__":
    sys.exit(run(main))
