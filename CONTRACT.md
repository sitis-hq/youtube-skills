# The contract of the YouTube channel set

What every recipe of the set must keep, whoever changes it — the owner, the recipe editor or
"Improve Spec Templates". The recipes evolve on their own after real runs, and that is intended; this
page is what they must not lose while they do, because the recipes depend on each other through it.

The recipes were first built from briefs, kept at the git tag `briefs-v1`. Since then the live
recipes and their revision history are the source of truth for what each recipe does; this file is
the source of truth for how they fit together. A change that would break a rule here is a change of
the contract: change this file first, then every recipe it touches.

## The set

| Recipe | Runs | Reads from |
| --- | --- | --- |
| "YouTube Onboarding" | once per channel, by hand; steps 1–7 again when an audit shifts the niche (steps 8–18 close without acting) | Channel Audit, Planning |
| "YouTube Daily Data" | daily | Onboarding, Recon |
| "YouTube Recon" | weekly, Monday | Onboarding, Daily Data, Community, Planning, creation recipes |
| "YouTube Analytics" | weekly, Tuesday | Onboarding, Daily Data, Recon, Planning, Community, Channel Audit, creation recipes |
| "YouTube Planning" | monthly, the 1st | Onboarding, Daily Data, Recon, Analytics, Channel Audit, creation recipes |
| "YouTube Community" | weekdays | Onboarding |
| "YouTube Channel Audit" | quarterly, the 25th of the quarter's last month; first run by hand | Onboarding, Daily Data, Planning, creation recipes |
| "Create Music Release Mix" | by hand, when the owner starts a mix (Planning's slot or an idea) | Onboarding, Planning, Recon, Create Music Release |

The creation recipes ("Create Music Release", "Create Music Release Mix") publish videos and write
`publish` records. Recipes find each other by these exact names: `find-spec-template` ignores case
and matches a part of the name ("Create Music Release" also finds "Create Music Release Mix"), so
take only the result whose name equals the one wanted. Every schedule is cron in UTC; a recipe's
local hour is in `profile:channel`'s timezone (rule 16).

## Rules every recipe of the set follows

### 1. Everything in English

The recipe name, description, requirements, design, step names and step texts are all written in
English.

### 2. Tools come from the shelf, never by link

Attach every tool with `attach-from-shelf`. Use `attach-tool` with a URL only if the shelf does not
have the tool, and then tell the owner the tool is missing from the shelf.

A copy taken from the shelf moves when the owner raises the pin on the shelf. A tool attached by
link does not move, and stays on its old version.

The tools of this set on the shelf:

| Shelf entry | Kind | What it gives |
| --- | --- | --- |
| `youtube-records` | skill | the memory contract; `records.py` |
| `youtube-data` | skill | Data, Analytics and Reporting API reads; transcripts; thumbnails |
| `youtube-metrics` | skill | velocity, candidate scoring, outliers, retention, title checks, YPP |
| `youtube-thumbnail-check` | skill | thumbnail measurements and the judging checklist |
| `youtube-demand` | skill | DataForSEO requests and their normalisation |
| `youtube-strategy` | skill | strategy, ideation, calendar, analytics report, thresholds |
| `youtube-channel-setup` | skill | brand profile, banner and avatar previews, channel copy, settings, applying them |
| `youtube-metadata` | skill | titles, descriptions, tags, hashtags, chapters, A/B tests |
| `youtube-community` | skill | comment triage and replies |
| `youtube-studio` | skill | Studio playbooks and `intent.py` for irreversible actions |
| `dataforseo-mcp-server` | MCP | DataForSEO API (`api_request`) |
| `yt-dlp` | CLI | public video data, subtitles |
| `poyoapi` | CLI | image generation (`poyo`) |
| `opencv-python-headless` | library | needed by `youtube-thumbnail-check` and `youtube-channel-setup` previews; it brings numpy |

`playwright` and `ai-integration` are platform tools that every run has. Never attach them.

Attach each skill **to the step that uses it**, not to the whole recipe. The one exception is
`youtube-records`: attach it to the recipe, because most steps read or write records.

### 3. Scripts are called from the skill's own directory

The run tells the agent each skill's base directory. A step calls a script as
`python3 <base of skill>/scripts/<script>.py`, never as a path relative to the run's working
directory.

A step's text names the script and the command, for example
`youtube-data: scripts/data_api.py channels --mine`. Exact flags are left to the skill's own
`SKILL.md`, which the agent reads at run time.

**A step names every script it must run.** The agent reads a skill's `SKILL.md` to learn *how* to
call a script; whether to call it, it takes from the step. A script described only in the skill is
optional in the agent's eyes, and it will improvise instead (the first Onboarding run ranked niches
without the competition script that sat in the attached skill, and wrote its own DataForSEO client).
So:

- a step names each script it runs, as `<skill>: scripts/<script>.py` — in its subtasks or in its
  section of the recipe's design, which every run receives whole;
- a skill attached to a step is there because the step names one of its scripts or references; a
  skill attached with nothing named is a gap.

### 4. Memory goes only through `youtube-records`

- A step never writes a record by hand. It calls `records.py write <kind> …`, which validates the
  record and writes it.
- A step builds a key to look up with `records.py key`.
- When a step reads a record that another recipe wrote, it checks it with `records.py validate`.
- Each kind of record has one writer recipe. The full table is in
  `skills/youtube-records/SKILL.md`.

### 5. Reading another recipe

A recipe reads another recipe's memory or files only after declaring it.

1. Find the other recipe with `find-spec-template --name <name>`. It finds drafts and published
   recipes that have never run.
2. Declare it with `declare-read`.

The run context then gives the producer's id, and deleting the producer warns that this recipe
breaks.

A recipe never reads another it has not declared, not even by finding it by name. A producer that
is not declared, or has nothing yet, is absent: the reader says so in its run and goes on. A recipe
added to the set later declares itself in each existing recipe that reads it.

### 6. Credentials

A step declares exactly the keys it uses, with `declare-cred-key` on that step.

| Key | Kind | Who sets it | Used for |
| --- | --- | --- | --- |
| `YOUTUBE_CLIENT_SECRET` | secret | the owner uploads the OAuth client JSON on the project's Credentials page (Onboarding step 10) | the YouTube connection; a step that declares it learns whether it is held, never its value |
| `YOUTUBE_REFRESH_TOKEN` | secret | the worker, when the owner completes the Connect dialog (Onboarding step 11) | every API step; `ai-integration oauth-token --connection YOUTUBE` needs it declared |
| `GOOGLE_SESSION` | session | the owner signs in once in the worker's browser | Google Cloud console and Google Auth Platform |
| `YT_STUDIO_SESSION` | session | the owner signs in once at **`studio.youtube.com`** in the worker's browser | every Studio step; its browser tools are `mcp__playwright-yt-studio__*` |
| `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD` | secret | the owner, from DataForSEO's API Access page (not the website password) | `dataforseo-mcp-server` |
| `POYO_API_KEY` | secret | the owner | `poyo` image generation |
| `LINK_<NAME>` (e.g. `LINK_SPOTIFY`, `LINK_APPLE_MUSIC`, `LINK_INSTAGRAM`, `LINK_WEBSITE`) | config | Onboarding step 13, with `update-project-credentials` | links a recipe must put into descriptions or the About page |
| `BUSINESS_EMAIL` | config | Onboarding step 13, with `update-project-credentials` | the channel's business contact, for the About page and descriptions |
| `MUSIC_AI_GENERATED` | config | the first uploading step that finds it missing asks the owner once and sets it with `update-project-credentials --kind config` | `true`/`false`: this project's music is made with AI; every upload sets `status.containsSyntheticMedia` from it (YouTube Help 14328491) |

If none of a step's declared keys is usable, the run pauses and the owner is told; when only some are
missing, the run goes on and the owner is told which. A step needing a missing key stops and asks for
it — except a config key the table says a recipe sets after asking the owner once. A step never works
around a missing key.

A session or a link is never written into a record or an artifact.

### 7. Irreversible actions

Some actions on the channel cannot be undone: an upload, an update, a reply, a pin, a post, a change
of settings. Every such action goes through `youtube-studio: scripts/intent.py`, either directly or
through a script that calls it (`apply_channel.py`, `apply_video.py`, `comments.py`).

- The script claims the action before doing it and commits it after.
- If an earlier run already committed the action, the step skips it and says so.
- If the outcome of the action is unknown, the step does not retry. It reports what happened to the
  owner.

### 8. Studio steps check the session first

Before touching Studio, a step runs the check in `youtube-studio/references/session.md`. If the
check fails, the step re-mints the session or asks the owner to sign in. It never acts on a page it
is not signed in to.

### 9. The owner approves what will be seen in public

Prepare banner, avatar and channel copy, then send them to the owner with `send-message`. The
message carries the images or the text, with buttons. Then wait for the answer with `await-reply`.
Apply them only after the owner approves.

### 10. Validators

Turn on the step validator wherever the step's result must meet a rubric (a decision, a ranking, a
public text). The rubric says what must be true of
the step's artifacts, not how the step was done.

### 11. Who writes what

Each record kind has one writer (`skills/youtube-records/SKILL.md`). A step artifact that another
recipe reads is found by its recipe and step name (`list-step-artifacts --step-name`): renaming a
step that others read breaks them, so a rename is a change of the contract. The artifacts other
recipes read today:

