# YouTube skills

Skills, deterministic scripts and the shared memory contract for the recipes that run a YouTube
channel on Sitis: onboarding, daily data, recon and ideas, analytics, planning and optimization,
community. One repository so that a rule lives in one place: a recipe attaches the skills it needs,
and raising one pin on the shelf moves every copy.

## Skills

| Skill | What it gives a step |
| --- | --- |
| [`youtube-records`](skills/youtube-records/SKILL.md) | The memory contract between the recipes: record kinds, keys, units, one writer per kind; `records.py` validates and writes |
| [`youtube-data`](skills/youtube-data/SKILL.md) | Data API and Analytics API reads within quota, retention curves, transcripts, competitor thumbnails |
| [`youtube-metrics`](skills/youtube-metrics/SKILL.md) | Growth velocity and anomalies, candidate scoring, outliers both ways, retention diagnosis, title and thumbnail-text checks |
| [`youtube-thumbnail-check`](skills/youtube-thumbnail-check/SKILL.md) | Computer-vision measurements of a thumbnail: faces, contrast, colour, text density, mobile legibility |
| [`youtube-demand`](skills/youtube-demand/SKILL.md) | Keyword demand through DataForSEO: volume, CPC, web keyword difficulty, YouTube interest index, YouTube SERP competition |
| [`youtube-strategy`](skills/youtube-strategy/SKILL.md) | Channel strategy, idea generation, content calendar and analytics reports — output templates and dated thresholds |
| [`youtube-channel-setup`](skills/youtube-channel-setup/SKILL.md) | Brand profile, banner and avatar with device safe-area previews, About text, home page sections, channel settings |
| [`youtube-metadata`](skills/youtube-metadata/SKILL.md) | Titles, descriptions, tags, hashtags, chapters, Shorts metadata and thumbnail A/B tests |
| [`youtube-community`](skills/youtube-community/SKILL.md) | Comment triage, replies in the channel's voice, pinning, community posts |
| [`youtube-studio`](skills/youtube-studio/SKILL.md) | Browser playbooks for what the APIs do not offer, and irreversible actions behind an intent reservation |

## Layout

```
skills/<name>/SKILL.md        the skill: when to use it and how
skills/<name>/scripts/        its deterministic tools
skills/<name>/references/     knowledge loaded on demand
skills/<name>/tests/          tests of its scripts
lib/ytskills/                 Python shared by several skills' scripts
```

A run receives the pinned commit's whole tree, and its CLI reports each skill's own directory as
the skill's base. Scripts are therefore called by a path from that base
(`<base>/scripts/x.py`), never from the run's working directory, and a script that needs `lib/`
finds it relative to its own file.

## Rules of this repository

- **Only new commits on `main`. Never rewrite history.** Recipes pin commits; a commit that can no
  longer be fetched leaves every copy pinned to it without its skills, silently.
- **A script prints JSON on stdout and nothing else; diagnostics go to stderr; a refusal exits
  non-zero with a reason.** The agent reads the output, so its shape is the script's interface.
- **Python 3.11, standard library first.** A third-party package is allowed only when the platform
  shelf carries it as a pinned wheel: today `opencv-python-headless==4.14.0.94` and `numpy==2.2.6`
  (see [Dependencies](#dependencies)). Nothing here is installed by running code from this
  repository: there is no installer and there must not be one.
- **No secrets in a script's arguments or files.** A token comes from
  `ai-integration oauth-token --connection YOUTUBE` at the moment of use and is never written down.
- **A number carries its unit and date.** Thresholds in references name their source and the date
  they were read; a record field says whether it is a fraction or a percentage.
- **Code taken from elsewhere keeps its licence.** Each such file opens with its origin (repository,
  commit, licence) and what was changed; [`NOTICE`](NOTICE) lists them.
- **Every script has tests**, run by CI on Python 3.11 with the shelf's pins.

## Dependencies

| Package | Pin | Needed by |
| --- | --- | --- |
| `opencv-python-headless` | `4.14.0.94` | `youtube-thumbnail-check`, `youtube-channel-setup` previews |
| `numpy` | `2.2.6` | the same — the last numpy with a CPython 3.11 wheel |
| `google-api-python-client` | shelf pin | `youtube-data` |
| `yt-dlp` | shelf pin | `youtube-data` (transcripts, public thumbnails) |

`opencv-python` 5.x ships without the Haar cascades, so face detection fails there silently; the
non-headless build needs `libgl1`, which the worker image does not have.

## Tests

```bash
python3 run_tests.py
```
