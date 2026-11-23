# Brief 5 — YouTube Planning

Follow [the rules of the set](README.md); this brief adds what is specific to Planning.

**Name:** `YouTube Planning` · **Scope:** global recipe, run inside the channel's own project ·
**Schedule:** monthly — cron `0 6 1 * *` (06:00 on the 1st) in the time zone of
`profile:channel`'s `country`, like every scheduled recipe of the set except Daily data (UTC);
confirm the day and time with the owner · **Reads from:** "YouTube Onboarding", "YouTube Daily data",
"YouTube Recon", "YouTube Analytics", "YouTube Channel Audit" (when it exists), and each creation
recipe that publishes to this channel.

## What it is for

Once a month it does three jobs for one channel:

1. **Plans the month.** It turns Recon's idea backlog into a dated content calendar, with the
   cadence and the pillars of Onboarding's format plan. Each slot becomes a `plan:<date>:<slot>`
   record, which the creation recipes read to know what to make next.
2. **Fixes what already shipped.** It finds the channel's own videos that fall short of the
   channel's own median. It writes a new package for each one: title, description, tags, chapters
   and thumbnail. After the owner approves, it applies each change once, or starts a thumbnail
   A/B test in Studio.
3. **Applies channel settings.** After Onboarding, Planning is the one recipe that changes the
   channel's settings. Analytics recommends (`settings-reco.md`, `settings-desired.json`) and
   applies nothing. Planning shows the owner the diff, and applies what the owner approves.

A run never calls another recipe. It reads the latest memory and files the other recipes left
behind. Where something is missing, the run works with what exists and says what was missing.

What it leaves behind:

- **Records** (memory, through `youtube-records`): `plan:<date>:<slot>`, one per calendar slot.
  Planning is the only writer of `plan`, and the only one that closes a slot as `published` or
  `dropped`.
- **Artifacts:**
  - `inputs.md` (what was read and how fresh it is);
  - `idea-ranking.json`;
  - `calendar-YYYY-MM.md`;
  - `underperformers.json`;
  - `reopt-package.json`;
  - `approvals.json`;
  - `apply-report.md`;
  - `ab-variants.json`, and `ab-test-<videoId>.json` for each test result read.
- **Actions on the channel**, each claimed by its script through `intent.py`, and only after the
  owner approves:
  - metadata changes and thumbnail changes (`apply_video.py`);
  - channel settings (`apply_channel.py branding`);
  - thumbnail A/B tests (Studio).

What it never does:

- It never edits another recipe's record.
  - It does not move an `idea`'s status: the `plan` record names the idea in its `idea` field.
  - It does not re-measure or rewrite `seed` records. Recon re-measures seeds older than 31 days
    into its own memory.
- It never changes a live video or the channel without the owner's approval in the chat.

**How a slot is matched to a video.** A creation recipe writes `publish.plan` as the full plan key
(`plan:<date>:<slot>`), and `publish.idea` as the idea's slug without the `idea:` prefix — the same
value as `plan.idea`. Planning matches on exactly those two values.

## Requirements (EARS) to put into the recipe

