# Recipe briefs for the YouTube channel set

Each file here is a brief for the AI Spec Template Editor: what one recipe does, its steps, and for
every step the skills, credentials and records it uses. The owner attaches the brief to the editor
chat. The editor builds the recipe from it with its own commands (`add-spec-task-template`,
`attach-from-shelf`, `declare-cred-key`, `declare-read`, `update-spec-template`,
`apply-template-revision`, `publish-spec-template`, `add-spec-template-schedule`).

The briefs live in the same repository as the skills they name, so a brief and the skills it
relies on come from one commit and cannot drift apart.

| # | Brief | Runs | Reads from |
| --- | --- | --- | --- |
| 1 | [Onboarding](01-onboarding.md) | once per channel, by hand; steps 1–7 again when an audit shifts the niche | Channel Audit |
| 2 | [Daily data](02-daily-data.md) | daily | Onboarding, Recon |
| 3 | [Recon, trends and ideas](03-recon.md) | weekly, Monday | Onboarding, Daily data, Community, Planning, creation recipes |
| 4 | [Analytics](04-analytics.md) | weekly, Tuesday (a day after Recon) | Onboarding, Daily data, Recon, Planning, Community, Channel Audit, creation recipes |
| 5 | [Planning and optimization](05-planning.md) | monthly | Onboarding, Daily data, Recon, Analytics, Channel Audit, creation recipes |
| 6 | [Community](06-community.md) | weekdays | Onboarding |
| 7 | [Channel Audit](07-channel-audit.md) | quarterly; the first run by hand after Onboarding of an existing channel | Onboarding, Daily data, Planning, creation recipes |

The exact recipe names, which the briefs use to find each other: "YouTube Onboarding", "YouTube Daily
data", "YouTube Recon", "YouTube Analytics", "YouTube Planning", "YouTube Community", "YouTube Channel
Audit". A creation
recipe (such as "Create Music Release") publishes videos and writes `publish` records.

## Rules every recipe of the set follows

The editor applies these to every recipe. A brief repeats one of them only where the step needs
something more specific.

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

- a brief names, step by step, each script the step runs, as `<skill>: scripts/<script>.py`;
- a skill attached to a step is there because the step's text names one of its scripts or
  references; a skill attached with nothing named is a gap in the brief;
- the table [Scripts and the steps that run them](#scripts-and-the-steps-that-run-them) below lists
  every script of the set with the briefs and steps that run it. `python3 run_tests.py` checks it
  against the scripts in `skills/` and against the briefs: a new script needs a row, and a brief that
  names a script must be cited in its row.

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

A recipe never reads another it has not declared, not even by finding it by name. When a producer
does not exist yet as the reader is built (the briefs are built in order 2 → 7), the reader is built
without that read and treats the producer as absent, saying so in its run. The producer's brief then
tells the editor to add the `declare-read` to each earlier reader it names, so the set is complete
once the last brief is built.

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

If a declared key is missing when the step runs, the run pauses and asks the owner for it. A step
never works around a missing key.

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

Turn on the step validator wherever the brief gives a rubric. The rubric says what must be true of
the step's artifacts, not how the step was done.

## Scripts and the steps that run them

A row cites `<brief>: <steps>`. "Inside" means another script runs it, and no step calls it directly.

| Skill | Script | Run by |
| --- | --- | --- |
| `youtube-channel-setup` | `apply_channel.py` | 1: 16, 17; 5: 7, 8 |
| `youtube-channel-setup` | `avatar_preview.py` | 1: 12 |
| `youtube-channel-setup` | `banner_preview.py` | 1: 12 |
| `youtube-community` | `comments.py` | 6: 1, 6 |
| `youtube-data` | `analytics.py` | 1: 18; 4: 2, 3, 4, 6, 7; 5: 5; 7: 2, 3, 4, 5 |
| `youtube-data` | `channel_baselines.py` | 1: 1; 3: 9; 7: 2, 6 |
| `youtube-data` | `data_api.py` | 1: 11, 18; 2: 1; 3: 2, 4, 5, 10; 4: 4, 5, 11; 5: 1, 5; 7: 2 |
| `youtube-data` | `reporting.py` | 1: 11; 2: 3; 4: 6; 5: 5; 7: 3 |
| `youtube-data` | `thumbnails.py` | 3: 8; 5: 6, 8 |
| `youtube-data` | `transcript.py` | 3: 7; 4: 7; 5: 6 |
| `youtube-demand` | `dfs.py` | 1: 1, 3, 6; 3: 2, 3, 10; 5: 6; 7: 6 |
| `youtube-demand` | `niches.py` | 1: 1; 3: 9; 7: 6 |
| `youtube-demand` | `normalize.py` | 1: 6; 3: 3, 10; 5: 6 |
| `youtube-demand` | `yt_competition.py` | inside `niches.py` and `normalize.py` |
| `youtube-metadata` | `apply_video.py` | 5: 7, 8 |
| `youtube-metadata` | `check_metadata.py` | 1: 13; 5: 4, 6 |
| `youtube-metrics` | `candidates.py` | 3: 4 |
| `youtube-metrics` | `chapters.py` | 5: 6 |
| `youtube-metrics` | `deadair.py` | 4: 8 |
| `youtube-metrics` | `retention.py` | 4: 8; 5: 5; 7: 4 |
| `youtube-metrics` | `swipe.py` | 1: 1; 3: 6, 7; 4: 9; 5: 5; 7: 2 |
| `youtube-metrics` | `title.py` | 3: 11; 4: 9; 5: 4, 6 |
| `youtube-metrics` | `velocity.py` | 2: 2 |
| `youtube-metrics` | `ypp.py` | 1: 18; 4: 4 |
| `youtube-records` | `records.py` | 1: 6, 7; 2: 1, 2, 3; 3: 1, 4, 10, 11; 4: 1; 5: 1, 2, 4; 6: 1, 6, 7; 7: 1 |
| `youtube-strategy` | `score_idea.py` | 3: 11; 5: 3 |
| `youtube-studio` | `intent.py` | 1: 16, 17; 4: 12; 5: 9; 6: 6, 7 |
| `youtube-studio` | `studio_reach.py` | 2: 3 |
| `youtube-thumbnail-check` | `analyze_thumbnail.py` | 3: 8; 5: 6 |