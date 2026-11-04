---
name: youtube-studio
description: Browser playbooks for YouTube Studio jobs the APIs do not offer — impressions and CTR export (fallback to the Reporting API), thumbnail A/B tests, pinning, hearting and reporting comments, community posts and polls, upload defaults, channel profile and branding, home tab — with the Studio sign-in check, and `intent.py`, the at-most-once guard for every irreversible YouTube action (API or browser). Use before any step acts in Studio, and before any reply, pin, post, thumbnail, metadata or settings change on a channel.
---

# YouTube Studio

Two things live here: how a step does in Studio what the APIs cannot, and the guard that keeps any
irreversible action — through the API or the browser — from happening twice.

Call the scripts by their path from this skill's base directory: `python3 <base>/scripts/x.py`.

## Rules

1. **API first.** Before opening Studio, read `references/api-alternatives.md`: if a method exists,
   use it; Studio is for what has none, or for a `403 insufficientPermissions` that points here.
2. **Session check first, every time** — `references/session.md`. Signed out, wrong channel or a
   human check: `ai-integration ensure-session`, close the browser and retry once; otherwise
   `ai-integration request-browser-login` and stop the Studio part. Never type or ask for a password;
   never guess a result that was not read.
3. **Every irreversible action goes through `intent.py`**: key → claim → act only on `"act": true` →
   verify on YouTube → commit (or fail when it certainly did not happen). When you cannot tell
   whether it happened, leave the claim and report; a later check settles it, a retry could double it.
4. **Read before you change, verify after.** Save the current state of a settings page as an
   artifact before changing it, and read it back after saving.
5. **Find controls by meaning.** Labels below are Studio's as of 2026; take a snapshot and match the
   control's role and text. If a control does not exist, the feature is not offered: fail the claim
   with that reason and report.

## The intent helper

| Need | Command |
| --- | --- |
| The key of an intention | `python3 <base>/scripts/intent.py key <verb> --… ` |
| Claim before acting | `python3 <base>/scripts/intent.py claim --key <key>` |
| It happened and was verified | `python3 <base>/scripts/intent.py commit --key <key> --result-file r.json` |
| It certainly did not happen | `python3 <base>/scripts/intent.py fail --key <key> --reason "…"` |

Verbs and their keys (`intent.py key --help`): `reply|pin|heart|hide|report --comment-id` →
`<verb>:comment:<id>`; `post --date --title` → `post:community:<date>:<slug>`;
`ab --video-id --date` → `ab:video:<id>:<date>`; `thumbnail --video-id --file` and
`branding --part banner|avatar|watermark --file` → keyed by the image's content;
`settings --area channel|upload-defaults|home-tab --state-file` and `metadata --video-id --state-file`
→ keyed by the desired state's canonical JSON. A key not built by `key` is refused.

`claim/commit/fail` take the run's ids from the `Process id` and `Project id` lines of
`current-task.md` (or `--spec-template-id`, `--project-id`). Claim answers: `act: true` → do it once;
`status: committed` → already done, skip and say so (its `result` is what that run journaled);
`status: claimed` → an earlier attempt was never confirmed — do not act, check and report.

## Playbooks — read the one you need

| Job | Recipe | Read |
| --- | --- | --- |
| Signing in, checking the channel, asking for a login | all | `references/session.md` |
| Impressions and impression CTR per video | Daily data | `references/impressions-ctr.md` — Reporting API `channel_reach_basic_a1` first; Studio export + `scripts/studio_reach.py` as fallback |
| Thumbnail A/B test (start, read result) | Planning & optimization | `references/ab-test.md` — winner by watch-time share, never by CTR |
| Pin, heart, hide, report a comment; reply via Studio | Community | `references/comment-actions.md` |
| Community post or poll | Community | `references/community-post.md` |
| Upload defaults | Onboarding | `references/upload-defaults.md` |
| Channel settings, picture, name, handle, banner, watermark | Onboarding | `references/channel-profile.md` |
| Home tab: featured videos, sections | Onboarding | `references/home-tab.md` |

## `studio_reach.py`

`python3 <base>/scripts/studio_reach.py --csv "Table data.csv" --as-of <day> --video <id> …` turns a
Studio Advanced-mode export into the fields of `records.py write studio`: CTR percent → fraction from
the header, Total row skipped, every expected video a row (`available=false` when absent). A CTR
header without `%` needs `--ctr-unit`; it refuses rather than guess.

## What a recipe declares for this skill

- A browser session record on each Studio step: `YT_STUDIO_SESSION` in this set's recipes (its browser
  is `mcp__playwright-yt-studio__*`). Onboarding creates it with the owner's sign-in.
- `YOUTUBE_REFRESH_TOKEN` on steps that use the API path.
- Nothing to attach for the browser: Playwright is a platform tool.