1. WHEN a run starts THEN system MUST read `profile:channel`, the `seed`, `watch`, `idea`, `velocity`, `studio` and `publish` records, and its own earlier `plan` records, each from its writer's memory after `find-spec-template` + `declare-read`, MUST validate each with `records.py validate`, and MUST list what is missing or stale in `inputs.md` instead of failing.
2. WHEN a run starts THEN system MUST read Onboarding's `format-plan.md`, `audience-profile.md`, `brand-profile.md` and `upload-defaults.md`, Daily data's newest settled `ctr-scale-check.md`, and the latest `report-YYYY-MM-DD.md`, `settings-reco.md` and `settings-desired.json` of the Analytics recipe, through `list-step-artifacts`, and MUST name the instance and the date of each file it used.
3. WHEN an idea's keyword is in Recon's newest `keywords.json` THEN system MUST take its seed measures (`yt_interest` included) from that file, and otherwise from the `seed` record with the later `as_of` across Onboarding's and Recon's memories; WHEN the measures used are older than 31 days THEN system MUST mark them stale in `inputs.md` and in the score basis of every idea that uses them, and MUST NOT write any `seed` record.
4. WHEN a `planned` slot, or a `dropped` slot dated within the last 60 days, has a `publish` record whose `plan` equals its key, or whose `idea` equals its `idea` THEN system MUST write that slot again with status `published`; WHEN a `planned` slot is more than 14 days past its date without one THEN system MUST write it with status `dropped` and name it in the calendar artifact.
5. WHEN ideas are ranked THEN system MUST score every candidate idea with `youtube-strategy: scripts/score_idea.py` in one batch, and MUST NOT rank by hand.
6. WHEN the calendar is built THEN system MUST take the cadence and the pillars from Onboarding's `format-plan.md`, MUST keep the trend share at or below 30 % of the month's slots, MUST give each long-form slot three titles that pass `check_metadata.py`, and MUST NOT plan an idea that a `plan` record whose status is not `dropped` already names.
7. WHEN a calendar slot already has a `plan` record THEN system MUST NOT plan it again, and MUST write each new slot as a `plan` record with status `planned` and the idea's slug in `idea`.
8. WHEN own videos are judged THEN system MUST compare each with the channel's own median for the same format, on views (`swipe.py`, run per format), impression CTR and retention (`retention.py --hook-seconds` 15 for long-form, 3 for Shorts), MUST use a `velocity` or `studio` record only when it is fresh by `thresholds.md`, MUST mark CTR as "no data" where the reach data has none, and MUST NOT judge a video whose A/B test has not been read yet.
9. WHEN a video is repackaged THEN system MUST keep every identity token verbatim, MUST take the keyword from a `seed` (or measure it first), MUST keep the description's fixed block intact, MUST lint the package with `check_metadata.py` and `title.py`, and MUST measure every thumbnail candidate with `analyze_thumbnail.py`.
10. WHEN a change to a live video or to the channel's settings is ready THEN system MUST send the owner the current and the proposed state with the script's `--dry-run` diff, and MUST NOT apply anything before the owner approves it.
11. WHEN an approved change is applied THEN system MUST apply it through `apply_video.py` or `apply_channel.py`, which claim and commit it through `intent.py`, and MUST NOT retry a change the script reports as `uncertain`.
12. WHEN a thumbnail A/B test is started THEN system MUST run the Studio session check first, MUST start at most one test per video, MUST leave the claim open and report, never retry, when it cannot tell whether the test started, and MUST judge a finished test by watch-time share, never by CTR.

## Steps

The "Skills" column lists skills from the shelf, attached to that step. `youtube-records` is
attached to the recipe, as rule 2 says.

| # | Step | Who | Skills and tools on the step | Credentials | Writes |
| --- | --- | --- | --- | --- | --- |
| 1 | Read the channel's memory and files | AI | `youtube-data` | `YOUTUBE_REFRESH_TOKEN` | `inputs.md`, `inputs.json`, `uploads.json` |
| 2 | Close last month's slots | AI | — | — | `plan` records (`published` / `dropped`), `closed-slots.md` |
| 3 | Rank the ideas | AI | `youtube-strategy` | — | `idea-ranking.json` |
| 4 | Build the calendar | AI + owner | `youtube-strategy`, `youtube-metadata`, `youtube-metrics` | — | `calendar-YYYY-MM.md`, `plan` records |
| 5 | Find underperformers | AI | `youtube-data`, `youtube-metrics`, `youtube-strategy` | `YOUTUBE_REFRESH_TOKEN` | `underperformers.json`, `retention-<videoId>.csv` |
| 6 | Repackage metadata and thumbnails | AI | `youtube-metadata`, `youtube-metrics`, `youtube-thumbnail-check`, `youtube-data`, `youtube-demand`, `poyoapi`, `opencv-python-headless`, `yt-dlp`, `dataforseo-mcp-server` | `POYO_API_KEY`, `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD`; only the `LINK_*` keys (and `BUSINESS_EMAIL`, if any) the description's fixed block carries | `reopt-package.json`, `meta-<videoId>.json`, thumbnail candidates and previews |
| 7 | Owner approval | AI + owner approval | `youtube-metadata`, `youtube-channel-setup` | `YOUTUBE_REFRESH_TOKEN` | dry-run diffs, `approvals.json` |
| 8 | Apply the approved changes | AI | `youtube-metadata`, `youtube-channel-setup`, `youtube-data` | `YOUTUBE_REFRESH_TOKEN` | `apply-report.md` |
| 9 | Thumbnail A/B tests (optional) | AI (browser) | `youtube-studio` | `YT_STUDIO_SESSION` | `ab-variants.json`, `ab-test-<videoId>.json` |

**Order.** Step 1 comes first. After it there are two chains:

- the calendar: 2 → 3 → 4;
- the fixes: 5 → 6 → 7, then 8 and 9 side by side.

Step 7 also carries the channel settings that step 1 read, so it runs even when step 5 finds no
video to fix. Dependencies use `requiredStatus: "passed"`. Steps 8 and 9 do nothing when step 7
approved nothing; that is a pass, not a failure.

## Design notes per step

