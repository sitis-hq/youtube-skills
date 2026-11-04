---
name: youtube-demand
description: Keyword demand for a YouTube channel through DataForSEO — Google web search volume, CPC, web keyword difficulty and intent (Labs), YouTube search interest index (Google Trends type=youtube), rising related queries, and competition in the YouTube top 20 (our formula over the YouTube SERP). Use when a step measures or expands seed keywords (Onboarding seed set, weekly Recon keyword research and rising queries, Planning's keywords for repackaging) and writes `seed` records.
---

# YouTube demand

## What the numbers are — read this first

- **No source gives YouTube search volume.** Not DataForSEO, not Google Ads, not any actor found
  (demand review, 2026-11-04). `volume` is **Google web** monthly searches from Google Ads data.
- `yt_interest` is **Google Trends with `type: "youtube"`**: a relative index 0–100, not a count.
  Up to 5 keywords in one request share one scale; values from different requests do not compare.
  A keyword asked alone is scaled to its own peak, so its number says how steady interest was, not
  how large. Put the terms you want ranked against each other in the same request.
- `kd_web` is DataForSEO's keyword difficulty 0–100, built from link profiles of the top 10 **web**
  pages — a weak proxy for YouTube. Record it as it comes; never rescale it.
- `yt_competition` is **ours**: a 0..1 heuristic from the YouTube top 20 (below). Treat it as a
  ranking aid between keywords, not as a measurement.

## Access: DataForSEO MCP server `dataforseo-mcp-server@3.1.3`

Checked against the 3.1.3 package source (2026-11-04). The server exposes four generic tools —
`docs_index`, `docs_list_sections`, `docs_search`, `api_request`; the named tools older guides
mention (`kw_data_google_trends_explore`, `serp_youtube_organic_live_advanced`, …) no longer exist.

`api_request` takes `{"method": "POST", "path": "/v3/...", "data": [{...}], "noAiMode": true}`.

- **Always pass `noAiMode: true`.** By default the server appends `.ai` to the path and returns an
  undocumented trimmed shape; the scripts here read only the documented full response and refuse
  anything else. GET calls (`task_get`, `tasks_ready`) need it too.
- **Save the response body to a file exactly as it came** (one file per call, under the step's work
  directory) and pass the files to the scripts. Do not retype or summarise numbers.
- A **Live** endpoint takes one task per call; the server silently drops extra tasks with a warning.
- Shell variant, same binary, keeps big responses out of the conversation:
  `npx -y dataforseo-mcp-server@3.1.3 request -X POST -p <path> -d '<json array>' --no-ai-mode > file.json`
  (use only when the step has node; a leading `Warning:` line is tolerated by the scripts).
- **Credentials** (secret credentials of the project): `DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD`,
  the API login/password from app.dataforseo.com/api-access, not the account password. The server
  reads `DATAFORSEO_LOGIN` and falls back to `DATAFORSEO_USERNAME` as an alias; the password has no
  alias. When they are missing, say so to the owner (they add them as secrets), do not invent
  numbers, and record seeds without metrics (`--source owner` or `competitor`).
- Errors (docs appendix, 2026-11-04): a top-level `status_code` other than `20000` (`40100`
  unauthorised, `40200` balance empty, `40202` rate limit) fails the whole call; a task with another
  code failed alone (`40102` = no results for that task).

## Calls

Location and language come from the `profile` record (`country`, `language`); pass names
(`"location_name": "United States"`, `"language_name": "English"`) or codes (`2840`, `"en"`).
Prices from DataForSEO's pricing pages as read 2026-11-04; the response's `cost` field is the truth.

| Need | Path | Body (one task) | Cost |
| --- | --- | --- | --- |
| Metrics for a list (volume, CPC, KD, intent, 12 monthly volumes) | `/v3/dataforseo_labs/google/keyword_overview/live` | `{"keywords": [..≤700], "location_name": L, "language_name": G}` | $0.012 + $0.00012 per keyword (Live only) |
| Expand seeds into ideas | `/v3/dataforseo_labs/google/keyword_ideas/live` | `{"keywords": [..≤200], "location_name": L, "language_name": G, "limit": 100, "order_by": ["keyword_info.search_volume,desc"]}` | same |
| Related searches of one seed | `/v3/dataforseo_labs/google/related_keywords/live` | `{"keyword": K, "depth": 1, "location_name": L, "language_name": G, "limit": 100}` | same |
| YouTube interest, compare ≤5 terms | `/v3/keywords_data/google_trends/explore/live` | `{"keywords": [..≤5], "type": "youtube", "time_range": "past_12_months", "location_name": L, "item_types": ["google_trends_graph"]}` | Live $0.011 per task |
| Rising/top YouTube queries of one term | same path | `{"keywords": [K], "type": "youtube", "time_range": "past_90_days", "location_name": L, "item_types": ["google_trends_queries_list"]}` (related queries need exactly one keyword) | same |
| YouTube top 20 for a keyword | `/v3/serp/youtube/organic/live/advanced` | `{"keyword": K, "location_name": L, "language_code": "en", "device": "mobile", "block_depth": 20}` | Live $0.002 per 20 results |

`include_clickstream_data: true` doubles the Labs price — leave it off. Google Ads
`/v3/keywords_data/google_ads/search_volume/live` ($0.09 per task of up to 1 000 keywords) is the
fallback for volume and CPC when Labs has no data for a market; `normalize.py --labs` reads it too.

**Standard instead of Live** (cheaper, asynchronous): Trends `.../google_trends/explore/task_post`
$0.0027 (results within ~45 min) and SERP `/v3/serp/youtube/organic/task_post` $0.0006, up to 100
tasks per POST. Collect with `GET .../explore/tasks_ready` / `.../organic/tasks_ready`, then
`GET /v3/keywords_data/google_trends/explore/task_get/<id>` or
`/v3/serp/youtube/organic/task_get/advanced/<id>`. Use Standard when the step can post early and
collect later (weekly Recon with many seeds); use Live when it needs the answer now. Labs is Live only.

Weekly budget guide for one channel (demand review): ~30 seeds → about $0.2–0.4 a week Live.

## Scripts

| Need | Command |
| --- | --- |
| Saved responses → `seed` rows | `python3 <base>/scripts/normalize.py --labs F [--labs F2] [--trends F] [--serp F] [--channels F] [--only TERM ...] --as-of YYYY-MM-DD` |
| Competition alone | `python3 <base>/scripts/yt_competition.py --serp F [--channels F]` or `--videos F --keyword K` |

`normalize.py` merges all files by term (lowercased) and prints `rows` (only the `seed` fields,
plus `write_args`), `related` (Trends rising/top queries: candidates **without** metrics — run them
through `keyword_overview` before they become seeds), `trends_batches` (which terms share a scale),
`competition`, `cost_usd`, `errors` (failed tasks) and `warnings`. Labs ideas return many terms you
did not ask for: choose, then pass `--only` for the ones to keep. It refuses Trends that are not
`type: youtube`, the `.ai` shape and account errors (exit 2).

Write each chosen row through youtube-records:
`python3 <records-base>/scripts/records.py write seed <write_args...>`.

`--channels` and `--videos` take youtube-data output (`data_api.py channels --id ...`, `videos`):
the DataForSEO SERP has no subscriber counts, so without `--channels` competition is computed
without the authority part. `--videos` lets a step use Data API search results instead of the
DataForSEO SERP (pass ids in search-rank order).

## `yt_competition` — the formula (a heuristic)

Over the top 20 organic videos (channels, playlists and paid results are skipped):

```
scale(x, lo, hi) = clamp((x - lo) / (hi - lo), 0, 1)
traffic   = mean(scale(log10(median views), 2, 7), scale(log10(median views/day), 0, 4))
targeting = share of titles containing every word of the keyword (case and accents folded)
authority = scale(log10(median channel subscribers), 3, 7)     # only when ≥ half have a count
yt_competition = 0.45·traffic + 0.25·targeting + 0.30·authority   (weights rescaled if a part is missing)
```

Read the parts, not just the total: high `traffic` with low `targeting` means big videos answer the
query without targeting it — a precise title can still win; high `targeting` with low `traffic` is
a crowded but small query. `confidence: "low"` below 5 videos. `shorts_share` and
`median_age_days` are reported for the reader; old, slow top results suggest room for a fresh video.
The anchors (100 views, 10M views, 1k–10M subscribers) are our choices, not YouTube's.

## Which recipe uses what

- **Onboarding (1)**: niche check (`keyword_overview` + Trends compare on 10–15 niche terms, SERP on
  3–5 core terms), then the initial seed set → `seed` records (`--source dataforseo`).
- **Recon (3)**: rising queries per main seed (Trends queries list) → measure with Labs → new
  `seed` records in Recon's own memory; SERP for competition of the week's candidates. Recon never
  rewrites a record in Onboarding's memory (one writer per record; see youtube-records).
- **Planning (5)**: read `seed` records first; call Labs only for terms that have none or whose
  `as_of` is older than a month (Labs updates monthly).
