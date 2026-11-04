#!/usr/bin/env python3
"""Lint a video's metadata before it is applied: YouTube's hard limits as errors, our placement rules
as warnings.

Errors — YouTube rejects or ignores something (sources read 2026-11-04):
  title           1..100 characters, no "<" or ">"            Data API videos resource, snippet.title
  description     at most 5000 bytes UTF-8, no "<" or ">"     Data API videos resource, snippet.description
  tags            at most 500 characters all together; the commas between tags count, and a tag
                  with a space counts as if quoted (+2)         Data API videos resource, snippet.tags[]
  hashtags        more than 60 in title + description: YouTube ignores every one of them
                                                                YouTube Help 6390658
  chapters        when the description has timestamps: the first is 0:00, at least three, ascending,
                  each chapter at least 10 seconds              YouTube Help 9884579
  required tokens each --require-token (an identity token: artist, series, show) appears in the
                  title exactly as given, case included — the recipe decides which are required

Warnings — our rules, not YouTube's (see references/metadata-rules.md):
  the keyword is missing from the title, or starts after character 40 (front-load it);
  the keyword is missing from the first 150 characters of the description;
  a tag starts with "#" (tags are not hashtags); duplicate tags;
  a Short's description holds a URL (links in Shorts descriptions are not clickable).

Input: flags, or --file with a JSON object of the same names (title, description, tags, keyword,
format, duration, require_tokens). Prints {"ok", "errors", "warnings", "facts"}; exits 0 when there
are no errors (and, with --strict, no warnings), 1 when there are, 2 on a refusal (unusable input).
Standard library only: Python 3.11.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

TITLE_MAX = 100
DESCRIPTION_MAX_BYTES = 5000
TAGS_MAX = 500
HASHTAGS_MAX = 60
CHAPTERS_MIN = 3
CHAPTER_MIN_S = 10
# Ours: where the keyword must start in the title, and the description opening it must sit in.
TITLE_FRONT = 40
DESCRIPTION_OPENING = 150

# A hashtag: "#" not glued to a preceding word or "&" (HTML entity), then letters/digits/underscore,
# at least one of them a letter — "#1" in "track #1" is a number sign, not a hashtag.
HASHTAG = re.compile(r"(?<![\w&])#(\w*[^\W\d_]\w*)")
TIMESTAMP_LINE = re.compile(r"^\s*[\[(]?((?:\d{1,2}:)?\d{1,2}:\d{2})[\])]?\s*(?:[-–—:|]\s*)?(.*)$")
URL = re.compile(r"https?://|www\.", re.I)


class Refusal(Exception):
    pass


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.findall(r"\w+", text))


def phrase_at(keyword: str, text: str) -> int | None:
    """Character position in `text` where the keyword's words begin, as a phrase; None if absent."""
    words = re.findall(r"\w+", fold(keyword))
    if not words:
        return None
    # Match on the folded text but report the position in the original, so "char 41" is checkable.
    pattern = r"(?<!\w)" + r"\W+".join(re.escape(w) for w in words) + r"(?!\w)"
    folded_chars, index = [], []
    for i, ch in enumerate(text):
        for c in unicodedata.normalize("NFKD", ch.casefold()):
            if not unicodedata.combining(c):
                folded_chars.append(c)
                index.append(i)
    m = re.search(pattern, "".join(folded_chars))
    return index[m.start()] if m else None


def seconds(stamp: str) -> int:
    parts = [int(p) for p in stamp.split(":")]
    total = 0
    for p in parts:
        total = total * 60 + p
    return total


def tags_length(tags: list[str]) -> int:
    # Data API: commas between items count, and a tag with a space is counted with its quotes.
    return sum(len(t) + (2 if " " in t else 0) for t in tags) + max(len(tags) - 1, 0)