| Artifact | Written by (recipe → step) | Read by |
| --- | --- | --- |
| `niche-decision.md`, `niche-candidates.json`, `channel-history.json` | Onboarding → "Niche selection", "Niche discovery" | Channel Audit |
| `audience-profile.md`, `format-plan.md`, `brand-profile.md`, `upload-defaults.md` | Onboarding → "Audience, language and region", "Formats and content pillars", "Brand profile", "Channel settings (desired state)" | Analytics, Planning, Community, creation recipes |
| `seed-keywords.json` (with `anchor`) | Onboarding → "Seed keywords" | Recon |
| `ctr-scale-check.md` | Daily Data → "Impressions and CTR" | Analytics, Planning, Channel Audit |
| `keywords.json`, `ideas.md`, `trend-radar.md` | Recon → "Keyword research and new seeds", "Idea backlog and idea status", "Trend radar" | Planning, creation recipes |
| `community-ideas.md` | Community → "Mine ideas from questions" | Recon |
| `report-<date>.md`, `settings-reco.md`, `settings-desired.json` | Analytics → "Weekly report", "Settings recommendations" | Planning |
| `audit-<quarter>.md`, `audit-decision.json` | Channel Audit → "Diagnosis and decision", "Owner review" | Planning, Onboarding, Analytics |
| the song's lyrics and theme | Create Music Release → "Create text content" | Create Music Release Mix |
| the master: the one `.wav` of the run; the summary's Subgenre row | Create Music Release → "Generate audio" | Create Music Release Mix |
| the clean 16:9 cover (`*cover-16x9*`) | Create Music Release → "Create cover images" | Create Music Release Mix |
| the 16:9 full video (`*16x9-full*.mp4`) | Create Music Release → "Create music videos" | Create Music Release Mix |

Each comes from the newest passed run of its step (`list-step-artifacts`, which returns exactly
that). File names changed over the recipe's life, so a reader matches the patterns above, never one
exact name.

### 12. Keywords belong to a niche

A `seed` record carries `niche` (required): `profile:channel`'s niche when it was written. A reader
uses only the seeds whose `niche` equals the profile's niche now. So a change of niche never deletes the old keywords — they stay as
history and come back if the channel returns to that niche — and never mixes them into the new one.

### 13. One audit decision counts at a time

