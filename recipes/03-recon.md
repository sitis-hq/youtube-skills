# Brief 3 — YouTube Recon

Follow [the rules of the set](README.md); this brief adds what is specific to Recon.

**Name:** `YouTube Recon` · **Scope:** global recipe, run inside the channel's own project ·
**Schedule:** weekly, Monday 05:00 in the time zone of `profile:channel`'s country · **Reads from:** "YouTube Onboarding"
(`profile:channel`, `seed:*`), "YouTube Daily data" (`velocity:*`), "YouTube Community"
(`community-ideas.md` of the last 7 days' runs), "YouTube Planning" (`plan:*`) and each creation
recipe that publishes to the channel, such as "Create Music Release" (`publish:*`).

## What it is for

Once a week it decides what is worth filming. It finds what is fresh and popular in the niche by
topic — no competitor list is needed up front — keeps a scored watchlist of competitor videos, finds
the videos that beat their own channel's normal, reads what their titles, hooks and thumbnails do,
measures the keywords behind the week's rising topics, and turns all of it into a ranked,
deduplicated idea backlog.

What it leaves behind, every week:

- **Records** (its own memory, through `youtube-records`):
  - `watch:<videoId>` — the competitor watchlist. Daily data snapshots these every day.
  - `seed:<slug>` — the keywords Recon added or re-measured. Onboarding's seeds stay in
    Onboarding's memory; Recon never writes there.
  - `idea:<slug>` — the idea backlog, each with a status. Planning and the creation recipes read it.
    Recon is its one writer, so Recon alone moves an idea's status forward: to `planned` when a
    Planning `plan` record names it, to `published` when a creation recipe's `publish` record does.
- **Artifacts:** `inputs.md`, `candidates-raw.json`, `rising-queries.json`, `competitors-raw.json`,
  `outliers.json`, `patterns.md`, `thumb-benchmark.md`, `trend-radar.md`, `keywords.json`,
  `ideas.md`, and every saved API response the scripts read.

Recon is API-only: it touches no Studio page and takes no irreversible action on the channel, so it
needs no Studio session and no intent keys.

## Requirements (EARS) to put into the recipe

1. WHEN a run starts THEN system MUST read `profile:channel` and the `seed` records from "YouTube Onboarding" and the `velocity` records from "YouTube Daily data", validate each with `records.py validate`, and MUST stop and report if `profile:channel` is missing or invalid.
2. WHEN an upstream has no records yet (no seeds, no velocity, no plan or publish records, no Community file) or a producer recipe does not exist THEN system MUST continue on what exists, and MUST say in `inputs.md` which input was empty or absent.
3. WHEN a run starts THEN system MUST read the `community-ideas.md` of every "YouTube Community" run of the last 7 days through `list-step-artifacts`, the `plan` records of "YouTube Planning" and the `publish` records of each declared creation recipe, validating each record with `records.py validate`.
4. WHEN discovery runs THEN system MUST find fresh, popular niche videos by topic within a stated Data API unit budget and a stated DataForSEO spend, and MUST save the raw responses.
5. WHEN a candidate video is scored THEN system MUST score it by views per day against its own channel's median with `candidates.py`, and MUST write a `watch` record only for the candidates it decides to follow, each with a one-sentence reason.
6. WHEN a candidate is already on the watchlist THEN system MUST NOT write it again.
7. WHEN outliers are flagged THEN system MUST measure them as a multiple of their own channel's median with `swipe.py`, MUST add the spike and drop flags of Daily data's `velocity` records where they exist, and MUST say when a flag is missing or stale.
8. WHEN outliers are found THEN system MUST describe the title, hook, format and thumbnail patterns behind them from measurements (hook formulas, transcripts, thumbnail measurements and previews), and MUST name what competitors cover that this channel does not.
9. WHEN rising queries are found THEN system MUST measure each one it keeps (volume, CPC, `kd_web`, intent, `yt_interest`, `yt_competition`) before writing it as a `seed` record in Recon's own memory, with all Trends requests of the run sharing one anchor term.
10. WHEN ideas are produced THEN system MUST score each one with `score_idea.py`, MUST write each as an `idea` record with keyword, hook, thumbnail concept, format, source and status, and MUST NOT write an idea whose slug, or whose keyword and angle, an earlier `idea` record already holds.
11. WHEN a repeated viewer question from `community-ideas.md` fits the niche THEN system MUST treat it as an idea source, with `source community`, and MUST NOT propose the same question twice across runs.
12. WHEN a `plan` record names an idea THEN system MUST rewrite that idea record, same key, with status `planned`; WHEN a `publish` record names it THEN with status `published`; WHEN every plan naming a `planned` idea is `dropped` and no `publish` names it THEN with status `shortlisted`; and MUST NOT move a status backward otherwise, nor move a `rejected` or `published` idea.
13. WHEN an idea's title is written THEN it MUST keep every identity token of `profile:channel` verbatim, MUST fit the channel type and the niche chosen in Onboarding, and MUST stay within 100 characters.
14. WHEN the run ends THEN system MUST state the Data API units and the DataForSEO cost it spent, each summed from the scripts' outputs.
15. WHEN a number is quoted THEN it MUST carry its source and date; a threshold MUST come from `youtube-strategy/references/thresholds.md`.

## Steps

The "Skills" column lists skills from the shelf, attached to that step. `youtube-records` is
attached to the recipe, as rule 2 says.

| # | Step | Who | Skills and tools on the step | Credentials | Writes |
| --- | --- | --- | --- | --- | --- |
| 1 | Inputs and budget | AI | — | — | `inputs.md`, `community-questions.json`, `idea-status.json` |
| 2 | Discovery of fresh and popular videos | AI | `youtube-data`, `youtube-demand`, `dataforseo-mcp-server` | `YOUTUBE_REFRESH_TOKEN`, `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD` | `candidates-raw.json`, `videos-found.json`, saved responses |
| 3 | Rising queries | AI | `youtube-demand`, `dataforseo-mcp-server` | `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD` | `rising-queries.json`, saved responses |
| 4 | Score candidates, extend the watchlist | AI | `youtube-data`, `youtube-metrics` | `YOUTUBE_REFRESH_TOKEN` | `watch` records, `watch-scoring.json` |
| 5 | Watchlist data | AI | `youtube-data` | `YOUTUBE_REFRESH_TOKEN` | `competitors-raw.json`, `own-uploads.json` |
| 6 | Outliers | AI | `youtube-metrics` | — | `outliers.json` |
| 7 | Title, hook and format patterns | AI | `youtube-data`, `yt-dlp`, `youtube-strategy` | — | `patterns.md`, transcripts |
| 8 | Competitor thumbnails | AI | `youtube-data`, `youtube-thumbnail-check`, `opencv-python-headless` | — | `thumb-benchmark.md`, thumbnails, previews |
| 9 | Trend radar | AI | `youtube-data`, `youtube-demand`, `yt-dlp`, `youtube-strategy` | — | `trend-radar.md`, `baselines.json` |
| 10 | Keyword research and new seeds | AI | `youtube-demand`, `youtube-data`, `dataforseo-mcp-server` | `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD`, `YOUTUBE_REFRESH_TOKEN` | `seed` records, `keywords.json` |
| 11 | Idea backlog and idea status | AI | `youtube-strategy`, `youtube-metrics` | — | `idea` records, `ideas.md` |

Order: 1 first; 2 and 3 in parallel; 4 after 2; 5 after 4; 6 after 5; 7 and 8 after 6; 9 after 3, 6
and 7; 10 after 9; 11 after 8 and 10.

## Spend per weekly run

Both budgets are written into `inputs.md` by step 1 and checked by every step that spends.

**Data API** (10,000 units a day per Google project, shared with Daily data's snapshot of the same
day; costs from `youtube-data/SKILL.md`):

| Call | Units |
| --- | --- |
| search, at most 5 pages a run (100 a page) | ≤ 500 |
| videos, 1 per 50 ids (discovery, watchlist, own uploads) | ≈ 10–20 |
| uploads with stats, about 2 per channel, at most 40 channels | ≤ 80 |
| channels, 1 per 50 ids | ≈ 2 |
| **Ceiling for the run** | **800** |

**DataForSEO** (Live prices from `youtube-demand/SKILL.md`, read 2026-11-04; the response's `cost`
field is the truth and is what the run sums):

| Call | Count a run | Price | Spend |
| --- | --- | --- | --- |
| YouTube SERP, discovery (step 2) | ≤ 10 terms | $0.002 | ≤ $0.020 |
| Trends rising queries, one keyword each (step 3) | ≤ 5 | $0.011 | ≤ $0.055 |
| Labs `keyword_overview`, one call (step 10) | 1 call, ≤ 100 keywords | $0.012 + $0.00012 × keywords | ≤ $0.024 |
| Trends graph, anchor + 4 terms a request (step 10) | ≤ 8 | $0.011 | ≤ $0.088 |
| YouTube SERP, the week's keywords (step 10) | ≤ 30 | $0.002 | ≤ $0.060 |
| **Ceiling for the run** | | | **$0.25** (hard stop at **$0.40**) |

The SERP and Trends calls may go through Standard (`task_post`, then `tasks_ready` and `task_get`),
which costs about a quarter of Live ($0.0006 a SERP, $0.0027 a Trends task); Labs is Live only.
`include_clickstream_data` stays off: it doubles the Labs price. A step that would cross the hard
stop drops its lowest-priority calls and says which.

## Design notes per step

**1 — Inputs and budget.**

Verify before acting: every later step works on what this step found.

1. Take the producers' ids from the run context ("Reads from other processes"): "YouTube
   Onboarding", "YouTube Daily data", "YouTube Community", "YouTube Planning" and each declared
   creation recipe (such as "Create Music Release"). A producer the context does not list is
   absent for this run (README rule 5): it is not looked up or read by name, its input is skipped,
   and `inputs.md` says so. Declaring it later is the producer's build's job. Only Onboarding is
   required.
2. Read `profile:channel` from Onboarding's memory (`get-template-record`) and every `seed:` record
   (`query-template-records`, prefix `seed:`). Check each with `youtube-records: scripts/records.py
   validate`. A missing or invalid `profile:channel` stops the run with a report: ideas cannot
   respect a channel type and identity tokens that are not known.
3. Read every `velocity:` record from Daily data's memory and validate each. Note each one's
   `as_of`, and mark it stale by the `velocity` staleness row of
   `youtube-strategy/references/thresholds.md` → Ours (stale when `as_of` is more than 2 days before
   the run). A stale record's flag is reported, not used. Read Recon's own `watch:`, `seed:`
   and `idea:` records the same way (own memory, no declaration needed).
4. **Community questions.** Community runs every weekday and Recon once a week, so one file is not
   the week. List them with `list-step-artifacts --spec-template-id <Community> --step-name "Mine
   ideas from questions" --limit 10`, keep the instances of the last 7 days, and download each
   one's `community-ideas.md`. A file that says "No repeated
   questions between <since> and <today>" contributes nothing and is not an error. Merge the
   questions across the files: the same question (same comment ids, or the same need in other
   words) is one entry, its comment ids the union, its count the number of distinct comment ids,
   its date range the widest. Drop a question that an earlier `idea` record with `source
   community` already answers (its `note` names the question). Write `community-questions.json`:
   each question, count, comment ids, videos, date range, the angle as Community wrote it, and the
   run dates of the files read.
5. **Idea status.** Read every `plan:` record from Planning's memory and every `publish:` record
   from each declared creation recipe's memory, and validate each. For each of Recon's `idea`
   records, find:
   - a `publish` record whose `idea` equals the idea's slug → the idea is `published`;
   - else a `plan` record whose `idea` equals the slug, with status `planned` or `published` → the
     idea is `planned`;
   - else, when every `plan` record naming the slug is `dropped`, an idea now `planned` goes back
     to `shortlisted`, so the backlog offers it again.
   Accept the slug with or without the `idea:` prefix. Status moves forward only (new →
   shortlisted → planned → published), with that one exception: `planned` back to `shortlisted`
   when its only plans are dropped and no `publish` names it. Planning drops a slot only 14 days
   after its date and moves it to `published` if a `publish` arrives later, so a late video ends as
   `published` here too. A `published` idea never moves; a `rejected` idea is never moved, and a
   match on one is listed as a conflict. Write `idea-status.json`: each idea whose status
   must move, its current and new status, and the `plan` or `publish` key that moves it. Step 11
   writes the changes.
6. The run's **anchor term** for every Trends request is Onboarding's: the main term of
   `profile:channel`'s `niche` — the term Onboarding anchored its seed set on. It is the same every
   week, and step 10 writes it into `keywords.json` as `anchor`. Planning takes `yt_interest` (and
   the other seed measures) from Recon's newest `keywords.json`, so it has to be one scale.
7. Choose the run's **main terms** (at most 10): Onboarding's and Recon's seeds with the highest
   `yt_interest` and `volume`, one per content pillar where the seeds allow; with no seeds, the
   `niche` of `profile:channel` alone.
8. Write `inputs.md`: the profile (channel type, language, country, niche, identity tokens), the
   count of each kind read and from whom, the Community files read (run dates) and the count of
   merged questions, the ideas whose status must move, stale and invalid records, producers absent
   (undeclared), the anchor, the main terms, and both budgets from "Spend per weekly run". Empty
   inputs are named, not treated as errors.

**2 — Discovery of fresh and popular videos.**

Two sources, because they find different things: the Data API filters by date and sorts by views
(fresh and popular), and the DataForSEO YouTube SERP shows what ranks for a query on a phone, at no
quota.

1. For at most 5 main terms, run `youtube-data: scripts/data_api.py search --q <term>
   --published-after <run date − 30 days> --order viewCount` with the channel's `--region` and
   `--language`. One page each, 100 units a page.
2. For every main term, get one SERP with `youtube-demand: scripts/dfs.py post
   /v3/serp/youtube/organic/live/advanced` (`block_depth` 20, `device` mobile, location and
   language from `profile:channel`), one saved response per call.
3. Search returns no view counts, and the SERP no channel ids for some rows: read every id found in
   both with `youtube-data: scripts/data_api.py videos --ids-file <file>` (it takes the search
   output and the SERP files as they are), and keep that output as it came: `videos-found.json`.
4. Write `candidates-raw.json`: for each video, the term it came from and the source (`search` or
   `serp`); the files read; the units and the DataForSEO cost spent.

**3 — Rising queries.**

1. For each main term (at most 5), call Trends explore with `type: youtube`, `time_range:
   past_90_days`, `item_types: ["google_trends_queries_list"]` and exactly one keyword, with
   `youtube-demand: scripts/dfs.py`, one saved response per call.
2. Run `youtube-demand: scripts/normalize.py --trends <files> --as-of <run date>` and keep its
   `related` list: the rising and top queries, without metrics yet.
3. Drop queries already held as a seed in either memory (same slug), and queries off the niche of
   `profile:channel`. Write `rising-queries.json`: each query, its parent term, rising or top, and
   its value as it came.
4. Write no `seed` here: a rising query becomes a seed only after step 10 measured it.

**4 — Score candidates, extend the watchlist.**

1. For each channel among the candidates, read its recent uploads with `youtube-data:
   scripts/data_api.py uploads --channel-id <id> --max 20 --with-stats`. Skip channels already
   fetched this run; stop at 40 channels and list the rest.
2. Run `youtube-metrics: scripts/candidates.py videos-found.json --source search --baseline
   <uploads files> --max-age-days 30 --top 20`. Use `--source search` for both discovery sources
   (the `watch` schema knows search, trends and competitor-list; `serp` is recorded in
   `watch-scoring.json`, not in the record).
3. A candidate in `need_baseline` has no score: fetch its channel's uploads and run again. Never
   write it unscored.
4. Choose whom to follow: a score at or above 3 (the outlier line of `thresholds.md`, applied to
   views per day), on topic for the channel's niche. Skip any video whose `watch:` key Recon already
   holds — it is followed already, and its later numbers are Daily data's `velocity`.
5. Write each chosen one with `youtube-records: scripts/records.py write watch`, passing the
   script's `record` fields as they came, plus `--reason` (one sentence: what makes it worth
   following).
