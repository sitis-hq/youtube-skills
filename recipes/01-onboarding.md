# Brief 1 — YouTube Onboarding

Follow [the rules of the set](README.md); this brief adds what is specific to Onboarding.

**Name:** `YouTube Onboarding` · **Scope:** global recipe, run inside the channel's own project ·
**Schedule:** none — started by hand, once per channel · **Reads from:** no other recipe.

## What it is for

It takes a brand-new, empty channel-project to a working channel in four moves:

1. **Strategy.** It chooses the niche, the audience, the formats and the brand, all from data.
2. **Wiring.** It sets up a Google Cloud project, an OAuth application in production, the connected
   channel, a Studio session, and a Reporting API job.
3. **Assets.** It prepares the banner, the avatar, the copy and the settings, and the owner approves
   them.
4. **Application.** It applies the approved assets and settings to the channel.

Every later recipe of the set stands on what Onboarding leaves behind:

- **Records** (memory, through `youtube-records`):
  - one `profile:channel` record;
  - a set of `seed:<term>` records.
- **Artifacts:**
  - `audience-profile.md`;
  - `format-plan.md`;
  - `brand-profile.md`;
  - `channel-settings.json`, the desired state that was applied.
- **Credentials and sessions:**
  - `YOUTUBE_CLIENT_SECRET`;
  - `YOUTUBE_REFRESH_TOKEN`;
  - `GOOGLE_SESSION`;
  - `YT_STUDIO_SESSION`;
  - the `LINK_*` config keys.
- **A Reporting API job** for `channel_reach_basic_a1`. Daily data reads impressions and
  impression click-through rate (CTR) from it, with no browser. The job collects only from the day
  it is created, so Onboarding creates it as early as the connection allows.

## Requirements (EARS) to put into the recipe

1. WHEN discovery runs THEN system MUST rank niche candidates by views per day of age, from real YouTube results.
2. WHEN a niche is chosen THEN system MUST record the choice, the rationale and the main risks.
3. WHEN the audience, formats and brand are defined THEN system MUST produce `audience-profile.md`, `format-plan.md` and `brand-profile.md` as durable artifacts.
4. WHEN seed keywords are produced THEN system MUST write each one as a `seed` record through `records.py`, with `kd_web` on DataForSEO's 0–100 scale and `yt_interest` marked as an index.
5. WHEN the channel exists THEN system MUST write the `profile:channel` record, with channel id, title, language, niche, channel type and identity tokens.
6. WHEN a Google admin page or Studio shows a signed-out state THEN system MUST re-mint the session or ask the owner to sign in, and MUST NOT act until it is signed in.
7. WHEN the Google Cloud project is set up THEN system MUST enable YouTube Data API v3, YouTube Analytics API and YouTube Reporting API in a project dedicated to this channel, and MUST publish the OAuth app to production.
8. WHEN the channel is connected THEN system MUST verify API access, and MUST ensure the Reporting API job `channel_reach_basic_a1` exists.
9. WHEN the live admin UI differs from what the recipe expects THEN system MUST record the difference in `admin-drift.md`.
10. WHEN banner and avatar candidates exist THEN system MUST send the owner the upload image AND the device safe-area preview, and MUST NOT apply anything before the owner approves.
11. WHEN the channel's links are collected THEN system MUST store them as `LINK_*` config credentials of the project.
12. WHEN branding or settings are applied THEN system MUST apply each change at most once, through `intent.py`, and MUST verify the result on YouTube.
13. WHEN onboarding ends THEN system MUST state the distance to the YouTube Partner Program (YPP) thresholds, with the date they were read.

## Steps

The "Skills" column lists skills from the shelf, attached to that step. `youtube-records` is
attached to the recipe, as rule 2 says.

