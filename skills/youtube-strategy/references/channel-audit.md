# Channel audit

How to find why a channel is not growing and pick the one thing to change. Used by the quarterly
"YouTube Channel Audit" recipe, and in part by Onboarding when the channel already exists ("Using a
channel's history" below). Every number here is a row of `thresholds.md`; this page says how to use
them.

Built from the stalled-channel research of 2026-11-23, which reads YouTube's own position (YouTube
Help, Creator Insider, Rene Ritchie, Todd Beaupré) and the published methods of Paddy Galloway,
1of10 and vidIQ. Its main finding: there is no channel penalty to hunt for. Recommendations are
matched per video and per viewer, and a channel stalls when viewers stop choosing most of its
videos (Help 141805). So the audit diagnoses videos — click, hold, topic demand, audience fit —
and never explains a stall by cadence, breaks, old videos, tags or a shadow ban ("Never
recommended" in `thresholds.md`).

## Inputs

| What | Where from |
| --- | --- |
| Every public video: id, date, format (long or Short), length, title, views | youtube-data `data_api.py` (connected channel) or `channel_baselines.py` (any channel, yt-dlp) |
| Views, watch time, average view duration and percentage, subscribers gained and lost, per video and period | youtube-data `analytics.py video-metrics` |
| Views by traffic source, per video | `analytics.py traffic --id` |
| Retention curve and the Intro (share watching at 30 s) | `analytics.py retention`, then youtube-metrics `retention.py --duration` (`intro_30s`) |
| Impressions and CTR per video and traffic source, the last 60 days at most | `reporting.py sources --ctr-scale <settled>`; the subscriptions feed is a "browse features" detail |
| New, casual and regular viewers, "Popular with different audiences" | Studio only (youtube-studio); not in the APIs |
| What the channel was meant to be | `profile:channel`, Onboarding's `niche-decision.md`, `format-plan.md` |
| What was planned and published since the last audit | `plan` and `publish` records |
| The previous audit's decision and its test | the previous `audit-YYYY-QN.md` |
| The niche's market now | youtube-demand `niches.py` on the channel's niche terms (openness, demand, freshness) |

A number the channel cannot give (no CTR scale settled, Studio not signed in, fewer than 5 videos of
a format) is written as "no data" with the reason. The audit still decides on what it has, and says
which rows of the table it could not test.

## 1. Baseline

1. Split the videos by format (long, Short) and, for long videos, by length band (`thresholds.md`,
   Length bands). Every comparison stays inside one group.
2. For each video take views at 7 and at 28 days (Analytics by date range from the publish date).
   The group's median at the same age is the baseline; a video's ratio to it is its score. An
   outlier is a score of 3 or more, or 1/3 or less (`thresholds.md`, Outlier).
3. A viral spike is not the baseline: a video at 10× or more of its group's median (`thresholds.md`,
   Spike) is left out of the median, and its traffic is read as "viewers who may not return" (Help
   141805).
4. A group of fewer than 5 videos is "too few to judge" (`thresholds.md`). When every group is, the
   decision is not a fix: a young channel needs a "critical mass of content" (Help 16559651) — one
   topic, a growing library, judged at the next audit.
5. A window that crosses a change in how views are counted (`thresholds.md`, Secondary) is named;
   Shorts are compared on engaged views where the data gives them.

## 2. The four constraints, in this order

Galloway's published order is ideas and packaging first, then retention (Creator Science 2023); the
research's synthesis adds returning viewers last. The first constraint that fails is the binding
one; later ones are reported, not acted on.

1. **Topic** — is there demand, and does this audience want it? Market: `niches.py` demand and
   openness of the channel's terms now against Onboarding's numbers. Fit: the subscriptions-feed
   CTR and views of each topic cluster against the channel's median.
2. **Click** — impressions are there, CTR is not. CTR per video against the group's median for the
   same traffic source, never one channel-wide CTR. The 2–10 % band is a sanity bound only. A Short
   has no thumbnail click: its click is "Stayed to watch" and its reach "Shown in feed", both from
   Studio, against the channel's own Shorts. A Short's first hundreds or thousands of views are a
   test (Ritchie, 2024-04-04): one that stalls there lost in the feed, it was not suppressed.
3. **Hold** — the Intro against the channel's typical for the same length band; then the middle of
   the curve (`slide`, `cliffs`).
4. **Return** — casual and regular viewers, and subscribers lost against gained.

## 3. Decision table

