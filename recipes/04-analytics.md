# Brief 4 — YouTube Analytics

Follow [the rules of the set](README.md); this brief adds what is specific to Analytics.

**Name:** `YouTube Analytics` · **Scope:** global recipe, run inside the channel's own project ·
**Schedule:** weekly, Tuesday 05:00 (`0 5 * * 2`) in the time zone of `profile:channel`'s
`country` — the zone every scheduled recipe of the set except Daily data uses, so Recon's Monday
05:00 is in the same zone. Recon runs Monday 05:00 and can take well over an hour, so Analytics runs a day later
and reads the newest Recon run, whichever day it finished · **Reads from:** YouTube Onboarding,
YouTube Daily data, YouTube Recon, YouTube Planning (when it exists), and every content-creation
recipe that writes `publish` records (for example "Create Music Release").

## What it is for

Once a week it reads how the channel did and says what to change first. It is a reader: it changes
nothing on the channel, takes no irreversible action and claims no intent. Its settings
recommendations are artifacts that "YouTube Planning" reads and decides on, with the owner's
approval and under an intent; after Onboarding, Planning is the one recipe that applies channel
changes, so no two recipes revert each other's settings.

1. **Measure.** Channel totals, traffic sources, audience and revenue for the week, from the
   Analytics API; the distance to the YouTube Partner Program (YPP) thresholds.
2. **Per video.** Every video published in the last ~30 days gets a funnel — impressions → CTR →
   views → average view duration — joining the API's numbers with the impressions and CTR that Daily
   data recorded. A fresh video re-enters the window for several weeks in a row, so the recipe sees
   its numbers mature without any trigger.
3. **Diagnose.** Each fresh video's retention curve is measured, and each cliff is matched with what
   was said at that moment. Outliers both ways are found against the channel's own median; each
   published idea is judged against its score, and each planned slot against what was published.
4. **Decide.** A weekly report ending in **one** main fix, and settings recommendations that the
   data supports.

What it leaves behind:

- **Records:** none. No record kind has Analytics as its writer (`records.py schema`); long rows
  and conclusions are step artifacts.
- **Artifacts:** `inputs.json`, `channel-weekly.json`, `audience.json`, `revenue-ypp.md`,
  `recent-videos.json`, `funnel.json` + `funnel.md`, `retention-<videoId>.csv`, `<videoId>.srt`,
  `retention-diagnosis-<videoId>.md`, `outliers.json`, **`report-<YYYY-MM-DD>.md`** (the weekly
  report), `settings-reco.md` and `settings-desired.json`. Planning and the owner find them with
  `list-step-artifacts`.

## Requirements (EARS) to put into the recipe

1. WHEN the run starts THEN system MUST read `profile:channel` (Onboarding), `studio:*` and `velocity:*` (Daily data), `watch:*` and `idea:*` (Recon), `plan:*` (Planning, when it exists) and `publish:*` (each declared content-creation recipe) from their writers' memory, MUST validate every record it uses with `records.py validate`, and MUST list the records it rejected.
2. IF `profile:channel` is missing or invalid THEN system MUST stop and tell the owner that Onboarding has not run; IF any other producer has no records THEN system MUST continue and state what is missing and what that limits.
3. WHEN channel metrics are read THEN system MUST cover a 7-day period ending three days before the run (the Analytics API lags), the 7 days before it for comparison, and traffic sources over 28 days, each saved as a dated artifact.
4. WHEN the audience is read THEN system MUST save geography, devices, age and gender, and subscribed vs not subscribed, and MUST say which audience views the API does not offer.
5. WHEN revenue is read THEN system MUST report revenue and RPM only from the API's answer, writing "no data" when the channel is not monetised or the scope is missing, and MUST state the YPP distance with `ypp.py`, dated.
6. WHEN recent videos are listed THEN system MUST include every public upload of the last 30 days, using `publish` records for format, idea and plan where they exist and the uploads playlist where they do not.
7. WHEN a funnel is built THEN system MUST join each video's Analytics numbers with its impressions and CTR over the same 7 days from the Reporting API, read under the CTR scale Daily data settled, MUST write CTR as a fraction, and IF no scale is settled THEN system MUST use impressions only and say so; IF the Reporting API cannot be read THEN system MUST fall back to the `studio` records and say the values are a single day's; IF a video has neither THEN system MUST write "no data" and MUST NOT fail.
8. WHEN Daily data's records are used THEN system MUST judge their freshness only by the staleness rows of `youtube-strategy/references/thresholds.md` (`velocity` stale when `as_of` is more than 2 days before the run, `studio` when more than 4 days).
9. WHEN a video's numbers are judged THEN system MUST compare them with the channel's own median for the same format (and traffic source where the data has it), MUST NOT compare browse CTR with search CTR, and MUST NOT use external averages as a benchmark.
10. WHEN a fresh video has a retention curve THEN system MUST measure it with `retention.py` against the video's real duration, MUST name what was said at each cliff when a transcript exists, and MUST classify the curve with the classes of `thresholds.md`.
11. WHEN outliers are sought THEN system MUST find them both ways against the channel's median with `swipe.py`, and MUST judge each published idea against its `idea` score.
12. WHEN the report is written THEN system MUST follow `youtube-strategy/references/analytics-report.md`, MUST cite a number with source and date for every diagnosis, and MUST end in exactly one main fix with at most two follow-ups.
13. WHEN settings are recommended THEN system MUST name for each the data behind it, the current and the proposed value, and whether the API or Studio applies it, and MUST recommend nothing the week's data does not support.
14. WHEN settings recommendations are written THEN system MUST leave them as artifacts (`settings-reco.md`, `settings-desired.json`) for "YouTube Planning", and MUST NOT change anything on the channel, take any irreversible action or claim any intent.
15. WHEN `plan` records exist THEN system MUST compare each planned slot of the recent window with what was published; IF Planning has not run THEN system MUST skip the comparison and say so.

