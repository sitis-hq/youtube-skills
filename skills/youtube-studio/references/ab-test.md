# Thumbnail A/B test (Studio "A/B Testing", formerly "Test & Compare")

Used by Planning & optimization (recipe 5, optional step). The Data API has no method for it
(resource list read 2026-11-04); the variants are prepared by youtube-metadata and measured by
youtube-thumbnail-check before this playbook runs.

## What YouTube decides, and how

From Google's help article "A/B test titles & thumbnails" (support.google.com/youtube/answer/13861714,
read 2026-11-04):

- Up to **three** thumbnails and/or titles: test thumbnail only, title only, or both.
- The winner is the option with the highest **watch time**; results are reported "based on watch time
  share". YouTube says it optimizes "for overall watch time over other metrics, like click-through-rate".
  **Do not judge a test by CTR** — a variant with more clicks and less watching loses, by design.
- Outcomes: **Winner**, **Performed Same**, **Inconclusive**. Without a clear winner, the first
  uploaded option stays.
- A test usually finishes within about two weeks.
- Desktop only, in Studio; the channel needs advanced features enabled.
- Not available for videos made for kids, for mature audiences, or private; not for Shorts,
  scheduled lives or premieres (a premiere becomes eligible after it ends).

## Preconditions

- Session check of `session.md` passed as the channel.
- The video is long-form, public or unlisted, not made for kids, no test already running on it.
- Two or three thumbnail files on disk, each one change away from the others (youtube-metadata's
  rule), passed by youtube-thumbnail-check.

## Steps

1. Key: `python3 <base>/scripts/intent.py key ab --video-id <id> --date <today>`; then
   `intent.py claim --key <key>`. Act only on `"act": true`.
2. Open `https://studio.youtube.com/video/<videoId>/edit` and run the session check (the video page
   must belong to the channel).
3. In the **Thumbnail** area click **A/B Testing**. If there is no such control, the feature is not
   offered for this channel or video: `intent.py fail --key <key> --reason "A/B Testing not offered"`
   and report — nothing happened.
4. Choose **Thumbnail only**, upload the files with the browser's file upload, in the order you want
   (the first is the fallback when the test is inconclusive — put the current thumbnail first).
5. **Done**, then **Save** on the video page.

## Verify

Reload the details page: the thumbnail area shows a test in progress with your variants. Analytics →
**Reach** shows "How your A/B test is going". Then `intent.py commit --key <key> --result-file r.json`
with `{"video_id", "started": "<date>", "variants": ["<sha256 prefix of each file>"]}`. If you cannot
tell whether Save went through, leave the claim as it is and report — do not start a second test.

## Reading the result (a later run)

Read-only, no intent. Open the video's Analytics → **Reach** → under "How your A/B test is going",
**Manage test**. Copy the outcome and each variant's watch-time share into the step's artifact
(`ab-test-<videoId>.json`). If the outcome is Winner, YouTube has already applied it; the step does
not change the thumbnail again. There is no record kind for tests; Planning reads the artifact.
