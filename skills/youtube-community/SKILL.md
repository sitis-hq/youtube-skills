---
name: youtube-community
description: Comment triage and replies for one's own YouTube channel — fetch fresh comment threads since a day within quota, drop what was already handled, sort into piles (answer, correct, thank, leave, hide, escalate), choose what to pin, draft replies in the channel's voice, post replies and hide spam through the Data API under an intent so nothing happens twice, and write the `replied` records. Use in the Community recipe, or whenever a step reads, answers, pins or moderates the channel's comments or prepares a community post.
---

# YouTube community

The comment section, handled once per comment. Data API for reading, replying and hiding; Studio
(youtube-studio) for pinning, hearts, reports and community posts, which have no API.

Call scripts by their path from this skill's base directory: `python3 <base>/scripts/comments.py`.
It needs youtube-studio's `scripts/intent.py` beside it in the tree (it is, in a run).

## 1. Collect

1. Read this recipe's `replied` records (its own memory; keys `replied:<commentId>:<action>`) and save their
   keys as a JSON list, e.g. `handled.json`.
2. `python3 <base>/scripts/comments.py fetch --channel-id <profile.channel_id> --since <day> --handled-file handled.json`
   - `--since`: the last run's day (overlap is harmless — handled comments are dropped).
   - `--include-held` also reads held-for-review and likely-spam threads, for the hide pile.
   - `--full-replies` reads every reply of busy threads (1 unit a page); without it only the replies
     YouTube returns inline are seen.
   - `--max-pages` (default 10, 1 unit each); `"truncated": true` means older comments were left.
3. The output's `items` are the fresh comments (top-level and follow-up replies, newest first);
   `dropped` counts what was left out and why; `units_used` is the quota spent. Save it as
   `comments.json`.

Known limit: threads come newest-first by their top-level comment, so a new reply under a thread
older than `--since` is not seen. The owner sees those in Studio.

## 2. Triage and draft

Read `references/triage.md` (the piles, pin and heart rules, reply rules, output format) and
`references/voice.md` (where the voice comes from and the voice file's format). Write
`replies-draft.json` and the summary. Never invent a fact; escalate instead.

## 3. Act — each action once

| Action | How |
| --- | --- |
| Reply | `python3 <base>/scripts/comments.py reply --comment-id <id> --video-id <id> --text-file reply.txt` |
| Hide (reject; cannot be undone) | `python3 <base>/scripts/comments.py hide --comment-id <id> --video-id <id>` |
| Pin, heart, report, reply via Studio | youtube-studio `references/comment-actions.md` |
| Community post or poll | youtube-studio `references/community-post.md` |

`reply` and `hide` claim the intent key (`reply:comment:<id>`, `hide:comment:<id>`), call the API, and
commit; they take the run's ids from `current-task.md`. Their answers:

- `"acted": true` → write the record from its `record` field:
  `python3 <records-base>/scripts/records.py write replied --comment-id … --video-id … --action reply --at … --reply-id … --source community`.
- `"acted": false` → done earlier (`status: committed`; write the record from `claim.result` if it is
  missing) or never confirmed (`status: claimed`; do not retry, report it).
- `"fallback": "studio"` → the API lacks the scope; do it with the Studio playbook under a new claim.
- `"uncertain": true` → the outcome is unknown; do not retry; report the comment to the owner.

Budget: each reply or hide is 50 units of the project's 10,000 a day. Cap replies per run; say what
was left.

## Records

Writes `replied:<commentId>:<action>` (youtube-records: `comment_id`, `video_id`, `action` reply|pin|heart|hide|report,
`at`, `reply_id` for replies, `source` = `community`). One record per action: a comment answered and
then pinned has a `reply` record and a `pin` record. Reads only its own `replied` records and the
`profile` record.

## What the recipe declares

`YOUTUBE_REFRESH_TOKEN` on the collect and act steps; `YT_STUDIO_SESSION` on the step that pins,
hearts or posts; the voice file, if the owner has one, pinned to the triage step.
