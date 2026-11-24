# Viewer groups, the Shorts feed and Analytics for Artists

Used by the Channel Audit. None has an API: the Analytics API has no new, casual or regular
viewers and no Shorts-feed numbers, and Analytics for Artists is a Studio view. Read them in Studio under `YT_STUDIO_SESSION`,
after the session check (`session.md`).

## What YouTube defines (read 2026-11-23)

- **Casual** viewers watched in 1–5 of the last 12 months, **regular** viewers in 6 or more; the
  groups replaced "returning viewers" in July 2025 and are not its direct equivalent (YouTube via
  Search Engine Journal and Social Media Today, 2025-07). **New** viewers are as the card defines
  them: read its tooltip and write the definition shown.
- The groups do not affect reach or monetisation; returning viewers make recommending the channel's
  later videos more likely (Help 10246996).
- The Audience tab can show a card "Popular with different audiences": which videos brought new
  viewers and which kept regular ones (Help 10246996).
- Analytics for Artists, on an Official Artist Channel, separates "Official Artist Channel" (Art
  Tracks included) from "Other Channels" (fan videos whose main component is the song) (Help
  18736729).

## Reading the viewer groups

1. Studio → **Analytics** → **Audience**. Period: the audit period (`thresholds.md`, Audit period),
   set as a custom range.
2. Read the card with new, casual and regular viewers: the count or share of each, as shown.
3. Read the "Popular with different audiences" card if it is there: the videos named for each group.
4. Repeat for the 90 days before it, so the audit compares two periods.
5. Write `viewer-groups.json`:

```json
{"as_of": "2026-11-23", "period": ["2026-08-25", "2026-11-23"],
 "groups": {"new": 0, "casual": 0, "regular": 0}, "unit": "viewers | percent, as shown",
 "popular_with": {"new": ["<videoId>"], "casual": [], "regular": []},
 "previous": {"period": ["…", "…"], "groups": {"new": 0, "casual": 0, "regular": 0}},
 "source": "studio", "not_shown": []}
```

A card that is not shown (too few viewers, or not offered to the channel) goes into `not_shown` with
what Studio said. Never estimate a missing group.

## The Shorts feed

A Short has no thumbnail impressions: its reach is "Shown in feed" ("the number of times that your
Shorts showed in the Shorts Feed", Help 12942217) and its click is "Stayed to watch" (viewed vs
swiped away).

1. Studio → **Analytics** → **Content** → **Shorts**, the audit period.
2. For each Short of the period, open its analytics and read: Shown in feed, Stayed to watch (or
   viewed vs swiped away), views and engaged views, average percentage viewed.
3. Read the **Restrictions** column of Content → Shorts for each Short (copyright, Content ID).
4. Write `shorts-feed.json`: per Short the numbers as shown, `restrictions`, and `not_shown` for
   what Studio did not show. Never estimate a missing number.

## Analytics for Artists (music-artist channels)

1. Studio → **Analytics**; on an Official Artist Channel the view has a toggle between "Official
   Artist Channel" and "Other Channels".
2. For each toggle, read total views and unique viewers for the audit period, and the top songs with
   their views.
3. Write `artist-reach.json`: both toggles, the songs, the period, `source: "studio"`.

A channel without the toggle is not an Official Artist Channel: write that, and the audit judges the
own uploads only, saying so.

## Drift

The paths above are what YouTube Help describes; the screens change. Whatever differs — a card
renamed, moved or missing — goes into `admin-drift.md` with what was seen instead, as every Studio
playbook does.