| # | Step | Who | Skills and tools on the step | Credentials | Writes |
| --- | --- | --- | --- | --- | --- |
| 1 | Niche discovery | AI | `youtube-demand`, `youtube-metrics`, `dataforseo-mcp-server` | `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD` | `niche-candidates.json` |
| 2 | Niche selection | AI + owner | `youtube-strategy` | — | `niche-decision.md` |
| 3 | Audience, language and region | AI | `youtube-strategy`, `youtube-demand`, `dataforseo-mcp-server` | DataForSEO keys | `audience-profile.md` |
| 4 | Formats and content pillars | AI | `youtube-strategy` | — | `format-plan.md` |
| 5 | Brand profile | AI + owner | `youtube-channel-setup`, `youtube-strategy` | — | `brand-profile.md` |
| 6 | Seed keywords | AI | `youtube-demand`, `dataforseo-mcp-server` | DataForSEO keys | `seed` records, `seed-keywords.json` |
| 7 | Create the channel | owner + AI | — | `GOOGLE_SESSION` | `channel-created.md`, `profile:channel` record |
| 8 | Google Cloud project and APIs | AI (browser) | — | `GOOGLE_SESSION` | `gcp-setup-notes.md`, `admin-drift.md` |
| 9 | OAuth application to production | AI (browser) | — | `GOOGLE_SESSION` | `oauth-consent-notes.md`, `admin-drift.md` |
| 10 | OAuth client and `YOUTUBE_CLIENT_SECRET` | AI (browser) + owner | — | `GOOGLE_SESSION` | `oauth-client-notes.md` |
| 11 | Connect the channel, Studio session, Reporting job | owner + AI | `youtube-data`, `youtube-studio` | `YOUTUBE_REFRESH_TOKEN`, `YT_STUDIO_SESSION` | `connection-check.md` |
| 12 | Banner and avatar | AI + owner approval | `youtube-channel-setup`, `poyoapi`, `opencv-python-headless` | `POYO_API_KEY` | chosen images, previews, `asset-decision.md` |
| 13 | Channel copy and links | AI + owner approval | `youtube-channel-setup`, `youtube-metadata` | — | `channel-copy.md`, `LINK_*` config credentials |
| 14 | Home page plan | AI | `youtube-channel-setup` | — | `home-plan.md` |
| 15 | Channel settings (desired state) | AI | `youtube-channel-setup` | — | `channel-settings.json`, `upload-defaults.md` |
| 16 | Apply branding | AI | `youtube-channel-setup`, `youtube-studio`, `opencv-python-headless` | `YOUTUBE_REFRESH_TOKEN`, `YT_STUDIO_SESSION` | `branding-apply-report.md` |
| 17 | Apply settings, home page, upload defaults | AI | `youtube-channel-setup`, `youtube-studio` | `YOUTUBE_REFRESH_TOKEN`, `YT_STUDIO_SESSION` | `settings-apply-report.md` |
| 18 | Monetization readiness | AI | `youtube-metrics`, `youtube-strategy`, `youtube-data` | `YOUTUBE_REFRESH_TOKEN` | `monetization-checklist.md` |

## Design notes per step

**1 — Niche discovery.**
- Search the owner's topic with the YouTube organic SERP through DataForSEO. The request shape is in
  `youtube-demand/SKILL.md`, and every call passes `noAiMode: true`.
- Rank the videos with `youtube-metrics: scripts/candidates.py`, by views per day of age.
- The Data API is not connected yet, so the channel-median baseline may be missing. The script lists
  those channels as `need_baseline`, and the step accepts that.

**2 — Niche selection.**
- Weigh viability, competition and durability with `youtube-strategy` (`references/strategy.md`).
- Present the top 2–3 niches to the owner with buttons, then wait for the answer.
- Validator rubric: one niche chosen, with a rationale grounded in step 1's numbers and at least two
  named risks.

**3–4 — Audience, formats.**
- Use the output templates of `youtube-strategy` (`strategy.md`, `calendar.md`).
- `audience-profile.md` names:
  - the persona;
  - the language and region;
  - the expected CPM/RPM band, marked as an estimate with its source.
