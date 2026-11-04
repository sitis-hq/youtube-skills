# Comment triage

<!-- Derived from youtube-agent-skill, skills/yt-comment/SKILL.md
     (https://github.com/Jakeschincariol/youtube-agent-skill, commit a2feb2104981a375ffd4f87ee04f4f5344ac43c6,
     MIT, Copyright (c) 2026 Jake Schincariol). Rewritten: the four piles are kept and extended with
     moderation and escalation; the voice file moved from ~/.claude to the recipe (voice.md); the
     "nothing publishes" gate is replaced by the intent bracket; "heart generously" is limited because
     a heart is a browser action here; the unsourced claim about the first hours was dropped. -->

Sort every fresh comment before writing anything, and say how many landed in each pile. The count is
part of the step's summary: a run that answered 3 of 40 questions should say so.

## The piles

| Pile | What lands here | What the step does |
| --- | --- | --- |
| **answer** | A real question about the video, the music, the channel, where to find something | Draft a reply. Count repeats: the same question from several people is a content idea |
| **correct** | Someone points out a mistake | If you can check it and they are right, thank them and say so plainly. If you cannot check it, escalate — never argue a fact |
| **thank** | Praise, a story, a personal reaction | Reply to a few, briefly, naming something specific from their comment. Identical thank-yous to many read as automated |
| **leave** | Bait, provocation, trolling, arguments between viewers, one-word noise | No reply, no comeback, however deserved. Count them and move on |
| **hide** | Spam, scams ("message me on…", fake giveaways), impersonation of the channel, hate, doxxing | `comments.py hide` (irreversible). Impersonation and scams are also reported (Studio) |
| **escalate** | Business or collaboration offers, press, legal or copyright claims, a viewer in crisis, anything that needs a fact only the owner has | No reply. Put it in the summary with the reason for the owner |

A comment goes to one pile. When unsure between **answer** and **escalate**, escalate: a missing
reply costs little; a wrong one is public.

## Pin, heart, first

- **Pin one per video, at most** — the question most viewers share, or a comment that adds what the
  video lacks (a correction, a timestamp, the answer to the top question). Never self-promotion,
  never a reply (only top-level comments can be pinned). A pin replaces the current pin, which the owner
  may have chosen: when the video already has a pinned comment, propose the change in the summary
  instead of pinning, unless the recipe explicitly allows replacing pins.
- **Heart** a few praise comments and the ones you answer. Hearts have no API: each is a browser
  action under an intent, so keep the number small (the recipe may set a cap).
- **Answer first** the comment with the most likes among the questions; name it in the summary.

## Writing a reply

- Answer in the first sentence. Short: about 30 words is the upstream rule of thumb (yt-comment), a
  heuristic, not a measured threshold.
- In the channel's voice (`voice.md`); in the commenter's language when the voice file allows it,
  otherwise the channel's language (`profile.language`).
- At most one question back, and only a real one.
- Emoji only if the voice file allows them.
- **Never invent**: no numbers, dates, release plans, collaborations or facts the owner has not stated
  in the voice file, the profile or the video's own description. If the answer needs one, escalate.
- **Never promise a video.** A request for a video is an idea for Recon, not a commitment.
- Links only from the project's config credentials (the channel's links), never typed from memory.

## Never twice

Three guards, each for a different failure:

1. `comments.py fetch` drops comments with a `replied` record, the channel's own comments, and
   threads the channel already answered by hand — a later run does not see them.
2. The intent key (`reply:comment:<id>`, `pin:comment:<id>`, …) stops a second action when a run is
   repeated before its record was written.
3. The `replied` record is written right after a verified action, from the `record` the script
   prints: `records.py write replied --comment-id … --video-id … --action … --at … [--reply-id …]
   --source community`.

When `reply` or `pin` answers `"acted": false` with `status: committed`, the action happened in an
earlier run: write the `replied` record from the claim's `result` if it is missing, then move on.

## Output of the triage step

`replies-draft.json` — one entry per fresh comment:

```json
{"comment_id": "...", "video_id": "...", "pile": "answer", "reply": "text or null",
 "pin": false, "heart": true, "first": false, "language": "en", "why": "one line"}
```

and a summary: the count per pile, the comment to pin per video and why, the one to answer first, the
escalations with their reason, and the repeated questions (with counts) for idea mining.

## Quota

`fetch` costs 1 unit a page; each reply and each hide costs 50 (Data API quota table, read
2026-11-04). The channel's project has 10,000 units a day shared with every other recipe — the step
caps replies per run (20 replies = 1,000 units) and says how many it left for the next run.
