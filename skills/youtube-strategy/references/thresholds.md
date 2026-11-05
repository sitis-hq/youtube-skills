# Thresholds

Every number a strategy, calendar, idea or report may lean on, with where it comes from and when it
was read. Rewritten from claude-youtube (`references/*.md`, commit 84c3fa68, MIT, Copyright (c) 2025
Daniel Agrici); its numbers were checked against YouTube's own pages where such pages exist, and the
rest were kept only as labelled secondary context or dropped (list at the end).

Three kinds, and a report must say which kind it is quoting:

- **YouTube** — from a YouTube or Google page; a fact about the platform.
- **Ours** — a decision rule of this repository, with its reason. Not a claim about the algorithm.
- **Secondary** — a third-party study as cited by claude-youtube; the original was not read. Context
  for a sentence, never a pass/fail gate.

The channel's own history beats any external benchmark: compare a video with the channel's median
for the same format over its last 10–20 videos (youtube-metrics computes it) before comparing with
anybody's average.

## YouTube (read 2026-11-04)

| Fact | Number | Source |
| --- | --- | --- |
| YPP, expanded tier (fan funding, Shopping; not ad revenue) | 500 subscribers + 3 public uploads in 90 days + either 3 000 watch hours in 12 months or 3 M Shorts views in 90 days; listed countries only | Help 13429240 "Overview of the expanded YouTube Partner Programme" |
| YPP, ad revenue sharing | 1 000 subscribers + either 4 000 public long-form watch hours in 12 months or 10 M public Shorts-feed views in 90 days; Shorts-feed watch hours do not count toward the 4 000 | Help 72851, Help 13429240 |
| Shorts length | up to 3 minutes | Help 10059070 |
| Thumbnail tests | up to 3 variants; winner by watch time; ~2 weeks; no Shorts, Premieres, scheduled lives, made-for-kids, mature, private | Help 13861714 |
| Thumbnail specification | 16:9 (Shorts 9:16); up to 3840×2160; min width 640; JPG/PNG; 2 MB on mobile, 50 MB on desktop; verified account | Help 72431 |
| Metadata limits | title 100 characters, description 5 000 bytes, tags 500 characters, > 60 hashtags all ignored, chapters ≥ 3 from 0:00 and ≥ 10 s | youtube-metadata `references/metadata-rules.md` |
| Tags' weight | minimal for discovery except common misspellings | Help 146402 |
| Shorts description links | not clickable since 2023-08-31 | Tubefilter 2023-08-10 (secondary report of YouTube's announcement) |

A reported 2027 rise of the ad-revenue thresholds (8 000 hours / 20 M Shorts views, The Next Web)
is **not** on Help 13429240 as read 2026-11-04 — re-read the page before telling an owner.

## Ours

| Rule | Number | Why |
| --- | --- | --- |
| Channel size tiers | new < 1 k subscribers; growing 1 k–10 k; established 10 k–100 k; large ≥ 100 k | one scale for every report (upstream had two that disagreed); 1 k matches the YPP line |
| Outlier | ≥ 3× the channel's median views, both directions; for the same format and age band where the input allows | Paddy Galloway: an outlier is "3 or 4 times more than the average at minimum on a channel" (Creator Science podcast, 2024-09-03); vidIQ's Outlier Score also divides by the channel's own average (help article, 2026-08), 1of10 counts 10× and up. Median, not mean: one viral video moves a mean. youtube-metrics `swipe.py` and youtube-demand `niches.py` use this line |
| Niche openness | mean of three shares of a niche term's YouTube top 20: breakouts (videos ≥ 3× their channel's median, from channels under 100 k subscribers), 1 − the top three channels' share, videos published within 365 days; equal weights | what makes a niche hard is a few incumbents holding the top, an old top, and no small channel breaking through (TubeBuddy, "how to tell if a niche is too crowded", ~2026-10; YouTube's Trends tab shows "Breakout videos" for the same reason, Help 11962757). The weights are ours |
| Niche demand floor | median views of the top 20 ≥ 10 000 | ours: an open niche nobody watches is not an opportunity. Galloway reads market size from what the best in the niche get; the number is our choice |
| Traffic concentration | flag one traffic source > 60 % of views over 28 days | a channel living on one surface loses most of its views when that surface changes; a flag, not a fault |
| Trending share of a calendar | ≤ 30 % of the month's slots | trend videos decay fast; evergreen slots keep the channel's baseline (upstream's balance check) |
| Hero (tentpole) videos | counted per quarter (0–2), not as a % of output | resolves upstream's 15 % vs "1–2 a year" vs 10 % (see channel-types.md) |
| CTR comparison | against the channel's own median for the same format and traffic source | external CTR averages mix surfaces: browse CTR is structurally lower than search CTR |
| Retention curve classes | cliff: ≥ 20 points lost in the first 15 s (long-form) or most viewers gone in the first 3 s (Shorts); valley: a dip in the middle that recovers; bump: a rise (rewatch); steady decline: none of these | the names a report uses; definitions, not norms (youtube-metrics measures the curve) |
| Actions in a report | one main fix + at most two follow-ups | from youtube-agent-skill `yt-audit` ("ends in ONE fix"); upstream's "up to 5" diluted the priority |
| Idea score | 0–100 by `scripts/score_idea.py` | defined scales (ideation.md); upstream's "/40" had none |
| Shorts from a long video | 2–3 clip candidates per long-form slot when the channel runs Shorts | upstream calendar rule, kept as a planning prompt, not a requirement |
| Data freshness | seed metrics older than 31 days are re-measured before ranking | DataForSEO Labs updates keyword metrics monthly (Labs keyword_overview docs, 2026-11-04) |

## Secondary (context only)

| Claim | Source as cited by claude-youtube | Use |
| --- | --- | --- |
| Average CTR by traffic source: search 12.5 %, suggested 9.5 %, browse 3.5 %, external 2.8 % | Focus Digital, December 2025 (single agency) | only to explain why browse CTR must not be compared with search CTR |
| Channels uploading 12+ times a month grew views faster | vidIQ study of 5.08 M channels | only as "consistency matters"; cadence is set by what the channel can sustain |
| Ad rates are higher in Q4 and lowest in January | several marketing sources, no single study | qualitative: schedule monetisable topics into Q4; no percentage |

## Dropped, and why

| Upstream claim | Why dropped |
| --- | --- |
| "> 15 hashtags → all ignored" | YouTube says 60 (Help 6390658) |
| Title length optima "70–100 chars +10–14 %" and "< 50" / "< 55" | contradict each other; no checkable source; YouTube sets only the 100 limit |
| Hub/Help/Hero 70/15/15 vs Hero "1–2× a year" vs 60/30/10 | contradictory; replaced by Hub/Help split per type + Hero per quarter |
| Two size-tier scales (New…Authority, Nano…Mega) | replaced by one scale above |
| AVD "below 40 % is deprioritised", "50 % = 3× more recommended" | no source |
| "Max 3 notifications per 24 h" | not verified on a YouTube page |
| "Shorts older than 28–30 days lose distribution" | no source |
| "50+ comment replies in 2 h → 15–20 % more reach" | no source |
| CTR tiers "< 3 % fix / 4–6 / 7–10 / 10 %+", niche CTR and RPM tables, "US viewers 5–8× more valuable", "Q4 +30–60 %" | no source or a single vendor's marketing figure; RPM by niche ages within months |
| "Faces +20–30 % CTR", "chapters +4 % AVD", "AI narration −70 % retention", "+106 % from updating evergreen" | no checkable source |
| Thumbnail spec "1280×720, ≤ 2 MB" | outdated; current spec above |
| Test winners "by CTR" | YouTube judges by watch time |
| YPP expanded tier "500 / 3 / 3 000" written as the only tier | correct numbers, but incomplete — both tiers above |
