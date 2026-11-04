# API or Studio: which path for which action

The browser is the fallback: an API call has a defined answer, a Studio click has a page that may have
changed. Use Studio only where no method exists, or where the API answered with a missing scope
(`403 insufficientPermissions`), which then points here.

The platform's YouTube connection asks for `youtube`, `youtube.force-ssl`, `yt-analytics.readonly` and
`yt-analytics-monetary.readonly`, so every method below is within its scopes.

| Action | Data API v3 method | Scope (any of) | Units | Studio playbook |
| --- | --- | --- | --- | --- |
| Reply to a comment | `comments.insert` (replies only; a top-level comment is `commentThreads.insert`) | `youtube.force-ssl` | 50 | `comment-actions.md` (fallback) |
| Hide a comment | `comments.setModerationStatus` (`rejected`; `heldForReview`; `published`, but never from rejected) | `youtube.force-ssl` | 50 | `comment-actions.md` |
| Pin, heart, report a comment | — | — | — | `comment-actions.md` |
| Community post or poll | — (no resource) | — | — | `community-post.md` |
| Thumbnail A/B test | — | — | — | `ab-test.md` |
| Set a video's thumbnail | `thumbnails.set` (Shorts: only after processing succeeded; 429 `uploadRateLimitExceeded`) | `youtube`, `youtube.force-ssl`, `youtube.upload` | 50 | — |
| Video title, description, tags | `videos.update` `part=snippet` (sends the whole snippet) | `youtube`, `youtube.force-ssl` | 50 | — |
| Channel description, keywords, country, language, trailer | `channels.update` `part=brandingSettings` (overwrites the whole part) | `youtube`, `youtube.force-ssl` | 50 | `channel-profile.md` |
| Banner | `channelBanners.insert` + `channels.update` | `youtube`, `youtube.force-ssl`, `youtube.upload` | 50 + 50 | — |
| Watermark | `watermarks.set` / `unset` | `youtube`, `youtube.force-ssl` | 50 | — |
| Profile picture, name, handle, links | — | — | — | `channel-profile.md` |
| Home sections (playlist types) | `channelSections.insert/update/delete` (≤ 10) | `youtube`, `youtube.force-ssl` | 50 | `home-tab.md` |
| Featured video for returning subscribers | — | — | — | `home-tab.md` |
| Upload defaults | — | — | — | `upload-defaults.md` |
| Impressions, impression CTR per video | Reporting API `channel_reach_basic_a1` | `yt-analytics.readonly` | (Reporting API quota) | `impressions-ctr.md` |

Quota: 10,000 units a day per Google Cloud project, shared by every method except `search.list` and
`videos.insert`, which have their own buckets (quota cost page, read 2026-11-04). Recipes of one
channel share one project, so a step budgets its writes (a run of 20 replies is 1,000 units).

Every row with a method is still an irreversible action: wrap it in `intent.py` like a Studio action.

Sources: developers.google.com/youtube/v3/docs (resource index), …/comments/insert,
…/comments/setModerationStatus, …/thumbnails/set, …/channels/update, …/channelBanners/insert,
…/channelSections/insert, …/determine_quota_cost — read 2026-11-04. `videos.update` and
`watermarks.set` scopes are from the reference as known, not re-read on that date.
