# Brief 1 — YouTube Onboarding

Follow [the rules of the set](README.md); this brief adds what is specific to Onboarding.

**Name:** `YouTube Onboarding` · **Scope:** global recipe, run inside the channel's own project ·
**Schedule:** none — started by hand, once per channel; steps 1–7 again when the Channel Audit
decides a shift of niche or a repositioning · **Reads from:** "YouTube Channel Audit", when it exists (its brief adds
the declaration).

## What it is for

It takes a channel-project to a working channel in four moves. The channel is either new, or one
that already exists and has a history; the moves are the same for both.

1. **Strategy.** It chooses the niche, the audience, the formats and the brand, all from data. For
   an existing channel the research is just as full: the channel's history is one more input to it
   (what already worked, what did not), never a setting to keep.
2. **Wiring.** It sets up a Google Cloud project, an OAuth application in production, the connected
   channel, a Studio session, and the Reporting API jobs.
3. **Assets.** It prepares the banner, the avatar, the copy and the settings, and the owner approves
   them.
4. **Application.** It applies the approved assets and settings to the channel.

Every later recipe of the set stands on what Onboarding leaves behind:

- **Records** (memory, through `youtube-records`):
  - one `profile:channel` record;
  - a set of `seed:<term>` records.
- **Artifacts:**
  - `channel-history.json`, for an existing channel;
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
- **Two Reporting API jobs:** `channel_reach_basic_a1` and `channel_reach_combined_a1`. Daily data
  reads impressions and impression click-through rate (CTR) per video from the first, with no
  browser; the Channel Audit reads CTR per traffic source from the second. A job gets only the 30
  days before its creation and the days after, and YouTube keeps reports for 60 days, so Onboarding
  creates both as early as the connection allows.

## Requirements (EARS) to put into the recipe

1. WHEN discovery starts THEN system MUST ask whether the channel is new or already exists, and for an existing channel MUST read its public history — its own outliers against its own median, long-form and Shorts apart — and add the topics that worked to the candidates, as input to the research and not as a decision.
2. WHEN discovery runs THEN system MUST rank niche candidates by how open each is to a new channel — small channels breaking out above their own median, how spread the top results are across channels, how fresh they are — measured on real YouTube results, with demand as a floor, and MUST name candidate terms whose results are mostly the same videos as one audience.
3. WHEN a niche is chosen THEN system MUST recommend the most open niche over the demand floor unless a stated reason with numbers rules it out, MUST record the choice with a rationale that cites its openness and its demand, and MUST name the main risks; for an existing channel whose chosen niche serves a different audience than its history, it MUST tell the owner that YouTube's own advice is a separate channel, and let the owner decide.
4. WHEN the audience, formats and brand are defined THEN system MUST produce `audience-profile.md`, `format-plan.md` and `brand-profile.md` as durable artifacts.
5. WHEN seed keywords are produced THEN system MUST write each one as a `seed` record through `records.py`, with `kd_web` on DataForSEO's 0–100 scale and `yt_interest` marked as an index.
6. WHEN the channel exists THEN system MUST write the `profile:channel` record, with channel id, title, language, niche, channel type and identity tokens.
7. WHEN a Google admin page or Studio shows a signed-out state THEN system MUST re-mint the session or ask the owner to sign in, and MUST NOT act until it is signed in.
8. WHEN the Google Cloud project is set up THEN system MUST enable YouTube Data API v3, YouTube Analytics API and YouTube Reporting API in a project dedicated to this channel, and MUST publish the OAuth app to production.
9. WHEN the channel is connected THEN system MUST verify API access, and MUST ensure both Reporting API jobs, `channel_reach_basic_a1` and `channel_reach_combined_a1`, exist.
10. WHEN the connection step runs again on a channel whose connection, channel id and Studio session already check out THEN system MUST NOT ask the owner anything, and MUST only verify and create what is missing.
11. WHEN the live admin UI differs from what the recipe expects THEN system MUST record the difference in `admin-drift.md`.
12. WHEN banner and avatar candidates exist THEN system MUST send the owner the upload image AND the device safe-area preview, and MUST NOT apply anything before the owner approves.
13. WHEN the channel's links are collected THEN system MUST store them as `LINK_*` config credentials of the project.
14. WHEN branding or settings are applied THEN system MUST apply each change at most once, through `intent.py`, and MUST verify the result on YouTube.
15. WHEN onboarding ends THEN system MUST state the distance to the YouTube Partner Program (YPP) thresholds, with the date they were read.

