# Channel settings, upload defaults, and what changes where

For the onboarding steps that recommend and apply settings (`channel-settings.md`), the analytics
step that recommends changes (`settings-reco.md`), and the steps that apply branding.

## What changes where

Data API facts from developers.google.com/youtube/v3 (`channels/update`, `channelBanners/insert`,
`watermarks`, `channelSections`), read 2026-11-04. Every write below is irreversible from the
recipe's point of view: it goes through an intent reservation, and browser work goes through
`youtube-studio`.

| Setting | Data API | Studio only | Notes |
| --- | --- | --- | --- |
| Channel name | — | Customization → Basic info | rate-limited by YouTube; owner decides |
| Handle | — | Customization → Basic info | rules in `channel-copy.md` |
| Description (About) | `apply_channel.py branding` (`channels.update` `brandingSettings.channel.description`) | also | ≤ 1,000 characters |
| Channel keywords | `apply_channel.py branding` (`brandingSettings.channel.keywords`) | Settings → Channel | space-separated, phrases in quotes |
| Country of residence | `apply_channel.py branding` (`brandingSettings.channel.country`) | Settings → Channel | a legal/monetisation fact about the owner, not a reach lever |
| Default language | `apply_channel.py branding` (`brandingSettings.channel.defaultLanguage`) | | the language of the channel's own title and description |
| Translations of name and description | `localizations.<lang>.title/description` | also | |
| Made for kids (channel default) | `status.selfDeclaredMadeForKids` | Settings → Channel → Advanced | legal declaration (COPPA); never guess, ask the owner if unclear |
| Trailer for non-subscribers | `apply_channel.py branding` (`brandingSettings.channel.unsubscribedTrailer`) | Customization → Layout | |
| Featured video for subscribers | — | Customization → Layout | |
| Home sections | `channelSections.*` (≤ 10 shelves) — not scripted | Customization → Layout | apply with `youtube-studio/references/home-tab.md`; verify the result on the page (`home-page.md`) |
| Banner | `apply_channel.py banner`: `channelBanners.insert` (16:9, ≥ 2048×1152, ≤ 6 MB, JPEG/PNG, 50 units), then `channels.update` with `brandingSettings.image.bannerExternalUrl` = the returned url | Customization → Branding | `banner_preview.py` output fits these limits |
| Profile picture | — | Customization → Branding | `avatar_preview.py` output; apply with `youtube-studio/references/channel-profile.md` |
| Video watermark | `apply_channel.py watermark` (`watermarks.set`); `watermarks.unset` not scripted | Customization → Branding | square, ≥ 150×150, < 1 MB; at the end (last 15 s), from a custom start, or the whole video (Help 10456525, read 2026-11-04) |
| Links, contact email | — | Customization → Basic info | values come from config credentials |
| Upload defaults | — | Settings → Upload defaults | see below |

**`channels.update` replaces the whole part.** Sending `brandingSettings` with only the field you
change deletes every other existing value in it (the API docs say so). Always `channels.list
part=brandingSettings` (or `localizations`, `status`) first, change the one field in that object,
and send the whole object back. Each `channels.update` costs 50 quota units. `apply_channel.py`
does exactly this; compose the request by hand only for what it does not cover (`localizations`,
`status`).

## Upload defaults (Studio → Settings → Upload defaults)

Studio only. They pre-fill uploads made in Studio. Whether an upload through the Data API inherits
them is not documented, so the creation recipes set every field explicitly and do not rely on them:

- **Visibility**: Private or Unlisted, so nothing goes public before its scheduled release.
- **Category**: the channel's category (Music for an artist).
- **Video language** and **title and description language**: the channel's language.
- **Licence**: Standard YouTube licence unless the owner chooses Creative Commons.
- **Tags**: a few identity terms (artist, series) only; the creation recipes add the rest per video.
- **Description**: a short footer — links line and subscribe line in the brand's voice; it is
  pre-filled, the per-video description goes above it.
- **Comments**: on, with "hold potentially inappropriate comments for review"; matches the
  community recipe's triage.
- **Audience (made for kids)** is a channel setting, not an upload default; set it once, correctly.

## Recommending settings (`channel-settings.md`, onboarding)

From the brand profile and the audience step:

```
Default language: <code>        Country of residence: <owner's, ask>
Made for kids: <no / yes — owner's declaration>
Keywords: <list>
Description: see channel-copy.md
Translations: <languages, only if the audience is known to need them>
Watermark: <the avatar mark or logo>, <end of video | whole video>
Upload defaults: visibility <private>, category <...>, language <...>, licence <...>, tags <...>,
                 description footer <...>, comments <...>
Apply by API: <fields>     Apply in Studio: <fields>
```

## Recommending changes from analytics (`settings-reco.md`)

The analytics recipe reads its own channel and audience data (`youtube-data`, `youtube-metrics`) and
recommends only what the data supports. Each recommendation names the data behind it, the setting,
the current and proposed value, and whether the API or Studio applies it.

- **Language and translations**: if a substantial and stable share of views comes from a language
  area other than the channel's language (geography and subtitle-language reports), propose
  translated title and description (`localizations`) for that language, and translated video
  metadata in the creation recipes. Not on one week's data.
- **Default language / category** mismatched with what the videos actually are: correct them.
- **Hashtags** (YouTube Help "Hashtags", support.google.com/youtube/answer/6390658, read
  2026-11-04): up to three are shown by the title; more than 60 on a video makes YouTube ignore all
  of them. Recommend a small fixed set (identity + niche) for the description footer.
- **Audience**: if returning viewers dominate and subscribers grow slowly, the trailer and the
  sections are the lever (`home-page.md`); if new viewers dominate, the featured video and the
  first shelf are.
- **Made for kids** and **country** are declarations, not optimisations: recommend a change only if
  the current value is wrong, and let the owner confirm.
- Never recommend a change only because it "may boost reach" without data in this report showing why.