6. Write `watch-scoring.json`: the script's output, who was written, who was skipped as already
   followed, and the count of new watch records.

Validator rubric:
- every new `watch` record has `video_id`, `channel_id`, `source`, `score` and a `reason`;
- every new record's `score` is the one `candidates.py` gave, and is at least 3;
- no video was written that Recon already held under `watch:`;
- the step's summary states how many records are new and how many units were spent.

**5 — Watchlist data.**

1. Read current stats for every `watch:` record of Recon's memory with `youtube-data:
   scripts/data_api.py videos --ids-file <the query-template-records answer>`; `missing` videos
   (deleted, private) are listed, not dropped silently.
2. For outlier detection every channel needs at least 4 of its videos in the input: reuse step 4's
   uploads files and read the remaining watched channels with `youtube-data: scripts/data_api.py
   uploads --channel-id <id> --max 20 --with-stats`.
3. Read the channel's own recent uploads with `youtube-data: scripts/data_api.py uploads --mine
   --max 50 --with-stats`, for the "what we do not cover" comparison of step 7.
4. Write `competitors-raw.json` as an object whose `videos` list holds the competitors' rows as
   `data_api.py` gave them (watched videos and their channels' uploads, no repeats), with a
   `velocity` object of each watched video's Daily data record and its `as_of`, and the units
   spent. Keep the own uploads apart, in `own-uploads.json`.

**6 — Outliers.**

1. Run `youtube-metrics: scripts/swipe.py competitors-raw.json --direction both --lang <channel
   language>`. Upward outliers are at or above 3× their channel's median
   (thresholds.md, "Outlier"); downward ones are what to avoid.
2. Join each outlier with its `velocity` record: `anomaly` spike or drop, `views_per_day`, `as_of`.
   A video without a fresh record keeps its views per day from step 4's scoring, marked as the
   views-per-age proxy.
3. Channels in `skipped_thin_channels` are listed, not ranked.
4. Write `outliers.json`: the script's output as it came, the joined flags, and the rule lines it
   used.

**7 — Title, hook and format patterns.**

1. From `outliers.json`, take the title formulas `swipe.py` named and count them; for a language
   without formulas (`unsupported-language`) read the titles yourself and say so.
2. For the top 5 upward outliers, read the transcript with `youtube-data: scripts/transcript.py --id
   <id> --lang <channel language> --format srt --out <id>.srt` and quote the first 30 seconds: that
   is the hook. An outlier without subtitles is named as such; an `en` auto-caption of a video in
   another language is a machine translation — say so.
3. Format: long or Short (duration from `videos`), length band, series or one-off.
4. Compare with the channel's own uploads (`own-uploads.json` of step 5): the topics and formats that outliers cover
   and this channel does not.
5. Write `patterns.md` with the structure of competitors' titles and hooks from
   `youtube-strategy/references/ideation.md` ("Inputs"), every claim pointing to its outlier and
   its multiple.

**8 — Competitor thumbnails.**

1. Download the thumbnails of the upward outliers and of the top 10 of each main term's SERP with
   `youtube-data: scripts/thumbnails.py --ids-file <file> --out-dir thumbs/`.
2. Measure each outlier's thumbnail with `youtube-thumbnail-check: scripts/analyze_thumbnail.py
   <image> --out-dir thumb-check/<id> --compare-dir thumbs/` (Shorts with `--kind short`). The
   comparison is colour and layout correlation with the others: it ranks, it has no "too similar"
   line.
3. Open the 120 px and 168 px previews and judge with
   `youtube-thumbnail-check/references/checklist.md` → "Judging": subject, text and emotion at feed
   size, text not repeating the title, one focal point.
4. Write `thumb-benchmark.md`: per outlier, the measurements (contrast, dominant colours, faces,
   similarity mean and top 3), the judgement with the preview it rests on, and the patterns common
   to the outliers. Claim no CTR effect: the checklist gives none.

**9 — Trend radar.**

1. Read the median of every channel ranking in step 2's SERPs with `youtube-data:
   scripts/channel_baselines.py --serp <files> --out baselines.json`. It reads public pages through
   yt-dlp and needs no token; on 429, wait and run it again with the same arguments.
2. Run `youtube-demand: scripts/niches.py --serp <files> --baselines baselines.json --as-of <run
   date>`: for each main term, this week's breakouts, spread and freshness of its top. A term whose
   openness fell since last week's `trend-radar.md` is a warning for the ideas that target it.
3. Cluster the rising queries (step 3), the outlier themes (step 6) and the patterns (step 7) into
   topics. For each topic: its signals with numbers and dates, its direction, and an urgency from
   `youtube-strategy/references/ideation.md` — flash, sustained or seasonal (with the date it must
   be out by).
4. Write `trend-radar.md`, and the list of terms step 10 must measure: every rising query kept,
   every gap term from step 7, the search term each Community question of step 1 maps to, plus
   the existing seeds each topic maps to.

**10 — Keyword research and new seeds.**

Every keyword an idea targets is measured in this run's one anchored Trends set, so the ideas of a
week are scored on one scale.

1. Labs metrics: one `keyword_overview` call for every term to measure that has no seed yet, or
   whose newest seed (in either memory) is older than 31 days (thresholds.md, "Data freshness"),
   with `youtube-demand: scripts/dfs.py`.
2. YouTube interest: Trends explore `type: youtube`, `past_12_months`, the anchor of step 1 plus 4
   terms per request, for every term an idea may target this week, with `youtube-demand:
   scripts/dfs.py`, one saved response per call.
3. Competition: one YouTube SERP per new term with `youtube-demand: scripts/dfs.py`; reuse step 2's
   SERPs for the main terms. For the authority part, read the ranking channels' subscribers with
   `youtube-data: scripts/data_api.py channels --id <comma list>`.
4. Run `youtube-demand: scripts/normalize.py --labs <files> --trends <files> --anchor <anchor>
   --serp <files> --channels <channels file> --as-of <run date> --only <term> ...`.
5. Write a `seed` with `youtube-records: scripts/records.py write seed <write_args>` for each row
   that is new, or that replaces a seed older than 31 days. A term Onboarding holds and that is
   fresh is not written again: Recon writes only into its own memory, and never rewrites
   Onboarding's record.
6. Write `keywords.json`: `anchor` (step 1's term), `trends_batches`, every row with volume, CPC, `kd_web`,
   intent, `yt_interest`, `yt_competition` and its parts, the seeds written, `errors`, `warnings`
   and the cost.

Validator rubric:
- every new `seed` record has `as_of` and `source`, and has `yt_interest` and `yt_competition`;
- every Trends request in the saved responses carries the anchor named in `keywords.json`;
- `kd_web` is on 0–100 as it came; no term is a duplicate of an existing seed under a different
  spelling;
- the DataForSEO cost summed from the responses is stated and is under the hard stop.

**11 — Idea backlog and idea status.**

1. Read `youtube-strategy/references/ideation.md` and the section of `profile:channel`'s
   `channel_type` in `youtube-strategy/references/channel-types.md` before writing an idea.
2. Draft 10–15 ideas from `trend-radar.md`, `patterns.md`, `thumb-benchmark.md`,
   `community-questions.json` and `keywords.json`. Each Community question that fits the niche is
   an idea source: a repeated viewer question is a validated need, so it is weighed for an idea
   before the rest; a question off the niche is listed, not turned into an idea. Each targets one measured keyword, sits inside the niche chosen in Onboarding,
   keeps every identity token verbatim in its title, and follows the channel type's title, hook and
   thumbnail shapes.
3. Drop an idea whose slug (`youtube-records: scripts/records.py key idea --title <title>`) or whose
   keyword and angle an earlier `idea` record of Recon holds, including a rejected one.
4. Lint each title with its thumbnail text: `youtube-metrics: scripts/title.py --title <title>
   --thumb <text> --lang <channel language>`. It ranks drafts; it predicts no CTR. Its "no number"
   check does not fit music releases.
5. Score the batch with `youtube-strategy: scripts/score_idea.py --file ideas.json`: volume,
   `yt_interest` and `yt_competition` from `keywords.json`; fit, packaging and feasibility judged
   with the anchored rubric of `ideation.md`. A veto (fit or feasibility 0) is written as `rejected`
   with its reason in `note`. A refusal names a missing input: measure it or judge it, never default
   it.
6. Write each idea with `youtube-records: scripts/records.py write idea`: `status shortlisted` for
   the week's top 3–5 by score and urgency, `new` for the rest, `rejected` for vetoes; `source` names
   what grounded it (`watch:<id>`, `trend`, `seed:<slug>`, or `community` for an idea from a viewer
   question); `note` carries traffic strategy, urgency and the one-line "why now", and for a
   Community idea the question, its count and its comment ids.
7. Move the status of the ideas in step 1's `idea-status.json`: write each one again with
   `youtube-records: scripts/records.py write idea` — the same title (so the same key), the other
   fields as the record holds them, only `status` changed (to `planned`, `published`, or back to
   `shortlisted`), and `note` extended with the `plan` or `publish` key that moved it. Recon is the one writer of `idea`;
   Planning and the creation recipes only name the idea in their own records.
8. Write `ideas.md` in the output shape of `ideation.md`, ending with the ranking table and
   the run's spend: Data API units and DataForSEO cost, summed from steps 2–10.
9. Send the owner the shortlist with `send-message`: title, score, urgency, one line each. Nothing
   here is public, so the run does not wait for an answer.

Validator rubric:
- every `idea` record has title, keyword, hook, thumbnail, format, status, source and score;
- every keyword is a measured term in `keywords.json` or an existing seed;
- every title keeps every identity token of `profile:channel` verbatim and is at most 100
  characters;
- no two ideas of the batch, and no idea and an earlier `idea` record, share a slug or the same
  keyword and angle;
- at least two traffic strategies across the batch, and every trend idea carries an urgency;
- every thumbnail concept adds to its title rather than repeating it;
- every Community question that fits the niche became an idea or is listed with the reason it did
  not, and every Community idea's `note` carries its comment ids;
- every status change in `idea-status.json` was written, forward only except `planned` →
  `shortlisted` for an idea whose only plans are dropped, and no `rejected` or `published` idea was
  moved;
- the spend is stated and inside both budgets.

## Building it: reads and schedule

- **Reads.** Declare each producer with `find-spec-template --name "<exact name>"` and
  `declare-read`: "YouTube Onboarding" (required), "YouTube Daily data", "YouTube Community",
  "YouTube Planning", and each creation recipe that publishes to the channel ("Create Music
  Release" today). A producer that does not exist yet is left out (README rule 5): build the
  recipe without that read and tell the owner which one. That producer's own brief tells the
  editor to add the `declare-read` here once it is built; until then step 1 treats it as absent.
- **Readers built earlier.** "YouTube Daily data" reads Recon's `watch` records and is built before
  Recon. After publishing Recon, find Daily data with `find-spec-template --name "YouTube Daily
  data"`, add a `declare-read` of "YouTube Recon" on it, and apply its revision.
