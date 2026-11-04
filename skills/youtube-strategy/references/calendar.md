# Content calendar (Planning)

Rewritten from claude-youtube `sub-skills/calendar.md` (commit 84c3fa68, MIT, Copyright (c) 2025
Daniel Agrici). Changed: slots come from `idea` records and become `plan` records; the fixed
"Tue–Thu 14:00–16:00" default is replaced by the channel's own audience-activity data; CPM
percentages are dropped (thresholds.md); the 3-title rule stays.

## Inputs

- The strategy artifact (pillars, cadence, Hero moments) and `profile` from Onboarding.
- `idea` records from Recon's memory with status `new` or `shortlisted`, and their scores.
- This recipe's earlier `plan` records and the creation recipes' `publish` records — to close
  published slots and not plan an idea twice.
- Seasonal dates: owner-provided events and release dates, holidays in the audience's country.
- When the audience is online: Studio's "When your viewers are on YouTube" if a step exported it;
  otherwise the channel's past best publish hours from its own uploads; otherwise state the
  assumption.

## Steps

1. **Close the past**: for each earlier `plan` slot, find its `publish` record (by `plan` or `idea`
   field); write the slot again with `status published` (Planning owns `plan`), or `dropped` with a
   note in the artifact.
2. **Count the month's slots** from the cadence: long-form days, Shorts, lives, posts; Hero moments
   placed on their dates.
3. **Fill slots** in score order, respecting: pillar rotation (no two consecutive long-form slots
   from one pillar unless the cadence forces it); trend share ≤ 30 % of slots (thresholds.md); flash
   trends in the first week or not at all; seasonal ideas published before their date with the
   lead time counted backwards.
4. **Per long-form slot**, 3 working titles — search-led, browse-led, hybrid — each with the
   keyword and identity tokens verbatim; the thumbnail concept; the hook type; when the channel
   runs Shorts, 2–3 Shorts cut candidates from it.
5. **Balance check** and the production timeline (what is scripted, made, edited and published
   each week, sized for the stated resources).

## Output (artifact `calendar-[YYYY-MM].md`)

```
## [Month YYYY]
Slots: [n] long-form + [n] Shorts + … · Hero: … · Key dates: … (with lead times)
Audience hours: [source or stated assumption]

| Week | Mon | Tue | Wed | Thu | Fri | Sat | Sun |   (LF = long-form, SH = Short, LV = live)

### [date] [slot] — [pillar] (Hub|Help|Hero) — [format]
Idea: [slug] (score …) · Keyword: … · Strategy: search|browse|trend · Hook type: …
Titles: 1. [search-led] 2. [browse-led] 3. [hybrid]
Thumbnail: … · Shorts from it: … · Effort: [hours by stage]

## Balance
Evergreen / trend / hybrid: …% / …% / …% — PASS | WARNING (trend > 30 %: swap [slot] for [idea])
Pillars per week: …
## Production timeline
| Week | Script | Make | Edit | Publish |
## Closed from last month
| Slot | Status | Video |
```

## Quality bar

- Every slot is complete — no TBD — and its dates match the real calendar of the month.
- Three titles per long-form slot, lint-clean (youtube-metadata `check_metadata.py`).
- The trend share is computed and flagged above 30 %.
- Lead times are dated backwards from each event.
- The timeline fits the resources the strategy states.

## Records

- Writes `plan` (`plan:<date>:<slot>`; slot `main`, `short-1`, `live`, …) with `title`, `format`,
  `status planned`, `idea` (the slug) and `source planning`. Several per day are separate slots.
- Never edits `idea` records (Recon's); the plan record names the idea instead.