**1 — Read the channel's memory and files.**

Every later step works from this step's `inputs.json`. So this step reads everything once, checks
it, and writes down what is missing; later steps do not query other recipes again.

1. Take each producer's id from the run context ("Reads from other processes"). Query its memory
   with `query-template-records --spec-template-id <producer> --project-id <this project>
   --key-prefix <kind>:`:
   - Onboarding: `profile:channel`, `seed:`;
   - Recon: `seed:`, `watch:`, `idea:`;
   - Daily data: `velocity:`, `studio:`;
   - each creation recipe: `publish:`;
   - this recipe's own memory: `plan:`.
2. Check every record with `youtube-records: scripts/records.py validate --key <key> --data
   '<json>'`. Leave out a record that fails, and list it with the reason. A record whose `v` is not
   1 stops the step: report it rather than guess.
3. **Seeds.** Onboarding's and Recon's seeds were measured against Trends anchors at different
   times, so their `yt_interest` values do not compare. Recon re-measures seeds older than 31 days
   with Onboarding's anchor (the main term of `profile`'s `niche`), and writes the week's measures
   into `keywords.json`, with that `anchor` named.
   - For a term in Recon's newest `keywords.json`, take every seed measure from that file.
   - For any other term, take the `seed` record with the later `as_of`, from either memory, and
     name both records in `inputs.md`.
   - Measures older than 31 days are used as they are and marked **stale**
     (`youtube-strategy/references/thresholds.md` → "Data freshness"). Planning does not
     re-measure them and writes no `seed` record.
4. **Freshness of Daily data's records** (`thresholds.md` → "Ours"): a `velocity` record is stale
   when its `as_of` is more than 2 days before the run, and a `studio` record when its `as_of` is
   more than 4 days before the run. Mark stale ones in `inputs.json`; step 5 does not use them as
   current. A `velocity` record with `source: views-per-age` is a lifetime proxy, not a measured
   daily rate: keep that label wherever its number is quoted.
