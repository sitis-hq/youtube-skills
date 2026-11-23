# Brief 2 — YouTube Daily data

Follow [the rules of the set](README.md); this brief adds what is specific to Daily data.

**Name:** `YouTube Daily data` · **Scope:** global recipe, run inside the channel's own project ·
**Schedule:** daily, on the recipe (`add-spec-template-schedule`) · **Reads from:** "YouTube Onboarding"
(`profile:channel`), "YouTube Recon" (`watch:*`), and its own earlier runs' step artifacts.

## What it is for

Every day it takes one dated snapshot of the videos the channel follows, and turns it into the two
signals the weekly and monthly recipes read:

1. **Growth.** How many views a day each video gains, and whether today's rate is a spike or a
   drop against the video's own history.
2. **Reach.** Thumbnail impressions and impression click-through rate (CTR) of the channel's own
   videos, from the Reporting API job Onboarding created, with Studio as the fallback.

It is data collection, not judgement: every number comes from a script, and the agent's work is to
run the scripts in order, write what they print, and say what was missing.

The videos it follows are of two kinds:

- **own** — the channel's latest uploads (up to 50), read every run from the Data API. This list
  never depends on another recipe, so the recipe is useful from the day after Onboarding, before
  "YouTube Recon" has run even once.
- **watch** — the competitor videos "YouTube Recon" follows (`watch:<videoId>`). Empty on the first
  days; not an error.

What it leaves behind:

- **Records** (memory, through `youtube-records`); this recipe is the one writer of both kinds:
  - `velocity:<videoId>` for every own and watch video with a measurable rate — read by Recon,
    Analytics and Planning;
  - `studio:<videoId>` for every own video, including the days without data (`available=false`) —
    read by Analytics and Planning.
- **Artifacts** (one set per run; the long rows live here, never in records):
  - `video-list-<date>.json` and `snapshot-<date>.json` — the daily snapshot, which step 2 of later
    runs reads back as history;
  - `velocity-<date>.json` — the full output of the velocity script, baselines included;
  - `reach-<date>.json`, and `studio-metrics-<date>.csv` on the days Studio was used;
    `ctr-scale-check.md`, the settled CTR scale of the Reporting file, written once and carried
    forward by every later run.

## Requirements (EARS) to put into the recipe

1. WHEN the daily run starts THEN system MUST read `profile:channel` from "YouTube Onboarding", validate it, and MUST verify that the connected channel's id equals its `channel_id` before reading anything else.
2. WHEN the video list is built THEN system MUST include the channel's own latest uploads (up to 50) from the Data API and every valid `watch:<videoId>` record of "YouTube Recon" when Recon is a declared read, MUST NOT look up an undeclared recipe by name, and MUST treat an empty watchlist or an undeclared Recon as normal and say so.
3. WHEN the snapshot is taken THEN system MUST read every listed video's statistics in batches of 50 with `videos.list`, MUST NOT call `search.list`, and MUST state the Data API units the run spent.
4. WHEN the snapshot is taken THEN system MUST keep the full daily rows as the dated artifact `snapshot-<date>.json` and MUST NOT put view history into records.
5. WHEN growth is computed THEN system MUST compute views per day and the anomaly flag with `velocity.py` over today's snapshot and up to 15 earlier ones of this recipe, MUST write one `velocity:<videoId>` record per video the script measured, and MUST say how many records carry the one-snapshot proxy `views-per-age`.
6. WHEN impressions and CTR are read THEN system MUST read them from the Reporting API job `channel_reach_basic_a1` first, and MUST use the Studio export only when the job is missing, has no reports yet, fails, or is needed to settle the CTR scale.
7. WHEN no earlier run's `ctr-scale-check.md` holds a settled CTR scale THEN system MUST NOT write a CTR read under a guessed scale; it MUST settle the scale by `ctr_raw_max` above 1 under `--ctr-scale unknown` or by comparison with Studio for the same video and day, MUST record it in `ctr-scale-check.md`, and MUST tell the owner the finding once.
8. WHEN impressions and CTR are written THEN system MUST write exactly one `studio:<videoId>` record per own video in each run, with CTR as a fraction and the source of the numbers, and MUST write `available=false` with the reason where no number was read.
9. WHEN the Studio page shows a signed-out state THEN system MUST re-mint the session or request a sign-in, MUST NOT act until signed in, and MUST NOT block the API work of the run.
10. WHEN the run is repeated on the same day THEN system MUST overwrite the same keys, not add records.

## Steps

