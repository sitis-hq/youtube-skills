# Weekly analytics report (Analytics)

Rewritten from claude-youtube `sub-skills/analyze.md` and `references/analytics-guide.md` (commit
84c3fa68, MIT, Copyright (c) 2025 Daniel Agrici), with the "ends in one fix" rule of
youtube-agent-skill `yt-audit` (commit a2feb210, MIT, Copyright (c) 2026 Jake Schincariol).
Changed: the input is the recipe's own data (Analytics API through youtube-data, `studio` and
`velocity` records, `publish` records), not screenshots; benchmarks are the channel's own medians
first; the action list is one main fix and at most two follow-ups instead of up to five.

## Inputs

- Channel and per-video metrics for the period (youtube-data analytics: views, watch time, average
  view duration and percentage, traffic sources, subscribers gained/lost; revenue when the scope
  allows).
- `studio` records (impressions, `ctr` as a fraction; `available false` = no data that day) and
  `velocity` records from Daily data.
- `publish` records (which idea and plan slot each video came from), `plan` records, `idea` records.
- Retention curves and their measurements from youtube-metrics.
- The previous report, to say what changed since.

## Steps

1. **Funnel per video and for the channel**: impressions → CTR → views → average view duration.
   Name the **one** stage that loses most against the channel's median for the same format and
   traffic source. Diagnostic reading:

   | Impressions | CTR | Retention | Reading |
   | --- | --- | --- | --- |
   | high | low | — | the package (thumbnail + title) does not earn the click |
   | — | high | low | the package promises what the video does not deliver |
   | low | high | high | the topic or its packaging reaches too few people; check demand |
   | low | low | — | the video is not being tested widely; check the topic and early signals |

   CTR falls as impressions widen to colder audiences; a falling CTR with rising impressions is not
   by itself a problem.
2. **Retention**: classify each curve (cliff, valley, bump, steady decline — definitions in
   thresholds.md) with the timestamps; say whether several videos share a pattern.
3. **Traffic sources**: shares per source; flag one source > 60 % (ours). Never compare browse CTR
   with search CTR.
4. **Outliers both ways** (youtube-metrics, ≥ 3× / ≤ ⅓ of the median for format and age): what the
   winners share and the losers share — topic, format, length, package, publish time.
5. **Ideas judged**: for each video with a `publish.idea`, how it did against its idea's score and
   the median; this is how Recon learns which scores mean something.
6. **Revenue** only when the data is there: RPM against the channel's own past, not niche tables.
7. **The fix**: one main fix — named, the evidence for it, what to do this week, the metric that
   will show it worked and when to read it. At most two follow-ups. Then three things that work and
   must not be broken, and what not to do yet.

## Output (artifact `report-[YYYY-MM-DD].md`)

```
## Week [start]–[end]
Data: [sources] · Missing: [what is absent and what it limits]

### Funnel
| Stage | Value | Channel median | Read |
Main leak: [stage] — [evidence]

### Retention
| Video | Pattern | At | Reading |

### Traffic sources
| Source | Share | vs last week | Note |   (flag > 60 %)

### Outliers
Up: | Video | Views vs median | Why |
Down: | Video | Views vs median | Why |

### Ideas judged
| Video | Idea | Idea score | Result vs median |

### The fix
**[One action]** — because [evidence]. Do: [this week]. Measure: [metric], read on [date].
Follow-ups (≤ 2): …
Keep doing: 1. … 2. … 3. …
Not yet: … (why)
```

## Quality bar

- Every diagnosis cites the number it rests on; nothing generic.
- Exactly one main fix; no padding to fill a list.
- Traffic shares add up to about 100 %.
- Benchmarks are the channel's own medians; any external number is labelled secondary.
- Missing data is stated and its consequence for the conclusions said.

## Records

Reads `studio`, `velocity` (Daily data), `publish` (creation recipes), `plan` (Planning), `idea`
(Recon), `profile` (Onboarding). Writes none: the report is the step's artifact.
