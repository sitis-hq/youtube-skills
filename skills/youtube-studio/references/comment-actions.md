# Comment actions: pin, heart, hide, report — and a reply when the API cannot

Used by Community (recipe 6). Which comment gets which action is decided by youtube-community's
triage; this file is how the action is done once, safely.

| Action | API? | How |
| --- | --- | --- |
| Reply | yes — `comments.insert`, scope `youtube.force-ssl`, 50 units | `youtube-community/scripts/comments.py reply` (intent inside). Studio only as fallback, below |
| Hide (reject) | yes — `comments.setModerationStatus` `rejected`, `youtube.force-ssl`, 50 units | `comments.py hide`. Rejected cannot be set back to published |
| Pin | **no** | Studio / watch page, below |
| Heart | **no** | Studio, below |
| Report | **no** | Studio, below |

(Data API v3 reference, read 2026-11-04: the Comments resource has list, insert, update, delete and
setModerationStatus; nothing pins, hearts or reports.)

Every action below: build the key with `intent.py key <verb> --comment-id <id>`, `intent.py claim`,
act only on `"act": true`, verify, then `intent.py commit` (or `fail` when it certainly did not
happen; leave it claimed when unsure). Then write the `replied` record (see youtube-community).
First run the session check of `session.md`.

## Pin

A pin **replaces** the video's current pin, and the owner may have chosen that one. So before
pinning, read which comment is pinned now and put it in the step's report.

1. Open `https://www.youtube.com/watch?v=<videoId>&lc=<commentId>`. The comment shows at the top as
   **Highlighted comment**. Only top-level comments can be pinned — for a reply, stop and say so.
2. Check the page is signed in as the channel (account menu names the channel). If not, `session.md`.
3. Note the currently pinned comment, if any (its line reads "Pinned by …").
4. The highlighted comment's **⋮** menu → **Pin** → confirm in the dialog.
5. Verify: reload `https://www.youtube.com/watch?v=<videoId>` (without `lc`); the first comment reads
   "Pinned by <channel>" and is the one you pinned. Commit with
   `{"video_id", "replaced": "<previous pinned comment id or null>"}`.

## Heart

1. Open the comment in Studio: `https://studio.youtube.com/channel/<channel_id>/comments/inbox`, search
   or scroll to it — or use the watch page with `&lc=<commentId>`.
2. If the heart already shows as given, **do not click**: a second click removes it. Commit with
   `{"already": true}`.
3. Click the heart. Verify it shows as given after a reload, then commit.

## Hide, when the API path is not available

Studio comment **⋮** → **Remove** deletes the comment for everyone. "Hide user from channel" is a
different, stronger action that affects every future comment of that person — only on the owner's
explicit word, never from triage alone.

## Report

Studio comment **⋮** → **Report** → pick the reason that fits (spam or scam, harassment, …) → submit.
Verify the confirmation. Commit with `{"reason": "<the reason chosen>"}`. The `replied` record has no
`report` action; write `hide` if the comment was also removed, otherwise the report lives in the
claim's result and the step's report.

## Reply through Studio (fallback)

Only when `comments.py reply` answered `"fallback": "studio"`. Its key `reply:comment:<id>` was failed
by the script, so claim it again here.

1. Studio comments inbox → the comment → **Reply** → paste the drafted text → **Reply**.
2. Verify the reply shows under the comment, posted by the channel.
3. The `replied` record needs the reply's id. Read it with the API (1 unit):
   `comments.list part=snippet parentId=<top-level id>`, and take the channel's reply with this text.
   Commit with `{"reply_id": …, "via": "studio"}`.
