#!/usr/bin/env python3
"""Competition for a keyword in YouTube's own results, 0..1 — our heuristic, not a YouTube metric.

No source gives a YouTube keyword difficulty. DataForSEO's keyword_difficulty (`kd_web`) is built from
the link profiles of the top 10 *web* pages, a weak proxy for YouTube. So we look at the YouTube
results themselves: who holds the top 20 videos for the query, and how hard they would be to pass.

The formula (every part is a choice, written down so a reader can disagree with it precisely):

  scale(x, lo, hi) = clamp((x - lo) / (hi - lo), 0, 1)

  traffic   = 0.5 * scale(log10(median views),          2, 7)   # 100 views -> 0, 10M -> 1
            + 0.5 * scale(log10(median views per day),  0, 4)   # 1/day -> 0, 10k/day -> 1
  targeting = share of the videos whose title contains every word of the keyword
  authority = scale(log10(median channel subscribers),  3, 7)   # 1k -> 0, 10M -> 1

  yt_competition = 0.45 * traffic + 0.25 * targeting + 0.30 * authority

Views per day uses the video's age, so an old video with a large total but little current traffic
counts for less than a fresh one pulling the same total now. Subscribers are not in DataForSEO's
YouTube SERP; they come from youtube-data `channels` (`--channels`). When fewer than half of the
videos have a subscriber count, authority is left out and the other two weights are rescaled to sum
to 1 — the output says so in `weights`. Fewer than 5 videos gives `confidence: "low"`.

Inputs:
  --serp FILE        a DataForSEO /v3/serp/youtube/organic/.../advanced response, saved as it came
                     (full schema: call with noAiMode / --no-ai-mode). Every task is one keyword.
  --videos FILE      youtube-data `videos` output ({"videos": [...]}) for ids in search-rank order;
                     needs --keyword.
  --channels FILE    youtube-data `channels` output, for subscriber counts (optional, repeatable).
  --top N            how many videos to read (default 20).
  --as-of DATE       the day ages are counted to (default: the SERP's own datetime, else today, UTC).

Prints {"ok": true, "keywords": [{keyword, yt_competition, components, ...}]}. A refusal exits 2.
Standard library only: Python 3.11.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

WEIGHTS = {"traffic": 0.45, "targeting": 0.25, "authority": 0.30}
TOP = 20
LOW_CONFIDENCE_BELOW = 5


class Refusal(Exception):
    pass


def scale(x: float, lo: float, hi: float) -> float:
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


def words(text: str) -> list[str]:
    # Accents and case are folded so "Café" in a title matches the keyword "cafe".
    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return re.findall(r"\w+", folded)


def title_matches(keyword: str, title: str) -> bool:
    need = set(words(keyword))
    return bool(need) and need <= set(words(title or ""))


_REL = re.compile(r"(\d+)\s*(second|minute|hour|day|week|month|year)s?\s+ago", re.I)
_REL_DAYS = {"second": 1 / 86400, "minute": 1 / 1440, "hour": 1 / 24, "day": 1, "week": 7,
             "month": 30.44, "year": 365.25}


def parse_when(value: Any) -> datetime | None:
    """An absolute publication time: DataForSEO's "2022-12-30 14:12:23 +00:00" or ISO 8601."""
    if not value or not isinstance(value, str):
        return None
    text = value.strip().replace("Z", "+00:00")
    for fmt in ("%Y-%m-%d %H:%M:%S %z", None):
        try:
            dt = datetime.strptime(text, fmt) if fmt else datetime.fromisoformat(text)
        except ValueError:
            continue
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def age_days(item: dict[str, Any], now: datetime) -> float | None:
    when = parse_when(item.get("timestamp")) or parse_when(item.get("published_at"))
    if when:
        return max((now - when).total_seconds() / 86400, 0.0)
    # Only the relative text ("Streamed 2 days ago") is left; it is coarse but better than nothing.
    m = _REL.search(str(item.get("publication_date") or ""))
    if m:
        return int(m.group(1)) * _REL_DAYS[m.group(2).lower()]
    return None


