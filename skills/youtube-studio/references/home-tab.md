# Home page: featured videos and sections

Used by Onboarding (apply branding / sections). The plan of sections comes from youtube-channel-setup.

## API first (Data API v3 reference, read 2026-11-04)

- **Sections** — `channelSections.insert / update / delete`, 50 units each, scope `youtube` or
  `youtube.force-ssl`. At most 10 sections ("A channel can create a maximum of 10 shelves";
  `maxChannelSectionExceeded` beyond). The documented types are playlist-based (`singlePlaylist`,
  `multiplePlaylists`, `multipleChannels`); whether upload-list types (recent, popular, Shorts) can be
  inserted is not documented — make those in Studio.
- **Featured video for people who have not subscribed** (the trailer) —
  `brandingSettings.channel.unsubscribedTrailer` through `channels.update` (see `channel-profile.md`:
  the whole part is overwritten).
- **Featured video for returning subscribers** — no API.

Key every change with `intent.py key settings --area home-tab --state-file <home-plan.json>`, where
the file is the whole desired home tab (featured videos and the ordered sections).

## Studio

**Preconditions:** session check of `session.md`; `home-plan.json` with the ordered sections and the
two featured videos by video id.

1. Claim the key above.
2. Studio → **Customization** → **Home tab** (formerly "Layout").
3. Save the current layout as `home-tab-before.json`.
4. Featured video for non-subscribers and for returning subscribers: **Add** / **Change** → pick the
   video by id or title.
5. Sections: **Add section** for each missing one, remove the ones the plan drops, then order them
   as planned (drag, or the move controls). Studio shows its own limit on sections — follow it.
6. **Publish**.

**Verify:** reload the Home tab in Studio and compare with the plan; open
`https://www.youtube.com/channel/<channel_id>` and check the featured video and the first sections.
Commit with `{"sections": [...], "featured": {...}}`; on a refused Publish, `intent.py fail` with the
message.
