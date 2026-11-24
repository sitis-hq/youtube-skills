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
| Title tests (Test & Compare) | titles, thumbnails or both, up to 3 variants, up to 2 weeks, winner by watch-time share, may end "inconclusive"; global for channels with advanced features since December 2025 | Help 16391400 via Search Engine Journal, 2025-12 (read 2026-11-23) |
| Thumbnail specification | 16:9 (Shorts 9:16); up to 3840×2160; min width 640; JPG/PNG; 2 MB on mobile, 50 MB on desktop; verified account | Help 72431 |
| Metadata limits | title 100 characters, description 5 000 bytes, tags 500 characters, > 60 hashtags all ignored, chapters ≥ 3 from 0:00 and ≥ 10 s | youtube-metadata `references/metadata-rules.md` |
| Tags' weight | minimal for discovery except common misspellings | Help 146402 |
| Shorts description links | not clickable since 2023-08-31 | Tubefilter 2023-08-10 (secondary report of YouTube's announcement) |

## YouTube, for diagnosing a channel (read 2026-11-23)

From the stalled-channel research of 2026-11-23 (sources as it cites them; "via" = a YouTube
statement known through a write-up). `channel-audit.md` builds on these rows.

| Fact | Number or statement | Source |
| --- | --- | --- |
| Impressions CTR spread | half of all channels and videos have impressions CTR between 2 % and 10 %; CTR varies by content, audience and where the impression was shown | Help 7628154 |
| Intro key moment | the percentage of viewers still watching after the first 30 seconds; a high one means the opening "matched the viewer's expectation of the video's thumbnail and title" | Help 9314415 |
| Viewer groups | casual = watched in 1–5 of the last 12 months; regular = 6 or more of the last 12 | YouTube (Creator Insider) via Search Engine Journal and Social Media Today, 2025-07 |
| Viewer groups and reach | the groups do not affect reach or monetisation; returning viewers make recommending later videos more likely | Help 10246996 |
| Breaks and cadence | "no correlation between break length and changes in views"; growth in views across uploads "not correlated with time between uploads"; it "may take some time to 'warm up' your audience again" | Help 141805 |
| One weak video | does not hurt the channel; views fall "when viewers stop watching most of your videos when they're recommended to them" | Help 141805 |
| Unlisted, then public | does not hurt: "what matters is how viewers respond after it's been published" | Help 141805 |
| Monetisation and reach | the system "doesn't know which videos are monetizing" | Help 141805 |
| A video's life | evergreen videos can get most of their views "a month or more after publishing"; the first hour does not decide | Todd Beaupré, Creator Insider 2026-09-01, via Founder Presence 2026-11-19 |
| Subscriptions as control | the subscriptions feed is the most consistent audience from upload to upload: a video that fails even there points at its topic and title | same |
| Judging a pivot | not on its first 3 videos, "or even its first ten"; set success metrics and a timeline first | Kyle Monahan, Creator Insider 2026-09-18, via Vanpelt Studio 2026-09-24 |
| Pivot or new channel | "if it's for the same audience, at least try it on the same channel. If it's for a different audience, try it on a different channel"; a pivot is "essentially starting a new channel with maybe a boost" | Rene Ritchie, TubeTalk 2026-02-16 |
| Unoriginal Shorts | from 2026-10-01 the Shorts feed reduces the reach of re-uploads that add nothing of the uploader's own; channels primarily aggregating get less distribution | TeamYouTube, "Prioritizing original content on Shorts", Help Community 2026-10-01 |
| Shorts and long-form | ranked by separate systems; "we haven't seen evidence of Shorts negatively impacting long-form performance" | The YouTube Team, "Shorts truths", blog.youtube 2025-05-06 |
| Artist reach | Analytics for Artists separates "Official Artist Channel" (Art Tracks included) from "Other Channels" (fan videos whose main component is the song) | Help 18736729 |
| Reach reports | the Reporting API keeps reports 60 days (historical ones 30); a new job gets the 30 days before its creation | developers.google.com/youtube/reporting (read 2026-11-23) |

Added from the research on deleting and hiding videos (2026-11-24; quotes as it gives them):

| Fact | Number or statement | Source |
| --- | --- | --- |
| Per-video judgement | "An individual video's underperformance does not penalize a channel overall"; what can hurt is a viewer repeatedly not watching the channel's videos when they are recommended; experimenting with formats "will not inherently confuse the algorithm"; a new channel needs a "critical mass of content" for viewers to watch next | Help 16559651 "Good to know about recommendations" |
| Shorts' first views | the first hundreds or thousands of views of a Short are a test, "initial views are basically impressions"; a Short that loses in the feed goes no further | Rene Ritchie, "Rene's Top Five", blog.youtube 2024-04-04 |
| Shorts' click | in the Shorts feed the click is "Stayed to watch" (viewed vs swiped away), which Ritchie called the Shorts analogue of CTR; "Shown in feed" = "the number of times that your Shorts showed in the Shorts Feed". No published threshold | Ritchie, same; Help 12942217 "Content tab analytics tips" |
| Shorts viewers and long-form | the system links a viewer's interests across formats, but moving from Shorts to long-form "is not common behavior from viewers" | Help 16559651 |
| Deleting and hiding | Todd Beaupré: "Don't delete videos unless you have a very, very good reason … keep your videos public or unlist them if you must"; deleting removes the channel's connection with that video's viewers. Ritchie: think three times before deleting, privating or unlisting "purely because you think it'll change your channel's performance" | blog.youtube "Rene's Top Five", 2024-03-28 |
| What hiding does | private and unlisted videos leave the channel's Videos tab, search, recommendations and the subscriptions feed; unlisted can still sit in a channel section and play by link | Help 157177 |
| Re-uploading own Shorts | re-uploading or re-using Shorts to pull more views "could be seen by the system as spam/abusive behavior"; make a better version instead | YouTube Liaison on X, 2023-08-09 (pre-2024) |

Added from the research on two Shorts of one release (2026-11-24; quotes as it gives them):

| Fact | Number or statement | Source |
| --- | --- | --- |
| Many Shorts for a song | "Make Many Different Shorts for a Song. The more a fan hears your song in Shorts, the more likely they are to listen to your song in other formats"; "Channel size or number of uploads do not influence how your Shorts perform"; "Try posting weekly and then re-adjust your posting schedule based on your Shorts' performance" | artists.youtube "Shorts for Artists" |
| One audio snippet before release | use the same audio snippet in all pre-release content, so the Shorts gather on one sound page: the sound may repeat, the video may not | artists.youtube "Pre-Release Strategy" |
| Each Short is tested on its own | a Short is shown to a seed audience, then "may get a lot more traffic or it may kind of taper off"; no ideal length ("to what length do you need to tell your story?"); "most thumbnails are never seen because people are in the feed" | Todd Sherman, Creator Insider 2023-08-23 (pre-2024), via OutlierKit 2026-10-03 |
| Shorts over one minute with Content ID | "Any Short that is over one minute in duration with an active Content ID claim of any type, including manual claims, will be blocked globally"; an artist's own distributor or label can create the claim. A reported relaxation from 2026-09-24 is not on the page as read 2026-11-24 | Help 15424877 "Understand three-minute YouTube Shorts" |
| Repetitive content and monetisation | content that "may feel repetitive to viewers after watching several videos in a row from the same channel" is not monetised; each video's substance "should be materially varied"; reviewers look at the newest and most viewed videos and their metadata, thumbnails included | Help 1311392 "YouTube channel monetization policies" ("Generic or Repetitive Content") |

## Never recommended

YouTube refutes these, so no report, audit or plan offers them as a growth lever. A step that is
about to write one of them stops and says which row forbids it.

| Do not recommend | Why |
| --- | --- |
| Upload more often, or daily, to grow | cadence is not correlated with growth (Help 141805). Restoring output after a drop is different: fewer uploads are fewer chances, not a penalty — the audit's "volume" row |
| Delete old videos; hide weak ones to lift the channel | a weak video does not hurt the channel (Help 141805, 16559651); Beaupré: don't delete, keep public or unlist "if you must" (2024-03-28); hidden videos stop counting for YPP. The one exception is targeted unlisting of off-topic videos that still bring an audience the new videos do not keep — `channel-audit.md`, row 19 |
| Re-upload the same video or Short for more views | YouTube Liaison: it "could be seen by the system as spam/abusive behavior" (2023-08-09); a new version of the idea is not a re-upload |
| Tags as a discovery lever | "not important" except misspellings (Help 141805, 146402) |
| A shadow ban as the explanation | Ritchie: channels claiming one still get most traffic from recommendations (TubeTalk 2026-02-16); the one real per-channel reduction is unoriginal Shorts, above |
| Re-uploading or publishing in a set hour for reach | publish time does not affect a video's long-term performance except Live and Premieres (Help 141805) |

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
| Stale `velocity` | its `as_of` more than 2 days before the run | Daily data runs daily; two missed runs mean the rate no longer describes the video. Every reader uses this row |
| Stale `studio` | its `as_of` more than 4 days before the run | a `studio` record describes the run date − 2 by design (Reporting API and Studio lag two days), so 4 days is two missed runs |
| Plan slot dropped | no `publish` 14 days after the slot's date; a later `publish` reopens it as published | a release can slip a week or two without being abandoned; Planning re-checks dropped slots of the last 60 days |
| Video ages for a baseline | views at 7 and at 28 days, against the channel's median at the same age and format | compares like with like (Help 7628154: CTR varies by where and when it is shown); the research's recommendation, the ages are ours |
| Smallest sample to read a pattern | 5 videos of the same format in the window; fewer → the audit says "too few to judge" | no published minimum exists; 5 is ours, chosen so one outlier cannot carry a median |
| Judging an intro or format change | 5 uploads with the change, against the last 10 of the same length band | no published number (research, open question 2); 5 is ours, the 10 is Studio's "typical" comparison |
| Judging a niche shift or repositioning | 15 uploads with the change, judged on their 28-day views | Monahan: not on the first 3 "or even the first ten" (above); 15 is ours, past his line |
| Length bands of long-form | under 8 min, 8–20 min, over 20 min | ours: comparisons stay among videos of similar length, as Studio's "typical" does; 8 min is where mid-rolls become available (Help 6175006), 20 min splits long talks from the rest |
| Spike | a video at 10× or more of its group's median | ours, at 1of10's top band (10×); a spike is left out of the median and read as viewers who may not return (Help 141805) |
| Topic that worked | a topic with 3 or more upward outliers | 1of10's validation rule: "find 3+ videos on the same concept that all became outliers" (1of10 on X, undated) |
| Too few impressions to read CTR | under 100 impressions for the video and source in the window | ours; a write-up of Help 7628154 (1dsmgmt.com, read via the research 2026-11-23) says new videos and those under 100 views show wider CTR ranges |
| Audit period | the 90 days ending 3 days before the run (the Analytics API lags), against the 90 days before; CTR by source covers what the Reporting API still keeps (60 days) | ours: one window for every step of the audit |
| Destructive step gate | repositioning or a new channel only when the same cause holds over 10 or more videos | the research's recommendation 5; ours as a rule |
| Data freshness | seed metrics older than 31 days are re-measured before ranking | DataForSEO Labs updates keyword metrics monthly (Labs keyword_overview docs, 2026-11-04) |

## Secondary (context only)

| Claim | Source as cited by claude-youtube | Use |
| --- | --- | --- |
| Average CTR by traffic source: search 12.5 %, suggested 9.5 %, browse 3.5 %, external 2.8 % | Focus Digital, December 2025 (single agency) | only to explain why browse CTR must not be compared with search CTR |
| Channels uploading 12+ times a month grew views faster | vidIQ study of 5.08 M channels | never as advice to upload more: YouTube finds cadence not correlated with growth (Help 141805). Cadence is set by what the channel can sustain |
| Views are counted per start: Shorts since 2025-03-31 (the old count is now "engaged views"); long-form reportedly since 2026-08-24 | TechCrunch 2025-03-26 (Shorts); PPC Land 2026-09-02 (long-form, not on a YouTube page as read) | a baseline whose window crosses a counting change says so; use engaged views where the data gives them |
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
| "4–6 % CTR is average, 10 %+ excellent", CTR tables by channel size | no source; YouTube publishes only the 2–10 % half-of-channels band (research 2026-11-23) |
| "70 % still watching at 30 s is strong, under 50 % needs a fix" | no source; compare the Intro with the channel's own typical |
| "70–80 % Stayed to watch is normal for Shorts" | community consensus with no method (research 2026-11-24); compare with the channel's own Shorts |
| "5–10 variations per song", "the feed never shows two Shorts of one creator in a row" | marketers' opinions without data; no YouTube statement on Shorts of one channel competing with each other (research 2026-11-24) |
| Shorts-to-long-form conversion rates ("under 10 %", "12–18 subscribers per 10 k views") | no source; YouTube publishes none |
| "Galloway's 500-channel study: Shorts + long-form grew 2.8× faster" | no primary trace |
| "The algorithm punishes a break", "the first hour decides", "a 20/50/80 % gradual pivot" | refuted by YouTube or reported to fail (rows above) |
| YPP expanded tier "500 / 3 / 3 000" written as the only tier | correct numbers, but incomplete — both tiers above |
