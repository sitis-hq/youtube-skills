# Brief 7 — YouTube Channel Audit

Follow [the rules of the set](README.md); this brief adds what is specific to the Channel Audit.

**Name:** `YouTube Channel Audit` · **Scope:** global recipe, run inside the channel's own project ·
**Schedule:** quarterly — cron `0 6 25 3,6,9,12 *` (06:00 on the 25th of the quarter's last month)
in the time zone of `profile:channel`'s `country`, like every scheduled recipe of the set except
Daily data; Planning runs on the 1st, so its next calendar has the audit's decision. The first run
is started by hand right after Onboarding of an existing channel · **Reads from:** "YouTube
Onboarding", "YouTube Daily data", "YouTube Planning", and each creation recipe that writes
`publish` records ("Create Music Release" is the known one).

## What it is for

Once a quarter it finds why the channel grows or does not, and decides the one thing to change. The
weekly Analytics report fixes the week's biggest problem; the audit steps back to the quarter and
asks which of four constraints binds the channel — topic, click, hold or return — and which rung of
the action ladder answers it, from repackaging to a new channel. The method, the decision table and
the ladder are in `youtube-strategy/references/channel-audit.md`; every number it uses is a row of
`youtube-strategy/references/thresholds.md`.

Its starting point is YouTube's own position: there is no channel penalty. A channel stalls when
viewers stop choosing most of its videos (Help 141805). So the audit diagnoses videos and never
explains a stall by cadence, breaks, old videos, tags or a shadow ban ("Never recommended" in
`thresholds.md`).

It is a reader. It changes nothing on the channel, takes no irreversible action and claims no
intent. Its decision goes to the recipe that owns the change: Planning (repackaging, the calendar),
the creation recipes (intro, format, length, through Planning's calendar), Onboarding steps 1–7 (a
shift of niche or a repositioning, with the owner), or the owner alone (a new channel).

**The audit period** is one window for every step: the 90 days ending 3 days before the run (the
Analytics API lags), compared with the 90 days before it (`thresholds.md`, Audit period). CTR by
traffic source covers only what the Reporting API still keeps, the last 60 days.

What it leaves behind:

- **Records:** none. No record kind has the audit as its writer; its conclusions are artifacts.
- **Artifacts:** `inputs.json`, `videos.json`, `baseline.json`, `click.json`, `hold.json`,
  `retention-<videoId>.csv`, `viewer-groups.json`, `artist-reach.json` (music-artist channels),
  `return.json`, `market.json`, `previous-decision.md`, **`audit-YYYY-QN.md`** and
  **`audit-decision.json`**. Planning, Onboarding and the next audit find them with
  `list-step-artifacts`.

## Requirements (EARS) to put into the recipe

1. WHEN the run starts THEN system MUST read `profile:channel` (Onboarding), `plan:*` (Planning, when declared) and `publish:*` (each declared creation recipe) from their writers' memory, MUST validate every record with `records.py validate`, and MUST list the records it rejected.
2. IF `profile:channel` is missing or invalid THEN system MUST stop and tell the owner that Onboarding has not run; IF any other producer has nothing THEN system MUST continue and state what that limits.
3. WHEN the baseline is built THEN system MUST group the videos by format and length band, MUST compare each video's views at 7 and at 28 days with its group's median at the same age, MUST take a spike out of the median, and MUST call a group of fewer than 5 videos too few to judge.
4. WHEN click is judged THEN system MUST ensure the combined reach job exists, MUST compare each video's CTR over its first 28 days with its group's median for the same traffic source, MUST read it from the Reporting API under the CTR scale Daily data settled and stop trusting CTR when the file contradicts that scale, MUST use the subscriptions feed as the control for topic and packaging, and MUST NOT judge on one channel-wide CTR.
5. WHEN hold is judged THEN system MUST measure the Intro (share still watching at 30 s) and the middle of each curve with `retention.py`, against the channel's typical for the same length band.
6. WHEN return is judged THEN system MUST read new, casual and regular viewers in Studio, and subscribers gained and lost from the Analytics API, and MUST write "no data" for what Studio does not show.
7. WHEN the channel's type is `music-artist` THEN system MUST judge it at the song level across the official channel and other channels (Analytics for Artists), and MUST NOT apply talk-channel duration or Intro norms to music videos.
8. WHEN the market is read THEN system MUST re-rank the channel's niche terms with `niches.py` and compare openness and demand with Onboarding's numbers.
9. WHEN a previous audit exists THEN system MUST judge its decision on the metric and date it set before looking for a new constraint, and MUST NOT stack a new change on a decision that has not had its uploads yet.
10. WHEN the decision is made THEN system MUST name exactly one row of the decision table and one rung of the action ladder, the videos it concerns, the metric to judge it and when, at most two follow-ups, a number with source and date for every claim, and the rows it could not test.
11. WHEN the decision is a rung above 5 (repositioning or a new channel) THEN system MUST show that the same cause holds over 10 or more videos, and MUST leave the choice to the owner.
12. WHEN anything is recommended THEN system MUST NOT recommend an item of `thresholds.md`'s "Never recommended".
13. WHEN the audit ends THEN system MUST change nothing on the channel other than creating a missing Reporting API job, take no irreversible action and claim no intent, and MUST send the owner the decision with where it goes next.
14. WHEN the owner answers THEN system MUST record the answer as accepted, declined or changed, with the date and the quarter, so that readers act only on an accepted decision of the newest audit.

## Steps

The "Skills" column lists skills from the shelf, attached to that step. `youtube-records` is
attached to the recipe, as rule 2 says.

| # | Step | Who | Skills and tools on the step | Credentials | Writes |
| --- | --- | --- | --- | --- | --- |
| 1 | Inputs from the other recipes | AI | — (`youtube-records` on the recipe) | — | `inputs.json` |
| 2 | Videos and baseline | AI (scripts) | `youtube-data`, `youtube-metrics`, `youtube-strategy`, `yt-dlp` | `YOUTUBE_REFRESH_TOKEN` | `videos.json`, `baseline.json` |
| 3 | Click by traffic source | AI (scripts) | `youtube-data`, `youtube-strategy` | `YOUTUBE_REFRESH_TOKEN` | `click.json` |
| 4 | Hold | AI (scripts) | `youtube-data`, `youtube-metrics`, `youtube-strategy` | `YOUTUBE_REFRESH_TOKEN` | `retention-<videoId>.csv`, `hold.json` |
| 5 | Return and viewer groups | AI (script + browser) | `youtube-data`, `youtube-studio` | `YOUTUBE_REFRESH_TOKEN`, `YT_STUDIO_SESSION` | `viewer-groups.json`, `artist-reach.json`, `return.json` |
| 6 | The niche's market now | AI (scripts) | `youtube-demand`, `youtube-data`, `yt-dlp`, `dataforseo-mcp-server` | `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD` | `market.json` |
| 7 | The previous decision | AI | `youtube-strategy` | — | `previous-decision.md` |
| 8 | Diagnosis and decision | AI | `youtube-strategy` | — | `audit-YYYY-QN.md`, `audit-decision.json` |
| 9 | Owner review | AI + owner | — | — | the owner's answer in `audit-decision.json` |

Order: 1 first; 2 after it; 3, 4, 5 and 6 after 2 (they can run in parallel); 7 after 1; 8 after
2–7; 9 after 8.

## Design notes per step

**1 — Inputs from the other recipes.**

The recipe is built with a `declare-read` for each producer, found with `find-spec-template --name`
by its exact name: "YouTube Onboarding", "YouTube Daily data", "YouTube Planning", and each
creation recipe that exists at build time. The audit is built after all of them, so every producer
exists; a creation recipe added later declares itself here (README rule 5).

1. Take each producer's id from the run context. Read with `query-template-records --spec-template-id
   <producer>` by key prefix: `profile:channel` from Onboarding, `plan:` from Planning, `publish:`
   from each creation recipe. Up to 500 a request; page on.
2. Check every record with `youtube-records: scripts/records.py validate --key <key> --data
   '<json>'`. A record that fails is left out and listed. A record whose `v` is not 1 stops the
   step: report it, do not guess its fields.
3. No `profile:channel`, or an invalid one → stop the run and tell the owner that YouTube Onboarding
   has to run first.
4. Download with `list-step-artifacts --spec-template-id <producer> --step-name "<step>"`, then
   `s3 download`:
   - from Onboarding: `niche-decision.md` ("Niche selection"), `niche-candidates.json` and, for an
     existing channel, `channel-history.json` ("Niche discovery"), `format-plan.md` ("Formats and
     content pillars");
   - from Daily data: the newest `ctr-scale-check.md` with a conclusion ("Impressions and CTR",
     `--limit 30`) — the settled CTR scale step 3 uses; none → "CTR scale not settled";
   - from this recipe: the newest `audit-decision.json` and `audit-*.md` ("Diagnosis and
     decision", and the owner's answer from "Owner review"). None → "first audit".
   A file that is not found goes under `missing`; the step does not guess a substitute.
5. Write `inputs.json`: the channel, the audit period and the period before it (dates), the
   producers, what was read, what is missing and what that limits.

**2 — Videos and baseline.**

1. List every public upload with `youtube-data: scripts/data_api.py uploads --mine --with-stats
   --max 1000`: id, date, duration, title, views.
2. Tell Shorts apart: the Data API has no orientation. Read the Shorts tab with `youtube-data:
   scripts/channel_baselines.py --channel-id <id> --tab shorts --max-videos 1000 --videos-out
   shorts.json --out shorts-baseline.json`; a video on it is a Short. A `publish` record's format
   wins where one exists.
3. For each video old enough, read views at 7 and at 28 days with `youtube-data:
   scripts/analytics.py video-metrics --id <id> --start <published> --end <published + 6 or + 27
   days>`. A video younger than 28 days has its 7-day number only.
4. Group by format and length band (`channel-audit.md`, Baseline). Rank each group's 28-day views
   with `youtube-metrics: scripts/swipe.py --direction both`. swipe takes the median per
   `channel_id`, so write each row with its group key as `channel_id` (and `channel`), never the
   channel's own id: otherwise every group shares one median. Do the same for the 7-day views.
5. A spike (`thresholds.md`, Spike) is taken out of its group's median and named.
6. Write `videos.json` (every video with its group, ages, numbers) and `baseline.json` (each
   group's medians, outliers both ways, spikes, groups too few to judge).

**3 — Click by traffic source.**

1. Run `youtube-data: scripts/reporting.py ensure-job` first. Onboarding creates both reach jobs
   at connection, but a channel connected before the combined job existed has only the basic one;
   this read is the audit's, so the audit makes sure of it. A job created now has data in about 48
   hours: write "CTR by source: no data this quarter, the job was created today" and tell the owner.
2. Read impressions and CTR per video and traffic source over each video's first 28 days with
   `youtube-data: scripts/reporting.py sources --ctr-scale <settled> --published videos.json
   --first-days 28`. A row marked `partial` began before the reports the API still keeps: name it,
   and compare it only with other partial rows or leave it out. Not settled → `--ctr-scale
   unknown`: impressions only, and "CTR: no data, scale not settled". A `scale_warning`, or a
   refusal under the settled scale, means the file contradicts the scale: write "CTR: no data, the
   file contradicts the settled scale", keep impressions, and tell the owner.
3. Name the subscriptions feed: among the "browse features: <detail>" rows, the detail that is the
   subscriptions feed. Write which value it was and why; if none can be told apart, write "no
   subscriptions split" and use browse features as a whole, saying so.
4. Read views per traffic source per video over 28 days with `youtube-data: scripts/analytics.py
   traffic --id <id>`.
5. For each group of step 2 and each traffic source, take the median CTR; mark each video above or
   below it. The 2–10 % band of `thresholds.md` is a sanity bound only, never a target.
6. Write `click.json`: the period, the scale, the subscriptions detail, per video and source the
   impressions, CTR and its ratio to the group median, and the rows with too few impressions to read
   (`thresholds.md`, Too few impressions to read CTR).

**4 — Hold.**

1. For each long video of the audit period, and the 10 before them in the same length band, write the
   curve of its first 28 days with `youtube-data: scripts/analytics.py retention --id <id>
   --start <published> --end <published + 27 days> --duration <s> --csv retention-<videoId>.csv`.
   Keep its `relative_retention_mean` too: YouTube's own comparison with videos of similar length.
2. Measure it with `youtube-metrics: scripts/retention.py retention-<videoId>.csv --axis percent
   --duration <s>`: `intro_30s` (Studio's Intro), `slide`, `cliffs`.
3. The typical of a band is the median `intro_30s` and `slide` of its last 10 videos. Mark each
   video of the period above or below it. An `intro_30s` that is null (its `intro_note` says why)
   is left out of the median.
4. Shorts: measure their curves too, but judge them only with other Shorts; a Short of 30 s or less
   has no Intro (`intro_30s` is null).
5. Music videos of a `music-artist` channel are compared only with the channel's own music videos.
6. Write `hold.json`.

**5 — Return and viewer groups.**

1. Subscribers gained and lost per month over the last six full months: `youtube-data:
   scripts/analytics.py channel --by month --start <first day of the month six months back> --end
   <last day of the last full month>`. The month dimension needs whole months.
2. Viewer groups in Studio, following `youtube-studio/references/viewer-groups.md`, after the
   session check (rule 8): `viewer-groups.json`.
3. A `music-artist` channel: Analytics for Artists by the same reference, `artist-reach.json`. A
   channel without the toggle is judged on its own uploads, and the file says so.
4. Write `return.json`: gained, lost, net per month; the viewer groups and their change; for music,
   song-level reach. What Studio did not show is "no data", never an estimate.

**6 — The niche's market now.**

1. Take the niche's terms from Onboarding's `niche-decision.md` (the chosen niche and the terms of
   `niche-candidates.json` merged into it).
2. Get one YouTube SERP per term with `youtube-demand: scripts/dfs.py`, one response file per call,
   in the profile's language and region.
3. Read the ranking channels' normal with `youtube-data: scripts/channel_baselines.py --serp …`.
4. Rank with `youtube-demand: scripts/niches.py --baselines …`.
5. Write `market.json`: openness and its three parts, and demand, for each term now and as
   Onboarding measured them, with both dates.

**7 — The previous decision.**

No previous audit → write "first audit" and stop the step. Otherwise read its
`audit-decision.json` and the owner's answer:

- the owner declined → "declined", nothing to judge;
- its date to judge has not come, or the uploads it needs are not published yet → "not judged
  yet", with how many are missing. Step 8 then keeps it and does not start a new change;
- otherwise judge it on its own metric, from steps 2–5: worked, failed, or unclear, with the
  numbers.

Write `previous-decision.md`.

**8 — Diagnosis and decision.**

Follow `youtube-strategy/references/channel-audit.md` from top to bottom:

1. Walk the four constraints in order — topic, click, hold, return — with the evidence of steps
   2–6. The first that fails binds; the later ones are reported, not acted on.
2. Match the evidence to one row of the decision table, and pick the lowest rung of the ladder that
   answers it. A rung above 5 needs the same cause over 10 or more videos; cite them.
3. A previous decision "not judged yet" stays the decision: this audit reports, and adds no new
   change.
4. Write `audit-YYYY-QN.md` with the reference's output template, and `audit-decision.json`:

```json
{"quarter": "2026-Q4", "row": 1, "cause": "…", "action": "…", "rung": 1,
 "routes_to": "planning | creation | onboarding | owner",
 "videos": ["<videoId>"],
 "judge_on": "…", "judge_after": {"uploads": 5, "not_before": "YYYY-MM-DD"},
 "follow_ups": ["…"], "previous": "worked | failed | unclear | not judged yet | declined | first audit",
 "owner_answer": null}
```

`routes_to`: rung 1 → `planning` (its repackaging and A/B steps, on the videos in `videos`);
rungs 2–3 → `creation`, through Planning's calendar; rungs 4–6 → `onboarding` (steps 1–7 re-run
with this audit as input, so the niche is measured anew and `profile:channel` changes); rung 7 →
`owner`, who starts a new project and its own Onboarding. `videos` names the videos the decision
concerns (the ones to repackage, or the evidence of the cause); it may be empty for rungs 4–7.

Validator rubric:
- exactly one row and one rung, with `videos`, `judge_on` and `judge_after`;
- every claim carries a number with source and date, or says "no data";
- no comparison crosses format or length groups; no channel-wide CTR;
- nothing from `thresholds.md`'s "Never recommended";
- a rung above 5 cites 10 or more videos with the same cause;
- the rows that could not be tested are listed;
- a previous decision "not judged yet" is kept, not replaced.

**9 — Owner review.**

Send the owner the decision in plain words with `send-message`: the cause in one sentence, the
evidence in three numbers, the action, how and when it will be judged, and where it goes next.
Buttons: "Accept" (recommended), "Decline" and "Discuss". Then `await-reply`.

- Accepted, `routes_to` `planning` or `creation` → Planning picks it up on the 1st; say so.
- Accepted, `onboarding` → ask the owner to re-run steps 1–7 of the channel's YouTube Onboarding;
  those steps read this audit.
- Accepted, `owner` (a new channel) → the owner starts it; this channel goes on with the follow-ups.
- Declined → record it; nothing is routed.
- "Discuss" → answer from the evidence; if the decision changes, rewrite it with the same quarter and
  ask again.

Write the final `audit-decision.json` with `owner_answer`: `{"answer": "accepted" | "declined" |
"changed", "date": "YYYY-MM-DD"}` ("changed" = accepted after a change made in "Discuss"). Readers
act on a decision only when its `owner_answer.answer` is `accepted` or `changed` and its `quarter`
is the newest audit's; an older quarter's decision is never acted on again.

## Building it: reads, keys and schedule

1. **Declare the producers.** Find each with `find-spec-template --name "<exact name>"` and
   declare it with `declare-read`: "YouTube Onboarding", "YouTube Daily data", "YouTube Planning",
   and "Create Music Release". Ask the owner whether any other creation recipe publishes to this
   channel, and declare each one they name.
2. **Wire the audit into its readers.** "YouTube Planning" applies the audit's decision and
   "YouTube Onboarding" re-runs steps 1–7 with it; both were built before it. For each:
   - find the reader with `find-spec-template --name`;
   - run `declare-read --spec-template-id <reader> --producer-spec-template-id <YouTube Channel
     Audit>`;
   - apply that reader's revision.
3. **Keys.** Declare on each step exactly the keys of its row above.
   Step 3 runs `reporting.py ensure-job`, the one write of the recipe; tell the owner at build time.
4. **Schedule.** Settle the project with the owner, then run `add-spec-template-schedule` with cron
   `0 6 25 3,6,9,12 *` in the time zone of `profile:channel`'s `country` (for a country with several
   zones, the one the owner names). Read back the schedule's zone and next fire time and confirm
   them to the owner.
5. **First run.** For an existing channel, tell the owner to start the first run by hand now,
   without waiting for the quarter.