The "Skills" column lists skills from the shelf, attached to that step. `youtube-records` is
attached to the recipe, as rule 2 says. Step 1 is the entry step; steps 2 and 3 depend on it
(`requiredStatus: "passed"`) and do not depend on each other.

| # | Step | Who | Skills and tools on the step | Credentials | Writes |
| --- | --- | --- | --- | --- | --- |
| 1 | Video list and snapshot | AI (scripts) | `youtube-data` | `YOUTUBE_REFRESH_TOKEN` | `video-list-<date>.json`, `snapshot-<date>.json` |
| 2 | Velocity and anomaly flags | AI (scripts) | `youtube-metrics` | — | `velocity` records, `velocity-<date>.json` |
| 3 | Impressions and CTR | AI (scripts; browser fallback) | `youtube-data`, `youtube-studio` | `YOUTUBE_REFRESH_TOKEN`, `YT_STUDIO_SESSION` | `studio` records, `reach-<date>.json`, `studio-metrics-<date>.csv` (fallback), `ctr-scale-check.md` (written once, carried forward) |

Step 2 declares no credential: it reads artifacts through the platform's own commands and computes
locally. Step 3 declares `YT_STUDIO_SESSION` even on days it stays in the API: the fallback needs
it, and a declared key without a credential is named to the owner at the start of the run (the
platform notifies them, and `current-task.md` lists it as "Not signed in yet") rather than
discovered in the middle of the step. A missing session does not stop the API path.

Expected Data API cost per run: `uploads --mine` = 2 units (`channels.list` + one
`playlistItems.list` page), `videos` = 1 unit per 50 listed videos. With 50 own videos and up to
100 watched ones that is 5 units, about 0.05 % of the 10,000-unit daily quota of the channel's
Google Cloud project, which "YouTube Recon" shares (its `search.list` costs 100 a page). The
Reporting API and Studio do not count against it.

## Design notes per step

**1 — Video list and snapshot.**

1. Read who the channel is. The run context ("Reads from other processes" in `current-task.md`)
   gives the id of "YouTube Onboarding", the declared producer. Get `profile:channel` with
   `get-template-record` from that id and the run's project, and check it with
   `youtube-records: scripts/records.py validate --key profile:channel --data '<json>'`. A missing
   or invalid profile stops the run: nothing else can be checked against it.
2. Read the own uploads with `youtube-data: scripts/data_api.py uploads --mine --max 50`. Its
   `channel_id` must equal the profile's; a different channel means the wrong account is
   connected — stop and tell the owner, do not snapshot another channel.
3. Read the watchlist, only from a declared "YouTube Recon": its id comes from the run context the
   same way (README rule 5). Recon not among the declared reads is an empty watchlist — never look
   it up by name; say "YouTube Recon is not declared yet" and go on. Declared but no records under
   `watch:` (`query-template-records --key-prefix watch: --limit 500`) is an empty watchlist too:
   say so and go on. Check each record with `records.py validate`; leave out the ones
   that fail and name them.