def load_json(path: str) -> Any:
    text = Path(path).read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # The DataForSEO CLI may print a warning line before the body.
        start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
        if start > 0:
            try:
                return json.loads(text[start:])
            except json.JSONDecodeError:
                pass
        raise Refusal(f"{path} is not JSON") from None


def serp_tasks(doc: Any, path: str) -> list[dict[str, Any]]:
    """Each successful task's first result: {keyword, datetime, items}."""
    if not isinstance(doc, dict) or "tasks" not in doc:
        raise Refusal(f"{path}: not a DataForSEO response (no 'tasks'); save the body as it came, "
                      "requested with noAiMode: true (MCP) or --no-ai-mode (CLI)")
    if doc.get("status_code") not in (None, 20000):
        raise Refusal(f"{path}: DataForSEO error {doc.get('status_code')}: {doc.get('status_message')}")
    out = []
    for task in doc["tasks"] or []:
        if task.get("status_code") != 20000:
            print(f"{path}: task {task.get('id')} failed: {task.get('status_code')} "
                  f"{task.get('status_message')}", file=sys.stderr)
            continue
        for result in task.get("result") or []:
            out.append({"keyword": result.get("keyword") or (task.get("data") or {}).get("keyword"),
                        "datetime": result.get("datetime"), "items": result.get("items") or []})
    return out


