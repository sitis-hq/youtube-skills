# Channel strategy (Onboarding)

Rewritten from claude-youtube `sub-skills/strategy.md` (commit 84c3fa68, MIT, Copyright (c) 2025
Daniel Agrici). Changed: the inputs come from records and youtube-demand data instead of questions
to the user; CPM/RPM tables and the vidIQ cadence citation are replaced by thresholds.md; milestones
are tied to the YPP thresholds YouTube publishes; the result also fills the `profile` record.

## Inputs

- What the owner gave the recipe (niche idea, the creator, resources, goal). Missing pieces are
  asked for once, in one message, with a recommended default for each — never a blocking quiz.
- Demand for 10–15 niche terms and the YouTube top 20 for 3–5 core terms (youtube-demand: Labs
  `keyword_overview`, Trends compare `type=youtube`, YouTube SERP → `seed` rows, `yt_competition`).
- Who already serves the niche: the channels holding those top 20 (youtube-data for their size,
  cadence and recent views).

## Steps

1. **Pick the channel type** from channel-types.md. It becomes `profile.channel_type`.
2. **Positioning** in one sentence: `[Channel] helps [specific viewer] get [outcome] through
   [format/angle], unlike [what the incumbents do]`. Start narrow (a micro-niche the channel can own;
   "30–50 videos" is an upstream rule of thumb with no source) and name the widening step for later.
3. **Niche viability** from data, each line with its number and source:
   - demand: volumes (web) and `yt_interest` (relative, same-batch only) of the core terms;
     trend direction from the Trends series (rising / flat / falling over 12 months);
   - competition: `yt_competition` and its parts for the core terms; the size spread of the channels
     in the top 20 (all large, or a mix with small ones ranking);
   - evergreen share: how much of the top 20 is older than a year and still pulling views/day;
   - monetisation: CPC of the core terms as a relative signal of advertiser interest (not an RPM
     estimate); the YPP route that fits the type (long-form hours vs Shorts views).
   Verdict: strong / workable / weak, with the single biggest risk and the biggest opening.
4. **Pillars**: 3–5, each labelled Hub or Help, plus Hero moments per quarter; per pillar its
   purpose, format, cadence, main surface, and 3 example working titles grounded in seed terms.
5. **Cadence**: what the creator can sustain (type's starting point adjusted to resources), long-form
   and Shorts separately, with the weekly production rhythm.
6. **Identity**: the identity tokens every title keeps verbatim (`profile.identity_token`), the
   audience in one sentence, the voice in one sentence (Community replies use it).
7. **Milestones** at 30/60/90 days: numeric and tied to actions — videos published, median views
   per video, subscribers, the distance to the YPP tier that fits.

## Output (artifact `strategy.md` of the step)

```
## Positioning
> [one sentence]
Micro-niche start: … · Widening at: [subscriber count or milestone] → …

## Niche viability
| Factor | Evidence (number, source, as_of) | Read |
| Demand | … | strong / workable / weak |
| Competition | yt_competition …, top-20 channel sizes … | … |
| Evergreen share | … | … |
| Monetisation signal | CPC …, YPP route … | … |
Verdict: … — biggest risk: … — biggest opening: …

## Pillars
### [Name] — Hub|Help — [n]/month — surface: search|browse|suggested|Shorts
Purpose · Format · Examples: 1. … 2. … 3. … (each with its seed term)
Hero moments this quarter: …
| Pillar | Type | Videos/month | Share |

## Cadence
Long-form: … · Shorts: … · Weekly rhythm: …

## Identity
channel_type: … · identity tokens: … · audience: … · voice: …

## Milestones
| Day | Metric | Target | Action |
```

## Quality bar

- The positioning names the viewer, the outcome, the format and the difference — all four.
- Every viability line cites a number with its source and date, or says "no data" — no adjectives
  standing in for data, no niche RPM tables.
- Each pillar is labelled Hub or Help and has 3 example titles tied to seed terms.
- Milestones are numbers with an action each; nothing like "grow the audience".
- The chosen type is one of the slugs in channel-types.md and its guidance visibly shaped the plan.

## Records

- Writes `profile` (Onboarding is its writer): `channel_type`, `niche`, `identity_token` (repeat),
  `audience`, `voice`, `language`, `country` — through youtube-records.
- Writes the initial `seed` set through youtube-demand.