- `format-plan.md` names:
  - the pillars;
  - the role of each format (long, Shorts, live);
  - a cadence the owner can keep.

**5 — Brand profile.**
- Follow `youtube-channel-setup/references/brand-profile.md`.
- The brand profile is the place for palette, typography, visual style and voice.
- It also names the channel type: one of the names in
  `youtube-strategy/references/channel-types.md`.
- It also names the identity tokens: names kept verbatim in every title, such as an artist, a
  series or a show.
- The owner confirms the name and the identity tokens.

**6 — Seed keywords.**
1. Through DataForSEO, call Labs `keyword_ideas` / `keyword_overview` for volume, CPC, KD and intent.
2. Call Trends explore with `type: youtube` for the interest index. For rising queries, call it with
   exactly one keyword.
3. Save the raw responses as files.
4. Run `youtube-demand: scripts/normalize.py` on them. Each row it prints carries the arguments for
   `records.py write seed`; write every row.
5. Write `seed-keywords.json`, mirroring what was written.

Validator rubric:
- at least 20 seeds;
- every seed has `as_of` and `source`;
- `kd_web` is on 0–100;
- no seed is a duplicate under a different spelling.

**7 — Create the channel.**
1. The owner creates the channel: YouTube's terms, the captcha and the phone check mean the agent
   cannot. The step gives the owner a precise checklist, matching the brand's name and @handle.
2. The step verifies the channel in the browser under `GOOGLE_SESSION`.
3. Then it writes `profile:channel` with `records.py write profile`. The fields:
   - `channel_id` and `title`;
   - `language`, `country` and `niche`, from steps 2–3;
   - `channel_type`, `audience`, `voice` and `identity_token`, from step 5.

**8–10 — Google Cloud, OAuth app, OAuth client.**
- These keep the previous recipe's proven path. They drive the browser under `GOOGLE_SESSION` and
  follow rule 8, applied to Google's consoles.
- Step 8 enables three APIs: YouTube Data API v3, YouTube Analytics API, and **YouTube Reporting
  API**. Reporting is new: Daily data reads impressions and CTR from it.
- Step 9 sets the branding pages to `https://sitis-hq.github.io/` (`/privacy`, `/terms`, domain
  `sitis-hq.github.io`). It uploads no logo: a logo forces Google's verification.
- Step 9 requests the scopes `youtube`, `youtube.force-ssl`, `yt-analytics.readonly` and
  `yt-analytics-monetary.readonly`, then publishes the app to production. An app left in testing
  gets refresh tokens that live 7 days.
- Step 10 creates a Desktop-app OAuth client. The owner uploads its JSON on the project's
  Credentials page, in the "Connect to YouTube" row. The agent never sees the secret.
- Every difference from the expected screens goes into `admin-drift.md`.

**11 — Connect, Studio session, Reporting job.**
1. The owner completes the Connect dialog. They paste the `http://127.0.0.1:8085/?…` address after
   consent; the page not loading is expected. The worker then seals `YOUTUBE_REFRESH_TOKEN`.
2. The owner signs in once at `studio.youtube.com` in the worker's browser, and records the session
   under the site `studio.youtube.com` (see `youtube-studio/references/session.md`).
3. The step verifies the API with `youtube-data: scripts/data_api.py channels --mine`. The channel id
   it returns must equal the one in `profile:channel`.
4. The step verifies Studio with the session check, against that channel id.
5. The step runs `youtube-data: scripts/reporting.py ensure-job` and records the job id in
   `connection-check.md`.

**12 — Banner and avatar.**
- The design rules are in `youtube-channel-setup/references/banner-and-avatar.md`.
- Render with `poyo`. Always use the newest GPT Image model available at run time: list the models,
  pick the newest `gpt-image-*`, and never write a version into the recipe. Prompts are plain
  natural language.
