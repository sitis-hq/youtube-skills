# Metadata rules

Rewritten from youtube-seo-skills (`youtube-seo`, `youtube-seo-optimize`; commit 779b0f13, MIT,
Copyright (c) 2026 Deeploy), claude-youtube (`sub-skills/seo.md`, `sub-skills/metadata.md`,
`references/seo-playbook.md`, `references/shorts-playbook.md`, `references/thumbnail-ctr-guide.md`;
commit 84c3fa68, MIT, Copyright (c) 2025 Daniel Agrici), youtube-agent-skill (`yt-seo` query test,
`yt-package` pairing rule; commit a2feb210, MIT, Copyright (c) 2026 Jake Schincariol) and
sitis-skills `youtube-music-metadata-optimization` (commit 2f35086). Kept: what is generic and checks
out against YouTube's own pages. Dropped: genre templates, unsourced uplift percentages, and the
claims listed at the end as wrong.

Two kinds of rule below. **YouTube** rules are hard: something is rejected or ignored; each names
its page and the day it was read. **Ours** are placement and style decisions with a reason, not
facts about the algorithm; a step may break one when it says why.

## Hard limits (YouTube)

| Field | Limit | Source, read 2026-11-04 |
| --- | --- | --- |
| Title | 1–100 characters; no `<` or `>` | Data API `videos` resource, `snippet.title`; Help 10059070 (Shorts: "max 100 characters") |
| Description | 5 000 **bytes** UTF-8; no `<` or `>` | Data API `videos`, `snippet.description` — Cyrillic, Greek, CJK and emoji take 2–4 bytes a character |
| Tags | 500 characters together; commas between tags count; a tag with a space counts with quotes (`Foo Baz` = 9) | Data API `videos`, `snippet.tags[]` |
| Hashtags | over 60 on a video: every hashtag on it is ignored; up to 3 "considered most engaging" show by the title; no spaces inside | Help 6390658 "Use hashtags for YouTube videos" |
| Chapters | first timestamp `0:00` (`00:00`), at least 3 in ascending order, each chapter at least 10 s | Help 9884579 "Video chapters" |
| Shorts | up to 3 minutes, vertical | Help 10059070 |
| Tags' weight | "title, thumbnail, and description are more important"; tags help mainly when the subject is commonly misspelled; excessive tags breach spam policy | Help 146402 "Add tags to your videos" |

`scripts/check_metadata.py` enforces every row it can check from text.

## Title

- **Identity tokens verbatim.** Names from `profile.identity_token` (artist, series, show) appear
  exactly as written there — same case, spelling, diacritics. They are never translated, replaced
  by a higher-volume keyword, or abbreviated. Which tokens a title must carry is the recipe's call
  (`--require-token` in the linter).
- **One primary keyword**, chosen from `seed` records (demand), in natural word order. Front-load
  it: ours, within the first 40 characters, because feeds and search results cut long titles and the
  cut point varies by surface and device (YouTube publishes no number; upstream's 40–70 figures were
  observations and disagreed with each other).
- No fixed "best length": upstream claimed both "70–100 characters is 10–14 % better" and "under 50",
  neither with a checkable source. Use the length the promise needs.
- The promise of the title is kept by the first seconds of the video and the thumbnail. Title and
  thumbnail are one unit: the thumbnail text adds to the title, it does not repeat it (the pairing
  check is youtube-metrics' title/thumbnail-text check).
- Write several (ten is cheap), lint all, keep two or three; for a test, vary one thing at a time.
- Surface decides the order of hook and keyword (ours, from youtube-seo-optimize):

  | Surface the video is for | Title | Description priority |
  | --- | --- | --- |
  | Search (how-to, named things) | keyword first, then the promise | full keyword and entity coverage |
  | Browse / home (subscribers, curiosity) | hook first, keyword second | an opening that sells the click |
  | Suggested (next to a parent video) | the parent's vocabulary | link to the parent |
  | Shorts | short and specific; hook | two lines at most |

## Description

1. **Opening (first ~150 characters).** It is what shows before "…more" and in search snippets; the
   exact cut varies by surface, so treat 150 as the budget (ours). It states what the viewer gets, in
   the words of the primary keyword (the linter checks the keyword is there). No link-only line
   first unless the recipe requires one.
2. **Recipe's fixed block**, when the recipe has one: required links (stream links, socials — config
   credentials of the project, never typed from memory), labels, credits. The recipe decides what is
   in it and where; this skill only keeps it intact.
