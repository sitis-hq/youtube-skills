# Derived from youtube-agent-skill, https://github.com/Jakeschincariol/youtube-agent-skill
# commit a2feb2104981a375ffd4f87ee04f4f5344ac43c6, skills/yt-edit/deadair.py (`parse_ts`, `load`).
# MIT licence, Copyright (c) 2026 Jake Schincariol; the text is in licenses/youtube-agent-skill.txt.
# Changed: cues are read block by block, so a WebVTT cue identifier is no longer glued to the
# previous cue's text; yt-dlp's inline word timings (<00:00:01.120><c>...</c>), other tags and HTML
# entities are removed; the rolling duplicate lines of YouTube auto-captions are collapsed; WebVTT
# headers, NOTE and STYLE blocks are skipped; SRT and plain-text writers were added.
"""Timed transcripts: read SRT, WebVTT (including yt-dlp auto-captions) and whisper JSON into cues.

A cue is (start_seconds, end_seconds, text). retention.py, deadair.py and chapters.py read cues;
youtube-data's transcript.py writes them as SRT or plain text.
"""

from __future__ import annotations

import html
import json
import re
from typing import Iterable

Cue = tuple[float, float, str]

TIMING = re.compile(r"^\s*(\d[\d:.,]*)\s*-->\s*(\d[\d:.,]*)")
TAG = re.compile(r"<[^>]*>")


def parse_ts(s: str) -> float:
    s = s.strip().replace(",", ".")
    p = s.split(":")
    if len(p) == 3:
        return int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2])
    if len(p) == 2:
        return int(p[0]) * 60 + float(p[1])
    return float(p[0])


def clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG.sub("", line))).strip()


def parse_timed_text(raw: str) -> list[Cue]:
    """SRT or WebVTT text into cues, with auto-caption repetition removed."""
    raw = raw.replace("\ufeff", "")
    # Only WebVTT carries the rolling repetition; in SRT a line said twice was said twice.
    dedupe = raw.lstrip().startswith("WEBVTT")
    cues: list[Cue] = []
    # Auto-captions show each line twice: as the new bottom line of one cue, then as the top line
    # of the next (and once more in a 10 ms "hold" cue). Remembering the last lines emitted and
    # skipping them leaves each spoken line once, at the time it first appeared.
    recent: list[str] = []
    cur: list | None = None
    for line in raw.splitlines() + [""]:
        m = TIMING.match(line)
        if m:
            cur = [parse_ts(m.group(1)), parse_ts(m.group(2)), []]
            continue
        if line == "":
            # Only a truly empty line ends a cue: auto-captions put a line of one space inside a
            # cue, and treating it as the end would orphan the cue's text.
            if cur is not None and cur[2]:
                cues.append((cur[0], cur[1], " ".join(cur[2])))
            cur = None
            continue
        if cur is None:
            continue  # WEBVTT header, NOTE, STYLE, REGION, a cue identifier or an SRT number
        text = clean_line(line)
        if not text or (dedupe and text in recent):
            continue
        cur[2].append(text)
        recent = (recent + [text])[-3:]
    # A line that appeared in one cue and lingered on screen ends when the next one starts.
    out: list[Cue] = []
    for i, (s, e, t) in enumerate(cues):
        if i + 1 < len(cues) and cues[i + 1][0] < e:
            e = max(s, cues[i + 1][0])
        out.append((s, e, t))
    return out


def parse_whisper_json(raw: str) -> list[Cue]:
    d = json.loads(raw)
    segs = d.get("segments", []) if isinstance(d, dict) else d
    return [(float(s["start"]), float(s["end"]), clean_line(s.get("text") or "")) for s in segs
            if clean_line(s.get("text") or "")]


def load(path: str) -> list[Cue]:
    with open(path, encoding="utf-8", errors="replace") as fh:
        raw = fh.read()
    if path.endswith(".json"):
        return parse_whisper_json(raw)
    return parse_timed_text(raw)


def _srt_ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(cues: Iterable[Cue]) -> str:
    parts = [f"{i}\n{_srt_ts(s)} --> {_srt_ts(e)}\n{t}\n" for i, (s, e, t) in enumerate(cues, 1)]
    return "\n".join(parts)


def to_text(cues: Iterable[Cue]) -> str:
    return "\n".join(t for _, _, t in cues) + "\n"