## Steps

The "Skills" column lists skills from the shelf, attached to that step. `youtube-records` is
attached to the recipe, as rule 2 says.

| # | Step | Who | Skills and tools on the step | Credentials | Writes |
| --- | --- | --- | --- | --- | --- |
| 1 | Inputs from the other recipes | AI | — (`youtube-records` on the recipe) | — | `inputs.json` |
| 2 | Channel metrics for the period | AI (script) | `youtube-data` | `YOUTUBE_REFRESH_TOKEN` | `channel-weekly.json` |
| 3 | Audience | AI (script) | `youtube-data` | `YOUTUBE_REFRESH_TOKEN` | `audience.json` |
| 4 | Revenue and YPP | AI (script) | `youtube-data`, `youtube-metrics` | `YOUTUBE_REFRESH_TOKEN` | `revenue-ypp.md` |
| 5 | Recent videos | AI (script) | `youtube-data` | `YOUTUBE_REFRESH_TOKEN` | `recent-videos.json` |
| 6 | Per-video funnel | AI | `youtube-data`, `youtube-strategy` | `YOUTUBE_REFRESH_TOKEN` | `funnel.json`, `funnel.md` |
| 7 | Retention curves and transcripts | AI (script) | `youtube-data`, `yt-dlp` | `YOUTUBE_REFRESH_TOKEN` | `retention-<videoId>.csv`, `<videoId>.srt` |
| 8 | Retention diagnosis | AI | `youtube-metrics`, `youtube-strategy` | — | `retention-diagnosis-<videoId>.md` |
| 9 | Outliers, titles and ideas judged | AI | `youtube-metrics`, `youtube-strategy` | — | `outliers.json` |
| 10 | Weekly report | AI | `youtube-strategy` | — | `report-<YYYY-MM-DD>.md` |
| 11 | Settings recommendations | AI | `youtube-channel-setup`, `youtube-data` | `YOUTUBE_REFRESH_TOKEN` | `settings-reco.md`, `settings-desired.json` |

Order: 1 first; 2, 3, 4 and 5 can run in parallel after it; 6 and 7 after 5; 8 after 7; 9 after
5 and 6; 10 after 2–9; 11 after 2, 3 and 10.

## Design notes per step

**1 — Inputs from the other recipes.**

The recipe is built with a `declare-read` for each producer, found with `find-spec-template --name`
by its exact name: "YouTube Onboarding", "YouTube Daily data", "YouTube Recon", "YouTube
Planning" when it exists, and each content-creation recipe that exists at build time ("Create
Music Release" is the known one). Planning also reads Analytics; a declared read in both
directions is allowed (Daily data and Recon read each other too).