## Steps

The "Skills" column lists skills from the shelf, attached to that step. `youtube-records` is
attached to the recipe, as rule 2 says.

| # | Step | Who | Skills and tools on the step | Credentials | Writes |
| --- | --- | --- | --- | --- | --- |
| 1 | Niche discovery | AI + owner | `youtube-demand`, `youtube-data`, `youtube-metrics`, `youtube-strategy`, `yt-dlp`, `dataforseo-mcp-server` | `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD` | `channel-history.json` (existing channel), `niche-candidates.json` |
| 2 | Niche selection | AI + owner | `youtube-strategy` | — | `niche-decision.md` |
| 3 | Audience, language and region | AI | `youtube-strategy`, `youtube-demand`, `dataforseo-mcp-server` | DataForSEO keys | `audience-profile.md` |
| 4 | Formats and content pillars | AI | `youtube-strategy` | — | `format-plan.md` |
| 5 | Brand profile | AI + owner | `youtube-channel-setup`, `youtube-strategy` | — | `brand-profile.md` |
| 6 | Seed keywords | AI | `youtube-demand`, `dataforseo-mcp-server` | DataForSEO keys | `seed` records, `seed-keywords.json` |
| 7 | Create the channel | owner + AI | — | `GOOGLE_SESSION` | `channel-created.md`, `profile:channel` record |
| 8 | Google Cloud project and APIs | AI (browser) | — | `GOOGLE_SESSION` | `gcp-setup-notes.md`, `admin-drift.md` |
| 9 | OAuth application to production | AI (browser) | — | `GOOGLE_SESSION` | `oauth-consent-notes.md`, `admin-drift.md` |
| 10 | OAuth client and `YOUTUBE_CLIENT_SECRET` | AI (browser) + owner | — | `GOOGLE_SESSION`, `YOUTUBE_CLIENT_SECRET` | `oauth-client-notes.md` |
| 11 | Connect the channel, Studio session, Reporting jobs | owner + AI | `youtube-data`, `youtube-studio` | `YOUTUBE_REFRESH_TOKEN`, `YT_STUDIO_SESSION` | `connection-check.md` |
| 12 | Banner and avatar | AI + owner approval | `youtube-channel-setup`, `poyoapi`, `opencv-python-headless` | `POYO_API_KEY` | chosen images, previews, `asset-decision.md` |
| 13 | Channel copy and links | AI + owner approval | `youtube-channel-setup`, `youtube-metadata` | — | `channel-copy.md`, `LINK_*` and `BUSINESS_EMAIL` config credentials |
| 14 | Home page plan | AI | `youtube-channel-setup` | — | `home-plan.md` |
| 15 | Channel settings (desired state) | AI | `youtube-channel-setup` | — | `channel-settings.json`, `upload-defaults.md` |
| 16 | Apply branding | AI | `youtube-channel-setup`, `youtube-studio`, `opencv-python-headless` | `YOUTUBE_REFRESH_TOKEN`, `YT_STUDIO_SESSION` | `branding-apply-report.md` |
| 17 | Apply settings, home page, upload defaults | AI | `youtube-channel-setup`, `youtube-studio` | `YOUTUBE_REFRESH_TOKEN`, `YT_STUDIO_SESSION` | playlists, `settings-apply-report.md` |
| 18 | Monetization readiness | AI | `youtube-metrics`, `youtube-strategy`, `youtube-data` | `YOUTUBE_REFRESH_TOKEN` | `monetization-checklist.md` |

## Design notes per step

**1 — Niche discovery.**

