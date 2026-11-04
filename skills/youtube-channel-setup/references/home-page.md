# Home page: trailer, featured video, sections

Partly rewritten from youtube-seo-skills `youtube-seo-channel` (commit 779b0f13, MIT).

## Video spotlight

Studio → Customization → Layout → Video spotlight has two slots:

- **Channel trailer** for visitors who have not subscribed. Settable in Studio, or through the Data
  API as `brandingSettings.channel.unsubscribedTrailer` (a video id).
- **Featured video** for returning subscribers — usually the newest release or the current best
  video. Studio only.

A new channel has no video for either slot yet: plan the trailer, and set the slots once videos exist.

## Trailer (`intro-script.md`)

A short video (30–90 s) that sells the channel to someone who just landed on it. It plays without
sound on many devices, so the picture and on-screen text must carry it.

1. **0–5 s** — the strongest image or sound of the channel and who it is for, in one line.
2. **5–25 s** — what they will get: two or three concrete things (series, formats, the kind of music),
   shown, not listed.
3. **25–45 s** — why this channel: a moment from the best video, a result, a recognisable face or sound.
4. **End** — the rhythm ("new track every Friday") and the invitation to subscribe.

For a music artist the trailer can be a cut of the best tracks with the artist's name and the release
rhythm on screen. Give the trailer a description in the channel's voice that repeats the About pitch.

## Sections (`sections-plan.md`)

The home tab shows shelves in the order chosen in Studio → Customization → Layout. The Data API
also manages them (`channelSections.insert/update/delete`, at most 10 shelves per the API docs,
read 2026-11-04; types `singlePlaylist`, `multiplePlaylists`, `popularUploads`, `recentUploads`,
`allPlaylists`, `liveEvents`, `upcomingEvents`, `completedEvents`, `multipleChannels`,
`subscriptions`). Whether a write through the API shows in the current home layout is not verified:
after a write, read the home page or `channelSections.list` and fall back to Studio.

Order the shelves by what a new visitor needs:

1. **Popular uploads** — social proof, once there are enough videos to rank.
2. **The active series or release playlists** — the binge path; one shelf per series.
3. **Recent uploads** — freshness.
4. **Shorts**, if the channel posts them.
5. **Topic or mood playlists** — for a music channel: by album, mood or use (study, sleep, workout).
6. **Live / upcoming**, only when the channel streams.

Keep fewer, fuller shelves: an empty or two-video shelf looks abandoned. A new channel starts with
recent uploads and one series playlist, and the plan says when to add the rest (e.g. "add Popular
at 10 videos").

### Playlists behind the shelves

- A title a viewer would search for or recognise (the series name, "Lo-fi for studying").
- A one- or two-sentence description with the main term in the first line.
- Ordered to be watched in sequence (series order, or the strongest first) rather than by date.
- Each video can end-screen to the next one in its playlist, so a session continues.

## `sections-plan.md`

```
Trailer (non-subscribers): <planned video / id>      Featured (subscribers): <rule, e.g. newest release>
Shelves now: 1. <type> <playlist> ...
Shelves later: <shelf> when <condition>
Playlists to create: <title> — <description> — <first videos>
```
