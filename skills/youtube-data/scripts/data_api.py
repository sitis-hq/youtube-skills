#!/usr/bin/env python3
"""Read YouTube Data API v3 within quota: videos, channels, a channel's uploads, search.

  data_api.py videos   --id ID [--id ID ...] | --ids-file F   stats, snippet, duration (1 unit / 50)
  data_api.py channels --id UC... | --handle @name | --mine   channel facts and uploads playlist
  data_api.py uploads  --channel-id UC... | --mine [--max N] [--since DATE] [--with-stats]
  data_api.py search   --q TEXT [--published-after DATE] [--order viewCount] [--pages 1]
                       100 units a page; refused beyond --budget

Every answer carries `quota.data_api_units`, the units this call spent. The output of `videos` is a
dated snapshot (`as_of`), the input youtube-metrics' velocity.py and candidates.py read.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

import _yt  # noqa: E402
from ytskills.common import Refusal, parse_date, parse_duration, run  # noqa: E402

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
CHANNEL_ID = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
WATCH_KEY = re.compile(r"^watch:([A-Za-z0-9_-]{11})$")


def _int(v: Any) -> int | None:
    return int(v) if v not in (None, "") else None


def collect_ids(values: list[str] | None, ids_file: str | None) -> list[str]:
    """Video ids from flags and from a file: lines, a JSON list, or any JSON holding video_id
    fields or watch:<id> keys (the shape query-template-records returns is read the same way)."""
    found: list[str] = []
    for v in values or []:
        found += [x.strip() for x in v.split(",") if x.strip()]
    if ids_file:
        try:
            text = Path(ids_file).read_text(encoding="utf-8")
        except OSError as e:
            raise Refusal(f"cannot read {ids_file}: {e.strerror}") from None
        try:
            doc = json.loads(text)
        except json.JSONDecodeError:
            found += [ln.strip() for ln in text.splitlines() if ln.strip()]
        else:
            def walk(node: Any) -> None:
                if isinstance(node, str):
                    m = WATCH_KEY.match(node)
                    if m:
                        found.append(m.group(1))
                    elif VIDEO_ID.match(node) and isinstance(doc, list) and node in doc:
                        found.append(node)
                elif isinstance(node, list):
                    for x in node:
                        walk(x)
                elif isinstance(node, dict):
                    for k, x in node.items():
                        if k in ("video_id", "videoId") and isinstance(x, str):
                            found.append(x)
                        else:
                            walk(x)
            walk(doc)
    bad = [x for x in found if not VIDEO_ID.match(x)]
    if bad:
        raise Refusal(f"not video ids: {', '.join(bad[:5])}")
    return list(dict.fromkeys(found))  # keep order, drop repeats: each id costs quota once


def video_row(item: dict[str, Any]) -> dict[str, Any]:
    sn, st, cd = item.get("snippet", {}), item.get("statistics", {}), item.get("contentDetails", {})
    duration = cd.get("duration")
    try:
        seconds = parse_duration(duration) if duration and duration not in ("P0D", "PT0S") else None
    except Refusal:
        seconds = None
    return {
        "video_id": item["id"],
        "channel_id": sn.get("channelId"),
        "channel_title": sn.get("channelTitle"),
        "title": sn.get("title"),
        "published_at": sn.get("publishedAt"),
        "duration_s": seconds,
        "views": _int(st.get("viewCount")),
        # Hidden like counts come back absent, which is not zero.
        "likes": _int(st.get("likeCount")),
        "comments": _int(st.get("commentCount")),
        "live": sn.get("liveBroadcastContent"),
        "category_id": sn.get("categoryId"),
        "language": sn.get("defaultAudioLanguage") or sn.get("defaultLanguage"),
        "tags": sn.get("tags", []),
    }


def fetch_videos(client: _yt.Client, ids: list[str], with_description: bool = False) -> dict[str, Any]:
    rows, seen = [], set()
    for batch in _yt.batches(ids, 50):
        page = client.data_api("videos", {"part": "snippet,statistics,contentDetails",
                                          "id": ",".join(batch), "maxResults": 50})
        for item in page.get("items", []):
            row = video_row(item)
            if with_description:
                row["description"] = item.get("snippet", {}).get("description", "")
            rows.append(row)
            seen.add(item["id"])
    now = datetime.now(timezone.utc)
    return {"ok": True, "as_of": now.date().isoformat(), "fetched_at": now.isoformat(timespec="seconds"),
            "videos": rows,
            # Deleted, private and mistyped ids are simply absent from the answer.
            "missing": [i for i in ids if i not in seen]}


def channel_row(item: dict[str, Any]) -> dict[str, Any]:
    sn, st, cd = item.get("snippet", {}), item.get("statistics", {}), item.get("contentDetails", {})
    return {
        "channel_id": item["id"],
        "title": sn.get("title"),
        "handle": sn.get("customUrl"),
        "published_at": sn.get("publishedAt"),
        "country": sn.get("country"),
        "subscribers": None if st.get("hiddenSubscriberCount") else _int(st.get("subscriberCount")),
        "views": _int(st.get("viewCount")),
        "videos": _int(st.get("videoCount")),
        "uploads_playlist": cd.get("relatedPlaylists", {}).get("uploads"),
    }


def cmd_videos(client: _yt.Client, a: argparse.Namespace) -> dict[str, Any]:
    ids = collect_ids(a.id, a.ids_file)
    if not ids:
        raise Refusal("no video ids: pass --id or --ids-file")
    return fetch_videos(client, ids, a.with_description)


def cmd_channels(client: _yt.Client, a: argparse.Namespace) -> dict[str, Any]:
    params: dict[str, Any] = {"part": "snippet,statistics,contentDetails", "maxResults": 50}
    if a.mine:
        params["mine"] = "true"
    elif a.handle:
        params["forHandle"] = a.handle if a.handle.startswith("@") else "@" + a.handle
    elif a.id:
        ids = [x.strip() for v in a.id for x in v.split(",") if x.strip()]
        bad = [x for x in ids if not CHANNEL_ID.match(x)]
        if bad:
            raise Refusal(f"not channel ids: {', '.join(bad)}")
        params["id"] = ",".join(ids[:50])
    else:
        raise Refusal("pass --id, --handle or --mine")
    page = client.data_api("channels", params)
    return {"ok": True, "channels": [channel_row(i) for i in page.get("items", [])]}


def cmd_uploads(client: _yt.Client, a: argparse.Namespace) -> dict[str, Any]:
    if a.mine:
        page = client.data_api("channels", {"part": "contentDetails", "mine": "true"})
        items = page.get("items", [])
        if not items:
            raise Refusal("the connected account has no channel")
        channel_id = items[0]["id"]
        playlist = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    else:
        if not a.channel_id or not CHANNEL_ID.match(a.channel_id):
            raise Refusal("pass --channel-id UC... (24 characters) or --mine")
        channel_id = a.channel_id
        # Every channel's uploads playlist is its id with UC replaced by UU; deriving it saves the
        # channels.list unit. A 404 falls back to asking.
        playlist = "UU" + channel_id[2:]
    since = parse_date(a.since, "--since") if a.since else None
    items, token, asked = [], None, a.mine
    while len(items) < a.max:
        params = {"part": "contentDetails", "playlistId": playlist, "maxResults": 50, "pageToken": token}
        try:
            page = client.data_api("playlistItems", params)
        except Refusal as e:
            if "404" not in str(e) or asked:
                raise
            asked = True
            ch = client.data_api("channels", {"part": "contentDetails", "id": channel_id})
            if not ch.get("items"):
                raise Refusal(f"channel {channel_id} not found") from None
            playlist = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
            continue
        stop = False
        for it in page.get("items", []):
            cd = it.get("contentDetails", {})
            published = cd.get("videoPublishedAt")
            if since and published and parse_date(published) < since:
                stop = True  # the uploads playlist lists newest first
                break
            items.append({"video_id": cd.get("videoId"), "published_at": published})
            if len(items) >= a.max:
                break
        token = page.get("nextPageToken")
        if stop or not token:
            break
    out: dict[str, Any] = {"ok": True, "channel_id": channel_id, "uploads_playlist": playlist,
                           "items": items}
    if a.with_stats and items:
        out["videos"] = fetch_videos(client, [i["video_id"] for i in items])["videos"]
        out["as_of"] = datetime.now(timezone.utc).date().isoformat()
    return out


def cmd_search(client: _yt.Client, a: argparse.Namespace) -> dict[str, Any]:
    cost = _yt.UNITS["search"] * a.pages
    if cost > a.budget:
        raise Refusal(f"{a.pages} page(s) of search cost {cost} units, over --budget {a.budget}; "
                      "search.list is 100 units a page against 1 for videos.list — narrow the query "
                      "or raise the budget on purpose")
    params: dict[str, Any] = {
        "part": "snippet", "type": "video", "q": a.q, "order": a.order, "maxResults": 50,
        "regionCode": a.region, "relevanceLanguage": a.language, "videoDuration": a.duration,
        "channelId": a.channel_id,
        "publishedAfter": f"{parse_date(a.published_after).isoformat()}T00:00:00Z" if a.published_after else None,
        "publishedBefore": f"{parse_date(a.published_before).isoformat()}T00:00:00Z" if a.published_before else None,
    }
    results, token = [], None
    for _ in range(a.pages):
        page = client.data_api("search", {**params, "pageToken": token})
        for it in page.get("items", []):
            sn = it.get("snippet", {})
            vid = it.get("id", {}).get("videoId")
            if vid:
                results.append({"video_id": vid, "channel_id": sn.get("channelId"),
                                "channel_title": sn.get("channelTitle"), "title": sn.get("title"),
                                "published_at": sn.get("publishedAt")})
        token = page.get("nextPageToken")
        if not token:
            break
    return {"ok": True, "query": a.q, "results": results,
            "note": "search returns no view counts; pass the ids to `videos` (1 unit per 50)"}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="data_api.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser("videos", help="stats, snippet and duration of videos, 50 per unit")
    v.add_argument("--id", action="append", help="a video id or a comma list; repeatable")
    v.add_argument("--ids-file", help="ids: one per line, a JSON list, or JSON with video_id / watch:<id>")
    v.add_argument("--with-description", action="store_true", help="include each description")

    c = sub.add_parser("channels", help="channel facts and its uploads playlist, 1 unit")
    c.add_argument("--id", action="append", help="a channel id UC... or a comma list")
    c.add_argument("--handle", help="a handle such as @name")
    c.add_argument("--mine", action="store_true", help="the connected channel")

    u = sub.add_parser("uploads", help="a channel's latest uploads, 1 unit per 50")
    u.add_argument("--channel-id")
    u.add_argument("--mine", action="store_true")
    u.add_argument("--max", type=int, default=50, help="at most this many videos (default 50)")
    u.add_argument("--since", help="stop at videos published before this date")
    u.add_argument("--with-stats", action="store_true", help="also read their stats (videos.list)")

    s = sub.add_parser("search", help="search.list, 100 units a page of up to 50")
    s.add_argument("--q", required=True, help="the query")
    s.add_argument("--order", default="relevance", choices=["date", "rating", "relevance", "title", "viewCount"])
    s.add_argument("--published-after")
    s.add_argument("--published-before")
    s.add_argument("--region", help="two-letter region code")
    s.add_argument("--language", help="relevanceLanguage, e.g. en")
    s.add_argument("--duration", choices=["any", "short", "medium", "long"],
                   help="short <4 min, medium 4-20, long >20")
    s.add_argument("--channel-id")
    s.add_argument("--pages", type=int, default=1, help="pages of 50 (default 1)")
    s.add_argument("--budget", type=int, default=200, help="most units this call may spend (default 200)")
    return p


COMMANDS = {"videos": cmd_videos, "channels": cmd_channels, "uploads": cmd_uploads, "search": cmd_search}


def main(argv: list[str] | None = None) -> dict[str, Any]:
    a = parser().parse_args(argv)
    client = _yt.Client()
    out = COMMANDS[a.command](client, a)
    out["quota"] = client.quota()
    return out


if __name__ == "__main__":
    sys.exit(run(main))