def check(meta: dict[str, Any]) -> dict[str, Any]:
    title = meta.get("title")
    if title is None:
        raise Refusal("no title: pass --title or a 'title' in --file")
    title = str(title)
    description = str(meta.get("description") or "")
    tags = [str(t).strip() for t in meta.get("tags") or [] if str(t).strip()]
    keyword = (meta.get("keyword") or "").strip()
    fmt = meta.get("format") or "long"
    if fmt not in ("long", "short", "live"):
        raise Refusal(f"format must be long, short or live, got {fmt!r}")
    duration = meta.get("duration")
    if duration is not None:
        try:
            duration = float(duration)
        except (TypeError, ValueError):
            raise Refusal(f"duration must be seconds, got {duration!r}") from None
    tokens = [str(t) for t in meta.get("require_tokens") or []]

    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    def err(check: str, message: str) -> None:
        errors.append({"check": check, "message": message})

    def warn(check: str, message: str) -> None:
        warnings.append({"check": check, "message": message})

    # Title
    if not title.strip():
        err("title.empty", "the title is empty")
    if len(title) > TITLE_MAX:
        err("title.length", f"{len(title)} characters; YouTube allows {TITLE_MAX}")
    if "<" in title or ">" in title:
        err("title.angle_brackets", "YouTube does not accept < or > in a title")
    for t in tokens:
        if t not in title:
            err("title.identity_token", f"the required token {t!r} is not in the title as written")

    # Description
    dbytes = len(description.encode("utf-8"))
    if dbytes > DESCRIPTION_MAX_BYTES:
        err("description.length", f"{dbytes} bytes; YouTube allows {DESCRIPTION_MAX_BYTES} bytes "
                                  "(non-Latin letters take 2-4 bytes each)")
    if "<" in description or ">" in description:
        err("description.angle_brackets", "YouTube does not accept < or > in a description")

    # Tags
    tlen = tags_length(tags)
    if tlen > TAGS_MAX:
        err("tags.length", f"{tlen} characters counted the Data API way; the limit is {TAGS_MAX}")
    if any(t.startswith("#") for t in tags):
        warn("tags.hashtag", "a tag starts with '#': tags are not hashtags, put hashtags in the description")
    seen, dups = set(), []
    for t in tags:
        k = t.casefold()
        if k in seen:
            dups.append(t)
        seen.add(k)
    if dups:
        warn("tags.duplicate", f"duplicate tags: {', '.join(dups)}")

    # Hashtags (title and description together, distinct, case-insensitive)
    found: list[str] = []
    for m in HASHTAG.finditer(title + "\n" + description):
        tag = "#" + m.group(1)
        if tag.casefold() not in {h.casefold() for h in found}:
            found.append(tag)
    if len(found) > HASHTAGS_MAX:
        err("hashtags.count", f"{len(found)} hashtags; over {HASHTAGS_MAX} YouTube ignores all of them")

    # Chapters
    chapters = []
    for line in description.splitlines():
        m = TIMESTAMP_LINE.match(line)
        if m:
            chapters.append({"start": m.group(1), "seconds": seconds(m.group(1)), "title": m.group(2).strip()})
    if chapters:
        if chapters[0]["seconds"] != 0:
            err("chapters.first", f"the first timestamp is {chapters[0]['start']}; chapters need the first at 0:00")
        if len(chapters) < CHAPTERS_MIN:
            err("chapters.count", f"{len(chapters)} timestamps; chapters need at least {CHAPTERS_MIN}")
        for a, b in zip(chapters, chapters[1:]):
            if b["seconds"] <= a["seconds"]:
                err("chapters.order", f"{b['start']} does not come after {a['start']}")
            elif b["seconds"] - a["seconds"] < CHAPTER_MIN_S:
                err("chapters.short", f"the chapter at {a['start']} lasts {b['seconds'] - a['seconds']} s; "
                                      f"the minimum is {CHAPTER_MIN_S} s")
        if duration is not None:
            last = chapters[-1]
            if last["seconds"] >= duration:
                err("chapters.beyond_end", f"{last['start']} is at or past the video's end ({duration:g} s)")
            elif duration - last["seconds"] < CHAPTER_MIN_S:
                err("chapters.short", f"the last chapter lasts {duration - last['seconds']:g} s; "
                                      f"the minimum is {CHAPTER_MIN_S} s")
        for c in chapters:
            if not c["title"]:
                warn("chapters.untitled", f"the chapter at {c['start']} has no label")

    # Keyword placement (ours)
    facts: dict[str, Any] = {}
    if keyword:
        pos = phrase_at(keyword, title)
        facts["keyword_position_title"] = pos
        if pos is None:
            warn("keyword.title", f"the keyword {keyword!r} is not in the title")
        elif pos > TITLE_FRONT:
            warn("keyword.title_front", f"the keyword starts at character {pos + 1}; front-load it "
                                        f"within the first {TITLE_FRONT}")
        dpos = phrase_at(keyword, description[:DESCRIPTION_OPENING])
        facts["keyword_in_description_opening"] = dpos is not None
        if dpos is None:
            warn("keyword.description", f"the keyword {keyword!r} is not in the first "
                                        f"{DESCRIPTION_OPENING} characters of the description")

    if fmt == "short" and URL.search(description):
        warn("short.link", "a Short's description has a URL; links there are not clickable")

    facts.update({"title_length": len(title), "description_bytes": dbytes, "tags_length": tlen,
                  "tag_count": len(tags), "hashtags": found, "hashtag_count": len(found),
                  "chapters": [{"start": c["start"], "title": c["title"]} for c in chapters]})
    return {"errors": errors, "warnings": warnings, "facts": facts}


