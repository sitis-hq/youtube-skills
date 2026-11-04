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
| Applying branding or settings | `references/settings.md` → "What changes where", then "Applying" below | the change, through `apply_channel.py` or a `youtube-studio` playbook, under an intent reservation |

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

Both scripts need `opencv-python-headless` (4.8+ or 5.x) attached (it brings numpy); without them they
refuse and name them. Output is JSON; exit 2 with `{"ok": false, "error": ...}` is a refusal.

## Approval

The owner approves the banner by seeing it **with and without the safe zone**: the step sends
`banner-upload.jpg` and `banner-zones.png` together (and `banner-phone.png` when text matters), and
for the avatar `avatar-circle.png` and `avatar-sizes.png`. Nothing is uploaded before the owner's
yes; uploading is an irreversible action (see `references/settings.md`).

## Applying

After the owner's yes, the API half is one script; each command claims its intent key itself
(`settings:channel:<desired state>`, `branding:banner|watermark:<file>`), so a repeated run skips.

```bash
python3 <base>/scripts/apply_channel.py branding --desired <desired.json> [--dry-run]
python3 <base>/scripts/apply_channel.py banner --image <artifact dir>/banner/banner-upload.jpg
python3 <base>/scripts/apply_channel.py watermark --image <mark.png> --timing offsetFromEnd --offset-ms 15000 [--duration-ms N]
```

- `desired.json` holds only the fields to set, out of `description` (≤ 1,000 characters),
  `keywords` (≤ 500), `country`, `defaultLanguage`, `unsubscribedTrailer`. The script sends the
  whole `brandingSettings` part back, so nothing else is lost; `"changed": false` means nothing
  differed and nothing was claimed. Run `--dry-run` first and show the owner the diff.
- The banner must already fit YouTube's limits (`banner_preview.py` output does); a watermark is a
  square PNG/JPEG, ≥ 150×150, under 1 MB. Both are refused before any claim otherwise.
- `"uncertain": true` → do not retry; check the channel on YouTube and tell the owner.
  `"fallback": "studio"` → the connection lacks the scope: do it with the named playbook.
- Pass `--spec-template-id` and `--project-id`, or run where `current-task.md` names them. The
  output reports `units_used` (channels.list 1, each write 50).

Home sections and the profile picture are not here: they stay with the Studio playbooks
(`youtube-studio/references/home-tab.md`, `youtube-studio/references/channel-profile.md`).

## Memory and credentials

- Channel facts — id, title, language, country, niche, channel type, identity tokens, audience,
  voice — go to the `profile` record through `youtube-records` (`records.py write profile ...`).
  Never write that record by hand.
- Links (website, Spotify, Apple Music, socials) and the business email are **config credentials**
  of the project, declared by the recipe; if one is missing the run pauses and asks the owner. They
  are not records and are not invented.
- Everything else (palette, typography, prompts, copy, plans) is a step artifact file.
