---
name: youtube-strategy
description: Channel strategy, video ideas, the monthly content calendar and the weekly analytics report for a YouTube channel — output templates with quality bars, the channel types that `profile.channel_type` names, dated and sourced thresholds, and a 0-100 idea score with defined scales. Use in Onboarding (niche, positioning, pillars, cadence), Recon (idea backlog), Planning (calendar) and Analytics (report ending in one main fix).
---

# YouTube strategy

Knowledge for the reasoning steps of the channel recipes. Each activity has its reference with
inputs, steps, an output template and a quality bar; read the one for your step before writing,
and check the output against its quality bar before finishing.

## Which reference for which step

| Step | Read | Reads records | Writes |
| --- | --- | --- | --- |
| Onboarding: niche, positioning, pillars, cadence, identity | `references/strategy.md`, `references/channel-types.md` | `seed` (after youtube-demand) | `profile` (with `channel_type`, `identity_token`), `seed` via youtube-demand; artifact `strategy.md` |
| Recon: idea backlog | `references/ideation.md` | `profile`, `seed`, `watch`, `velocity`, earlier `idea` | `idea` (+ new `seed` via youtube-demand); artifact `ideas.md` |
| Planning: monthly calendar | `references/calendar.md` | `profile`, `idea` (Recon's memory), `plan`, `publish` | `plan`; artifact `calendar-YYYY-MM.md` |
| Analytics: weekly report | `references/analytics-report.md` | `studio`, `velocity`, `publish`, `plan`, `idea`, `profile` | none; artifact `report-YYYY-MM-DD.md` |
| Any number you are about to quote | `references/thresholds.md` | — | — |

Records go through youtube-records (`records.py write/key/validate`), each read from its writer's
memory. Metadata wording (titles, descriptions) follows youtube-metadata; keyword numbers come from
youtube-demand; outliers, velocity and retention measurements from youtube-metrics.

## Idea score

```bash
python3 <base>/scripts/score_idea.py --title "..." --volume 5000 --yt-interest 40 \
    --yt-competition 0.35 --fit 4 --packaging 3 --feasibility 4
python3 <base>/scripts/score_idea.py --file ideas.json        # a batch, ranked
```

0–100 = 20 × (0.25 demand + 0.20 opportunity + 0.25 fit + 0.15 packaging + 0.15 feasibility), each
dimension 0–5. Demand (volume tier or Trends tier, the larger) and opportunity (1 − `yt_competition`,
else 1 − `kd_web`/100 as a web proxy) come from the seed; fit, packaging and feasibility are judged
with the anchored rubric in `references/ideation.md`. Fit 0 or feasibility 0 vetoes the idea. The
output's `basis` says which dimensions were measured and which judged. Write the score into the
`idea` record's `score`. A refusal (exit 2) names the missing input — measure it or judge it, never
default it.

## Rules for every output

- **Data first.** Every claim about demand, competition or performance carries its number, source
  and date, or says "no data". The channel's own medians are the benchmark; external numbers only
  from thresholds.md, labelled with their kind (YouTube / ours / secondary).
- **Identity tokens verbatim** in every title you propose (`profile.identity_token`).
- **One main fix** ends a report; a strategy ends in numeric milestones; an idea carries keyword,
  hook, thumbnail concept and format.
- **Ask once, with defaults.** When the owner's input is missing, ask in one message with a
  recommended default per question, and continue with the defaults where the recipe allows.
- Self-check against the reference's quality bar; rewrite a failing section once, then report what
  still fails rather than looping.
