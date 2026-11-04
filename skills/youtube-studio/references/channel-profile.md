# Channel settings and branding

Used by Onboarding (apply branding, apply settings). The content — texts, banner, avatar, settings —
is prepared by youtube-channel-setup; this file says how each change is made once. **API first**:
the browser only for what has no method.

## What the API can do (Data API v3 reference, read 2026-11-04)

| Change | Method | Units | Notes |
| --- | --- | --- | --- |
| Description, keywords, country, default language, trailer for non-subscribers | `channels.update` `part=brandingSettings` | 50 | Overwrites **every** mutable property of the part: read `channels.list part=brandingSettings` first and send all values back, changed or not |
| Localized title/description | `channels.update` `part=localizations` | 50 | Needs the default language set |
| Banner | `channelBanners.insert`, then `channels.update` with `brandingSettings.image.bannerExternalUrl` = the returned url | 50 + 50 | 16:9, at least 2048×1152, 2560×1440 recommended, at most 6 MB |
| Watermark | `watermarks.set` / `watermarks.unset` | 50 | |

Scopes: `youtube` or `youtube.force-ssl` (banner also `youtube.upload`) — the platform's YouTube
connection carries both. Each call is an irreversible change: key it with
`intent.py key settings --area channel --state-file <desired.json>` or
`intent.py key branding --part banner --file <banner.png>`, claim, call, read back, commit.

## What only Studio can do

Profile picture, channel name, handle, links on the channel, contact email; and the channel-level
"audience" default (made for kids) in Settings.

**Preconditions:** session check of `session.md`; the files and texts from youtube-channel-setup; for
name or handle, the owner's explicit approval in the recipe — Studio limits how often they can change
and shows the limit in the dialog; read it there before acting.

**Steps:**

1. Key: picture → `intent.py key branding --part avatar --file <avatar.png>`; texts and links →
   `intent.py key settings --area channel --state-file <profile.json>`. Claim.
2. Studio → **Customization** → **Profile** (Studio merged the former "Branding" and "Basic info"
   tabs; if you see those, use them).
3. Read the current values and save them as `channel-profile-before.json`.
4. Picture: **Change** → upload → adjust the crop if asked → **Done**. Texts and links: edit only
   the fields that differ.
5. **Publish** (top right). Nothing is applied until Publish.
6. Audience default: **Settings** → **Channel** → **Advanced settings** → the audience choice → **Save**.

**Verify:** reload Customization and read the fields back; open the public channel page
`https://www.youtube.com/channel/<channel_id>` and check the picture and name show (the picture can
take a while to propagate — say so rather than retrying the upload). Commit with the fields changed.
If Publish failed, `intent.py fail` with the error text.

Settings and links are not records: links are config credentials of the project (youtube-records).
