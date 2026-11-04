#!/usr/bin/env python3
# Derived from youtube-agent-skill, https://github.com/Jakeschincariol/youtube-agent-skill
# commit a2feb2104981a375ffd4f87ee04f4f5344ac43c6, skills/yt-package/title.py.
# MIT licence, Copyright (c) 2026 Jake Schincariol; the text is in licenses/youtube-agent-skill.txt.
# Changed: thumbnail text is flagged above three words, as its own message says (upstream checked
# > 4; PR #125); words are read in any script, not only [a-z], so a non-English title is measured
# instead of looking empty (PR #127); the English word lists (vague words, filler for the
# front-load check) apply to --lang en only and the answer names the checks it skipped; argparse,
# JSON-only output, issues as objects.
"""Lint a YouTube title together with its thumbnail text, before it goes out.

  title.py --title "..." [--thumb "THREE WORDS MAX"] [--lang en]
  title.py --titles-file titles.txt [--thumb "..."]          one title per line, ranked

The pairing is the unit: a thumbnail that repeats the title's words wastes half the click surface.
Checks: length (100 characters is YouTube's limit; desktop search shows about 60 and a mobile feed
about 40 — display widths observed, not published limits), all-caps words (more than two), vague
superlatives (en), a concrete number or date, filler in the first three words (en), title words
repeated on the thumbnail, and more than three words on the thumbnail.

`score` = 100 - 14 per issue + 4 per good point, clamped to 0..100: a way to rank drafts against each
other, not a prediction of click-through.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from ytskills.common import Refusal, run  # noqa: E402

DESKTOP, MOBILE, HARD = 60, 40, 100
THUMB_WORDS = 3
VAGUE = {"amazing", "incredible", "insane", "crazy", "huge", "massive", "ultimate", "best", "powerful",
         "secret", "revolutionary", "mindblowing", "epic", "perfect", "complete", "everything"}
STOP = {"the", "a", "an", "of", "for", "to", "in", "on", "and", "or", "is", "are", "with", "your", "you",
        "my", "i", "this", "that", "it", "how", "what", "why"}


def words(t: str) -> list[str]:
    return re.findall(r"[^\W_][\w']*", t.lower())


def check(title: str, thumb: str | None = None, lang: str = "en") -> dict[str, Any]:
    english = lang.split("-")[0] == "en"
    t = title.strip()
    n = len(t)
    issues: list[dict[str, str]] = []
    good: list[str] = []

    def issue(name: str, message: str) -> None:
        issues.append({"check": name, "message": message})

    if "<" in t or ">" in t:
        issue("forbidden", "YouTube refuses < and > in a title")
    if n > HARD:
        issue("length", f"{n} characters - YouTube's limit is {HARD}")
    elif n > DESKTOP:
        issue("length", f"{n} characters - desktop search shows about {DESKTOP}")
    else:
        good.append(f"{n} characters, inside the ~{DESKTOP}-character desktop cut")
    if n > MOBILE:
        head = t[:MOBILE].rsplit(" ", 1)[0]
        issue("mobile", f'a mobile feed shows about "{head}..." - check the subject survives')
    caps = [w for w in t.split() if len(w) > 2 and w.isupper()]
    if len(caps) > 2:
        issue("shouting", f"{len(caps)} all-caps words - more than two reads as shouting")
    elif caps:
        good.append(f"{len(caps)} all-caps word(s) for emphasis")
    if english:
        v = sorted({w for w in words(t) if w in VAGUE})
        if v:
            issue("vague", f"{', '.join(v)} - a number, a name or a date says more")
    nums = re.findall(r"\d[\d,.]*%?", t)
    if nums:
        good.append(f"carries a concrete figure ({', '.join(nums[:3])})")
    else:
        issue("no-number", "no number or date")
    if t.endswith("?"):
        good.append("an open question")
    if english and not [w for w in words(t)[:3] if w not in STOP]:
        issue("front-load", "the first three words are all filler - move the subject forward")
    if thumb:
        stop = STOP if english else set()
        tw = {w for w in words(t) if w not in stop and (english or len(w) >= 3)}
        hw = {w for w in words(thumb) if w not in stop and (english or len(w) >= 3)}
        shared = tw & hw
        if shared:
            issue("duplicate", f"the thumbnail repeats the title on {', '.join(sorted(shared))} - "
                               "it should say what the title does not")
        else:
            good.append("thumbnail and title carry different words")
        count = len(words(thumb))
        if count > THUMB_WORDS:
            issue("thumb-length", f"{count} words on the thumbnail - {THUMB_WORDS} is the ceiling at feed size")
    out: dict[str, Any] = {"title": t, "thumb": thumb, "chars": n,
                           "score": max(0, min(100, 100 - 14 * len(issues) + 4 * len(good))),
                           "issues": issues, "good": good}
    if not english:
        out["unsupported"] = ["vague", "front-load"]
    return out


def main(argv: list[str] | None = None) -> dict[str, Any]:
    p = argparse.ArgumentParser(prog="title.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--title", help="one title")
    src.add_argument("--titles-file", help="a file with one title per line")
    p.add_argument("--thumb", help="the thumbnail's text")
    p.add_argument("--lang", default="en", help="the title's language (default en)")
    a = p.parse_args(argv)
    if a.title is not None:
        titles = [a.title]
    else:
        try:
            titles = [ln for ln in Path(a.titles_file).read_text(encoding="utf-8").splitlines() if ln.strip()]
        except OSError as e:
            raise Refusal(f"cannot read {a.titles_file}: {e.strerror}") from None
    if not titles or not any(t.strip() for t in titles):
        raise Refusal("no title given")
    rows = sorted((check(t, a.thumb, a.lang) for t in titles), key=lambda r: -r["score"])
    return {"ok": True, "titles": rows}


if __name__ == "__main__":
    sys.exit(run(main))
