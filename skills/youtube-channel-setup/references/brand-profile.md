# Brand profile

The brand profile is what every later step reads when it writes a title, designs a thumbnail,
generates a banner or answers a comment. It is short, concrete and decided — options belong in the
conversation with the owner, not in the profile.

## What to ask the owner

Ask only what earlier steps (niche, audience, formats) did not settle. Group the questions in one
message with your recommendation for each, so the owner can answer "yes" to most.

1. **Who the channel is** — a person, an artist, a band, a brand, a faceless series. Whether a real
   face appears in the banner, avatar and thumbnails.
2. **Name** — the channel name as it should appear, and the handle they want (rules in
   `channel-copy.md`). Names that must never be changed by keyword optimisation: the artist, the
   series, the show — these become `identity_token`s.
3. **Audience** — one sentence: who watches, where, in which language.
4. **Voice** — how the channel speaks in titles, descriptions, posts and replies: formal or casual,
   first person or "we", humour or not, emoji or not, words it never uses. Give two example
   sentences in that voice: the community recipe uses them when it drafts replies.
5. **Visual style** — photographic, illustrated, 3D, typographic; references the owner likes
   (channels, covers, artists). Existing assets: a logo, cover art, press photos, fonts.
6. **Colours** — two or three brand colours and one accent, as hex.
7. **Links** — which links the channel shows. These are stored as config credentials of the
   project, not in the profile; ask for the ones the recipe declares and missing.

## What the profile file contains

`brand-profile.md`, an artifact of the step:

```
Channel: <name>  (@handle wanted: <handle>)
Type: <music-artist | ...>   Identity tokens: <names never rewritten>
Audience: <one sentence>   Language: <code>   Main country: <code>
Voice: <one sentence>  Examples: "<sentence>" / "<sentence>"   Never: <words, tones>
Visual style: <one line>   References: <2-3>
Palette: <#hex primary>, <#hex secondary>, <#hex accent>  (checked against light and dark themes)
Typography: <one heavy sans-serif for thumbnails/banner text, one for body if any>
Face: <yes: who / no>
Logo or mark: <exists: where / to make: what>
```

## What goes to memory

The facts other recipes need go to the `profile` record through `youtube-records`:
`channel_id`, `title`, `language`, `country`, `niche`, `channel_type`, `identity_token` (repeat the
flag), `audience`, `voice`. Run `records.py schema profile` first. `channel_id` exists only after
the channel is created; until then the profile lives as the file and the record is written by the
step that knows the id.

Palette, typography and visual style are not record fields: later steps read them from
`brand-profile.md`.

## Rules of thumb

- Two or three colours, used everywhere (banner, avatar, thumbnails, end screens): recognition in
  the feed comes from repetition, not from any one asset.
- Choose colours for contrast against both YouTube themes (white and near-black) and against each
  other; a palette that only works on white fails half the viewers.
- Colour meanings are cultural and weak. Pick by the genre's conventions and the owner's taste; do
  not justify a palette with "blue raises trust by N %" — there is no reliable number behind such claims.
- A music artist's identity is the artist: their name stays verbatim in every title and the visual
  style follows the cover art.
