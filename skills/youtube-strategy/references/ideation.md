# Ideation (Recon)

Rewritten from claude-youtube `sub-skills/ideate.md` and `sub-skills/competitor.md` (commit
84c3fa68, MIT, Copyright (c) 2025 Daniel Agrici). Changed: every idea becomes an `idea` record with
keyword, hook, thumbnail concept and format; the "composite N/40" with undefined scales is replaced
by `scripts/score_idea.py` and the rubric below; volume tiers are computed from seed data, not
guessed.

## Inputs (records and data, read before writing a single idea)

- `profile` (Onboarding's memory): type, pillars' vocabulary, identity tokens, audience.
- `seed` (Onboarding's and this recipe's memory): the keywords with volume, interest, competition.
- This week's discovery: `watch` candidates and outliers (youtube-metrics), `velocity` from Daily
  data, Trends rising queries (youtube-demand `related`), competitors' title/hook patterns.
- Earlier `idea` records, to skip duplicates (same slug, or the same keyword and angle).
- Optionally the Community recipe's mined questions (an artifact), each a validated need.

## What makes an idea

An idea is a video someone wants that this channel can make better or differently. Each one carries:

| Field (`idea` record) | Content |
| --- | --- |
| `title` | working title with the keyword, ≤ 100 characters, identity tokens verbatim |
| `keyword` | the seed term it targets (measure new terms with youtube-demand first) |
| `hook` | the first seconds in one sentence: the curiosity gap or the promise |
| `thumbnail` | the concept in one sentence: subject, emotion, ≤ 3 words of text, colour; text adds to the title, does not repeat it |
| `format` | `long`, `short`, `live` or `post` |
| `production` | what kind of work it is — `new`, `version`, `compilation`, `clip`, `cover` or `other` — by the "Production" table of `channel-types.md` for the channel's type; every idea carries one, so each creation recipe offers only the kinds it can make |
| `source` | what grounded it: `watch:<videoId>`, `trend`, `seed:<slug>`, `owner` |
| `score` | 0–100 from `score_idea.py` |
| `note` | traffic strategy (search / browse / trend), urgency, and the one-line "why now" |

Traffic strategy decides packaging: search-first ideas answer a query (how-to, named things);
browse-first ideas win on curiosity and the channel's audience; trend ideas ride a rising query and
carry an urgency: **flash** (make this week or drop it) vs **sustained** (rising for months) vs
**seasonal** (state the date it must be out by, counted back from the event).

## Scoring rubric

`python3 <base>/scripts/score_idea.py --volume V --yt-interest I --yt-competition C --fit F
--packaging P --feasibility E` (or `--file ideas.json` for the batch). Demand and opportunity are
computed from the seed; the three judged dimensions use these anchors — pick the closest, do not
average your way between them:

| Score | fit | packaging | feasibility |
| --- | --- | --- | --- |
| 5 | squarely in a pillar; the channel is the obvious one to make it | hook, title-with-keyword and thumbnail each land in one line; the thumbnail text and title tell two halves of one promise | can be made inside the normal cadence with what the channel has |
| 4 | in a pillar, a new angle on it | two of the three are sharp, the third works | one extra effort (a location, a guest, a purchase) |
| 3 | adjacent to a pillar; the audience would follow | the promise is clear but generic | needs a week beyond the cadence |
| 2 | stretches the niche; part of the audience would | the promise needs explaining | needs skills or gear the channel lacks, obtainable |
| 1 | barely related | vague or only works with a misleading thumbnail | barely possible |
| 0 | off-niche — **veto** | — | not makeable — **veto** |

A score is a ranking aid within one batch. Urgency is not in the score: a flash trend at 55 can
go before an evergreen 70; say so in `note`.

## Output (artifact `ideas.md`, and the records)

```
## Ideas — week of [date]
Sources used: [watch ids, trends, seeds, community questions]

### [n]. [Working title]  — score [s] (demand d · opportunity o · fit f · packaging p · feasibility e)
Keyword: [term] (volume …, yt_interest … in batch …, yt_competition …, as_of …)
Format: long|short|live|post · Strategy: search|browse|trend · Urgency: evergreen|flash: by [date]|seasonal: by [date]
Hook: …
Thumbnail: …
Why now: … · Source: …

## Ranking
| # | Title | Score | Strategy | Urgency |
```

## Quality bar

- No near-duplicates: distinct topic or angle, checked against earlier `idea` records.
- Every keyword is a seed term with its measurements (or measured now); no invented volumes or
  "trending" claims without a Trends or velocity signal.
- At least two traffic strategies across a batch of 10; trend ideas carry an urgency.
- Hooks and thumbnail concepts are specific enough to produce from; the thumbnail does not repeat
  the title.
- Every idea names its source.

## Records

- Writes `idea` (status `new`, or `shortlisted` for the week's top picks) through youtube-records;
  Recon is the only writer of `idea`. A rejected idea is written once with `status rejected` and a
  `note`, so the next run does not propose it again.
- New keywords: measured with youtube-demand and written as `seed` before the idea that uses them.
- An idea's status follows the other recipes' records: a `plan` naming it, or a `take` with status
  `in-work`, makes it `planned`; a `publish` naming it (or a `take` with status `published`) makes it
  `published`; when every plan and take naming it is `dropped` and nothing published it, it goes
  back to `shortlisted`.
- A `cover` idea uses someone else's work: it stays an idea until the owner decides on the rights; no
  creation recipe takes it on its own.
