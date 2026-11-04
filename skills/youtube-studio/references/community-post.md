# Community post or poll

Used by Community (recipe 6) and by Onboarding or a release, when a post is planned.

**No API.** The Data API v3 has 20 resource types and none of them is a post (reference index read
2026-11-04); the old channel bulletins (`activities.insert`) were withdrawn. So a post is made in the
browser, under an intent, and only the agent's verification proves it went out.

## Preconditions

- The post's text (and the poll options, or the image file) are final — drafted in the channel's
  voice by youtube-community, approved if the recipe asks for approval.
- Links in the post come from the project's config credentials (channel links), never typed from
  memory.
- Session check of `session.md` passed.

## Steps

1. Key: `intent.py key post --date <publish date> --title "<topic in a few words>"`, then
   `intent.py claim`. Act only on `"act": true`. The same topic on the same day is the same post; a
   rerun skips it.
2. Open the channel's Posts tab while signed in as the channel:
   `https://www.youtube.com/channel/<channel_id>/posts` (YouTube renamed the "Community" tab
   "Posts"). Alternatively Studio's **Create** (top right) → **Create post**.
3. If there is no composer, the channel cannot post yet: `intent.py fail --reason "posts not offered
   to this channel"` and report.
4. In the composer: paste the text; for a poll pick the poll type and fill the options; for an image
   use the image type and upload the file. Respect the limits the composer shows.
5. **Post** (or **Schedule** with the time the plan gives, in the channel's time zone).

## Verify

Reload the Posts tab: the newest post (or, for a scheduled one, the scheduled list) carries your
text. Open it through its timestamp link and copy its URL (`https://www.youtube.com/post/<postId>`).
Commit: `intent.py commit --key <key> --result-file r.json` with `{"post_url", "post_id", "scheduled_for"}`.
If the page errored after you clicked **Post** and the post is not visible, do not post again: leave
the claim and report — a later check settles it.

## Record

No record kind holds posts: the committed claim is the memory of the post (a rerun meets it), and the
step's `publish-report.md` lists the URL and the intent key. The `publish` kind is for videos only.