Signal pattern → likely cause → first action → how and when to judge. Rows follow the research's
table; the judging counts are `thresholds.md` rows.

| # | Signal pattern | Likely cause | First action | Judge on, and when |
| --- | --- | --- | --- | --- |
| 1 | impressions normal; CTR below the median for the same source and age; Intro and duration normal | packaging fails the click | Test & Compare three title/thumbnail packages on recent and evergreen videos | watch-time share winner, up to 2 weeks per test |
| 2 | CTR normal or high; Intro low; a cliff before 0:30 | the opening breaks the promise, or is slow | rewrite the first 30 s to deliver what the packaging promised; with high CTR, tone the packaging down | Intro of 5 uploads against the last 10 of the band |
| 3 | Intro fine; the middle decays steadily | format or length does not fit | change structure or length toward the niche's breakouts and the device mix | duration and watch time per impression against the median, 5 uploads |
| 4 | low impressions everywhere; CTR and hold normal; the niche's top is small too, or its demand fell since Onboarding | low or falling topic demand | move to an adjacent, evergreen topic with demand (Onboarding re-run) | 28-day views against the median, 15 uploads |
| 5 | new-topic videos fail on the subscriptions feed and browse; the same topic does well for others | the audience does not want this topic | seed the topic inside proven formats; a fundamentally different audience → a separate channel | subscriptions-feed CTR and views, 15 uploads |
| 6 | high variance; one cluster beats the median, others trail; few casual and regular viewers | scattered topics | narrow to the 1–3 clusters that work (`thresholds.md`, Topic that worked) | outlier rate and the casual and regular share, 15 uploads |
| 7 | per-video 7- and 28-day views stable; total views down after fewer uploads | fewer chances, not a penalty | restore the output the channel can sustain; expect a warm-up | total views over the following weeks; per-video median unchanged |
| 8 | subscribers come from Shorts; long-form returning viewers flat; Shorts topics differ from long-form | the Shorts audience is not the long-form audience | align Shorts topics with long-form; set the related video | long-form returning viewers before and after, the next audit |
| 9 | a clip or re-upload Shorts channel; Shorts reach fell from October 2026 | the originality reduction | add original commentary or editing; stop unoriginal re-uploads | Shorts-feed reach; no published timeline |
| 10 | the niche's top held by a few channels, old, few small-channel breakouts | a concentrated niche | an unsaturated angle, or a smaller adjacent niche | outlier rate, 15 uploads |
| 11 | subscribers lost and returning viewers step-changed on the date of a topic change | the pivot lost a topic-loyal audience | same audience → persist with evergreen bridge videos; different audience → a new channel | pre-set metrics, 15 uploads |
| 12 | strong search, weak browse, or the reverse | the surfaces want different packaging | package for the surface the video lives on (search: literal; browse: curiosity) | CTR and hold per traffic source |
| 13 | a sharp drop after a viral spike | back to the pre-spike baseline — not a stall | re-baseline without the spike; give the spike's viewers a follow-up | the pre-spike median |
| 14 | "shadow ban" suspected; recommendations still the main source | normal variance | run rows 1–6 | the traffic-source mix |
| 15 | the own uploads look flat, but the channel's type measures reach elsewhere (its "Measure" line in `channel-types.md`) and that reach grows | not a stall: the measure was wrong | judge on the type's measure | the type's measure, the next audit |
| 16 | views come only around the channel's own events (releases, launches, seasons) and fall to nothing between them | output tied to events only | the type's playbook for between the events (`channel-types.md`); keep the formats that need no event | views and returning viewers between events |
| 17 | Shorts: "Shown in feed" near zero | the Short did not enter the feed | check its format (a 16:9 video is long-form) and the Restrictions column: a Short over one minute with a Content ID claim is blocked worldwide (Help 15424877) | Shown in feed of the next Shorts |
| 18 | Shorts: shown in the feed, "Stayed to watch" below the channel's Shorts median | the first frame and seconds do not hold | change the hook and the first frame; never re-upload the same file (`thresholds.md`) | Stayed to watch against the median, 5 Shorts |
| 19 | after a change of topic, old off-topic videos still get impressions and bring viewers who do not watch the new videos ("Popular with different audiences", traffic to old videos) | the old catalogue pulls recommendations to the old topic | unlist those videos, one by one, never delete; not when the channel is near a YPP threshold (hidden videos stop counting) | the new videos' impressions and CTR, the 4 weeks before against the 4 after |
| 20 | two or more videos on one subject open the same way — same first seconds, same visual, often the same thumbnail (clips of one long video, versions of one release, one template reused) | one hook tested twice; the later one is swiped or skipped by viewers who saw the first; release after release it reads as the repetitive content the monetisation policy excludes (Help 1311392) | give each its own opening and visual, keep the subject; alternate which one goes first; never delete either | pairs compared on Stayed to watch (Shorts) or CTR and Intro (long), and subscribers, 4 pairs at least |

