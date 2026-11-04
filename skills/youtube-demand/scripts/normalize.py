#!/usr/bin/env python3
"""Turn saved DataForSEO responses into `seed` rows: term, volume, cpc, kd_web, intent, yt_interest,
yt_competition, as_of — the fields of the `seed` record in youtube-records, in its units.

The step calls DataForSEO (MCP `api_request` with noAiMode: true, or the CLI with --no-ai-mode),
saves each response body to a file as it came, and passes the files here:

  --labs FILE     /v3/dataforseo_labs/google/{keyword_overview,keyword_ideas,related_keywords}/live,
                  or the fallback /v3/keywords_data/google_ads/search_volume/... (repeatable)
  --trends FILE   /v3/keywords_data/google_trends/explore/... with "type": "youtube" (repeatable)
  --serp FILE     /v3/serp/youtube/organic/.../advanced (repeatable) -> yt_competition
  --channels FILE youtube-data `channels` output, subscriber counts for yt_competition

Units, as the records contract states them:
  volume         Google *web* monthly searches (Google Ads data). There is no YouTube search volume
                 anywhere; this is not one.
  cpc            USD.
  kd_web         DataForSEO keyword_difficulty 0-100, as it comes — a web metric, not YouTube.
  yt_interest    Google Trends YouTube-search interest, the mean of the term's series over the
                 requested range, 0-100. Relative: comparable only between terms of the SAME request
                 (up to 5 keywords share one scale). A term asked alone is scaled to its own peak, so its
                 mean says how steady interest was, not how large.
  yt_competition our 0..1 heuristic from the YouTube top 20 (yt_competition.py).

Prints {"ok": true, "rows": [...], "related": [...], "trends_batches": [...], "cost_usd": ...}.
Each row carries `write_args`, the flags for `records.py write seed`. Rising and top related queries
from Trends come back in `related` as candidates, without metrics: measure them with Labs before
they become seeds. A refusal exits 2 with {"ok": false, "error": ...}.

Standard library only: Python 3.11.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yt_competition  # noqa: E402

INTENTS = {"informational", "navigational", "commercial", "transactional"}
FIELDS = ("term", "source", "as_of", "volume", "cpc", "kd_web", "yt_interest", "yt_competition", "intent")


class Refusal(Exception):
    pass


def term_key(text: str) -> str:
    # DataForSEO lowercases keywords; whitespace differences must not split one term into two rows.
    return re.sub(r"\s+", " ", text.strip().lower())


def load(path: str) -> dict[str, Any]:
    try:
        doc = yt_competition.load_json(path)
    except yt_competition.Refusal as e:
        raise Refusal(str(e)) from None
    if not isinstance(doc, dict) or "tasks" not in doc:
        raise Refusal(f"{path}: not a DataForSEO response (no 'tasks'). Save the response body as it "
                      "came, requested with noAiMode: true (MCP api_request) or --no-ai-mode (CLI); "
                      "the default .ai shape is not documented and is not read here")
    if doc.get("status_code") not in (None, 20000):
        raise Refusal(f"{path}: DataForSEO error {doc.get('status_code')}: {doc.get('status_message')}")
    return doc


def results(doc: dict[str, Any], path: str, errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for task in doc.get("tasks") or []:
        if task.get("status_code") != 20000:
            errors.append({"file": path, "task": task.get("id"), "status_code": task.get("status_code"),
                           "status_message": task.get("status_message")})
            continue
        out.extend(r for r in task.get("result") or [] if isinstance(r, dict))
    return out


def _int(v: Any) -> int | None:
    return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def labs_row(entry: dict[str, Any]) -> dict[str, Any] | None:
    """One keyword from any Labs shape, or from Google Ads search_volume."""
    if "keyword_data" in entry:          # related_keywords wraps the keyword one level down
        entry = entry["keyword_data"] or {}
    kw = entry.get("keyword")
    if not kw:
        return None
    info = entry.get("keyword_info") or {}
    props = entry.get("keyword_properties") or {}
    intent = (entry.get("search_intent_info") or {}).get("main_intent")
    if "keyword_info" not in entry and "search_volume" in entry:   # Google Ads search_volume
        info = entry
    row: dict[str, Any] = {"term": kw}
    vol = _int(info.get("search_volume"))
    if vol is not None and vol >= 0:
        row["volume"] = vol
    cpc = info.get("cpc")
    if isinstance(cpc, (int, float)) and not isinstance(cpc, bool) and cpc >= 0:
        row["cpc"] = round(float(cpc), 4)
    kd = _int(props.get("keyword_difficulty"))
    if kd is not None:
        if 0 <= kd <= 100:
            row["kd_web"] = kd
        else:
            print(f"keyword_difficulty {kd} for {kw!r} is outside 0-100; dropped", file=sys.stderr)
    if intent in INTENTS:
        row["intent"] = intent
    return row


def labs_entries(result: dict[str, Any]) -> list[dict[str, Any]]:
    if "items" in result:
        entries = list(result.get("items") or [])
        # related_keywords also reports the seed itself; keep it, it is a measured keyword too.
        for seed in result.get("seed_keyword_data") or []:
            if isinstance(seed, dict):
                entries.append(seed)
        return entries
    return [result]   # Google Ads search_volume: each result is one keyword


def trends(result: dict[str, Any], batches: list[list[str]], related: list[dict[str, Any]],
           warnings: list[str]) -> dict[str, int]:
    keywords = [str(k) for k in result.get("keywords") or []]
    interest: dict[str, int] = {}
    for item in result.get("items") or []:
        kind = item.get("type")
        if kind == "google_trends_graph":
            kws = [str(k) for k in item.get("keywords") or keywords]
            series: list[list[float]] = [[] for _ in kws]
            for point in item.get("data") or []:
                if point.get("missing_data"):
                    continue
                for i, v in enumerate(point.get("values") or []):
                    if i < len(series) and isinstance(v, (int, float)):
                        series[i].append(float(v))
            averages = item.get("averages") or []
            for i, kw in enumerate(kws):
                if i < len(averages) and isinstance(averages[i], (int, float)):
                    value = float(averages[i])
                elif series[i]:
                    value = statistics.fmean(series[i])
                else:
                    continue
                interest[kw] = max(0, min(100, round(value)))
            if kws:
                batches.append(kws)
                if len(kws) == 1:
                    warnings.append(f"Trends was asked about {kws[0]!r} alone: its yt_interest is scaled to "
                                    "its own peak and does not compare with other terms")
        elif kind == "google_trends_queries_list":
            data = item.get("data") or {}
            for bucket in ("rising", "top"):
                for q in data.get(bucket) or []:
                    if q.get("query"):
                        related.append({"query": q["query"], "kind": bucket, "value": q.get("value"),
                                        "from": [str(k) for k in item.get("keywords") or keywords]})
    return interest


def merge(rows: dict[str, dict[str, Any]], row: dict[str, Any], source: str) -> None:
    key = term_key(row["term"])
    have = rows.setdefault(key, {"term": key, "source": source})
    for f, v in row.items():
        if f != "term" and v is not None and have.get(f) is None:
            have[f] = v


def write_args(row: dict[str, Any]) -> list[str]:
    args = []
    for f in FIELDS:
        if row.get(f) is not None:
            args += ["--" + f.replace("_", "-"), str(row[f])]
    return args


def run(argv: list[str] | None = None) -> dict[str, Any]:
    p = argparse.ArgumentParser(description="Normalise saved DataForSEO responses into seed rows.")
    p.add_argument("--labs", action="append", default=[], help="Labs or Google Ads volume response (repeatable)")
    p.add_argument("--trends", action="append", default=[], help="Google Trends explore response, type=youtube (repeatable)")
    p.add_argument("--serp", action="append", default=[], help="YouTube organic SERP response (repeatable)")
    p.add_argument("--channels", action="append", default=[], help="youtube-data `channels` output for subscriber counts")
    p.add_argument("--as-of", help="the day the numbers were read, YYYY-MM-DD (default: today, UTC)")
    p.add_argument("--source", default="dataforseo",
                   help="the seed's source for rows with Labs data (default dataforseo); Trends-only rows get 'trends'")
    p.add_argument("--only", action="append", default=[],
                   help="keep only these terms (repeatable); Labs ideas return many you did not ask for")
    a = p.parse_args(argv)
    if not (a.labs or a.trends or a.serp):
        raise Refusal("pass at least one of --labs, --trends, --serp")
    as_of = a.as_of or datetime.now(timezone.utc).date().isoformat()
    try:
        date.fromisoformat(as_of)
    except ValueError:
        raise Refusal(f"--as-of must be YYYY-MM-DD, got {as_of!r}") from None

    errors: list[dict[str, Any]] = []
    warnings: list[str] = []
    rows: dict[str, dict[str, Any]] = {}
    cost = 0.0
    for path in a.labs:
        doc = load(path)
        cost += float(doc.get("cost") or 0)
        for result in results(doc, path, errors):
            for entry in labs_entries(result):
                row = labs_row(entry) if isinstance(entry, dict) else None
                if row:
                    merge(rows, row, a.source)

    related: list[dict[str, Any]] = []
    batches: list[list[str]] = []
    for path in a.trends:
        doc = load(path)
        cost += float(doc.get("cost") or 0)
        for task in doc.get("tasks") or []:
            ttype = (task.get("data") or {}).get("type", "web")
            if task.get("status_code") == 20000 and ttype != "youtube":
                # Web interest under a field named yt_interest would be a silent lie.
                raise Refusal(f"{path}: Trends task {task.get('id')} has type {ttype!r}; yt_interest "
                              "needs \"type\": \"youtube\"")
        for result in results(doc, path, errors):
            for kw, value in trends(result, batches, related, warnings).items():
                key = term_key(kw)
                if key in rows:
                    rows[key].setdefault("yt_interest", value)
                else:
                    rows[key] = {"term": key, "source": "trends", "yt_interest": value}

    channels = yt_competition.subscribers_from(a.channels) if a.channels else {}
    competition = []
    for path in a.serp:
        doc = load(path)
        cost += float(doc.get("cost") or 0)
        for task in yt_competition.serp_tasks(doc, path):
            now = yt_competition.parse_when(task["datetime"]) or datetime.now(timezone.utc)
            c = yt_competition.score(task["keyword"] or "", yt_competition.videos_from_serp(task["items"]),
                                     now, channels)
            competition.append(c)
            key = term_key(c["keyword"])
            if key in rows:
                rows[key]["yt_competition"] = c["yt_competition"]
            elif key:
                rows[key] = {"term": key, "source": a.source, "yt_competition": c["yt_competition"]}

    if a.only:
        keep = {term_key(t) for t in a.only}
        rows = {k: v for k, v in rows.items() if k in keep}

    out_rows = []
    for row in rows.values():
        row["as_of"] = as_of
        clean = {f: row[f] for f in FIELDS if row.get(f) is not None}
        out_rows.append({**clean, "write_args": write_args(clean)})
    out_rows.sort(key=lambda r: (-(r.get("volume") or 0), r["term"]))
    if not out_rows and errors:
        raise Refusal(f"every DataForSEO task failed: {errors}")
    return {"ok": True, "as_of": as_of, "rows": out_rows, "related": related,
            "trends_batches": batches, "competition": competition,
            "cost_usd": round(cost, 6), "errors": errors, "warnings": warnings,
            "note": "volume is Google web search volume; yt_interest is a relative index, not a count; "
                    "no source gives YouTube search volume"}


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
