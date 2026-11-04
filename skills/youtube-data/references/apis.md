# YouTube APIs: what each gives, in which unit

Read 2026-11-04 from developers.google.com/youtube (pages named per section). Where the docs are
silent, this page says so instead of guessing.

## Data API v3 — public facts, quota units

Cost per call (`/youtube/v3/determine_quota_cost`): `videos.list`, `channels.list`,
`playlistItems.list`, `commentThreads.list` 1 unit each, up to 50 items per call;
`search.list` **100**. Default quota: 10,000 units a day per Google Cloud project, reset at midnight
Pacific time. Reads need the `youtube.readonly` scope (or `youtube`).

- A channel's uploads playlist is its id with `UC` replaced by `UU`; `data_api.py uploads` derives
  it and saves a `channels.list` call. Items come newest first.
- `statistics.likeCount` is absent when the owner hides likes; `subscriberCount` is rounded to
  three significant figures for public reads, and absent when hidden.
- `contentDetails.duration` is ISO 8601 (`PT4M13S`); the scripts give `duration_s`.

## Analytics API v2 — own channel, `reports.query`

`ids=channel==MINE`, `startDate`, `endDate` (YYYY-MM-DD), `metrics`, optional `dimensions`,
`filters`, `sort`, `maxResults`. Scope `yt-analytics.readonly`; revenue metrics need
`yt-analytics-monetary.readonly`. Its quota is separate from the Data API's.

| Metric | Unit (metrics page) |
| --- | --- |
| `views` | count |
| `estimatedMinutesWatched` | minutes |
| `averageViewDuration` | seconds |
| `averageViewPercentage` | percentage of the video; the docs do not state 0–1 or 0–100 — returned values read like `41.7`, i.e. 0–100 |
| `subscribersGained`, `subscribersLost`, `likes`, `comments`, `shares` | counts |
| `audienceWatchRatio` | ratio of viewers still watching at that point; **not a percent**, can exceed 1 where segments are rewatched |
| `relativeRetentionPerformance` | 0–1 against videos of similar length; 0.5 is the median |

**Not in this API** (metrics page): `impressionClickThroughRate`, `videoThumbnailImpressions` or
any thumbnail CTR. `impressions` is the former name of `adImpressions` (ad impressions, monetary)
— an upstream script that asks for `impressions` and `impressionClickThroughRate` gets ad numbers
or a 400. `analytics.py` refuses those names with this explanation.

Reports used (channel reports page):

- **Top videos / per video**: dimension `video`, `sort` required, `maxResults` ≤ 200;
  `filters=video==id1,id2` limits it to given videos. A video with no views in the period has no row.
- **Traffic sources**: dimension `insightTrafficSourceType`, metrics `views`,
  `estimatedMinutesWatched` (and `engagedViews`). Values include `YT_SEARCH`, `RELATED_VIDEO`
  (Studio's "suggested videos"), `SUBSCRIBER` (Studio's "browse features"), `YT_CHANNEL`, `SHORTS`,
  `EXT_URL`, `PLAYLIST`, `NOTIFICATION`, `END_SCREEN`, `HASHTAGS`, `ADVERTISING` and others (22 on
  the dimensions page).
  The video count × days must stay under 50,000.
- **Audience retention**: dimension `elapsedVideoTimeRatio`, filter `video==<one id>` (a list is
  refused), optional `audienceType` (`ORGANIC`, `AD_INSTREAM`, `AD_INDISPLAY`), `subscribedStatus`,
  `youtubeProduct`. The API returns **100 points, ratio 0.01 to 1.0**, each the exclusive end of
  its interval (dimensions page).

### Retention → retention.py

retention.py reads a position and a share still watching. `analytics.py retention` writes
position × 100 (percent of the video) and `audienceWatchRatio` × 100, with a header row, and its
`next` field is the call to make: `retention.py <csv> --axis percent --duration <seconds>`.
The duration must be the video's real length (`data_api.py videos` → `duration_s`); without it
retention.py cannot place a cliff in seconds and refuses `--transcript`. The upstream script guessed
the axis from `max(x) <= 100.5`, so the API's raw ratio was read as percent and the 30-second hook
window covered the whole video — the reason the axis is now stated.

## Reporting API — thumbnail impressions and CTR

Reach reports (channel reports page of the Reporting API):

- `channel_reach_basic_a1` — dimensions `date`, `channel_id`, `video_id`; metrics
  `video_thumbnail_impressions`, `video_thumbnail_impressions_ctr`.
- `channel_reach_combined_a1` — the same metrics split also by traffic source, OS and device.

`video_thumbnail_impressions`: "the number of times that video thumbnails were shown to viewers";
counted when the thumbnail is shown more than 1 second with at least 50 % visible.
`video_thumbnail_impressions_ctr`: "the percentage of impressions that resulted in a click to
watch", calculated as clicks / impressions. **Whether the file holds 0.045 or 4.5 is not stated.**
`reporting.py reach` therefore takes `--ctr-scale fraction|percent` from the caller and refuses a
value that contradicts it (above 1 with `fraction`). The first time a recipe reads a real file,
compare one video's CTR with Studio's figure for the same day, then fix the flag in the recipe.

How the bulk API works (reports overview page):

1. A job is created once per report type (`reporting.py ensure-job`), with the
   `yt-analytics.readonly` scope.
2. Reports are retrievable within 48 hours; each covers one day and arrives about two days after it.
   A new job also generates the 30 days before its creation.
3. A revised day is reissued under a new report id with the same `startTime`; the newest
   `createTime` wins (the script does this).
4. Standard reports are kept 60 days, historical ones 30. A day with no data is a header-only file.

So impressions and CTR come from the Reporting API or from Studio (the Reach tab's export); the
Reporting API needs no browser, but its newest day is about two days old. A video with no row in
the read reports is written `available=false`, which the studio record exists to say.

## Public files without a token

- Thumbnails: `https://i.ytimg.com/vi/<id>/{maxresdefault,sddefault,hqdefault}.jpg` and
  `https://i.ytimg.com/vi_webp/<id>/<size>.webp`. maxresdefault (1280×720) is missing for many
  videos; hqdefault (480×360) exists for every public one.
- Subtitles through yt-dlp: uploaded tracks by language code, auto-captions as `<lang>` or
  `<lang>-orig`. Auto-captions in another language than the spoken one are machine translations.
