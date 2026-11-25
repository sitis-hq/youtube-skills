# Channel types

The value of `profile.channel_type` is one of the slugs below, exactly. Each type is a starting
point for pillars, cadence, titles, thumbnails and hooks — the channel's own data overrides it.

Rewritten from claude-youtube `templates/*.md` (commit 84c3fa68, MIT, Copyright (c) 2025 Daniel
Agrici). Changed: the content mix is a Hub/Help split plus Hero videos **per quarter** (upstream
used three percentages that contradicted its other files); uplift figures ("8× faster growth",
"+10–15 % CTR", niche CTR/RPM numbers, "42.1 % retention") are removed — see thresholds.md;
`music-artist` is new. Terms: **Hub** — recurring formats the subscribers come back for; **Help** —
searchable answers to a need; **Hero** — a tentpole made to reach new people.

## Production: what kind of work an idea is

Every `idea` record carries `production`, so a creation recipe offers only the ideas it can make. The
values are the same for every type; what each means for a type:

| `production` | In general | music-artist | education, tutorial, niche-authority | entertainment, vlog, personal-brand, commentary, review |
| --- | --- | --- | --- | --- |
| `new` | a new original work | a new original song (its theme, mood, hook line, subgenre) | a new lesson, explainer or guide | a new video or episode |
| `version` | another version of an existing work | an instrumental, acoustic, sped-up or remixed version of a released song (the note names it) | an updated or re-recorded lesson | a re-edit or extended cut |
| `compilation` | a new video assembled from existing works | a mix or playlist of the channel's own songs | a "best of" or a course from existing lessons | a best-moments cut |
| `clip` | a cut from one existing work | a Short from a released song or video | a Short from a lesson | a Short from an episode |
| `cover` | someone else's work at the centre | a cover of another artist's song | a breakdown built on another creator's video | a reaction to someone else's video |
| `other` | none of these | a live session, behind the scenes, a vlog | a Q&A, a live | a live, a community post |

A `cover` needs rights the channel may not have, so it is never taken by a recipe on its own; the
owner decides. A `compilation` or `version` names in its `note` which existing works it uses.

Cadence below is a sustainable starting point for one creator, not a growth promise: consistency
beats volume, and a cadence the channel cannot keep is worse than a lower one.

**Main surface is a hypothesis, not a measurement.** It was carried over from the upstream templates,
which give no source for it (no published taxonomy of channel types with traffic mixes exists, from
YouTube or a named practitioner — niche research, 2026-11-05), and `music-artist` is ours. Nothing
ranks by it: niche choice is by openness (youtube-demand `niches.py`). Replace it with the channel's
own traffic sources (`analytics.py traffic`) once they exist.

| Slug | In one line | Hub / Help | Hero per quarter | Main surface (hypothesis) |
| --- | --- | --- | --- | --- |
| `education` | explainers and how-tos that teach a subject | 35 / 65 | 1 | search, suggested |
| `tutorial` | step-by-step fixes and walkthroughs for a tool or skill | 25 / 75 | 1 | search |
| `entertainment` | challenges, sketches, reactions made to be watched for fun | 85 / 15 | 2 | browse, suggested |
| `vlog` | the creator's life as a story | 80 / 20 | 1–2 | subscriptions, suggested |
| `review` | is this product worth it, A vs B, best of | 35 / 65 | 1 (launch-day) | search |
| `commentary` | opinion and analysis on news and culture | 70 / 30 | 1–2 | browse, suggested |
| `niche-authority` | deep expertise in one domain (finance, law, B2B) | 35 / 65 | 1 | search, suggested |
| `personal-brand` | the creator as the brand, several formats, one positioning | 60 / 40 | 1–2 | browse, suggested, search |
| `shorts-first` | mainly vertical short videos in recognisable series | 80 / 20 | 1–2 | Shorts feed |
| `music-artist` | an artist's releases and the life around them | 70 / 30 | 1 per release cycle | browse, suggested, search for names |

## education

- **Cadence**: 1 long-form a week; 2–3 Shorts with one concept each.
- **Pillars**: core lessons (Help), a recurring deep-dive or course playlist (Hub), a myth-busting
  tentpole (Hero).