4. Write `video-list-<date>.json`: `as_of` (the run's UTC date), `channel_id`, and `videos`, one
   object `{video_id, role}` per id, role `own` or `watch`, own first, no id twice.
5. Snapshot every listed id at once with `youtube-data: scripts/data_api.py videos --ids-file
   video-list-<date>.json`, and save its answer as it comes as `snapshot-<date>.json`. Its
   `missing` list (deleted or private videos) stays in the file; report it. With no ids at all (a
   channel with no uploads and no watchlist yet) do not call `videos`; write a snapshot with an
   empty `videos` list and say why.
6. The summary gives the counts (own, watch, missing) and the Data API units: the sum of
   `quota.data_api_units` of the two calls.

Validator rubric:
- the connected channel's id equals `profile:channel`'s `channel_id`;
- `video-list-<date>.json` holds every id of the uploads answer as `own` and every valid `watch`
  record as `watch`, with no duplicate;
- `snapshot-<date>.json` is `data_api.py videos` output for the run's date, and every listed id is
  either in its `videos` or in its `missing`;
- the summary states the Data API units spent.

**2 — Velocity and anomaly flags.**

The rate needs yesterday's count, which no record holds: `velocity` stores the rate, not the views.
So the step reads its own earlier snapshots back from this recipe's artifacts.

1. Collect the history: `ai-integration list-step-artifacts --spec-template-id <Process id>
   --project-id <Project id> --step 1 --limit 16`, then `s3 download` each `snapshot-*.json` it
   lists. Keep the anchor it prints in the summary. Fewer than 16 (the first weeks, or failed
   days) is normal; the script falls back by itself.
2. Run `youtube-metrics: scripts/velocity.py` on today's `snapshot-<date>.json` and every
   downloaded snapshot, in one call, with the default `--min-abs`. Save its answer as
   `velocity-<date>.json`. Do not recompute a rate or a flag by hand; the rule the flags follow is
   the script's `rule` field.
3. For every video whose result carries a `record`, write it with
   `youtube-records: scripts/records.py write velocity`, the record's keys as flags (`_` → `-`).
   Own and watch videos alike. A re-run on the same day overwrites the same keys.
4. Videos the script `skipped` get no record; name them with the reason it gives. A video absent
   from today's snapshot keeps its older record; readers judge it by its `as_of` with the staleness
   rows of `youtube-strategy/references/thresholds.md` ("Ours": a `velocity` record is stale more
   than 2 days before the run).
5. If the script refuses because no snapshot holds a video (step 1 had none), write nothing and
   say so.
6. The summary gives the counts from `summary` (videos, spike, drop, skipped), how many records
   carry `source: views-per-age` (one snapshot only: a lifetime average, not a measured rate), the
   number of history snapshots used and their oldest date, and every spike or drop with its video,
   rate and baseline.

**3 — Impressions and CTR.**

The Reporting API is the source; Studio is the fallback (`youtube-studio/references/impressions-ctr.md`,
`youtube-data/references/apis.md`). The own videos and the channel id come from step 1's
`video-list-<date>.json`; watch videos get no `studio` record (they are not this channel's). With no
own video the step writes nothing and says so.

The Reporting API's docs do not say whether its file holds 0.045 or 4.5. That is a property of
the API's file, not of the channel, and it is learned from a real file, so it is data a run finds,
not configuration the recipe carries. Its one store is **`ctr-scale-check.md`**, an artifact of this
step: the newest one with a conclusion is the scale every run uses.

1. Read the reports: `youtube-data: scripts/reporting.py reach --ctr-scale <scale> --since
   <run date − 7 days> --id <own ids>`. `--since` keeps the run to the last week's daily files
   instead of all 60 days; the script still picks each video's newest day and a reissued day's
   newest file. Save the answer as `reach-<date>.json`.
2. Know the scale before writing any CTR:
   - read the newest `ctr-scale-check.md` with a conclusion from this recipe's earlier runs
     (`list-step-artifacts --spec-template-id <Process id> --project-id <Project id> --step 3
     --limit 30`, then `s3 download`). Found → use its scale, and keep the same file, unchanged
     (its date and evidence as they were), among this run's artifacts, so the newest runs always
     carry it. Under a settled scale, a refusal means the file changed: use the Studio fallback
     for the day and report it;
   - none found → settle it now. Run `reach` with `--ctr-scale unknown`: it writes impressions
     only and reports `ctr_raw_max`, the largest raw CTR value read. Above 1 settles it as
     **percent** (a fraction cannot exceed 1); run `reach` again with `percent` for the records;
   - `ctr_raw_max` at most 1 is what a fraction and a CTR under 1 % share.
     Compare with Studio: take the video-day with the most impressions, export that day from
     Studio (the fallback below), and see which scale puts the Reporting value within 0.001 of
     Studio's fraction (Studio shows one decimal of a percent; the two scales differ 100 times);
   - write `ctr-scale-check.md` (video, day, the Reporting value as read, Studio's value, the scale,
     the date), and tell the owner the finding once with `send-message` (what was compared and the
     scale found). Do not wait for an answer; nothing needs the owner's action;
   - if it cannot be settled today (no impressions above zero, or Studio unavailable), write the
     Reporting records of the `--ctr-scale unknown` answer, `impressions` and no `ctr` (the
     `studio` record allows it): impressions do not depend on the
     scale, a CTR under a guessed one would be wrong a hundredfold. Write no `ctr-scale-check.md`
     without a conclusion; the next run tries again.
3. Choose the path from the answer:
   - `records` not empty → write each element with `youtube-records: scripts/records.py write
     studio`, fields as they come (`--source reporting-api`). Own videos without a row come back
     `available=false` already;
   - `reports_read` above zero but no `records` → the days had no data: write
     `--available false --source reporting-api` for every own video, `as_of` the run date minus 2
     days (the newest day a report covers);
   - refused with "no channel_reach_basic_a1 job" → run `reporting.py ensure-job` (it creates
     whichever of the two reach jobs, basic and combined, is missing — the Channel Audit reads the
     combined one), name the created jobs in the summary and tell the owner they were missing; then
     take the Studio fallback for today;
   - `reports_read` zero (a job younger than about 48 hours), or any other failure of the call →
     the Studio fallback. "not connected" or "reconnect" also asks the owner to reconnect YouTube
     on the project's Credentials page.
4. Studio fallback, per `youtube-studio/references/impressions-ctr.md`:
   - run the session check of `youtube-studio/references/session.md` against the profile's channel,
     with the `mcp__playwright-yt-studio__*` tools; signed out → `ensure-session`, close the browser,
     check once more; still not → `request-browser-login` and stop the Studio part;
   - export Advanced mode for one day, the run date minus 2 days, with Impressions and Impressions
     click-through rate, and keep the table as `studio-metrics-<date>.csv`;
   - convert it with `youtube-studio: scripts/studio_reach.py --csv … --as-of <that day> --video
     <id>` for every own video, and write each row with `records.py write studio` as it comes
     (`--source studio-export`);
   - no session, or the export failed → write `--available false --source studio-export` for every
     own video, for that day, and say why. The run does not fail on it.
   The fallback only reads; nothing in Studio is changed.
5. The summary gives the path taken, the scale used and its evidence, the newest day the numbers
   describe (two days behind the run, by how the Reporting API and Studio work), the count of
   `available=false` with their reasons, and any job or session the owner must fix.

Validator rubric:
- every own video of `video-list-<date>.json` has exactly one `studio` record written by this run,
  and no watch video has one;
- every record's `source` is the path its numbers came from, and every `ctr` is a fraction at most 1;
- a record with `source: reporting-api` and a `ctr` was read under the scale of a
  `ctr-scale-check.md` with a conclusion — an earlier one carried among this run's artifacts, or one
  this run wrote with its evidence (`ctr_raw_max` above 1, or both values of the Studio comparison);
- every `available=false` has its reason in the summary;
- a Studio export, when used, is kept as `studio-metrics-<date>.csv`, and nothing in Studio was
  changed.

## Building it: schedule and project

- **Project first.** The recipe runs inside the channel's project. Ask the owner which channel in
  their words, resolve it with `list-projects`, pass `--project-id` to the schedule, and read back
  its `effectiveProject` to the owner before going on.
- **Reads.** Declare each producer with `find-spec-template --name "<name>"` and `declare-read`:
  "YouTube Onboarding" always (it exists before this recipe), "YouTube Recon" only if it exists
  already. If it does not, build the recipe without that read and tell the owner; Recon's brief
  tells the editor to add the `declare-read` of Recon to this recipe once Recon is built (README
  rule 5). Until then step 1 treats Recon as absent — an empty watchlist, said so.
- **Schedule.** One schedule on the recipe, `add-spec-template-schedule`, daily at one fixed hour,
  for example `0 2 * * *` (UTC). Keep it stable and away from midnight UTC: a snapshot's `as_of` is
  the UTC date of the read, and the rate divides by whole days between snapshots. Confirm the hour
  with the owner. Step 1 is the only entry step.
- **Validators** on steps 1 and 3 with the rubrics above. Step 2 runs a script whose output is its
  own check.
- No step takes an irreversible action, so no step claims an intent.

## What changed from the owner's source brief

| Before | Now |
| --- | --- |
| impressions and CTR only from Studio, "no API" | Reporting API `channel_reach_basic_a1` first (`reporting.py reach`); Studio export as the fallback |
| step 3 parallel to step 1, browsing per video | step 3 depends on step 1 for the own video list; one Advanced-mode export for all own videos |
| watchlist only; own videos "if the watchlist is empty" | own latest uploads (up to 50) every run, from `data_api.py uploads --mine`, plus the watchlist |
| `google-api-python-client`, `yt-dlp` fallback | `youtube-data: scripts/data_api.py`, HTTPS only; no `yt-dlp` on this recipe |
| `records.py` pinned as a file | the `youtube-records` skill on the recipe |
| velocity computed in the step from "prior-day artifacts, or an accumulated history artifact" | `youtube-metrics: scripts/velocity.py` over up to 16 snapshots read back with `list-step-artifacts` |
| reads Recon only | reads Onboarding (`profile:channel`, to check the connected channel) and Recon |
| no skills needed | `youtube-data` on 1 and 3, `youtube-metrics` on 2, `youtube-studio` on 3 |
| CTR unit unstated | CTR a fraction; the Reporting file's scale settled once by a run and kept in `ctr-scale-check.md`, which later runs read |
| `YOUTUBE_REFRESH_TOKEN` optional on step 3 | required on step 3: it reads the Reporting API |
