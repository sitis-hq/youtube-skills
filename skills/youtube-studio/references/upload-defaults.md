# Upload defaults

Used by Onboarding (apply settings). What the defaults should be comes from youtube-channel-setup as a
desired-state JSON file; this playbook applies it. **No API** sets upload defaults (Data API v3
reference read 2026-11-04: `channels.update` writes only `brandingSettings`, `invideoPromotion` and
`localizations`).

## Preconditions

- `upload-defaults.json` — only the fields to set, by their Studio names, e.g.
  `{"title": "…", "description": "…", "visibility": "Private", "tags": ["…"], "category": "Music",
  "license": "Standard YouTube License", "comments": "Allow all comments", "video_language": "English"}`.
- Session check of `session.md` passed.

## Steps

1. Key: `intent.py key settings --area upload-defaults --state-file upload-defaults.json`; claim.
   The key comes from the content: the same desired state is applied once, a changed one is new.
2. Studio → **Settings** (bottom of the left menu) → **Upload defaults**. Two tabs: **Basic info**
   (title, description, visibility, tags) and **Advanced settings** (license, category, comments,
   language, and others).
3. **Read the current values first** and save them as the step's artifact `upload-defaults-before.json`
   — the owner's only way back.
4. Change only the fields that differ from the desired state. Leave every other field as it was.
5. **Save**.

## Verify

Close Settings, open it again, read every desired field back and compare. All equal → commit with
`{"changed": ["field", …]}`. Save refused or a field did not stick → `intent.py fail --reason …` with
the field names, and report. Nothing to write in records: settings are not records (youtube-records).