- **Schedule.** Weekly, Monday 05:00 in the time zone of `profile:channel`'s country, with `add-spec-template-schedule`.
  Settle the project with the owner first (`list-projects`), pass `--project-id`, and read back
  `effectiveProject` before going on.

## What changed from the source brief

| Before | Now |
| --- | --- |
| `google-api-python-client` | `youtube-data` scripts over HTTPS; the token from `ai-integration oauth-token --connection YOUTUBE` inside them |
| `records.py` pinned as a file | the `youtube-records` skill on the recipe |
| `youtube` (claude-youtube), `yt-viral`, `youtube-seo-thumbnail` skills | `youtube-strategy`, `youtube-metrics` (`swipe.py`, `candidates.py`, `title.py`), `youtube-thumbnail-check` |
| `opencv-python` + `numpy` by link, `torch` for `--serp-dir` CLIP | `opencv-python-headless` from the shelf; colour and layout similarity with `--compare-dir`, no CLIP |
| scoring by views÷age, channel age and upload count | views per day against the channel's own median (`candidates.py`) |
| rising queries written straight as seeds | measured first (Labs, Trends with one anchor, SERP), then written |
| ideas scored by taste | `score_idea.py` with the anchored rubric of `ideation.md` |
| `DATAFORSEO_USERNAME` | `DATAFORSEO_LOGIN` |
| DataForSEO through MCP | `youtube-demand: scripts/dfs.py`, one saved response per call, spend summed and capped |
| reads Onboarding, Daily data and Community | also reads Community's `community-ideas.md` of the whole week, Planning's `plan` and the creation recipes' `publish` records |
| `ideas-backlog.md` | `ideas.md`, the name `youtube-strategy` and the Planning brief use |
| idea status set once | Recon moves it forward to `planned` and `published` from Planning's and the creation recipes' records |
