# Channel copy: name, handle, About, keywords, links

Partly rewritten from youtube-seo-skills `youtube-seo-channel` (commit 779b0f13, MIT). Corrected
here: the channel description is limited to 1,000 characters, not "1,000–5,000"; its "Knowledge
Graph entities" and translation-lift percentages are dropped.

## Name

- The name people will search for and say aloud. For an artist, the artist's name exactly as on
  streaming platforms; for a series or brand, its name. Keywords do not belong in the name.
- Short: it is cut in search results, comments and on phones. Check how it looks next to the avatar
  at 36 px.
- Changing the name is a Studio action (Customization → Basic info) and YouTube limits how often it
  can change (YouTube Help states a limit of changes per 14 days; verify the current rule on the
  page before planning a change). The Data API cannot change it.

## Handle

From YouTube Help "Handles guidelines" (support.google.com/youtube/answer/11585688), read 2026-11-04:

- 3–30 characters (Han/Hangul 1–10, Ethiopic/Hiragana/Katakana 2–20).
- Letters or digits of a supported language, plus `_`, `-`, `.` and `·` — not at the start or end.
  Not URL-like or phone-number-like. Not case-sensitive. One handle per channel; it must be free.
- Prefer the name itself, then the name with a short qualifier (`music`, `official`, the country)
  over digits and underscores. Propose three in order; the owner checks availability in Studio.
- A handle is set in Studio or the YouTube app, not through the Data API.

## About (channel description)

Limit: 1,000 characters (Studio's counter; consistent across current guides, 2026-11-04). The
description shows in the channel's "more about this channel" panel and in channel search results,
where only the first line or two is visible — so the first ~150 characters carry the whole pitch.

Structure, in the brand's voice:

1. One sentence: who this is and what the viewer gets ("Original lo-fi beats for study and sleep,
   new track every Friday").
2. Who it is for and what to expect: formats, series, themes — two or three sentences that naturally
   contain the main search terms of the niche (from the `seed` records), without stuffing.
3. The rhythm: when new videos come out.
4. Where else to find the channel (the links themselves go in the links section) and one call to
   subscribe.
5. Business contact line if the owner wants one (the email itself is a config credential).

Write it in the channel's main language; add translations only for audiences the analytics show.

Settable through the Data API (`brandingSettings.channel.description`) or in Studio.

## Channel keywords

A list of terms describing the channel (Studio → Settings → Channel → Keywords; API
`brandingSettings.channel.keywords`, space-separated, multi-word terms in double quotes). Their weight
in ranking is not documented and is likely small; they still help classify a new channel.

- 10–15 terms: the identity tokens (artist, series), the niche, the genre or topic, the main seed
  terms, the language if it is a selling point.
- No competitors' names, no unrelated trending terms.

## Links

Up to the links the owner wants shown (website, Spotify, Apple Music, socials, merch). They are
config credentials of the project: read them from there, never invent or guess a URL; if one is
missing, the run pauses and asks. Links are set in Studio (Customization → Basic info); the Data API
does not set them. Order: the one action you most want first (for an artist: the streaming link).

## `channel-copy.md`

```
Name: <name>
Handle: @<first choice> / @<second> / @<third>
About (<n>/1000 chars):
<text>
Keywords: <term> "<multi word term>" ...
Links (from config credentials): <label> -> <credential key>, ...
```
