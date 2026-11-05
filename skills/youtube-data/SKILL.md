---
name: youtube-data
description: Deterministic YouTube reads within quota — Data API v3 (video stats in batches of 50, channel facts, a channel's uploads, search with a unit budget), Analytics API (per-video views, watch time, average view duration and percentage, traffic sources, the retention curve as a CSV for youtube-metrics' retention.py), Reporting API reach reports (thumbnail impressions and CTR as studio records), transcripts from subtitles through yt-dlp, channels' median views and subscribers from their public pages (channel_baselines.py, no token), and public thumbnail downloads of any video. Use whenever a step needs numbers or files from YouTube rather than an opinion: niche research before the channel is connected, daily snapshots, recon candidates, weekly analytics, retention diagnosis, competitor thumbnails.
---

# YouTube data

Scripts that read YouTube and print JSON. Call them by path from this skill's base directory:
`python3 <base>/scripts/<script>.py ...`. Standard library only; `transcript.py` needs the `yt-dlp`
CLI attached to the step. A refusal is `{"ok": false, "error": ...}` with exit code 2 — read the
error, fix the cause, do not work around it.

The token comes from `ai-integration oauth-token --connection YOUTUBE` inside the scripts, at the
moment of use. Never fetch it yourself to pass along, never print or save it. "not given" in an
error means the recipe or step lacks `YOUTUBE_REFRESH_TOKEN`; "not connected" or "reconnect" means
the owner connects YouTube on the project's credentials page — ask them.

## Commands

| Need | Command | Cost |
| --- | --- | --- |
| Stats, title, duration of videos (a dated snapshot) | `data_api.py videos --id ID,ID --ids-file F` | 1 unit / 50 videos |
| Channel facts: subscribers, video count, created, uploads playlist | `data_api.py channels --id UC... \| --handle @x \| --mine` | 1 unit |
| A channel's latest uploads, with stats | `data_api.py uploads --channel-id UC... --max 20 --with-stats` | 1 unit / 50 + videos |
| Search | `data_api.py search --q "..." --published-after D --order viewCount` | **100 units a page**; refused over `--budget` (200) |
| Per-video views, watch time, AVD, APV, subscribers, for own videos | `analytics.py video-metrics --id ... --start D --end D` | Analytics quota |
| Channel totals, by day or month | `analytics.py channel --start D --end D [--by day]` | Analytics quota |
| Traffic sources | `analytics.py traffic [--id ...] --start D --end D` | Analytics quota |
| Retention curve → CSV for retention.py | `analytics.py retention --id ID --start <published> --end D --duration <duration_s> --csv retention-ID.csv` | Analytics quota |
| Anything else in Analytics (audience, revenue) | `analytics.py query --metrics ... --dimensions ... --filters ...` | Analytics quota |
| Thumbnail impressions and CTR of own videos | `reporting.py ensure-job` once, then `reporting.py reach --ctr-scale <scale> --id ...` | Reporting API |
| Each channel's median views of its latest uploads and its subscribers, before the channel is connected (niche research) | `channel_baselines.py --serp F [--serp F2 ...] --out baselines.json` or `--channel-id UC...`; resumable, stops on 429 | none (yt-dlp, public pages) |
| Transcript (srt keeps timings) | `transcript.py --id ID --lang <channel language> --out ID.srt` | none (yt-dlp) |
| Competitor or own thumbnails | `thumbnails.py --id ID ... --out-dir thumbs/` | none (public files) |

`--ids-file` takes ids one per line, a JSON list, or any JSON with `video_id` fields or
`watch:<id>` keys — the answer of `query-template-records` can be passed as it comes.

## Rules

- **Quota.** The Data API gives 10,000 units a day per Google project. Every answer carries
  `quota.data_api_units`; say the total in the step's summary. Prefer `uploads` + `videos`
  (1 unit per 50) to `search` (100 per page); search only to discover, never to re-read what you know.
- **Search returns no view counts**: pass its ids to `videos`.
- **Absent is not zero**: `missing` (deleted or private videos), `no_rows` (no views in the
  period), `likes: null` (hidden). Report them; do not fill them in.
- **Analytics lags 2–3 days**; end a weekly period three days ago when exact days matter.
- **There is no impressions or CTR metric in the Analytics API.** `impressions` there is the old
  name of ad impressions. Thumbnail impressions and CTR come from `reporting.py` (Reporting API
  reach reports) or a Studio export — see `references/apis.md` before using either.
- **Retention**: pass the video's real duration (`duration_s` from `videos`); the answer's `next`
  is the exact retention.py command. Without views enough, `available: false` — say so.
- **Transcripts**: pass `--lang` = the channel's language (profile). For a video in another
  language, `en` auto-captions are a machine translation. Private videos have none.

## What to record after

| Read | Then |
| --- | --- |
| `videos` for the watchlist (daily) | keep the output as the dated snapshot artifact; youtube-metrics `velocity.py` → `records.py write velocity` |
| `search` / `uploads` for recon | youtube-metrics `candidates.py` → `records.py write watch` for the ones you keep |
| `reporting.py reach` | each element of `records` → `records.py write studio` (fields as they come) |
| analytics, transcripts, thumbnails | step artifacts; no record kind holds them |

Read `references/apis.md` when you query Analytics beyond the commands above, set up the reach
job, or need a metric's unit.