A producer that does not exist when this recipe is built is left out, and is **never read by name**
(README rule 5): "YouTube Planning", built after this recipe, has its brief tell the editor to add
the `declare-read` of Planning to this recipe; a creation recipe built later does the same. Until
then the run treats that producer as absent and says so (step 5 for `publish`, step 9 for `plan`).

1. Take each producer's id from the run context ("Reads from other processes"). Read with
   `query-template-records --spec-template-id <producer>` by key prefix: `profile:channel` from
   Onboarding; `studio:` and `velocity:` from Daily data; `watch:` and `idea:` from Recon (its
   newest run, whichever day it finished — Recon's memory holds the latest values); `plan:` from
   Planning; `publish:` from each creation recipe. Up to 500 a request; page on.
2. Check every record with `youtube-records: scripts/records.py validate --key <key> --data '<json>'`.
   A record that fails is left out and listed with the error. A record whose `v` is not 1 stops the
   step: report it to the owner, do not guess its fields.
3. No `profile:channel`, or an invalid one → stop the run and tell the owner that YouTube Onboarding
   has to run first. Every later step needs the channel id, language and channel type.
4. Any other producer with no records — not declared, never run, or empty — is not an error. Write
   it under `missing` with what it limits ("no `studio` records: the fallback for CTR is no data").
5. Download with `list-step-artifacts --spec-template-id <producer> --step-name "<step>"`, then
   `s3 download`:
   - from Onboarding, `format-plan.md` (step "Formats and content pillars"; formats and cadence) and
     `audience-profile.md` (step "Audience, language and region"; intended language and region);
   - from Daily data, the newest `ctr-scale-check.md` with a conclusion (step "Impressions and
     CTR", `--limit 30`): the settled scale of the Reporting API's CTR, which step 6 uses. Daily data
     carries the file forward in every run once it is settled. None → write "CTR scale not
     settled";
   - from this recipe, the previous `report-*.md` (step "Weekly report"), if any. A first run says
     "first report, nothing to compare".
   A file that is not found is written under `missing`; the step does not guess a substitute.
6. Write `inputs.json`: per kind, the count, the newest and oldest `as_of`, the rejected records,
   `missing`, and the CTR scale with the date of its check. Freshness follows the staleness rows of
   `youtube-strategy/references/thresholds.md` (Ours) and nothing else: a `velocity` record is stale
   when its `as_of` is more than 2 days before the run, a `studio` record when more than 4 days
   (it describes the run date − 2 by design). A `velocity` record with `source: views-per-age` is
   a lifetime proxy, not a measured gain: mark it so wherever it is used.

**2 — Channel metrics for the period.**
1. Period: end = three days before the run, start = end − 6; the previous period is the 7 days
   before it. Dates are stated in the artifact.
2. `youtube-data: scripts/analytics.py channel --start <start> --end <end> --by day`, and the same
   for the previous period.
3. `youtube-data: scripts/analytics.py traffic --start <end − 27> --end <end>` for the channel's
   28-day traffic shares (the window of the > 60 % flag in `thresholds.md`), and the same for the
   7-day period.
4. Write `channel-weekly.json` with the answers as they came (units included) and the week-on-week
   change of views, watch minutes, average view duration and net subscribers.

**3 — Audience.**
1. Read with `youtube-data: scripts/analytics.py query`, over the 28 days ending at step 2's end:
   - geography: dimension `country`, metrics `views,estimatedMinutesWatched`;
   - devices: dimension `deviceType`;
   - age and gender: dimensions `ageGroup,gender`, metric `viewerPercentage`;
   - subscribed vs not: dimension `subscribedStatus`.
   Exact metric and dimension names are in `youtube-data/references/apis.md` and the Analytics API's
   dimensions page; a refusal names the wrong one.
2. A small channel often gets empty age and gender rows (YouTube withholds them below a threshold):
   write "no data", not zero.
3. New vs returning viewers and the hours viewers are on YouTube are Studio-only views; this recipe
   uses no browser. Write them as "not offered by the API" and use subscribed vs not as the stated
   proxy.
4. Write `audience.json`.

**4 — Revenue and YPP.**
1. Revenue for step 2's period: `youtube-data: scripts/analytics.py query --metrics
   estimatedRevenue,estimatedAdRevenue,playbackBasedCpm --currency <USD or the owner's>`. A 403 or
   empty rows means the channel is not monetised or the connection lacks
   `yt-analytics-monetary.readonly`: write "no data" with the reason. RPM = estimated revenue ÷ views
   × 1,000, with both numbers shown.
2. The YPP inputs:
   - subscribers, with `youtube-data: scripts/data_api.py channels --mine`;
   - watch hours over 365 days, with `youtube-data: scripts/analytics.py channel` (minutes ÷ 60);
   - Shorts-feed views over 90 days: the `SHORTS` traffic-source row of `youtube-data:
     scripts/analytics.py traffic` over 90 days — the input the set states for `ypp.py` (its
     `--help` and `youtube-data/references/apis.md`), the same one Onboarding uses;
   - public uploads in 90 days, with `youtube-data: scripts/data_api.py uploads --mine --since <90 days ago>`.
3. Run `youtube-metrics: scripts/ypp.py` with them and copy its tiers, sources and read dates. The
   watch hours are a bound (they include Shorts-feed and non-public time); point to Studio's Earn tab.
4. Write `revenue-ypp.md`.

**5 — Recent videos.**
1. `youtube-data: scripts/data_api.py uploads --mine --max 50 --with-stats`. The uploads within 30
   days of the run are the recent window; the rest are the baseline for medians (the channel's last
   10–20 videos per format, `thresholds.md`).
2. For each video take `format`, `idea` and `plan` from its `publish` record when one exists. A
   video without one gets its format from its duration: ≤ 180 s is `short`, marked
   `format_source: duration` (a short horizontal video reads as a Short; say so). A `publish` record
   whose video is not in the uploads (deleted, private) is listed, not dropped silently.
3. Write `recent-videos.json`: per video id, title, published_at, duration_s, views, format and
   `format_source`, the `publish` fields, and `window: recent | baseline`. Say the Data API units spent.

**6 — Per-video funnel.**
1. `youtube-data: scripts/analytics.py video-metrics --id <every video of step 5>` for step 2's
   period, and again from each recent video's `published_at` to step 2's end (its life so far).
   Videos in `no_rows` had no views in the period: zero, not missing.
2. `youtube-data: scripts/analytics.py traffic --id <ids>` once for the long videos and once for the
   Shorts of the recent window, for each format's traffic shares.
3. Impressions and CTR over step 2's period, the same basis Planning uses:
   `youtube-data: scripts/reporting.py reach --ctr-scale <settled scale> --since <step 2's start>
   --all-days --id <every video of step 5>`, keeping the days up to step 2's end. Per video, sum the
   impressions and the clicks (impressions × ctr) of those days; the week's CTR is clicks ÷
   impressions, a fraction.
   - The scale is the one in Daily data's newest `ctr-scale-check.md` (step 1). Analytics never
     settles or guesses it. Not settled → run the same call with `--ctr-scale unknown`, which
     returns `impressions` only (they do not depend on the scale), and write "CTR: no data, scale
     not settled".
   - A refusal under the settled scale means the file changed: use the fallback and report it.
   - Refused with "no channel_reach_basic_a1 job", `reports_read` zero, or any other failure →
     fallback: the `studio:<videoId>` record from step 1 (`impressions`, `ctr` as stored, `as_of`,
     `source`), labelled "single day, <as_of>". The job is Onboarding's and Daily data's to create;
     this step does not create it.
   - A video with no rows in the week, `available: false`, or only a stale `studio` record → "no
     data" with which of these it is.
4. The channel's median per format, over the baseline videos that have the value: views, average
   view duration, average view percentage, and CTR — the week's CTR, never mixed with single-day
   fallback values in one median. List the videos behind each median. The reach report has no
   traffic-source split, so CTR is compared per format only, and the funnel says "by traffic
   source: no data". A format with fewer than four videos has no median: say so.
5. Read each video with the table of `youtube-strategy/references/analytics-report.md` (step 1 of
   it) and name the stage that loses most against its format's median. Do not call any number
   good or bad against an outside average.
6. Write `funnel.json` (every input number with its source and date) and `funnel.md` (the table).

Validator rubric:
- every recent video of `recent-videos.json` has a funnel row;
- every CTR is a fraction between 0 and 1, read under the settled scale named in `inputs.json`, or
  "no data" with its reason; a single-day fallback value is labelled with its `as_of`;
- every median names the videos it was computed from, and none mixes formats;
- no external benchmark is used as a comparison.

**7 — Retention curves and transcripts.**
1. For each recent video: `youtube-data: scripts/analytics.py retention --id <id> --start
   <published_at> --end <step 2's end> --duration <duration_s> --csv retention-<id>.csv`. Duration
   is the real one from step 5. `available: false` (too few views) → say so for that video and skip
   its diagnosis.
2. For each video with a curve: `youtube-data: scripts/transcript.py --id <id> --lang <profile
   language> --out <id>.srt` (srt keeps the timings). No subtitles → the diagnosis goes without
   speech; an `auto` transcript is said to be one.
3. Keep `relative_retention_mean` from each answer for step 8.

**8 — Retention diagnosis.**
1. For each curve, run `youtube-metrics: scripts/retention.py retention-<id>.csv --axis percent
   --duration <duration_s> --transcript <id>.srt` (without `--transcript` when step 7 has none).
   Long videos take `--hook-seconds 15` and Shorts `--hook-seconds 3`, so the hook leak reads
   directly against the cliff class of `thresholds.md` (≥ 20 points in 15 s long-form; most viewers
   gone in 3 s for Shorts).
2. Classify the curve: cliff, valley, bump or steady decline, as `thresholds.md` defines them.
   retention.py measures cliffs, hook leak and slide; a valley or a bump is read from the CSV, with
   the positions quoted.
3. For a spoken video with a cliff or a steep slide, run `youtube-metrics: scripts/deadair.py <id>.srt
   --lang <language>` and quote the dead air, filler or restarts within 10 s before the cliff. A
   video without speech (a music release, `channel_type` music-artist) skips deadair; say so.
4. Write `retention-diagnosis-<id>.md` per video: the class, the biggest single leak with its time
   and what was said there, `relative_retention_mean` (YouTube's comparison with videos of similar
   length, 0.5 = median), and one change for the next video. No "healthy" verdict: no published
   benchmark backs one.

**9 — Outliers, titles and ideas judged.**
1. Split step 5's videos by format and run `youtube-metrics: scripts/swipe.py <videos of one
   format>.json --direction both --min 3 --max 0.33 --lang <language>` on each: ≥ 3× and ≤ ⅓ of the
   channel's median, the outlier line of `thresholds.md`. A format with fewer than four videos is
   listed, not ranked. Multiples compare views, not age: say which outliers are under 14 days old.
2. For each outlier, lint its title with `youtube-metrics: scripts/title.py --title "<title>" --lang
   <language>` and put the findings side by side for the winners and the losers. title.py ranks
   wording; it predicts nothing about CTR, and its "no number" check does not fit artist – song
   titles.
3. Ideas judged: for each video whose `publish` record names an `idea`, take that idea's `score`
   and the video's views against its format's median. When the idea's `source` is `watch:<id>`,
   add that competitor video's `velocity` (views per day, `as_of`, and "proxy" when its source is
   `views-per-age`; stale per step 1) from step 1, so the report can say whether the idea followed a
   rising or a fading video.
4. Planned vs published: for each `plan` record dated in the recent window, the `publish` record
   that names its slot (or the upload with its title). Planning owns the slot's status; report it
   as Planning wrote it, beside what the records show:
   - published on the day, or published late (the `publish` date after the slot's date);
   - past, no `publish`, and within 14 days of its date → "overdue": Planning closes a slot
     `dropped` only 14 days after its date (ours), so it is not a drop yet;
   - `dropped` by Planning with a later `publish` naming it → listed as "published after drop";
     Planning moves it to `published` on its next run;
   - still `planned` for a future date.
   No Planning records (not declared or never run) → skip and write "Planning has not run". A
   published video that names a plan slot Planning does not have is listed.
5. Write `outliers.json`: up, down, the shared traits of each side (topic, format, length, title
   findings, publish weekday and hour), the ideas judged, and planned vs published.

**10 — Weekly report.**
Follow `youtube-strategy/references/analytics-report.md` — its steps, its output template and its
quality bar — over the artifacts of steps 1–9. The file is `report-<YYYY-MM-DD>.md`, dated with the
day of the run.

1. The "Data" line names each source with its date; the "Missing" line copies `inputs.json`'s
   `missing` and says what each absence limits.
   The "Ideas judged" section carries the idea outcomes and the planned vs published table of step 9.
2. Every number comes from an artifact of this run. External figures only from
   `youtube-strategy/references/thresholds.md`, labelled YouTube, ours or secondary; never as a
   pass/fail line.
3. Compare with the previous report where one exists: what moved, and whether last week's fix shows
   in the metric it named.
4. End in **one** main fix: the action, the evidence with its numbers, what to do this week, the
   metric that will show it worked and the date to read it. At most two follow-ups; then three
   things to keep and what not to do yet.
5. Send the owner the main fix and the path of the report with `send-message`. It needs no reply.

Validator rubric:
- the report has every section of the template in `analytics-report.md`, and a section with no data
  says so instead of being dropped;
- exactly one main fix, named, with its evidence (numbers, source, date), this week's action, a
  metric and a date to read it; at most two follow-ups;
- every diagnosis cites a number from this run's artifacts; nothing generic;
- every comparison is with the channel's own median for the same format; no browse CTR is compared
  with search CTR; any external number is labelled with its kind from `thresholds.md`;
- CTR appears as a percentage written from a fraction (0.045 → 4.5 %), never a value above 100 %;
- traffic shares add up to about 100 %, and a source above 60 % of 28-day views is flagged;
- missing data is stated with its consequence for the conclusions.

**11 — Settings recommendations.**
1. Follow `youtube-channel-setup/references/settings.md` → "Recommending changes from analytics".
   Read the current state first with `youtube-data: scripts/data_api.py channels --mine` (the
   channel's `brandingSettings`).
2. Compare it with `audience.json`, `channel-weekly.json`, the report and Onboarding's
   `audience-profile.md`. A language-area recommendation needs a stable share over at least four
   weekly reports, not one week.
3. Hashtags: a small fixed set from `profile.identity_token` and the niche, within YouTube's limits
   quoted in settings.md.
4. Write `settings-reco.md`: per recommendation, the data behind it, the setting, the current and
   the proposed value, API or Studio. "No change this week" is a valid result and is written.
5. Write the API-applicable part as `settings-desired.json` with only the fields to change, out of
   `description`, `keywords`, `country`, `defaultLanguage` and `unsubscribedTrailer`.
   Made-for-kids and country are declarations: recommend a change only if the current value is
   wrong.
6. Apply nothing. "YouTube Planning" reads `settings-reco.md` and `settings-desired.json`, decides
   with the owner and applies under an intent. The step's summary says the recommendations wait
   for Planning.

Validator rubric:
- every recommendation names the number and the artifact behind it;
- current and proposed values are both given, and the current one matches the channel as read;
- none rests on "may boost reach" without data;
- `settings-desired.json` holds only API-applicable fields that `settings-reco.md` recommends.

## What changed from the source brief

| Source brief | Now |
| --- | --- |
| "YouTube Analytics (weekly)" | `YouTube Analytics`, the name the other recipes look up |
| `google-api-python-client` attached to each task | `youtube-data` scripts over HTTPS; no library |
| `youtube` (claude-youtube) `/analyze` | `youtube-strategy/references/analytics-report.md` |
| `yt-retention` with a sibling `yt-edit` for `deadair.load` | `youtube-metrics`: `retention.py` and `deadair.py` in one skill |
| `records.py` pinned as a file | the `youtube-records` skill on the recipe |
| reads only Daily data and creation recipes | also Onboarding (`profile`, format plan), Recon (`watch`, `idea`) and Planning (`plan`), each declared |
| CTR from Daily data's `studio` records | the week's CTR from `reporting.py reach --all-days` under Daily data's settled scale, as Planning reads it; `studio` records as the fallback |
| retention CSV built by an ad-hoc adapter | `analytics.py retention` writes the CSV and the exact retention.py call |
| `weekly-report.md` | `report-<YYYY-MM-DD>.md`, the name in `analytics-report.md` |
| no outliers, no judged ideas | step 9: `swipe.py` both ways, `title.py`, ideas against their scores |
| task 10, optional apply under intent `update_channel_settings:channel:<id>` | removed: Analytics changes nothing and claims no intent; Planning applies `settings-desired.json` with the owner's approval |
| Monday 06:00 | Tuesday 05:00, a day after Recon |