def parse_tags(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(t) for t in raw]
    text = str(raw).strip()
    if text.startswith("["):
        try:
            return [str(t) for t in json.loads(text)]
        except json.JSONDecodeError:
            raise Refusal("--tags looks like JSON but does not parse") from None
    return [t for t in (x.strip() for x in text.split(",")) if t]


def run(argv: list[str] | None = None) -> tuple[dict[str, Any], bool]:
    p = argparse.ArgumentParser(description="Lint YouTube metadata: hard limits are errors, placement rules warnings.")
    p.add_argument("--file", help="JSON object with title, description, tags, keyword, format, duration, require_tokens")
    p.add_argument("--title", help="the title")
    p.add_argument("--description", help="the description text")
    p.add_argument("--description-file", help="read the description from this file (UTF-8)")
    p.add_argument("--tags", help="comma-separated tags, or a JSON array")
    p.add_argument("--keyword", help="the target keyword (from a seed record)")
    p.add_argument("--format", choices=["long", "short", "live"], help="the video's format (default long)")
    p.add_argument("--duration", type=float, help="the video's length in seconds, to check the last chapter")
    p.add_argument("--require-token", action="append", default=None,
                   help="a token the title must contain verbatim, e.g. the artist name (repeatable)")
    p.add_argument("--strict", action="store_true", help="fail on warnings too")
    a = p.parse_args(argv)

    meta: dict[str, Any] = {}
    if a.file:
        try:
            meta = json.loads(Path(a.file).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise Refusal(f"cannot read --file: {e}") from None
        if not isinstance(meta, dict):
            raise Refusal("--file must hold a JSON object")
    if a.description_file:
        try:
            meta["description"] = Path(a.description_file).read_text(encoding="utf-8")
        except OSError as e:
            raise Refusal(f"cannot read --description-file: {e}") from None
    for name in ("title", "description", "keyword", "format", "duration"):
        if getattr(a, name) is not None:
            meta[name] = getattr(a, name)
    if a.tags is not None:
        meta["tags"] = a.tags
    if a.require_token is not None:
        meta["require_tokens"] = a.require_token
    meta["tags"] = parse_tags(meta.get("tags"))
    result = check(meta)
    ok = not result["errors"] and not (a.strict and result["warnings"])
    return {"ok": ok, **result}, ok


def main(argv: list[str] | None = None) -> int:
    try:
        out, ok = run(argv)
    except Refusal as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
