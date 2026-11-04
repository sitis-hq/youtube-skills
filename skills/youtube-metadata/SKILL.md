---
name: youtube-metadata
description: Write and check a video's titles, description, tags, hashtags, chapters and Shorts metadata, and plan thumbnail/title A/B tests (Test & Compare, judged by watch time). One generic rule set for every channel type — identity names kept verbatim, keywords from demand data, fixed parts from the recipe; check_metadata.py lints YouTube's hard limits. Use when a step writes or repackages metadata (Planning & optimization, the creation recipes) or prepares an A/B test.
---

# YouTube metadata

## Where each part of the metadata comes from

A metadata set has three sources, and this skill decides only the third's wording, never its content:

1. **Identity — from the `profile` record.** Every `identity_token` (artist, series, show name) is
   kept exactly as written there: case, spelling, diacritics. Demand data never replaces, translates
   or shortens it.
2. **Demand — from `seed` records** (youtube-demand). The primary keyword and 2–4 secondary ones
   shape the descriptive part: the words of the title around the identity tokens, the description's
   opening and body, tags, hashtags. Use the seed's own term; do not invent volumes or "trending"
   claims. No seed for the topic → measure with youtube-demand first, or write without a keyword and
   say so.
3. **Fixed parts — from the recipe.** Required links (stream services, socials: config credentials
   of the project), labels such as "Official Audio", credits, lyrics in the description, a required
   title pattern — **the recipe decides** what is fixed and where it goes. This skill keeps them
   intact and fits the rest around them. A required link whose credential is missing pauses the run
   (the recipe's rule); never type a link from memory.

## Steps

1. Read `profile` (identity tokens, language, voice) and the `seed` records for the topic; for a
   planned video also its `plan` slot and `idea` (keyword, hook, thumbnail concept). Readers look up
   other recipes' records through youtube-records; this skill writes no record.
2. Pick one primary keyword. Decide the surface the video is for (search, browse, suggested,
   Shorts) — it sets whether the keyword or the hook leads (`references/metadata-rules.md`).
3. Write several titles, the description (opening → recipe's fixed block → chapters → body →
   hashtags), tags and hashtags.
4. Lint every candidate; fix every error; fix or justify every warning.
5. Hand the chosen set to the step that applies it (Data API `videos.update` or Studio, behind an
   intent reservation — youtube-studio / youtube-data). Keep the linted JSON as the step's artifact.

## Lint

```bash
python3 <base>/scripts/check_metadata.py --file meta.json            # title, description, tags, keyword, format, duration, require_tokens
python3 <base>/scripts/check_metadata.py --title "..." --description-file desc.txt \
    --tags "a, b" --keyword "sad phonk" --format long --duration 1260 --require-token "Dante Ray"
```

Exit 0 = no errors; 1 = errors (or warnings with `--strict`); 2 = unusable input. `errors` are
YouTube's limits: title 1–100 characters; description ≤ 5 000 bytes; no `<` `>`; tags ≤ 500
characters counted the Data API way; > 60 hashtags (all ignored); chapters (first 0:00, ≥ 3,
ascending, ≥ 10 s each, last one inside `--duration`); a `--require-token` missing from the title.
`warnings` are our rules: keyword missing from the title or starting after character 40, missing
from the description's first 150 characters, `#` in tags, duplicate tags, a URL in a Short's
description. `facts` gives lengths, bytes, the hashtags found and the parsed chapters.

## Shorts

Short specific title (identity tokens verbatim), one or two description lines, hashtags in the
description. Links in Shorts descriptions are not clickable — name the full video instead. Shorts
cannot be A/B tested.

## Thumbnail and title A/B tests (Test & Compare)

Up to 3 variants of thumbnail, title or both; YouTube keeps the one with the **highest watch time**
— judge and report by watch-time share, never by CTR; about two weeks; not for Shorts, Premieres,
scheduled lives, made-for-kids, mature or private videos (YouTube Help 13861714, read 2026-11-04).
Change one variable per variant. There is no API: youtube-studio sets it up, behind an intent
reservation. Measure thumbnail candidates first with youtube-thumbnail-check.

## Read on demand

`references/metadata-rules.md` — when writing (not just linting): the sourced limits table, title
and description structure, the surface table, tags, chapters, Shorts, Test & Compare, and the
upstream claims we dropped as wrong or unsourced (so they are not reintroduced).
