# Brief 6 — YouTube Community

Follow [the rules of the set](README.md); this brief adds what is specific to Community.

**Name:** `YouTube Community` · **Scope:** global recipe, run inside the channel's own project ·
**Schedule:** weekdays, once a morning in the time zone of `profile:channel`'s country (cron `0 9 * * 1-5`, see
[Schedule](#schedule)) · **Reads from:** "YouTube Onboarding" (`profile:channel`, `format-plan.md`),
and its own `replied` records.

## What it is for

The comment section of one channel, handled once per comment, every weekday:

1. **Collect.** The comments that arrived since the last run, minus what the channel already
   handled.
2. **Triage and draft.** Each comment goes into one pile (answer, correct, thank, leave, hide,
   escalate); replies are drafted in the channel's voice; the pin, the hearts and the one to answer
   first are chosen.
3. **Mine.** Questions that several viewers ask become `community-ideas.md`; "YouTube Recon" reads
   every such file of the last 7 days as validated needs.
4. **Propose a post.** Optionally one community post or poll.
5. **Approve.** The owner sees everything that would become public and approves it.
6. **Act.** Approved replies and hides go through the Data API; approved pins, hearts, reports and
   the post go through Studio. Every action happens at most once and leaves a `replied` record.

What it leaves behind:

- **Records** (its own memory, through `youtube-records`): `replied:<commentId>:<action>`, one per
  action taken (`reply`, `pin`, `heart`, `hide`, `report`). This recipe is the only writer and the
  only reader of the kind.
- **Artifacts:** `comments.json`, `replies-draft.json`, `triage-summary.md`, `community-ideas.md`
  (read by "YouTube Recon"), `post-draft.md`, `approval.json`, `api-actions.json`,
  `publish-report.md`.
- **Committed intents** for every action, including the post, which has no record kind: the
  committed `post:community:<date>:<slug>` claim is the memory of the post.

### What the owner approves

The source brief says the recipe publishes **the approved replies**, and names no case where a reply
goes out without approval. So **nothing public goes out without the owner's approval in step 5**:

| Action | Approval |
| --- | --- |
| Reply (answer, correct, thank) | owner, in the step-5 batch |
| Pin | owner, in the step-5 batch; a video that already has a pin keeps it unless the owner approved replacing that one |
| Heart | owner, in the step-5 batch |
| Hide (cannot be undone) | owner, item by item in the step-5 batch |
| Report | owner, item by item in the step-5 batch |
| Community post or poll | owner, in the step-5 batch, with its exact text |
| Escalations | no action: listed for the owner to answer personally |

The step-2 validator is a quality gate on the drafts, not a replacement for the owner. Letting
routine replies go out on the validator alone is a change the owner has to ask for; it is not in
this recipe.

## Requirements (EARS) to put into the recipe

1. WHEN the run starts THEN system MUST read `profile:channel` from "YouTube Onboarding" (declared read), validate it with `records.py validate`, and MUST stop and report if it is missing or carries another version.
2. WHEN comments are collected THEN system MUST fetch them through `comments.py fetch`, passing the keys of this recipe's own `replied` records, so that comments already handled, the channel's own comments, and threads the channel already answered by hand are left out.
3. WHEN comments are collected THEN system MUST state the Data API units spent and whether older comments were left (`truncated`).
4. WHEN comments are triaged THEN system MUST put each fresh comment into exactly one pile (answer, correct, thank, leave, hide, escalate) and MUST state the count of each pile.
5. WHEN a reply is drafted THEN system MUST write it in the channel's voice (the owner's voice file, else the profile's `voice`), keep the profile's identity tokens verbatim, and MUST NOT state any fact, number, date, plan or collaboration that is not in the voice file, the profile or the video's own description.
6. WHEN a reply needs a fact only the owner has, or is a business, press, legal or crisis matter THEN system MUST escalate it to the owner and MUST NOT reply.
7. WHEN a reply or a post carries a link or a contact THEN system MUST take it from the project's `LINK_*` or `BUSINESS_EMAIL` config credentials, and MUST NOT type a link from memory.
8. WHEN triage completes THEN system MUST name at most one comment to pin per video and the one comment to answer first.
9. WHEN several viewers ask the same question THEN system MUST write it into `community-ideas.md` with its count and the comment ids, as a need, never as a promised video.
10. WHEN anything would become public (a reply, pin, heart, hide, report, post or poll) THEN system MUST send it to the owner with `send-message` and buttons, wait with `await-reply`, and MUST NOT act on what the owner did not approve.
11. WHEN an approved action is taken THEN system MUST take it through `intent.py` (directly, or through `comments.py`), at most once, and MUST NOT retry an action whose outcome is unknown.
12. WHEN an action is verified THEN system MUST write its `replied:<commentId>:<action>` record through `records.py write`, the reply's own id included for a reply.
13. WHEN a step drives Studio THEN system MUST pass the session check first, re-mint the session or request a sign-in when signed out, and MUST NOT act until it is signed in as the channel.
14. WHEN a run ends THEN system MUST report what was done, what was left for the next run and why, and every action whose outcome is unknown.

## Steps

The "Skills" column lists skills from the shelf, attached to that step. `youtube-records` is
attached to the recipe, as rule 2 says. Dependencies use `requiredStatus: "passed"`.

| # | Step | Who | Skills and tools on the step | Credentials | Writes |
| --- | --- | --- | --- | --- | --- |
| 1 | Collect fresh comments | AI | `youtube-community` | `YOUTUBE_REFRESH_TOKEN` | `handled.json`, `comments.json` |
| 2 | Triage and draft replies | AI | `youtube-community`; the owner's voice file pinned, if there is one | the `LINK_*` keys and `BUSINESS_EMAIL` that replies may carry | `replies-draft.json`, `triage-summary.md` |
| 3 | Mine ideas from questions | AI | `youtube-community` | — | `community-ideas.md` |
| 4 | Post or poll proposal | AI | `youtube-community`, `youtube-studio` | the `LINK_*` keys and `BUSINESS_EMAIL` that a post may carry | `post-draft.md` |
| 5 | Owner approval | AI + owner | — | — | `approval.json` |
| 6 | Replies and hides through the API | AI | `youtube-community`, `youtube-studio` | `YOUTUBE_REFRESH_TOKEN` | `api-actions.json`, `replied` records |
| 7 | Studio actions: pin, heart, report, post | AI (browser) | `youtube-studio` | `YT_STUDIO_SESSION` | `publish-report.md`, `replied` records |

Order: 1 → 2 → 3 → 4 → 5 → 6 → 7. Step 3 follows step 2 because it counts the repeated questions
triage already found, rather than classifying the comments a second time. Attempts about 3; wall
time about 30 minutes for the AI steps, 45 for step 7.

## Design notes per step

**1 — Collect fresh comments.**

1. Find the producer with `find-spec-template --name "YouTube Onboarding"` (declared with
   `declare-read` when the recipe is built). Read its `profile:channel` with `get-template-record`
   and check it with `youtube-records: scripts/records.py validate`. Missing, invalid or another
   `v` → stop and report; nothing below runs without the channel id.
2. Read this recipe's own `replied` records with `query-template-records --key-prefix replied:`
   (this run's Process id and Project id). Save their keys as a JSON list in `handled.json`.
3. Choose the day to read from, `since`: the earlier of the previous weekday (Friday on a Monday)
   and the day of the newest `at` among those records, but never more than 14 days back. Overlap
   with the last run is harmless: handled comments are dropped.
4. Run `youtube-community: scripts/comments.py fetch` with the profile's `channel_id`, `since`,
   `--handled-file handled.json` and `--include-held`, so that held and likely-spam comments reach
   the hide pile. Keep the default page budget. Do not write another client.
5. Save the output as it came as `comments.json`. Say `count`, `dropped`, `units_used`, and
   `truncated`: when it is true, name the oldest comment read and say older ones were left.

Known limit (from the skill): a new reply under a thread older than `since` is not seen. Say so in
the summary when `since` is the previous weekday.

**2 — Triage and draft replies.**

Follow `youtube-community/references/triage.md` (piles, pin and heart rules, reply rules, output
format) and `youtube-community/references/voice.md` (where the voice comes from).

1. The voice: the owner's voice file if it is pinned to this step; else the profile's `voice`,
   `audience` and `language`; else draft conservatively and say in the summary that a voice file
   would make the replies better.
2. Put every comment of `comments.json` into one pile. Unsure between answer and escalate →
   escalate.
3. Draft replies for the answer, correct and thank piles. Short, in the commenter's language when
   the voice file allows it, else `profile.language`. Identity tokens exactly as the profile spells
   them. A link only as the value of a declared `LINK_*` key, an address only as `BUSINESS_EMAIL`;
   a key that is not set is not linked.
4. Choose at most one pin per video (a top-level comment, never a reply, never self-promotion), at
   most 5 hearts, and the one comment to answer first (the most-liked question).
5. Caps of this recipe per run: 20 replies, 10 hides, 5 hearts. What is over a cap waits for the
   next run; say how many.
6. Write `replies-draft.json` in the format of `triage.md`, and `triage-summary.md`: the count per
   pile, the pin per video and why, the one to answer first, the escalations with their reason,
   the hide and report candidates with their reason, and the repeated questions with counts.

Declare on this step only the `LINK_*` keys the replies may carry: the ones the voice file's "Links
we share" names, or, without a voice file, the ones Onboarding set (ask the owner which at build
time; declaring a key the project does not hold makes every run pause). Declare `BUSINESS_EMAIL`
only if replies may point to it.

Validator rubric (pass at 7 of 10):
- every comment of `comments.json` is in exactly one pile, and the summary's counts add up to its
  `count`;
- every reply matches the voice source named in the summary (register, length, emoji rule, words
  never used), and keeps the identity tokens verbatim;
- no reply states a number, date, release, collaboration or fact that is not in the voice file,
  the profile or the video's description;
- no reply promises a video or a date;
- no reply contains personal data: no e-mail, phone, address or real name beyond the commenter's
  public display name, and no `BUSINESS_EMAIL` unless the voice file allows it;
- every link in a reply is the value of a declared `LINK_*` key; no other URL appears;
- business, press, legal, copyright and crisis comments are escalated, not answered;
- at most one pin per video, every pin a top-level comment;
- the caps hold, and what is left over is counted.

**3 — Mine ideas from questions.**

1. Take the repeated questions from `triage-summary.md` and the answer pile of `replies-draft.json`,
   as triage counted them (`youtube-community/references/triage.md`: "the same question from several
   people is a content idea"). Do not re-classify the comments.
2. Write `community-ideas.md`, one section per question asked by two or more viewers:
   - the question in one line, in the viewers' words;
   - the count, the comment ids and the videos;
   - the date range of the comments;
   - an angle in one sentence, marked as a need, not a promise.
3. A run with no repeated questions writes the file with "No repeated questions between <since>
   and <today>". Recon reads every file of the last 7 days and merges them; an explicit empty file
   contributes nothing.

The file is what "YouTube Recon" reads (`youtube-strategy/references/ideation.md`, "Optionally the
Community recipe's mined questions"), by this step's name, "Mine ideas from questions". This recipe
writes no `idea` record: Recon is their one writer.

Validator rubric:
- every listed question has a count of at least 2 and its comment ids;
- every comment id is in `comments.json`;
- no entry promises a video or a date.

**4 — Post or poll proposal.**

1. Propose a post only when the owner asked for one in the chat, or when the format plan names
   community posts and a repeated question from step 3 makes a fitting poll. Read `format-plan.md`
   from "YouTube Onboarding" with `list-step-artifacts --step-name "Formats and content pillars"`
   (same declared read as step 1); no such file → no post is proposed from the format plan, said so.
   At most one post a run.
2. Draft it in the channel's voice (`youtube-community/references/voice.md`), with the
   preconditions of `youtube-studio/references/community-post.md`: final text, poll options,
   links only from the declared `LINK_*` keys.
3. Write `post-draft.md`: type (text or poll), text, options, topic in a few words (it becomes the
   intent key's title), the publish date. No post → the file says "No post proposed" and why.

Declare `LINK_*` and `BUSINESS_EMAIL` here only for the keys a post may carry.

**5 — Owner approval.**

1. Nothing to approve (no reply, pin, heart, hide, report or post) → write `approval.json` with
   `{"nothing": true}` and send nothing.
2. Otherwise send one message with `send-message`, its text from a file: the numbered items grouped
   as replies (comment, then draft), pins (noting that an existing pin is kept unless the owner
   says to replace it), hearts, hides and reports (each with its reason; hide cannot be undone),
   the post with its exact text, and the escalations for the owner to answer personally. Buttons:
   "Approve all", "Replies only", "Nothing today". The owner may also answer in words: item numbers
   to drop, a reply rewritten, a pin to replace.
3. `await-reply`. Write `approval.json`: the approved items with their final text, the dropped ones,
   and the owner's words. An owner's rewrite is sent as the owner wrote it.
4. No answer before the wait ends → approve nothing. The comments stay unhandled and the next run
   reads them again.

**6 — Replies and hides through the API.**

1. For each approved reply: write its text to a file and run `youtube-community: scripts/comments.py
   reply`. For each approved hide: `comments.py hide`. The script runs `youtube-studio:
   scripts/intent.py` itself (claim, act, commit); do not call it separately here.
2. Read each answer as `youtube-community/SKILL.md` says:
   - `"acted": true` → write the record from its `record` field with `youtube-records:
     scripts/records.py write replied`, `reply_id` included for a reply;
   - `"acted": false`, `status: committed` → done in an earlier run; write the record from
     `claim.result` if it is missing;
   - `"acted": false`, `status: claimed` → never confirmed; do not retry, report it;
   - `"fallback": "studio"` → hand it to step 7;
   - `"uncertain": true` → outcome unknown; do not retry, report it.
3. Write `api-actions.json`: every action with its intent key, its outcome, and `units_used`.

**7 — Studio actions: pin, heart, report, post.**

1. Nothing approved for Studio and no fallback from step 6 → write `publish-report.md` from
   `api-actions.json` and do not open the browser.
2. Run the session check of `youtube-studio/references/session.md` against the profile's
   `channel_id`, with the `mcp__playwright-yt-studio__*` tools. Signed out and not re-minted → do not
   claim anything, list what is blocked, and end the step with the report.
3. Do each approved action with `youtube-studio/references/comment-actions.md`, under its own
   `youtube-studio: scripts/intent.py key pin|heart|report --comment-id`, `claim`, act only on
   `"act": true`, verify, `commit` (or `fail` when it certainly did not happen; leave it claimed when
   unsure). Then write `replied` with `youtube-records: scripts/records.py write replied --action
   pin|heart|report`.
   - Pin: read the current pin first; if there is one and the owner did not approve replacing it,
     do not claim, and report it.
   - Heart: an already-given heart is committed as `{"already": true}`, never clicked again.
   - Report: the reason chosen goes into the commit; if the comment was also hidden, it has a `hide`
     record from step 6 as well.
4. A Studio fallback for a reply or hide from step 6: the playbook's "Reply through Studio" or
   "Hide, when the API path is not available", under a new claim. The reply's id is read in the
   browser from the reply's own link (`lc=<parent>.<replyId>`); without it, commit the claim and
   leave the record unwritten, and report it — step 1's fetch already skips a thread the channel
   answered.
5. The approved post: `youtube-studio/references/community-post.md`, under `intent.py key post
   --date <publish date> --title "<topic>"`. A channel without a composer → `fail` with that reason
   and report.
6. One Studio action per browser lifetime when the session was refreshed in this run.
7. Write `publish-report.md`: every action of steps 6 and 7 with its intent key and outcome, the
   post's URL, what was left over a cap, what was blocked, every outcome still unknown, and the
   Data API units of the run.

## Data API quota per run

Rates from `youtube-community` (Data API quota table, read 2026-11-04): `commentThreads.list` and
`comments.list` 1 unit a page; `comments.insert` (reply) and `comments.setModerationStatus` (hide)
50 units each.

| Part | Units |
| --- | --- |
| `fetch`, 3 statuses (published, held, likely spam) × at most 10 pages | ≤ 30 |
| replies, at most 20 | ≤ 1,000 |
| hides, at most 10 | ≤ 500 |
| pins, hearts, reports, post (Studio) | 0 |
| **A full run** | **≤ 1,530** |

A quiet weekday spends a few units for the fetch and 50 per reply. The project's 10,000 units a day
are shared with every other recipe of the channel ("YouTube Daily data" runs daily), so the caps
stay as written; the report states the units spent from the scripts' `units_used`.

## Building it

1. Declare the one producer this recipe reads: `find-spec-template --name "YouTube Onboarding"`,
   then `declare-read` on it. Community reads no other recipe's memory or files (README rule 5).
2. After this recipe is published, wire its one reader back: find "YouTube Recon" with
   `find-spec-template --name "YouTube Recon"`, add a `declare-read` of "YouTube Community" to it,
   and apply that revision. Recon was built before Community and treats it as absent until then.

### Schedule

The schedule fires the whole recipe; the steps run in order inside each run.

1. Settle the project with the owner first, in their own words, resolve it with `list-projects`,
   and pass `--project-id` to `add-spec-template-schedule`. Read `effectiveProject` back and confirm
   it is the channel's project: a run in another project holds none of its credentials.
2. Weekdays in the morning, cron `0 9 * * 1-5`, in the time zone of `profile:channel`'s country —
   the zone every scheduled recipe of the set uses except Daily data, which runs on UTC.

## What changed from the source brief

| Source brief | Now |
| --- | --- |
| `google-api-python-client` for `commentThreads` and `comments.insert` | `youtube-community: scripts/comments.py fetch` / `reply` / `hide`, which call the API over HTTPS |
| `yt-comment` and `youtube` skills | `youtube-community` (triage, voice) and `youtube-studio` (Studio playbooks, intents) from the shelf |
| `records.py` pinned as a file and extended with a `replied` kind | the `youtube-records` skill on the recipe; `replied:<commentId>:<action>` already exists |
| `replied:<commentId>`, fields `action` reply\|pin, `replied_at`, `source: template6-community` | `replied:<commentId>:<action>`, one record per action (reply, pin, heart, hide, report), `at`, `reply_id` for replies, `source: community` |
| reads nothing from other recipes | reads `profile:channel` (channel id, voice, identity tokens) and `format-plan.md` from "YouTube Onboarding", declared |
| `ai-integration claim-intent` / `commit-intent`, `post:community:<date>` | `youtube-studio: scripts/intent.py`; post key `post:community:<date>:<slug>` (same day, same topic = same post) |
| piles answer / pin / ignore / escalate | answer, correct, thank, leave, hide, escalate; the pin is chosen apart from the piles |
| "the approved replies", no approval step | step 5: the owner approves every reply, pin, heart, hide, report and post |
| one publish step for API and browser | step 6 (API, no session) and step 7 (Studio), so the API part goes on when Studio is signed out |
| step 3 parallel to step 2 | step 3 after step 2: it reads triage's counts of repeated questions |