5. Read the files through `list-step-artifacts --spec-template-id <producer> --project-id <this
   project> --step-name "<step>"`, then `s3 download` each file. The answer prints the anchor it
   resolved; write it into `inputs.md`.
   - From Onboarding:
     - `audience-profile.md` (step "Audience, language and region");
     - `format-plan.md` (step "Formats and content pillars");
     - `brand-profile.md` (step "Brand profile");
     - `upload-defaults.md` (step "Channel settings (desired state)").
   - From Analytics: the newest `report-YYYY-MM-DD.md` (step "Weekly report"). Analytics runs
     weekly, so pass `--limit` large enough to reach the latest passed run, and take the file with
     the newest date in its name. If the name no longer resolves, ask for the map with
     `--all-steps` and take the step whose artifacts include `report-*.md`. No report yet → write
     "no Analytics report" and go on.
   - From Daily data: the newest `ctr-scale-check.md` that has a conclusion (step "Impressions and
     CTR"). It is the settled scale of the Reporting API's CTR, and step 5 uses it. None → write
     "CTR scale not settled".
   - From Analytics, also the newest `settings-reco.md` and `settings-desired.json` (step
     "Settings recommendations"), taken as one pair from the same run. Analytics writes a pair
     every week; only the newest counts. Step 7 shows them to the owner. None → write "no settings
     recommendations".
   - From Recon:
     - the newest `keywords.json` (step "Keyword research and new seeds"), for the seed measures
       of point 3. None → the records alone, said so;
     - `ideas.md` (step "Idea backlog and idea status") and `trend-radar.md` (step "Trend radar"),
       when they exist. They are for reading only: the `idea` records are the contract.
   - From "YouTube Channel Audit", when declared (its brief adds the declaration): the newest
     `audit-decision.json` (step "Owner review": it carries the owner's answer) and its
     `audit-YYYY-QN.md` (step "Diagnosis and decision"). It counts only when its `quarter` is the
     quarter of the newest "Diagnosis and decision" file and its `owner_answer.answer` is
     `accepted` or `changed`; an audit the owner has not answered yet, or an older quarter's
     decision, is named in `inputs.md` and not acted on. A counting decision steers the month:
     `routes_to` `planning` (rung 1, repackaging) → step 5 takes the videos in its `videos` first and
     step 9 tests them, in the first Planning run after the answer only (an earlier `inputs.md` of
     this recipe that names the decision as applied means it was done; report it instead);
     `creation` (rungs 2–3: intro, format, length) → step 4 writes the change into every slot it
     concerns, each month until the decision's `judge_after` is reached; `onboarding` or `owner` →
     Planning changes nothing of its own and names the pending decision. Not declared or none → "no
     audit decision" and go on.
   - From this recipe's own earlier runs: `ab-variants.json` and every `ab-test-<videoId>.json`
     (step 9), so steps 5 and 9 know which tests are running. Also `apply-report.md` (step 8),
     so step 5 knows what was changed recently.
6. Read the channel's uploads with `youtube-data: scripts/data_api.py uploads --mine --with-stats`
   (published time, duration, views), and keep the output as `uploads.json`. Step 4 uses it for
   publish hours, and step 5 for the medians.
7. Write `inputs.json`: the validated records by kind, the seed measures chosen by point 3 with
   their source, the file paths and the instances they came from. Write `inputs.md`: per kind, the
   count, the newest and oldest `as_of`, the stale records, and what is missing (an undeclared
   producer included).

**2 — Close last month's slots.**

The calendar is a queue. A slot that was planned and made has to be marked as made, so that the
next calendar does not plan the same idea twice.

1. Check these own `plan` records: every `planned` one, and every `dropped` one dated within the
   last 60 days (a video can come out after its slot). For each, look for a `publish` record whose
   `plan` equals the slot's full key `plan:<date>:<slot>`. When none does, look for one whose
   `idea` equals the slot's `idea` (both are the bare slug).
2. If a `publish` record matches, write the slot again with `youtube-records: scripts/records.py
   write plan`, with the same `date`, `slot`, `title`, `format` and `idea`, `--status published`
   and `--source planning`. A `dropped` slot moves to `published` the same way.
3. If a `planned` slot is more than 14 days past its date with no match, write it with `--status
   dropped` (`thresholds.md` → "Ours"). Leave a younger slot as it is. `in-progress` is not used:
   no recipe of the set writes it.
4. Build each key with `records.py key plan --date … --slot …`; never by hand.
5. Write `closed-slots.md`: each slot, its new status, and the video id or "none".

**3 — Rank the ideas.**

1. Candidates:
   - `idea` records (Recon's memory) with status `new` or `shortlisted`;
   - minus every idea whose slug is named in `idea` by an own `plan` record whose status is not
     `dropped`. An idea whose only plans are `dropped` is a candidate again: Recon moves it back to
     `shortlisted` when it has no `publish` record.
2. Give each candidate its seed's measures by the idea's `keyword`, as step 1 chose them: from
   Recon's newest `keywords.json` when the term is in it, otherwise from the seed record. When the
   measures are stale, the idea's entry says "stale seed, as_of <date>" beside the script's
   `basis`. Say in the summary how many ideas were scored from `keywords.json` and how many from
   records: their `yt_interest` values share one scale only within `keywords.json`.
3. Judge fit, packaging and feasibility with the anchored rubric in
   `youtube-strategy/references/ideation.md`. The `idea` record keeps only Recon's total score, so
   Planning judges again. Fit is judged against the pillars of `format-plan.md`.
4. Score the whole batch at once with `youtube-strategy: scripts/score_idea.py --file ideas.json`.
   A refusal names the missing input: measure it or judge it, never default it. An idea whose seed
   has no numbers is judged on `--demand` / `--opportunity`, and the `basis` says so.
5. Write `idea-ranking.json`: the script's output, plus each idea's slug, format, Recon's `score`,
   and its traffic strategy and urgency as Recon's `note` states them (search / browse / trend;
   flash / sustained / seasonal with its date). When the `note` does not say, write "unstated".

**4 — Build the calendar.**

Follow `youtube-strategy/references/calendar.md`: its steps, its output template and its quality
bar.

1. **The month.** Plan the calendar month that begins on or after the run's day, in the schedule's
   time zone. On the 1st, that is the current month.
2. **The cadence and pillars** come from Onboarding's `format-plan.md`: long-form, Shorts and lives
   per month, the Hub/Help pillars, and Hero moments per quarter. Count the month's slots from it.
   No `format-plan.md` → the step does not invent a cadence: it asks the owner (below) and offers
   one long-form video a week as the default (`channel-types.md`).
3. **Existing slots.** For each date and slot, build the key with `youtube-records:
   scripts/records.py key plan` and check the own memory. A slot that already has a record is not
   planned again: it is shown in the calendar as it stands.
4. **Fill the free slots** in score order from `idea-ranking.json`, with the rules of
   `calendar.md`:
   - pillars rotate;
   - trend ideas are at most 30 % of the month's slots;
   - flash trends go in the first week or not at all;
   - seasonal ideas are dated backwards from their event.

   Ideas whose strategy is "unstated" count as evergreen, and the balance section says how many
   there were.
5. **Publish hours.** Take the channel's best past publish hours from `uploads.json`. With fewer
   than 4 uploads, state the assumption.
6. **Per long-form slot**, write three titles: search-led, browse-led and hybrid. Each keeps the
   identity tokens of `profile` verbatim and the idea's keyword.
   - Lint each title with `youtube-metadata: scripts/check_metadata.py --title … --keyword …
     --format long --require-token <each identity token>`.
   - Lint each title with its thumbnail text with `youtube-metrics: scripts/title.py --title …
     --thumb … --lang <profile language>`.

   Fix every error. Fix every warning, or justify it.
7. **Owner check.** Send the draft calendar with `send-message`: the month grid, the slots with
   their ideas and scores, and the balance line. Use the buttons "Approve" and "Change", and ask in
   the same message for dates to add: releases, events, holidays. Say there that on silence the
   draft stands, with no extra dates. A calendar is not public (README rule 9 covers what is), so
   silence keeps the draft; changes to live videos in step 7 work the other way. Then `await-reply`. Revise once on "Change".
8. **Write the records.** Write each new slot with `records.py write plan`:
   - `date` and `slot` (`main`, `short-1`, `live`, …);
   - the chosen `title`, the `format`, `--status planned`, `--idea <slug>` and `--source planning`.

   The other two titles, the hook, the thumbnail concept and the Shorts cuts stay in the artifact.
9. Write `calendar-YYYY-MM.md` with the template of `calendar.md`, including "Closed from last
   month" from step 2.

Validator rubric (Score 1-10, pass at 7):
- every slot of the month has a date of that month, a format, a title and an idea slug (or
  "owner" for a slot the owner set), with no TBD;
- the number of slots matches the cadence of `format-plan.md`, or the deviation is stated;
- the trend share is computed and is ≤ 30 %, or flagged with the swap that fixes it;
- every long-form slot has three titles, and each carries the identity tokens verbatim;
- no idea is planned twice, and no idea named by an earlier `plan` record that is not `dropped`
  is planned again;
- a `plan` record exists for each new slot, and no existing slot was overwritten.

**5 — Find underperformers.**

The channel's own median is the benchmark (`thresholds.md`); external CTR or retention averages
are not used. A video is a candidate when it falls short on views, on CTR, or on retention. The
funnel table in `youtube-strategy/references/analytics-report.md` says which part of the video to
fix.

1. **Format.** Take each video's format from its `publish` record. When there is none, use the
   duration: up to 180 s counts as "probably short", and say so.
2. **Views, per format.** Split `uploads.json` by that format into `uploads-long.json` and
   `uploads-short.json`, and run `youtube-metrics: scripts/swipe.py <file> --direction down` on
   each, so a long video is never measured against Shorts' views. It needs 4 or more videos of a
   format; with fewer, the step lists them and ranks nothing for that format. `swipe.py` compares
   views, not age, so give each candidate its age and its `velocity` record (`views_per_day`,
   `anomaly`) when it is fresh; a stale one is quoted as stale, and a `views-per-age` one as a
   proxy.
3. **Impression CTR over 28 days.** Run `youtube-data: scripts/reporting.py reach --since <28 days
   back> --all-days --ctr-scale <scale>`. The scale comes from Daily data's newest
   `ctr-scale-check.md` (step 1). Planning never settles the scale itself and never guesses it.
   - If the scale is not settled, or the script refuses under it, use the `studio` records
     instead, only the fresh ones (step 1), and say the CTR is a single day's.
   - Sum impressions and clicks per video, and compare the CTR with the channel's median for the
     same format.
   - No rows, or `available: false` → CTR is "no data" for that video; it is not zero, and the
     video is not dropped.
4. **Retention.** For the candidates:
   - read average view duration and percentage with `youtube-data: scripts/analytics.py
     video-metrics`;
   - read the curve with `analytics.py retention … --csv retention-<id>.csv`;
   - run `youtube-metrics: scripts/retention.py retention-<id>.csv --axis percent --duration <s>
     --hook-seconds 15` for a long-form video, and `--hook-seconds 3` for a Short, the same windows
     Analytics uses, so both recipes name the same hook leak.

   Report the biggest leak.
5. **Analytics' view.** When the latest Analytics report lists a video under "Outliers → Down", or
   its main fix names one, add it with that evidence.
6. **Leave out:**
   - videos with an A/B test that a `ab-variants.json` started and no `ab-test-<videoId>.json` has
     read yet (`youtube-thumbnail-check/references/checklist.md`: changing the title or thumbnail stops a test);
   - videos that this recipe changed (`apply-report.md` of earlier runs) within the last 28 days,
     because their new numbers are not in yet.
7. **What to fix.** For each candidate, name the leak from the funnel table:
   - package (impressions present, CTR low) → title and thumbnail;
   - promise (CTR fine, retention low) → title and description that match what the video
     delivers, never a stronger promise;
   - reach (both low) → keyword and title.
8. Read the current metadata of every candidate with `youtube-data: scripts/data_api.py videos
   --id … --with-description` (title, description, tags, duration), and keep it in the artifact.
   Step 6 needs no token.
9. Write `underperformers.json`: per video, every number with its source and date, the leak, and
   the current metadata. Keep the five with the largest gap to the median; list the rest.

Validator rubric (Score 1-10, pass at 7):
- every candidate's numbers cite their source and date, and the medians are the channel's own, per
  format;
- CTR is "no data" where the reach data had none, never 0;
- no video with an unread A/B test is a candidate;
- each candidate names one leak, and the evidence for it.

**6 — Repackage metadata and thumbnails.**

Follow `youtube-metadata/SKILL.md` and `references/metadata-rules.md`. A package fixes the leak
step 5 named, and nothing else.

1. **Identity and keyword.** Keep the identity tokens of `profile` verbatim. Choose one primary
   keyword from the seed measures step 1 chose; a stale one is named as stale. A topic with no
   seed:
   - measure it with `youtube-demand: scripts/dfs.py`: one Labs `keyword_overview`, and one YouTube
     SERP;
   - run `normalize.py --only <term>` on the two files;
   - keep the row in `reopt-package.json` as a term for Recon to consider.

   Planning does not write it as a seed.
2. **Fixed block.** Take the description's fixed block (links, labels, credits) from
   `upload-defaults.md` and the current description. Keep it intact. The links come from the
   `LINK_*` keys (and `BUSINESS_EMAIL`) declared on this step at build time, never typed from
   memory. A link in the fixed block whose key is not declared is kept exactly as the current
   description has it, and named in `reopt-package.json` as a key to declare.
3. **Titles.** Write several titles for the surface the video is for (the surface table in
   `metadata-rules.md`), and keep two or three. Then write the description, the tags and the
   hashtags.
4. **Chapters.**
   - Check the chapters of the current and the new description with `youtube-metrics:
     scripts/chapters.py validate --description-file … --duration <s>`.
   - A long video without chapters gets drafted ones: `youtube-data: scripts/transcript.py --id …
     --lang <profile language>` (needs `yt-dlp`), then `chapters.py draft <id>.srt`. Rewrite the
     drafted labels before use.
5. **Lint.** Lint each set with `youtube-metadata: scripts/check_metadata.py --file meta-<id>.json`
   (duration, format and `require_tokens` included), and each title with its thumbnail text with
   `youtube-metrics: scripts/title.py`. Fix every error; fix or justify every warning.
6. **Thumbnails** (when the leak is the package):
   - Download the current one with `youtube-data: scripts/thumbnails.py --id … --out-dir
     thumbs/`.
   - Write a redesign brief with `youtube-thumbnail-check/references/checklist.md` → "Redesign
     brief". The palette and style come from `brand-profile.md`.
   - Render 2–3 candidates with `poyo`, the newest `gpt-image-*` model at run time. Each candidate
     differs from the current thumbnail in one variable. Export each as JPEG or PNG, 16:9 (9:16 for
     a Short), at least 640 px wide and at most 50 MB (Help 72431, as youtube-thumbnail-check
     states it).
   - Measure the current thumbnail and every candidate with `youtube-thumbnail-check:
     scripts/analyze_thumbnail.py <image> --out-dir thumb-check/<id> --kind video|short`.
   - Open the 120 px and 168 px previews and judge them with the checklist.
7. **Route.** Mark each change:
   - `metadata`: a new title, description or tags;
   - `thumbnail`: a direct swap;
   - `ab`: a long-form video that is public or unlisted and not made for kids, where the owner may
     prefer a test (`youtube-studio/references/ab-test.md`). Shorts cannot be tested.
8. Save each proposed metadata set as `meta-<id>.json` with only the fields to change (`title`,
   `description`, `tags` as a list, `defaultLanguage`): step 7 diffs it and step 8 applies it.
9. Write `reopt-package.json`: per video, the current set, the proposed set, the lint outputs, the
   thumbnail measurements with their preview paths, the hypothesis in one sentence, and the route.

Validator rubric (Score 1-10, pass at 7):
- every proposed title keeps every identity token verbatim, and `check_metadata.py` reports no
  errors;
- each package addresses the leak step 5 named, with the evidence quoted;
- the primary keyword is a seed term with its numbers and `as_of`, or measured in this step, or the
  package says it has none;
- the fixed block of the description is unchanged, and no link was typed from memory;
- every thumbnail candidate has `analyze_thumbnail.py` output, and passes the 120–168 px legibility
  check or says why not;
- each A/B variant changes one variable against the current thumbnail;
- no claim of a CTR or watch-time lift appears without a source.

**7 — Owner approval.**

The owner decides from what the apply scripts would actually change, not from a draft. So each
proposal is shown with the script's own dry-run diff, which reads the live state and claims
nothing.

1. **Video diffs.** For each video in `reopt-package.json`, run `youtube-metadata:
   scripts/apply_video.py metadata --video-id <id> --desired meta-<id>.json --dry-run`.
   - The desired file holds only the fields to change: `title`, `description`, `tags` (a list),
     and `defaultLanguage` when needed.
   - An empty diff means the video already has this state. Say so, and propose nothing for it.
2. **Channel settings diff.** When step 1 found a `settings-desired.json`, run
   `youtube-channel-setup: scripts/apply_channel.py branding --desired settings-desired.json
   --dry-run`.
   - The diff is against the channel as it is now, not as it was when Analytics wrote the file.
   - An empty diff, or an Analytics "No change", means there is nothing to approve.
   - Recommendations in `settings-reco.md` that are Studio-only are listed for the owner as
     information. This recipe does not apply them.
3. **One message per video**, with `send-message`:
   - the dry-run diff of title, description and tags;
   - the thumbnail candidates with their 168 px previews;
   - the leak and the hypothesis.

   Use the buttons "Apply metadata", "Swap thumbnail: <candidate>" (one per candidate),
   "A/B test thumbnails" (only where step 6 marked the route `ab`) and "Skip".
4. **One message for the channel settings:** each recommendation of `settings-reco.md` with the
   data behind it, the dry-run diff, and the buttons "Apply settings" and "Skip".
5. After each message, `await-reply`. Silence means "Skip": say so in the message.
6. Write `approvals.json`: per item, what was approved, which candidate, the dry-run diff it was
   approved on, and the owner's words. Approve nothing on the owner's behalf.

**8 — Apply the approved changes.**

Every apply goes through a script that claims, acts, re-reads and commits its intent (the guard
of youtube-studio) by itself. The step does not build keys or claim by hand, and does not write
another API client.

1. **Metadata.** Run `youtube-metadata: scripts/apply_video.py metadata --video-id <id> --desired
   meta-<id>.json` — the same file that was approved.
   - The script merges the desired fields into the live snippet and sends the whole snippet back,
     because `videos.update` replaces it.
   - It re-reads to verify, and claims and commits `metadata:video:<id>:<digest>`.
2. **Thumbnail.** Run `youtube-metadata: scripts/apply_video.py thumbnail --video-id <id> --image
   <approved file>`.
   - The file must be JPEG or PNG, at least 640 px wide and at most 50 MB. The script checks this
     before it claims; step 6 exports its candidates that way.
   - A 2xx answer is the evidence, because the API cannot read a custom thumbnail back. Then look
     at the watch page once, or download it with `youtube-data: scripts/thumbnails.py --id <id>
     --out-dir after/`, and write what was seen. This is a check for the report, not a condition
     for the commit.
3. **Channel settings.** Run `youtube-channel-setup: scripts/apply_channel.py branding --desired
   settings-desired.json` with the approved file. It claims `settings:channel:<digest>` itself.
4. **Read each answer** (`ok`, `acted`, `changed`, `key`, `units_used`, `uncertain`):
   - `ok: true`, `acted: true` → done and verified (for a thumbnail, the 2xx); report the key.
   - `ok: true` with `changed: false`, or a committed claim skipped → the video or channel already
     has this state; report it.
   - `uncertain` → the claim stays open. Never run the same change again; report it to the owner.
   - `ok: false` → YouTube refused and nothing changed; the script has failed the intent. Report
     the error.
   - `fallback: "studio"` (a missing scope) → the set has no Studio playbook for the video details
     page yet. Stop that change and tell the owner which one and why; do not improvise in Studio.
5. Write `apply-report.md`: per change, its intent key, the outcome, the units used and the total
   of the run, and the thumbnail check. Do not retry anything that failed in this run.

**9 — Thumbnail A/B tests (optional).**

Follow `youtube-studio/references/ab-test.md` and `references/session.md`, with the browser tools
`mcp__playwright-yt-studio__*`.

1. **Session check first.** If it fails: `ensure-session`, close the browser, and check once more.
   If it still fails, `request-browser-login` and stop this step's Studio part: nothing is claimed.
2. **Read the earlier tests** (read-only, no intent). For each test in an earlier `ab-variants.json`
   without an `ab-test-<videoId>.json`, open its Reach tab and copy the outcome and each variant's
   watch-time share into `ab-test-<videoId>.json`.
   - "Winner": YouTube has already applied it, and the step does not change the thumbnail again.
   - "Performed same" or "Inconclusive": that is a result. Keep the original, and do not re-run
     the pair.
3. **Start the approved tests.** For each test approved in step 7:
   - build the key with `youtube-studio: scripts/intent.py key ab --video-id <id> --date <today>`;
   - run `intent.py claim`;
   - upload the current thumbnail first and the candidates after it;
   - save, reload, and verify that the test is in progress;
   - run `intent.py commit` with `{video_id, started, variants}`.

   Do one test per browser lifetime after a session refresh.
   - No "A/B Testing" control → run `intent.py fail --reason "A/B Testing not offered"` and report.
     Run `fail` only when the test certainly did not start.
   - Save or verify unclear (an error after Save, a page that does not show the test) → leave the
     claim open, do not retry, and report it to the owner. A later run's claim answers `claimed`
     and checks the video instead of starting a second test.
4. Write `ab-variants.json`: the tests started this run, with their start dates and the variant
   files.

## Building it: reads, keys and schedule

1. **Declare the producers.** Find each with `find-spec-template --name "<exact name>"` and
   declare it with `declare-read`:
   - "YouTube Onboarding";
   - "YouTube Daily data";
   - "YouTube Recon";
   - "YouTube Analytics";
   - "Create Music Release", the creation recipe of the set that writes `publish` records. Ask
     the owner whether any other creation recipe publishes to this channel, and declare each one
     they name.

   A producer that does not exist yet is left out (README rule 5). The run treats it as absent,
   says so in `inputs.md`, and does not look it up by name. When that producer is built later,
   its brief adds the declaration.
2. **Wire Planning back into its earlier readers.** After this recipe is published, Recon and
   Analytics read its `plan` records, and they were built before it. For each of "YouTube Recon"
   and "YouTube Analytics":
   - find the reader with `find-spec-template --name`;
   - run `declare-read --spec-template-id <reader> --producer-spec-template-id <YouTube Planning>`;
   - apply that reader's revision.
3. **Link keys of step 6.** Ask the owner which `LINK_*` keys the project holds, and which of them
   the descriptions' fixed block carries (Onboarding's `upload-defaults.md`). Declare only those on
   step 6. Declare `BUSINESS_EMAIL` only if the fixed block carries a contact address and the
   project holds it. A declared key the project does not hold makes every run pause.
4. **Schedule.** Settle the project with the owner, then run `add-spec-template-schedule` with cron
   `0 6 1 * *` in the time zone of `profile:channel`'s `country` (for a country with several
   zones, the one the owner names), or the day and time the owner prefers. Read back the
   schedule's zone and next fire time and confirm them to the owner.

