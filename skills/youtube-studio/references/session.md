# The Studio session: check first, then act

Every playbook starts here. A Studio step that acts on a signed-out page either fails in a confusing
place or, worse, acts as the wrong channel. So the step proves who it is before it touches anything,
and when it cannot, it asks for a sign-in instead of guessing.

## What the recipe declares

- A browser session record on the step that drives Studio. The recipe briefs of this set name it
  **`YT_STUDIO_SESSION`**. The platform does not fix the name: any key ending in `_SESSION` is a
  session record, and the browser that carries it is the MCP server `playwright-` + the key without
  `_SESSION`, lower-cased with dashes — for `YT_STUDIO_SESSION` the tools are
  `mcp__playwright-yt-studio__*`. Use the browser that `available-tools.md` lists for that key; one
  browser is one Google account.
- The channel's id, from the `profile` record (`channel_id`, `UC…`). Studio URLs carry it, which is
  how the step knows it is acting as the right channel.
- Do **not** attach Playwright: it is a platform tool.

Where the step creates the record for the first time (Onboarding), the owner signs in by hand in
the worker's browser; the record's site is set then. Ask the owner to record it as
`studio.youtube.com`, because `request-browser-login` matches `--domain` exactly against that site
(platform behaviour, read 2026-11-04).

## The check

Open `https://studio.youtube.com/channel/<channel_id>` and take a snapshot. The step is **signed in
as the channel** only when all of these hold:

1. The page stayed on `studio.youtube.com` and its URL still contains `/channel/<channel_id>`.
2. The Studio left menu (Dashboard, Content, Analytics, …) is on the page.
3. The account menu (avatar, top right) names the channel the `profile` record names.

It is **signed out** when any of these appear:

- a redirect to `accounts.google.com` (`/signin`, `/ServiceLogin`, `/v3/signin`, "Choose an account");
- a sign-in form, a password field, or a "Sign in" button where Studio's menu should be;
- a public page instead of Studio: `www.youtube.com`, the channel's public home, or a
  "studio.youtube.com" landing page that only offers to sign in;
- a captcha, "Verify it's you", a phone or second-factor prompt — this is signed out **with a
  human check**.

It is **the wrong channel** when Studio opens but the URL carries another `UC…` id, or the account
menu names another channel. If the account menu's "Switch account" lists the right channel under
the same Google account, switch and check again; otherwise treat it as signed out.

## When it is not signed in

1. `ai-integration ensure-session --key YT_STUDIO_SESSION` — the worker signs in from the owner's
   stored sign-in sequence. You never type a password and never ask for one.
2. On success, **close the browser** (`browser_close`) and start the playbook again from the check:
   a fresh session reaches a browser only when it creates its context, so the open one stays
   signed out. Do this once; do not loop.
3. When `ensure-session` fails (no sequence declared, a human check, it stopped at a step), call
   `ai-integration request-browser-login --domain studio.youtube.com --key YT_STUDIO_SESSION`.
   If it refuses with "holds a session for X", call it once more with `--domain X`. Then stop the
   Studio part of the step and say plainly which action is blocked and why.

## What "stop" means for the step

The step does not fail on a missing session, and it does not guess a result:

- An action not taken is not claimed (or, if already claimed, is failed with
  `intent.py fail --reason "Studio session missing"` — it certainly did not happen).
- A read not done is recorded as not done: for impressions and CTR, the `studio` records of the day
  are written with `--available false` (youtube-records: "no data" is written, not skipped).
- API work of the same step goes on; only the Studio part waits for the owner.

## One browser lifetime per action

After a session refresh the open pages are lost. Do one Studio action per browser lifetime where a
refresh is likely (a long run, a session that was refreshed recently), and verify each action before
starting the next.

Sources: `ai-integration ensure-session --help`, `ai-integration request-browser-login --help`, and the
platform's naming of session browsers — read 2026-11-04.