`audit-decision.json` carries `audit_id` (the audit run's date) and, when it replaces a decision of
an earlier audit that was never answered, `supersedes` (that audit's id). A reader acts on a
decision only when its `audit_id` is the newest audit's and its `owner_answer.answer` is `accepted`
or `changed`. A newer audit makes every older decision history, answered or not. A decision
without `audit_id` is not a decision of this contract: re-run its audit's "Diagnosis and decision".

A seed's key is its term alone (`seed:<slug(term)>`), so a term measured again for a new niche is
rewritten with that niche: the old niche keeps every term the new one does not share.

### 14. Ideas go into work once

- Recon writes every `idea` with `production` (`skills/youtube-strategy/references/channel-types.md`,
  "Production"). A creation recipe declares which kinds it makes ("Create Music Release": `new` — it
  writes and generates a song from nothing; a `version` needs the released song's audio, which it
  does not take as input). "Create Music Release Mix": `compilation`, format long — a mix of the
  channel's own released songs, joined from their 16:9 videos.
- A creation recipe starts by offering what to make: Planning's next `planned` slot for it, if any
  (only a recipe without its own cadence — rule 17), then the ideas of its kinds with status
  `shortlisted` or `new` and no `take`, best score first, at most ten, one line each (title, hook,
  keyword, score). The owner picks one or names their own.
- Taking an idea writes `take:<idea>` (status `in-work`) through `records.py write take` before any
  other work; the video moves it to `published` (with `video_id`), abandoned work to `dropped`.
- Recon moves the idea by the take (`in-work` → `planned`, `published` → `published`, all takes and
  plans `dropped` → back to `shortlisted`); Planning plans nothing for an idea with a take
  `in-work`; the creation recipes never offer it again.
- The idea gives defaults, never answers: its title proposes the theme, its `hook` (how the video's
  first seconds open — not a line of the content) the opening of the video, its keyword the main
  keyword of the metadata, its thumbnail concept the thumbnail. An idea carries no story or script:
  every question the recipe asks the owner (the story, the approvals) stays, and the owner's answer
  wins. The `publish` record names the `idea` (and the `plan` or the `release`, when it came from
  one).

### 15. Changing a recipe

- Each change is a revision (`apply-template-revision`); a revision can be rolled back.
- A step that acts on the channel keeps its intent (rule 7); a step that reads another recipe keeps
  its `declare-read` (rule 5); a step's credential keys stay declared on that step (rule 6).
- A reader skips what `records.py validate` calls foreign (exit 3) and stops only on another
  version of a contract record.
- No fallbacks for data written before a field or rule existed: when the contract changes, the
  recipe that wrote the old data re-runs and writes it in the new shape.
- A writer whose past work predates a record re-runs once to write it. "Create Music Release"
  released songs before it wrote `publish`; its catalog step "Register published release videos",
  added to one finished instance and run once, writes a `publish` (`release` = the instance's Spec id)
  for each of those videos that is public. Such a `publish` names a release with no `release` record:
  it is a video that is out, with nothing to plan or move — not a broken link.
- A check of the whole set is a check against this file: each rule, for each recipe.

### 16. The audience's clock

`profile:channel` carries `timezone` (required): the main audience's IANA zone, such as
`America/New_York` — a country is not enough (the US has six). Onboarding writes it in "Audience,
language and region" with the audience's country, and "Create the channel" puts it into the profile.

- Every local hour a recipe uses — when a video goes public, when a step asks the owner — is in that
  zone. No step writes a zone or an offset of its own ("ET", "19:00 New York").
- A `plan` slot carries `time` (required, local HH:MM): Planning chooses the hour when it plans the
  slot, and the recipe that fills it publishes at the slot's date and time in that zone.
- A schedule is cron in UTC, worked out from `timezone` when it is set, for the time of year it is
  set; the platform has no zone on a schedule, so a local hour moves by one with daylight saving.
  The recipe says the local hour it means, so the owner can see the shift.

### 17. Releases with their own cadence

Some work has its own rhythm and outside constraints — a music release has a distributor date, a
pitch window and a package of videos around one day. The creation recipe that makes it owns its
releases and their dates; Planning does not plan them.

- **What it owns.** The recipe declares the (`production`, format) pairs it owns. "Create Music
  Release": (`new`, `long`) and the Shorts cut from its own releases. Onboarding's
  `format-plan.md` lists the owned pairs; Planning's cadence counts only its own work; Planning
  plans no slot for an owned pair. Everything else (mixes, performances, stand-alone videos) stays
  Planning's.
- **One record per release.** `release:<Spec id>` (`records.py schema release`): date, time (local
  HH:MM in `profile:channel`'s `timezone`), title (the song, not the YouTube title), `pitch_ok`,
  `pitch`, idea, status `held | committed | dropped`, `submitted_at`, `video_id`, `moves`. The date is a field, so
  it can move; the key is the instance.
- **Writing it.** The first write is `records.py write release … --if-absent`; every later change is
  `records.py update --key release:<Spec id> …`, which writes only if nobody changed it meanwhile
  and retries once. A lost condition exits 4: re-read and decide.
- **Ensure the release.** Every step that needs the date reads the record first. None → it proposes
  a date to the owner, writes the record, and goes on; another step writing it meanwhile (exit 4) →
  it reads and uses that one. This is the one rule for every release, including one synced onto a
  new revision half-way.
- **The date.** A release's date is occupied while it is active. The owner confirms date, time and
  whether the release may be pitched once, where the recipe asks for it; on confirm the recipe re-reads the channel's active
  releases and asks again if the date was taken meanwhile.
- **Committed.** The first external act — a scheduled upload, a distributor submit — sets
  `committed` before it happens. A held release may move freely; a committed one moves only by the
  owner on the platforms themselves, and the recipe then records the move (`moves`) without
  re-timing anything.
- **State.** `records.py state` gives `active`, `released` (committed, its date passed, and a
  `publish` naming the release) or `dropped` (status dropped, or held more than 14 days past its
  date — a committed release never drops on its own). A dropped release frees its date; its take
  counts as dropped.
- **Pitching.** The owner decides which releases may be pitched to Spotify editorial: `pitch_ok`,
  asked with the date, silence = no — a pitch is irreversible, and silence never opts into one. Any
  number of releases may be allowed. The pitch description is approved by the owner in the creation
  recipe and stored as `pitch` before the distributor submit; a release without it is not pitched,
  and nothing drafts one in its place. "Pitch a Song on Spotify" reads release records and never
  writes them; it keeps its own `pitched:<release Spec id>`. Pitches are never closer than 21 days:
  `records.py pitch-slot` over every pitch that may have happened (submitted, or claimed with no
  known outcome), in days of `profile:channel`'s timezone, per project. The slot limits pitches, not
  releases, which may come as often as the recipe makes them.
- **Planning** reads the releases of every declared creation recipe, treats active ones as occupied
  dates, plans nothing of its own on such a date unless the owner says so, and shows them as fixed
  rows in its calendar.