## What changed from the source brief

| Source brief | Now |
| --- | --- |
| `youtube` (claude-youtube) `/calendar`, `yt-viral` `swipe.py` | `youtube-strategy` `calendar.md` + `score_idea.py`; `youtube-metrics` `swipe.py`, `retention.py`, `title.py`, `chapters.py` |
| `google-api-python-client` for reads and `videos.update` / `thumbnails.set` | `youtube-data` scripts for reads; `youtube-metadata: scripts/apply_video.py` for applying |
| `youtube-seo-thumbnail` by link + `opencv-python` + `numpy` | `youtube-thumbnail-check` + `opencv-python-headless` from the shelf |
| `records.py` pinned as a file; `plan:<date>` keys | the `youtube-records` skill on the recipe; `plan:<date>:<slot>` keys with `idea` naming the slug |
| `plan` statuses planned / in-progress / done | planned / published / dropped (`in-progress` unused), closed by Planning from `publish` records; `dropped` 14 days after the date, back to `published` when a late `publish` names it |
| `ai-integration claim-intent` with `update_metadata:video:<id>` keys | the apply scripts claim through `intent.py` themselves; A/B tests through `intent.py key ab` |
| CTR from the latest `studio` record | 28 days of Reporting API reach rows; the latest `studio` record only as fallback |
| reads Templates 1–3 | also Analytics' latest report and settings recommendations, and the creation recipes' `publish` records |
| channel settings applied by Analytics | applied here, after the owner approves the dry-run diff; Analytics only recommends |
| no seed freshness | seeds older than 31 days are marked stale; Recon re-measures them |
| no owner approval before applying | every change to a live video or the channel approved in the chat first |