def videos_from_serp(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Paid videos are bought, not ranked; channels and playlists are not videos to outrank.
    vids = [i for i in items if i.get("type") == "youtube_video"]
    vids.sort(key=lambda i: i.get("rank_absolute") or 0)
    return [{"video_id": i.get("video_id"), "title": i.get("title"), "views": i.get("views_count"),
             "channel_id": i.get("channel_id"), "timestamp": i.get("timestamp"),
             "publication_date": i.get("publication_date"), "is_shorts": i.get("is_shorts")}
            for i in vids]


def subscribers_from(paths: list[str]) -> dict[str, int]:
    subs: dict[str, int] = {}
    for p in paths:
        doc = load_json(p)
        rows = doc.get("channels") if isinstance(doc, dict) else doc
        if not isinstance(rows, list):
            raise Refusal(f"{p}: expected youtube-data `channels` output with a 'channels' list")
        for row in rows:
            if row.get("channel_id") and isinstance(row.get("subscribers"), int):
                subs[row["channel_id"]] = row["subscribers"]
    return subs


def score(keyword: str, videos: list[dict[str, Any]], now: datetime,
          subs: dict[str, int] | None = None, top: int = TOP) -> dict[str, Any]:
    videos = videos[:top]
    n = len(videos)
    out: dict[str, Any] = {"keyword": keyword, "n_videos": n}
    if n == 0:
        # Nothing ranks for it on YouTube: no competition, and probably no demand either.
        return {**out, "yt_competition": 0.0, "confidence": "low", "components": {},
                "weights": {}, "note": "no videos in the results"}

    views = [v["views"] for v in videos if isinstance(v.get("views"), (int, float))]
    vpd = []
    ages = []
    for v in videos:
        a = age_days(v, now)
        if a is not None:
            ages.append(a)
            if isinstance(v.get("views"), (int, float)):
                # A video published today has had at most a day to collect its views.
                vpd.append(v["views"] / max(a, 1.0))
    subs = subs or {}
    sub_counts = [subs[v["channel_id"]] for v in videos
                  if v.get("channel_id") in subs]
    sub_counts += [v["channel_subscribers"] for v in videos
                   if v.get("channel_id") not in subs and isinstance(v.get("channel_subscribers"), int)]

    med_views = statistics.median(views) if views else None
    med_vpd = statistics.median(vpd) if vpd else None
    parts = []
    if med_views is not None:
        parts.append(scale(math.log10(med_views + 1), 2, 7))
    if med_vpd is not None:
        parts.append(scale(math.log10(med_vpd + 1), 0, 4))
    components: dict[str, float] = {}
    if parts:
        components["traffic"] = sum(parts) / len(parts)
    components["targeting"] = sum(title_matches(keyword, v.get("title") or "") for v in videos) / n
    med_subs = statistics.median(sub_counts) if sub_counts else None
    if med_subs is not None and len(sub_counts) * 2 >= n:
        components["authority"] = scale(math.log10(med_subs + 1), 3, 7)

    total = sum(WEIGHTS[k] for k in components)
    weights = {k: round(WEIGHTS[k] / total, 4) for k in components}
    value = sum(components[k] * WEIGHTS[k] for k in components) / total

    shorts = [v for v in videos if v.get("is_shorts") is not None]
    return {**out,
            "yt_competition": round(value, 3),
            "confidence": "low" if n < LOW_CONFIDENCE_BELOW or "traffic" not in components else "normal",
            "components": {k: round(v, 3) for k, v in components.items()},
            "weights": weights,
            "median_views": med_views,
            "median_views_per_day": round(med_vpd, 1) if med_vpd is not None else None,
            "median_age_days": round(statistics.median(ages), 1) if ages else None,
            "median_subscribers": med_subs,
            "subscribers_known": len(sub_counts),
            "title_match_share": round(components["targeting"], 3),
            "shorts_share": round(sum(bool(v["is_shorts"]) for v in shorts) / len(shorts), 3) if shorts else None}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Competition for a keyword in the YouTube top results, 0..1 (a heuristic; "
                    "the formula is in this file's docstring and in SKILL.md).")
    p.add_argument("--serp", action="append", default=[],
                   help="DataForSEO YouTube organic response file (repeatable); full schema, not .ai")
    p.add_argument("--videos", help="youtube-data `videos` output for search results, in rank order")
    p.add_argument("--keyword", help="the keyword, required with --videos")
    p.add_argument("--channels", action="append", default=[],
                   help="youtube-data `channels` output with subscriber counts (repeatable)")
    p.add_argument("--top", type=int, default=TOP, help="how many top videos to read (default 20)")
    p.add_argument("--as-of", help="count ages to this day, YYYY-MM-DD (default: the SERP's datetime, else today)")
    return p


def run(argv: list[str] | None = None) -> dict[str, Any]:
    a = parser().parse_args(argv)
    if not a.serp and not a.videos:
        raise Refusal("pass --serp FILE or --videos FILE --keyword K")
    if a.videos and not a.keyword:
        raise Refusal("--videos needs --keyword: the search results do not carry the query")
    if a.top < 1:
        raise Refusal("--top must be at least 1")
    fixed_now = None
    if a.as_of:
        try:
            d = date.fromisoformat(a.as_of)
        except ValueError:
            raise Refusal(f"--as-of must be YYYY-MM-DD, got {a.as_of!r}") from None
        fixed_now = datetime(d.year, d.month, d.day, tzinfo=timezone.utc) + timedelta(hours=12)
    subs = subscribers_from(a.channels)
    results = []
    for path in a.serp:
        for task in serp_tasks(load_json(path), path):
            now = fixed_now or parse_when(task["datetime"]) or datetime.now(timezone.utc)
            results.append(score(task["keyword"] or "", videos_from_serp(task["items"]), now, subs, a.top))
    if a.videos:
        doc = load_json(a.videos)
        rows = doc.get("videos") if isinstance(doc, dict) else doc
        if not isinstance(rows, list):
            raise Refusal(f"{a.videos}: expected youtube-data `videos` output with a 'videos' list")
        results.append(score(a.keyword, rows, fixed_now or datetime.now(timezone.utc), subs, a.top))
    if not results:
        raise Refusal("no successful SERP task in the input")
    return {"ok": True, "keywords": results,
            "note": "yt_competition is our heuristic from the YouTube top results, not a YouTube metric"}


def main(argv: list[str] | None = None) -> int:
    try:
        out = run(argv)
    except Refusal as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 2
    except OSError as e:
        print(json.dumps({"ok": False, "error": f"cannot read input: {e}"}))
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
