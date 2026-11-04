# Impressions and impression CTR per video

Used by Daily data (recipe 2), read by Analytics and Planning through the `studio:<videoId>` record.

## Prefer the API: Reporting API reach reports

Google added reach reports to the **YouTube Reporting API** on 2026-01-15 (Reporting API revision
history, read 2026-11-04):

| Report | Dimensions | Metrics |
| --- | --- | --- |
| `channel_reach_basic_a1` | `date`, `channel_id`, `video_id` | `video_thumbnail_impressions`, `video_thumbnail_impressions_ctr` |
| `channel_reach_combined_a1` | the above + traffic source, device, OS | the same |

So impressions and impression CTR per video per day **do** come from an API, and Studio is the
fallback. What the path needs (Reporting API docs, read 2026-11-04):

- A **job** per report type, created once with `jobs.create` (Onboarding is the natural place).
  YouTube generates nothing until a job exists.
- The first daily report arrives about two days after the day it covers; a new job also backfills
  the 30 days before it was created. Reports stay downloadable 60 days (backfill: 30 days).
- One report per Pacific-time day; a day without data still produces a file with a header only —
  that is `available=false`, not a failure.
- Scope `yt-analytics.readonly`, which the platform's YouTube connection carries.
- **The CTR unit is not stated.** The metric is defined as "the percentage of impressions that
  resulted in a click … calculated as clicks divided by impressions". Before the first write, compare
  one video-day with Studio (this playbook, below) and fix the unit in the recipe; the `studio`
  record wants a fraction and refuses 4.5. `scripts/studio_reach.py --ctr-unit` takes it explicitly
  when a header does not show `%`.

Write `records.py write studio … --source reporting-api`. Fetching and parsing the report is data
work (youtube-data); this file only records why the browser is the fallback.

## Fallback: Studio Analytics, Advanced mode

Use it when the reach job does not exist yet, its report for the day is missing, or the owner asked
for a Studio cross-check.

**Preconditions:** the session check of `session.md` passed as the profile's channel; the list of the
channel's own video ids for the day (youtube-data) so every video gets a record.

**Steps** (labels as Studio showed them in 2026; Studio renames things — find controls by meaning
in a snapshot, not by position):

1. Open `https://studio.youtube.com/channel/<channel_id>/analytics` and run the session check.
2. Click **Advanced mode** (top right of Analytics). The table is grouped by **Content** (video).
3. Date range: a custom range with start = end = the `as_of` day. Take a day at least two days back:
   Studio's and the API's numbers for the last 48–72 h are still being processed (Reporting API
   revision history, 2026-09-09 entry, read 2026-11-04).
4. Metrics: make sure the table has **Impressions** and **Impressions click-through rate**. Add
   them from the metric picker if missing; other columns may stay.
5. Export: the download icon (**Export current view**) → **Comma-separated values (.csv)**. Studio
   downloads an archive with `Table data.csv` (per video), `Chart data.csv` and `Totals.csv`.
   If the browser's download does not reach the step's files, read the table from the page and write
   the same CSV by hand: `Content,Impressions,Impressions click-through rate (%)`, one row per video
   id, numbers as shown.
6. Convert: `python3 <base>/scripts/studio_reach.py --csv "Table data.csv" --as-of <day> --video <id> …`
   (one `--video` per own video). It reads the CTR unit from the header (`(%)` → divides by 100),
   skips the Total row, and gives every expected video a row — `available=false` when the export
   has none.
7. Write each row: `python3 <records-base>/scripts/records.py write studio --video-id … --as-of …
   --available … [--impressions … --ctr …] --source studio-export`.

**Verify:** the number of rows equals the number of own videos asked for; the Totals row's
impressions are not smaller than the largest single video; spot-check one video's CTR on its own
Analytics → Reach tab for the same day.

**Record:** the CSV as the step's artifact (`studio-metrics-<as_of>.csv`) and one `studio` record per
video. When the session is missing or the export fails, every video of the day gets
`--available false --source studio-export`, and the step says why.

No intent is needed: this playbook only reads.

Sources: developers.google.com/youtube/reporting/v1/reports/channel_reports, …/reports/metrics,
…/reporting/v1/reports (jobs, backfill, retention), …/reporting/revision_history — all read 2026-11-04.