- **Titles**: `How to [skill] [constraint]`, `[Topic] explained in [n] minutes`, `[n] mistakes in
  [skill] and the fix`, `Why [common belief] is wrong`. Keyword first.
- **Thumbnail**: 1–3 words naming the "what"; a before/after or step visual; a face optional.
- **Hook**: problem-agitation — name the problem searched for, promise the fix, show the result early.
- **Fails when**: it lectures instead of solving; it skips chapters on long lessons; it invests in
  production before it has a library.

## tutorial

- **Cadence**: 1–2 a week, batched by tool; Shorts with single tips.
- **Pillars**: single-problem fixes (Help), project builds and series (Hub), a complete guide (Hero).
- **Titles**: `How to [action] in [tool]`, `[error] fixed`, `[tool A] vs [tool B] for [use]`,
  `[tool] for beginners: [outcome]`. Tool name early; the version or year when software changes.
- **Thumbnail**: the result or the before/after of the screen, one highlighted element, 2–3 words.
- **Hook**: show the end result in the first seconds, then step one.
- **Fails when**: it covers unrelated tools; it re-explains basics in every video; no chapters.

## entertainment

- **Cadence**: 1–2 long-form a week; Shorts cut from them several times a week.
- **Pillars**: recurring formats and characters (Hub), big swings and collaborations (Hero), a
  behind-the-scenes strand (Help, for bonding rather than search).
- **Titles**: curiosity or disbelief — `I [extreme action] for [time]`, `We tried [thing] and
  [outcome]`, `[challenge] (it worked)`. One capitalised word at most.
- **Thumbnail**: a face with a strong, readable emotion; 0–2 words; something about to happen.
- **Hook**: open on the most surprising moment, then rewind.
- **Fails when**: thumbnails repeat one look until viewers stop noticing; it chases trends without
  a recognisable identity; low ad rates are not planned for.

## vlog

- **Cadence**: 1 a week on a fixed day; Shorts of moments.
- **Pillars**: the weekly story (Hub), lessons and routines (Help), milestones and moves (Hero).
- **Titles**: personal and concrete — `A day as a [role] in [place]`, `I finally [decision]`,
  `What I spend in a month as [identity]`. No promise the video does not keep.
- **Thumbnail**: genuine expression in a recognisable setting; one consistent colour grade.
- **Hook**: start inside the story's tension; say in the first 15 seconds what this episode is about.
- **Fails when**: there is no story arc; the schedule breaks; the format never evolves.

## review

- **Cadence**: 1–2 a week, timed to product launches; Shorts with quick verdicts.
- **Pillars**: single reviews (Help), comparisons and best-of roundups (Hub), launch-day or
  "I tested all of them" (Hero).
- **Titles**: `[product] review after [time]`, `[A] vs [B]: which to buy`, `Best [category] in
  [year]`, `Is [product] worth [price]?` — product name and "vs"/"best" are searched words.
- **Thumbnail**: the product and a face whose reaction matches the verdict; a rating or price.
- **Hook**: the verdict's direction in the first 30 seconds, then the evidence.
- **Fails when**: everything is positive; nobody searches for the product; the review comes after the
  buying window.

## commentary

- **Cadence**: 2 a week, one timely and one evergreen; Shorts for quick takes.
- **Pillars**: a recurring roundup or series (Hub), evergreen "why X happened" explainers (Help),
  fast takes on big moments (Hero).
- **Titles**: tension early — `The real reason [event] happened`, `Why everyone is wrong about
  [topic]`, `[n] things nobody says about [topic]`.
- **Thumbnail**: a face with a clear reaction, 3–4 bold words, the subject in the remaining space.
- **Hook**: a counter-consensus claim in the first seconds, context, then the structure of the argument.
- **Fails when**: it is only news, so nothing compounds; the voice copies others; the pace burns the
  creator out (keep a buffer of evergreen videos).

## niche-authority

- **Cadence**: 1 long-form a week, each aimed at one keyword cluster; Shorts with definitions.
- **Pillars**: search-led explainers (Help), a recurring update or case study (Hub), a complete guide
  or annual prediction (Hero). Start with one tight sub-topic and widen after ranking for it.