Re-run after an audit. Steps 1–7 run again when the newest `audit-decision.json` of "YouTube
Channel Audit" (declared; step "Owner review") routes to `onboarding`, its `quarter` is the newest
audit's, and its `owner_answer.answer` is `accepted` or `changed`. Step 1 then reads that file, its
`audit-YYYY-QN.md` and `market.json` (step "The niche's market now") before anything else. The
channel is an existing one: point 1 asks the owner only to confirm the topic, point 2 reads the
history again, and the audit's cause shapes the candidates (falling demand → adjacent topics with
demand; a concentrated niche → smaller or less crowded neighbours; an audience that does not want
the topic → topics of the history's groups that worked). Steps 2–6 follow as on a first run; step 7
rewrites `profile:channel` with the new niche. Steps 8–18 are not re-run.

Popularity is not what makes a niche hard. A niche is hard when a few channels hold its top, when
the top is old, and when small channels never break through; a popular niche that is spread out and
fresh is the best case, because its demand is proven. So the step measures those three and ranks by
them, with demand as a floor. The method and its sources are in `youtube-demand/SKILL.md` and
`youtube-strategy/references/thresholds.md`.

1. Ask the owner, in one message with `send-message`, then `await-reply`: is the channel new, or does
   it already exist (its link); the broad topic; anything already decided (genre, language, market).
   Nothing earlier in the recipe holds it. Write the answer into `niche-candidates.json` as `topic`
   and `channel` (`new`, or the link).
2. Existing channel only — read its history, before choosing terms. How to read it, and when to
   discard it, is in `youtube-strategy/references/channel-audit.md` ("Using a channel's history").
   - Resolve the link to the channel's `UC…` id with yt-dlp
     (`yt-dlp --print channel_id --playlist-items 1 <link>`).
   - Read both tabs with `youtube-data: scripts/channel_baselines.py --channel-id <id> --max-videos
     200 --videos-out <file>`: once with the default tab and once with `--tab shorts`, each into its
     own `--out`.
   - Rank each tab's videos with `youtube-metrics: scripts/swipe.py <file> --direction both`: the
     channel's own outliers, up and down, against its own median.
   - Group the upward outliers by topic. A group with 3 or more is a topic that worked; write it
     with its videos and multiples. Mark what is discarded and why (a spike, a topic whose demand
     has since fallen, fewer than 5 videos of a format).
   - Write `channel-history.json`: the channel id, the medians, the outliers, the groups, the
     discarded part.
   This is the channel's public history only: CTR, retention and traffic sources need the connection
   of step 11, and the Channel Audit reads them.
3. From the topic — and for an existing channel, also from the groups that worked — choose 8–15
   candidate niche terms: sub-genres or sub-topics a viewer would look for. A group that worked
   enters as a candidate like any other and is ranked by the same measures; it gets no bonus.
4. Get one YouTube SERP per term (`/v3/serp/youtube/organic/live/advanced`) with
   `youtube-demand: scripts/dfs.py`, one response file per call. Do not write another client.
   Location and language come from the owner's answer.
5. Read each ranking channel's normal with `youtube-data: scripts/channel_baselines.py`, passing
   every SERP file. It reads public pages through yt-dlp and needs no connection. If it stops on
   429, wait and run it again with the same arguments: it continues where it stopped.
6. Rank with `youtube-demand: scripts/niches.py`, passing every SERP file and `--baselines`.
7. Write `niche-candidates.json`: the `topic`, the `channel`, the terms (each history-born term
   marked), and the script's output as it came, `warnings` included.

**2 — Niche selection.**

The ranking decides; the step does not re-rank by taste. On a re-run after an audit, the decision
cites the audit and says what the new niche fixes.

1. Recommend the top niche of step 1's ranking: the most open one over the demand floor. Treat terms
   in `same_results` as one niche.
2. Recommend another niche only for a reason stated with numbers: the owner's answer in step 1 rules
   the top one out, or its `confidence` is "low" while the next one's is "normal". Write the reason.
3. Weigh durability and fit with `youtube-strategy` (`references/strategy.md`), and turn what you
   find into named risks of the recommended niche, not into a new order.
4. Existing channel: say whether the recommended niche serves the audience the channel already has
   (`channel-history.json`). Same audience → the channel keeps going in the new direction, seeded
   into its evergreen videos rather than switched at once. A different audience → tell the owner
   that YouTube's own advice is a separate channel ("same audience, same channel; different
   audience, different channel", Rene Ritchie, `thresholds.md`), and let the owner choose. The
   choice and its reason go into `niche-decision.md`.
