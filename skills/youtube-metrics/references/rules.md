# Rules, thresholds and where they come from

Each number below is either YouTube's (with the page and the day it was read) or this skill's own
choice (marked **ours**, with the reason). An "ours" number may be changed; change it in the script,
its test and here together.

## Velocity and anomaly — `velocity.py` (ours)

- `views_per_day` = views gained between the last two snapshots ÷ days between them. A falling count
  (YouTube removes views it judges invalid) gives 0; `views_delta` keeps the raw change.
- Baseline = median of the earlier daily rates (up to 14, at least 3). The median, not the mean, so
  one launch day or one odd day in the history does not lift the bar for every later day.
- Spike: latest ≥ 2 × baseline **and** ≥ baseline + 20 views/day. Drop: latest ≤ 0.5 × baseline
  **and** ≤ baseline − 20. The factor alone would flag 2 → 5 views a day; the absolute floor
  (`--min-abs`) keeps small videos quiet.
- Short history (fewer than 3 earlier rates): baseline = lifetime views ÷ age at the previous
  snapshot, for videos at least 7 days old, and only spikes are flagged. Daily views of nearly every
  video fall below its lifetime average once the first days are over, so a "drop" against it would
  flag ordinary decay.
- One snapshot: views ÷ age, written with `source: views-per-age` so a reader can tell it from a
  measured gain.

## Candidate score — `candidates.py` (ours)

score = (views ÷ age in days) ÷ (the channel's median of the same). Age is never below one day.
Raw views rank channel size; views alone rank old videos above new ones; the ratio to the channel's
own median ranks the video. The channel needs 4+ videos in the input (the candidates plus
`--baseline` uploads), the same floor as swipe.py — a median of two videos is one of them.

## Outliers — `swipe.py` (upstream, kept)

multiple = views ÷ the channel's median views in the input; upward ≥ 1.5 (default), downward ≤ 0.5
(added here; upstream found only winners, so under-performers for Planning had no tool). Formula
classification: 21 English regex families in `scripts/hooks.json`, by the upstream author; a
fixed vocabulary that labels the same title the same way every run, not evidence of cause.

## Retention — `retention.py`

- Hook window: the first 30 s (`--hook-seconds`), or the first 10 % without a duration.
- Cliff: one of the five steepest drops, each more than 0.8 percentage points (upstream values).
- Slide: mean loss per axis unit after the hook.
- Upstream labelled a hook leak "healthy" under 25 % and "severe" above 40 %. No source backs those
  figures, so they are not printed; compare a video with the channel's own other videos instead
  (`analytics.py retention` also gives `relative_retention_mean`, YouTube's own comparison with
  videos of similar length, 0.5 = median).

## Titles — `title.py`

- 100 characters: YouTube's title limit (Data API `videos` resource, `snippet.title`, read
  2026-11-04; `<` and `>` are not allowed either).
- ~60 desktop search, ~40 mobile feed: observed truncation widths quoted by the upstream author;
  YouTube publishes no figure, and the cut depends on the characters' width.
- Thumbnail text: three words at most (upstream rule; its code checked four — fixed).
- More than two all-caps words, vague superlatives, no number or date, filler first words, title
  words repeated on the thumbnail: upstream heuristics, kept as lint, not as predictions.
- Thumbnail A/B tests are judged by YouTube on watch-time share, not CTR — a lint score is no
  substitute for one.

## Chapters — `chapters.py` (YouTube)

support.google.com/youtube/answer/9884579, read 2026-11-04: the first timestamp is 00:00; at
least three, in ascending order; each chapter at least 10 seconds.

## YouTube Partner Program — `ypp.py` (YouTube)

| Tier | Applies | Subscribers | And | Either | Or | Source |
| --- | --- | --- | --- | --- | --- | --- |
| Revenue sharing | applications before 2027-02-01 | 1,000 | — | 4,000 public long-form watch hours / 12 months | 10 M Shorts-feed views / 90 days | support.google.com/youtube/answer/72851, read 2026-11-04 |
| Revenue sharing | applications from 2027-02-01 | 1,000 | — | 8,000 hours / 365 days | 20 M Shorts views / 90 days | YouTube announcement as reported by The Next Web, 2026-08-10; existing partners unaffected; read 2026-11-04 |
| Fan funding (memberships, Super Chat, Shopping) | since 2023-06-13, not in every country | 500 | 3 public uploads / 90 days | 3,000 hours / 12 months | 3 M Shorts views / 90 days | YouTube's 2023 expansion; unchanged per the 2026-08-10 report |

Re-read the help page before telling an owner they qualify: the 2027 figures were not yet on it
when read.