- **Titles**: keyword in the first 40 characters — `[topic] explained`, `How to [result], step by
  step`, `[advice] is wrong: do this instead`, `[method A] vs [method B]`.
- **Thumbnail**: clean, few elements, a number or chart, a consistent palette.
- **Hook**: the viewer's exact problem, then a credibility line, then the map of the video.
- **Fails when**: the niche is too broad at the start; jargon loses viewers early; packaging gets
  less effort than research.

## personal-brand

- **Cadence**: 1 long-form a week, alternating effortful and light formats; several Shorts.
- **Pillars**: the recurring personal format (Hub), how-tos from the creator's expertise (Help),
  milestones and collaborations (Hero). Every format serves one positioning sentence.
- **Titles**: "I"/"my" as the lens — `How I [result] in [time]`, `I tried [method] for [time]`,
  `[n] lessons from [experience]`.
- **Thumbnail**: the creator's face as the constant, the context or transformation as the variable.
- **Hook**: a personal moment with stakes, then what the viewer will get.
- **Fails when**: topics scatter without a through-line; it never ships for perfectionism.

## shorts-first

- **Cadence**: daily or near-daily Shorts, batched; one long-form a week once the audience exists,
  because Shorts alone earn little per view.
- **Pillars**: recognisable series (Hub), trend formats (Hero), quick tips (Help).
- **Titles**: short and specific; series names and numbers (`Day [n] of [series]`).
- **First frame**: the feed shows the video, not a thumbnail — the first frame is the hook; text in
  it must be readable small.
- **Hook**: no intro; start mid-action.
- **Fails when**: there is no bridge to long-form; licensed music on everything (it splits revenue);
  long gaps in posting.

## music-artist

New in this repository; written for channels whose videos are an artist's music.

- **Identity tokens**: the artist name and release titles are kept verbatim in every title
  (`profile.identity_token`); demand data shapes only the descriptive words around them.
- **Cadence**: set by the release cycle — each release gets its main video(s) and a run of Shorts
  around it (teaser before, the strongest section on release, performance or behind-the-scenes
  after). Between releases: Hub formats that do not need new music (live, acoustic, studio, lyrics).
- **Pillars**: releases — official audio, video, lyric video, visualiser (Hero per release); recurring
  performance or studio formats (Hub); mixes, playlists and "music for [activity/mood]" videos where
  demand data shows search for them (Help).
- **Titles**: the recipe fixes the release title pattern and labels (e.g. `Artist – Title (Official
  Audio)`); this type only adds: search-led Help titles name the mood/activity keyword from seeds.
- **Thumbnail**: release artwork as the consistent anchor; for Help videos, the mood made visible.
- **Hook**: the song's strongest moment early — the first seconds of a Short are the chorus or the
  drop, not an intro. Each Short of a release has its own entry point and visual (artists.youtube:
  "Make Many Different Shorts for a Song"); the sound may repeat, the opening may not.
- **Measure**: the artist at the song level across all channels, not the own uploads' views. On an
  Official Artist Channel, Analytics for Artists separates "Official Artist Channel" (Art Tracks
  included) from "Other Channels" (fan videos whose main component is the song) (Help 18736729;
  youtube-studio `viewer-groups.md`): an artist whose songs grow there is not stalled. Music videos
  are compared only with the channel's own music videos.
- **Releases have their own cadence** (CONTRACT.md, rule 17): the creation recipe that makes them
  ("Create Music Release") owns their dates; `format-plan.md` lists (new, long) and the Shorts cut
  from a release as its pairs, with no stand-alone Short slots for Planning unless the owner wants
  some. Focus = the release pitched to Spotify editorial: one pitched release at a time, the pitch at
  least 7 days before release (Release Radar), better 2–4 weeks; the recipe's settings hold the
  rhythm (interval, focus every N, both leads).
- **Between releases**: YouTube's artist playbook — a trailer about two weeks before, Shorts with the
  official audio, the music video as their related video, a release playlist, fan Shorts featured
  after release (artists.youtube resources). YouTube publishes no release cadence number.
- **Fails when**: generic keywords replace the artist's name; releases go out without Shorts; the
  Shorts of one release open the same way; views come only in release weeks; mood/activity videos
  are made where no seed shows demand.