3. **Chapters** for videos with distinct parts (see below).
4. **Body**: who it is for, what is covered, secondary keywords once each in natural sentences.
   Lyrics, when the recipe puts them here, count against the 5 000-byte limit.
5. **Hashtags** last, 3–5 relevant ones (ours: fewer, sharper; YouTube's own limit is the 60 above).
   YouTube picks which 3 show by the title, so do not count on order.

The query test (ours, from youtube-agent-skill `yt-seo`): write the three searches this video should
win; the title and the description opening must contain their words. If they do not, fix the title.

Also ours: no "out now", "new", or the current year in evergreen text (it dates the video); no
description copied from another video.

## Tags

Few and literal: the primary keyword, common misspellings and alternative spellings, names that
need disambiguation (Help 146402 says that is where tags matter). Not hashtags (no `#`), not other
artists' or channels' names the video is not about (spam policy). The 500-character total is the
only number YouTube sets.

## Chapters

From the content's real sections (or a transcript), first at `0:00`, ≥3, ascending, each ≥10 s;
the linter also checks the last chapter against `--duration`. Labels say what the section is — a
viewer scans them; a keyword belongs there only when it describes the section.

## Shorts metadata

- Title: specific, short, the hook; identity tokens still verbatim. Hashtags in the description.
- Description: one or two lines. **Links in Shorts descriptions and comments are not clickable**
  (since 2023-08-31; reported by Tubefilter 2023-08-10, YouTube's announcement not re-read) —
  name the full video in words instead; the linter warns on a URL in a Short.
- `#shorts` is not what makes a video a Short (length ≤ 3 min and vertical format do, Help 10059070);
  we found no official requirement for it.
- Shorts cannot be A/B tested (below).

## Thumbnail and title tests: Test & Compare

From Help 13861714 "Test & compare thumbnails and titles", read 2026-11-04:

- Up to **3** variants of the thumbnail, the title, or both.
- YouTube shows the variants and keeps the one with the **highest watch time** for all viewers — the
  winner is judged by **watch-time share, not CTR**. A variant that wins clicks but loses watch
  time loses.
- A test should complete within about **two weeks**.
- Not available for Shorts, scheduled lives, Premieres (until they end), and videos made for kids,
  for mature audiences, or private.

Ours: each variant changes one thing (the face, the text, the colour — not all three), so the
result says what worked. There is no API: the test is set up in YouTube Studio through the
youtube-studio playbooks, as an irreversible action behind an intent reservation. Record what was
tested and the result in the step's artifact; read the result only after YouTube reports it.

## Claims dropped, and why

- "More than 15 hashtags and all are ignored" (claude-youtube) — YouTube's page says 60.
- "The first 3 hashtags show above the title" — YouTube shows up to 3 it considers most engaging.
- "Description limit 5 000 characters" — it is 5 000 bytes.
- "Thumbnail tests are won on CTR" / "≥0.5 pt Browse CTR" (youtube-seo-thumbnail) — watch time decides.
- "Shorts are under 60 s" — up to 3 minutes since October 2024 (Help 10059070 today).
- "Optimised titles +15–30 % CTR", "numbers in titles +20–30 %", "chapters +4 % AVD",
  "smart links +25–40 % conversion", "Friday +18 %", "change the title right after publishing
  confuses the algorithm" — no checkable source.
- Genre tag lists and music-label templates (the music metadata skill) — fixed parts are the
  recipe's, the descriptive part comes from demand data; a skill-wide genre list is neither.