## 4. The action ladder

Cheapest and least destructive first; each step costs more history than the one before. No source
publishes this order as a rule — it is the research's synthesis, consistent with Galloway's
packaging-before-content priority.

1. repackage existing videos → 2. fix the first 30 seconds → 3. change format or length → 4. narrow
the niche → 5. shift to an adjacent niche → 6. reposition the same channel → 7. start a new channel.

- Hiding videos is not a rung: it is row 19 only, after a change of topic, with its evidence.
- Never skip a rung without the row that justifies it. Steps 6 and 7 only when the same cause (rows
  4, 5, 10 or 11) holds over 10 or more videos (`thresholds.md`, destructive step gate).
- Same audience → same channel; different audience → different channel (Ritchie, 2026-02-16).
- A shift is seeded, not "full sent": the new direction enters scripts, concepts and thumbnails of
  evergreen videos, so discovery has time to find its audience (Monahan, 2026-09-18).
- A repositioned channel's numbers look like a new channel's for a while, with "fell off" comments;
  that is expected, not a verdict. Judge on the metrics written before the change.
- Rungs 4–6 go back to Onboarding: its steps 1–7 are re-run with the audit as their input, so the
  candidates are measured anew and `profile:channel` carries the new niche. Rung 7, a new channel,
  is the owner's to start: a new project and its own Onboarding.

## 5. The channel's type

The method above is the same for every channel. What differs by type lives in
`channel-types.md`, under the type `profile:channel` names, and the audit reads that entry:

- **Measure** — where the type's reach is counted, when it is not only the own uploads' views (rows
  15–16). A type without the line is measured by the steps above alone.
- **Fails when** — the type's known failures. Each one is checked as one more hypothesis, with the
  same evidence rules as a row of the table, and named in the decision when it binds.
- Comparisons stay inside the type's own formats: duration and Intro norms of one format are not
  applied to another.

A type's entry never changes the order of the constraints or the ladder.

## 6. The previous audit

The audit starts from the last one: its decision, its metric and its date to judge. If that date has
passed, judge it first — worked, failed, or not enough uploads yet — and only then look for the next
constraint. A decision that has not had its uploads yet stays; the audit does not stack a second
change on top of an untested one.

## Using a channel's history (Onboarding, existing channel)

Onboarding researches the niche for an existing channel the same way as for a new one. The
channel's public history is one more input to that research, not a setting to keep:

- Outliers by the channel's own median (`channel_baselines.py` on the channel itself) name topics,
  formats and packaging that already worked; a cluster counts by `thresholds.md`'s "Topic that
  worked".
- Those clusters enter the candidate list next to the market's candidates, and are ranked by the same
  openness and demand.
- History is discarded when its outliers came from a topic whose demand has since fallen, from a
  viral spike, from Shorts that never converted, or from too few videos (fewer than 5 of a format).
- Same audience as the chosen niche → keep the channel; a different audience → the owner is told
  that YouTube's own advice is a new channel, and decides.

## Output: `audit-YYYY-QN.md`

```markdown
# Channel audit <quarter> — <channel>

## Previous decision
<what it was, its metric, worked | failed | unclear | not judged yet (why) | declined>

## Baseline
<groups, medians at 7 and 28 days, outliers, spikes excluded, groups too small>

## Constraints
| Constraint | Evidence (numbers, source, date) | Holds? |
| Topic | … | yes / no / no data |
| Click | … | … |
| Hold | … | … |
| Return | … | … |

## Decision
Row <n> of the decision table. Action: <one>. Rung <n> of the ladder.
Judge on: <metric>, after <uploads / date>.
Follow-ups (at most two): …

## Not tested
<rows that needed data the channel could not give, and why>
```

## Quality bar

- One decision, tied to one row of the table and one rung of the ladder, with its metric and its
  date to judge. At most two follow-ups.
- Every number has its source and date; every external number is a `thresholds.md` row.
- No item from "Never recommended".
- Comparisons stay inside a format and length group; no channel-wide CTR.
- A rung above 5 cites the 10-video gate it passed.
- What could not be tested is listed, not guessed.