5. Describe a niche only with the numbers in `niche-candidates.json` and the lines in
   `youtube-strategy/references/thresholds.md`. A claim from elsewhere carries its source and date,
   or is left out.
6. Send the owner the recommended niche first and at most two alternatives, each with the same
   numbers: openness and its three parts, demand (median views of the top), and one or two of its
   breakout videos. Use buttons, recommended first. Then wait for the answer.

Validator rubric:
- exactly one niche is chosen;
- it is step 1's top niche, or `niche-decision.md` states the reason with numbers;
- the rationale cites the chosen niche's openness and demand from `niche-candidates.json`;
- at least two named, specific risks are given;
- the owner's choice is in the chat;
- for an existing channel, the decision says whether the niche keeps its audience, and cites
  `channel-history.json`.

**3–4 — Audience, formats.**
- Use the output templates of `youtube-strategy` (`strategy.md`, `calendar.md`).
- Step 3 measures the markets before choosing one: one Labs `keyword_overview` per candidate market
  (2–3 markets, the chosen niche's main terms) with `youtube-demand: scripts/dfs.py`. Volume says
  where the audience searches; CPC is the evidence for the revenue band. Name the files in
  `audience-profile.md`.
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
Every seed carries every measure: a seed without its interest index or its competition cannot be
ranked against the others later.

1. Call Labs `keyword_ideas` / `keyword_overview` for volume, CPC, KD and intent, with
   `youtube-demand: scripts/dfs.py`, which saves each response as a file. Choose the seed set.
2. Call Trends explore with `type: youtube` for **every** seed, the same way: up to 5 keywords a
   request, and the same anchor term in every request (the chosen niche's main term) beside 4 seeds.
   For rising queries, call it with exactly one keyword.
3. Call the YouTube SERP for **every** seed, the same way: `normalize.py` turns it into
   `yt_competition` (about $0.002 a seed).
4. Run `youtube-demand: scripts/normalize.py` on them with `--anchor <that term>`. It puts every
   request on one scale and refuses several requests without an anchor. Each row it prints carries
   the arguments for `records.py write seed`; write every row.
5. Write `seed-keywords.json`, mirroring what was written.

Validator rubric:
- at least 20 seeds;
- every seed has `as_of` and `source`, and every seed has `yt_interest` and `yt_competition`;
- `kd_web` is on 0–100;
- no seed is a duplicate under a different spelling.

**7 — Create the channel.**
An existing channel is not created again: the step verifies it under `GOOGLE_SESSION` (it is the
channel of step 1's link, or the new one the owner chose to open in step 2) and goes to the
`profile:channel` record. On a re-run after an audit it writes the record again with the new
`niche` (and whatever steps 3–5 changed); the key is the same, so the new record replaces the old.
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
- Step 10 declares `YOUTUBE_CLIENT_SECRET` to learn whether the project already holds it: the run's
  `current-task.md` lists a held connection half without its value, or names it as missing. Held →
  check the Desktop-app client in the console and ask the owner nothing. Missing → create a
  Desktop-app OAuth client; the owner uploads its JSON on the project's Credentials page, in the
  "Connect to YouTube" row. The agent never sees the secret.
- Every difference from the expected screens goes into `admin-drift.md`.

**11 — Connect, Studio session, Reporting jobs.**
The step can run again at any time and asks the owner only for what does not check out: first it
runs the checks of points 3 and 4, and skips points 1 and 2 when they pass.
1. The owner completes the Connect dialog. They paste the `http://127.0.0.1:8085/?…` address after
   consent; the page not loading is expected. The worker then seals `YOUTUBE_REFRESH_TOKEN`.
2. The owner signs in once at `studio.youtube.com` in the worker's browser, and records the session
   under the site `studio.youtube.com` (see `youtube-studio/references/session.md`).
3. The step verifies the API with `youtube-data: scripts/data_api.py channels --mine`. The channel id
   it returns must equal the one in `profile:channel`.
4. The step verifies Studio with the session check, against that channel id.
5. The step runs `youtube-data: scripts/reporting.py ensure-job`. It creates whichever of the two
   reach jobs is missing and creates nothing when both exist. The step records both job ids, and
   which were created now, in `connection-check.md`.

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
3. Ask the owner for the channel's links (streaming, socials, site) and its business e-mail.
4. Store each link with `update-project-credentials` as a `LINK_<NAME>` config credential, and the
   e-mail as `BUSINESS_EMAIL`. A value the project already holds is kept unless the owner changes it.
5. The owner approves the final copy.

**14 — Home page plan.**
- Follow `youtube-channel-setup/references/home-page.md`: sections from the content pillars, the
  trailer for non-subscribers, and the featured video.
- For every playlist a shelf needs, write its spec for step 17: `playlist-<slug>.json` with
  `title`, `description`, `privacy` and `videos` — the channel's existing uploads, in order. A
  playlist that needs videos the channel does not have yet is planned for later, not specced.
- A trailer the channel does not have is not made here: making a video belongs to the content
  recipes. Name an existing upload as the interim trailer.

**15 — Channel settings.**
1. Produce `channel-settings.json`, the desired state of `brandingSettings.channel`: description,
   keywords, country, default language, the trailer if one exists. Follow
   `youtube-channel-setup/references/settings.md`.
2. Produce `upload-defaults.md` and the made-for-kids decision.

**16 — Apply branding.**

Onboarding applies the channel's first state once. After "YouTube Planning" has run, channel changes
are Planning's: do not re-run steps 16–17, whose desired state is older and would undo Planning's.

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
- First create the planned playlists, one `youtube-channel-setup: scripts/apply_channel.py playlist
  --spec <playlist-….json>` each. The script claims, creates, adds the videos, re-reads and commits;
  a title the channel already has is not created again.
- Then set up the home sections with `youtube-studio/references/home-tab.md`, including the
  shelves of those playlists.
- Set the upload defaults with `upload-defaults.md`.
- Each change is its own `intent.py` claim, verb `settings`, with area `home-tab` or
  `upload-defaults`.
- Re-check the session before each Studio part.

**18 — Monetization readiness.**
1. Read the channel's numbers:
   - subscribers, with `youtube-data: scripts/data_api.py channels --mine`;
   - watch hours over 365 days, with `youtube-data: scripts/analytics.py channel`, and Shorts-feed
     views over 90 days, the `SHORTS` row of `youtube-data: scripts/analytics.py traffic` (the
     input `ypp.py` names; Analytics reads it the same way);
   - public uploads in 90 days, with `youtube-data: scripts/data_api.py uploads`.
   A new channel reads zero; the step writes zero, not "no data".
2. Run `youtube-metrics: scripts/ypp.py` with them.
3. Write the thresholds with the date they were read, from `youtube-strategy/references/thresholds.md`.
   That includes the change announced for new applications from 2027-02-01, marked as reported by
   the press and not yet on YouTube's help page.
4. Add the AdSense and two-factor setup checklist.
5. Existing channel: end the message to the owner by asking them to start "YouTube Channel Audit"
   now, and say why (see "After Onboarding").

## After Onboarding

For an existing channel, the owner starts "YouTube Channel Audit" by hand once Onboarding ends,
without waiting for its quarter. The audit reads what Onboarding could not: CTR per traffic source,
retention and the viewer groups. A shift of niche or a repositioning it decides comes back here as
a re-run of steps 1–7, with the audit as their input (step 1, "Re-run after an audit"). Step 18 says
so to the owner.

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
| impressions and CTR planned through Studio | Reporting API jobs created in step 11: per video (`basic`) and per traffic source (`combined`) |
| a brand-new channel assumed | new or existing, asked in step 1; an existing channel's history feeds the niche research, which stays full |
| links not stored | `LINK_*` config credentials |
| `DATAFORSEO_USERNAME` | `DATAFORSEO_LOGIN` (the server still reads `USERNAME` as an alias) |
| niche ranked by views per day of age (`candidates.py`) | ranked by openness — breakouts of small channels, spread, freshness — with demand as a floor (`niches.py`); terms with the same results merged |
| step 2 chose among options by taste | step 2 recommends the top of the ranking unless a stated reason with numbers rules it out |
| the topic of the channel assumed | asked from the owner at the start of step 1 |
| DataForSEO through MCP, or a client written in the run | `youtube-demand: scripts/dfs.py`, one saved response per call |
