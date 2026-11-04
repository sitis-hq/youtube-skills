---
name: youtube-channel-setup
description: Setting up and tuning a YouTube channel's identity — brand profile, banner and profile picture (with device safe-area and small-size previews for the owner's approval), channel name, handle and About text, home page trailer and sections, channel settings and upload defaults, and which of these the Data API can change versus Studio only. Use in onboarding steps that define the brand, make the banner or avatar, write channel copy, plan the home page or recommend settings, and in analytics steps that recommend settings changes.
---

# YouTube channel setup

Knowledge for the onboarding steps that give a channel its identity, plus two scripts that prepare
the banner and the profile picture and show them the way YouTube crops them. Read the reference
that matches the step before writing anything:

| Step | Read | Produces |
| --- | --- | --- |
| Brand profile (tone, visual style, colours, naming) | `references/brand-profile.md` | `brand-profile.md`, the `profile` record |
| Banner and avatar: prompts, generation, evaluation | `references/banner-and-avatar.md` | prompts, generated images, previews, evaluation table |
| Channel copy: name, handle, About, links | `references/channel-copy.md` | `channel-copy.md` |
| Home page: trailer, featured video, sections | `references/home-page.md` | `intro-script.md`, `sections-plan.md` |
| Recommended settings (onboarding) and settings recommendations (analytics) | `references/settings.md` | `channel-settings.md` / `settings-reco.md` |
| Applying branding or settings | `references/settings.md` → "What changes where" | the change, through `youtube-studio` / the API under an intent reservation |

## Banner

```bash
python3 <base>/scripts/banner_preview.py <image> --out-dir <artifact dir>/banner [--fit cover|contain] [--format jpg|png]
```

Brings any image to 2560×1440 without distorting it: an image that is not 16:9 is refused until
`--fit cover` (crop the centre) or `--fit contain` (pad) is chosen — prefer regenerating at 16:9.
Writes `banner-upload.jpg` (under 6 MB), `banner-zones.png` (TV 2560×1440, desktop 2560×423,
tablet 1855×423, mobile/safe 1546×423, centred and labelled; everything outside the safe area
dimmed), `banner-desktop.png`, `banner-mobile.png` and `banner-phone.png` (the safe area at 390 px,
a phone's width). `detail.desktop_strip_edges_outside_safe` near 1 means detail — maybe text — sits
outside the safe area: look at `banner-zones.png`.

## Profile picture

```bash
python3 <base>/scripts/avatar_preview.py <image> --out-dir <artifact dir>/avatar [--fit cover|contain] [--sizes 98,48,36]
```

Brings the image to 800×800 (non-square refused without `--fit`), writes `avatar-upload.png`,
`avatar-circle.png` (the circle on YouTube's light and dark backgrounds), `avatar-sizes.png` (each
size at real pixel size) and `avatar-<N>.png`. `detail.edges_outside_circle` is the share of detail
in the corners the circle cuts off; `contrast_stddev_at_<N>px` near 0 means a flat dot when small.

Both scripts need `opencv-python-headless==4.14.0.94` attached (it brings numpy); without them they
refuse and name them. Output is JSON; exit 2 with `{"ok": false, "error": ...}` is a refusal.

## Approval

The owner approves the banner by seeing it **with and without the safe zone**: the step sends
`banner-upload.jpg` and `banner-zones.png` together (and `banner-phone.png` when text matters), and
for the avatar `avatar-circle.png` and `avatar-sizes.png`. Nothing is uploaded before the owner's
yes; uploading is an irreversible action (see `references/settings.md`).

## Memory and credentials

- Channel facts — id, title, language, country, niche, channel type, identity tokens, audience,
  voice — go to the `profile` record through `youtube-records` (`records.py write profile ...`).
  Never write that record by hand.
- Links (website, Spotify, Apple Music, socials) and the business email are **config credentials**
  of the project, declared by the recipe; if one is missing the run pauses and asks the owner. They
  are not records and are not invented.
- Everything else (palette, typography, prompts, copy, plans) is a step artifact file.
