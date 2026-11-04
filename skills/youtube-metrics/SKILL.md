---
name: youtube-metrics
description: Pure computations over YouTube numbers, each with a stated and tested rule — growth velocity and spike/drop anomaly flags from daily snapshots (velocity records), candidate scoring by views per day against the channel median (watch records), outliers up and down against each channel's own median with the title's hook formula, retention-curve diagnosis (hook leak, cliffs, slide, with what was said at each cliff), title and thumbnail-text lint, chapter-block validation, dead air in a transcript, and the YouTube Partner Program thresholds. Use after youtube-data has fetched the numbers, whenever a step must judge them the same way every run.
---

# YouTube metrics

Calculators: they read files, print JSON, touch no network and need nothing but Python 3.11. Call
them by path from this skill's base directory: `python3 <base>/scripts/<script>.py ...`. A refusal
is `{"ok": false, "error": ...}` with exit code 2 — it names what is wrong with the input.

## Commands

| Need | Command | Feeds |
| --- | --- | --- |
| Views per day and anomaly per video, from daily snapshots | `velocity.py snapshot-*.json` | `velocity` record |
| Score recon candidates | `candidates.py found.json --source search --baseline uploads.json` | `watch` record |
| Outliers against each channel's median | `swipe.py videos.json --direction up\|down\|both` | — (analysis) |
| Why viewers leave | `retention.py retention-ID.csv --axis percent --duration S --transcript ID.srt` | — (diagnosis) |
| Lint a title with its thumbnail text | `title.py --title "..." --thumb "..." --lang <lang>` or `--titles-file` | — |
| Check a description's chapters | `chapters.py validate --description-file d.txt --duration S` | — |
| Draft chapters from a transcript | `chapters.py draft ID.srt --target 7 --lang <lang>` | — |
| Dead air, filler, restarts | `deadair.py ID.srt --lang <lang>` | — |
| Distance to YPP | `ypp.py --subscribers N --watch-hours H --shorts-views V --uploads-90d U` | — |

Inputs are youtube-data's outputs as they come (`data_api.py videos`, `uploads --with-stats`,
`analytics.py retention`, `transcript.py`). Each script's `--help` states its rule in full.

## Writing the records

`velocity.py` and `candidates.py` give each video a `record` object whose keys are exactly the
record's fields. Pass them to youtube-records as flags, `_` becoming `-`:

```bash
python3 <records-base>/scripts/records.py write velocity --video-id ID --as-of 2026-11-04 \
  --views-per-day 812.5 --anomaly spike --source data-api
```

- `velocity`: one per video with a record, every run (it is overwritten daily; `as_of` dates it).
  `source: views-per-age` marks the one-snapshot proxy — say so in the summary.
- `watch`: only for the candidates you decide to follow; add `--reason` (one sentence, yours).
  A candidate in `need_baseline` has no score yet: fetch its channel's uploads and run again
  rather than writing it unscored.

## Rules the numbers carry

- **Anomaly** (`velocity.py`): against the video's own median daily gain over up to 14 earlier
  intervals (at least 3): spike ≥ 2× and ≥ 20 views/day more, drop ≤ 0.5× and ≥ 20 less. With
  shorter history, only a spike against the lifetime average, for videos 7+ days old. These are
  this skill's rules, not YouTube's; quote them when you report a flag.
- **Outliers** need 4+ videos of a channel in the input; thinner channels are listed, not ranked.
  A multiple compares views, not age: for fresh uploads prefer `candidates.py` (views per day).
- **Hook formula** names come from `scripts/hooks.json` (21 English formulas) and judge the title's
  words, not why a video worked. Other languages get `unsupported-language` — do not translate to
  force a match.
- **Retention**: state the axis (`percent` for analytics.py output, `seconds` for a Studio export
  of a Short). Report the biggest single leak and one change for it; the numbers carry no
  "healthy" verdict, because no published benchmark backs one.
- **title.py**'s score ranks drafts against each other; it predicts nothing about CTR. Checks that
  are English-only are listed under `unsupported` for other languages. The "no number" check does
  not fit music releases (artist – song titles); ignore it there.
- **YPP** thresholds change on 2027-02-01 for new applications; `ypp.py` dates each with its
  source. Analytics watch time overstates qualified hours (it includes Shorts-feed and non-public
  time) — call the result a bound and point to Studio's Earn tab.

Read `references/rules.md` for the sources and the reasoning behind each threshold.