- Run every banner candidate through `youtube-channel-setup: scripts/banner_preview.py`, and every
  avatar candidate through `scripts/avatar_preview.py`.
- Send the owner, per candidate:
  - for the banner: `banner-upload` and `banner-zones` together;
  - for the avatar: the circle preview and the small sizes.
- Wait for the owner's choice. Do not upload anything in this step.

Validator rubric:
- the chosen banner is 2560×1440 and under 6 MB;
- its `detail.desktop_strip_edges_outside_safe` is low, or the owner accepted it knowingly;
- the owner's approval is in the chat.

**13 — Channel copy and links.**
1. Write the About text with `youtube-channel-setup/references/channel-copy.md`: keyword-aware,
   from the step's own `seed` records, and at most 1,000 characters.
2. Lint the description part with `youtube-metadata: scripts/check_metadata.py` where it applies.
3. Ask the owner for the channel's links: streaming, socials, site.
4. Store each one with `update-project-credentials` as a `LINK_<NAME>` config credential.
5. The owner approves the final copy.

**14 — Home page plan.**
- Follow `youtube-channel-setup/references/home-page.md`: sections from the content pillars, the
  trailer for non-subscribers, and the featured video.

**15 — Channel settings.**
1. Produce `channel-settings.json`, the desired state of `brandingSettings.channel`: description,
   keywords, country, default language, the trailer if one exists. Follow
   `youtube-channel-setup/references/settings.md`.
2. Produce `upload-defaults.md` and the made-for-kids decision.

**16 — Apply branding.**
1. Apply the approved banner, the watermark (if the brand profile has one) and
   `channel-settings.json` through `youtube-channel-setup: scripts/apply_channel.py`.
   - `banner` uploads the approved banner image.
   - `watermark` uploads the watermark, if the brand profile has one.
   - `branding` applies `channel-settings.json`, with `--dry-run` first to show the diff.
   The script claims, acts, verifies and commits by itself.
2. Set the avatar in Studio: `youtube-studio/references/channel-profile.md`, under
   `intent.py claim` with verb `branding`, part `avatar`.
3. Report every action with its intent key and outcome.

**17 — Apply settings, home page, upload defaults.**
- Set up the home sections with `youtube-studio/references/home-tab.md`.
- Set the upload defaults with `upload-defaults.md`.
- Each change is its own `intent.py` claim, verb `settings`, with area `home-tab` or
  `upload-defaults`.
- Re-check the session before each Studio part.

**18 — Monetization readiness.**
1. Read the channel's numbers with `youtube-data`.
2. Run `youtube-metrics: scripts/ypp.py` with them.
3. Write the thresholds with the date they were read, from `youtube-strategy/references/thresholds.md`.
   That includes the change announced for new applications from 2027-02-01, marked as reported by
   the press and not yet on YouTube's help page.
4. Add the AdSense and two-factor setup checklist.

## What changed from the previous Onboarding recipe

| Before | Now |
| --- | --- |
| `youtube`, `youtube-seo`, `youtube-channel-banner-generate`, `user-avatar-generate` skills | the `youtube-*` skills of this set, from the shelf |
| `google-api-python-client` | none: the scripts call the APIs over HTTPS |
| `opencv-python` + `numpy` attached by link | `opencv-python-headless` from the shelf (numpy comes with it) |
| `records.py` pinned as a file on step 6 | the `youtube-records` skill on the recipe |
| `seed` with `difficulty` 0..1 | `seed` with `kd_web` 0–100, `yt_interest`, `as_of` |
| no `profile` record | `profile:channel` written in step 7 |
| safe area "1235×338" | 1546×423 within 2560×1440 (1235×338 is the same area at the 2048×1152 minimum) |
| impressions and CTR planned through Studio | Reporting API job created in step 11 |
| links not stored | `LINK_*` config credentials |
| `DATAFORSEO_USERNAME` | `DATAFORSEO_LOGIN` (the server still reads `USERNAME` as an alias) |
