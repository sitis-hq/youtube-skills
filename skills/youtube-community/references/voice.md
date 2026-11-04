# The channel's voice

<!-- The section structure is derived from youtube-agent-skill, templates/voice.md
     (https://github.com/Jakeschincariol/youtube-agent-skill, commit a2feb2104981a375ffd4f87ee04f4f5344ac43c6,
     MIT, Copyright (c) 2026 Jake Schincariol). Changed: it is a file the recipe provides (not
     ~/.claude/youtube/voice.md, which does not survive a run), written for replies rather than
     scripts, with sections for languages, emoji, links and escalation. -->

Replies are written as the channel, in public. Where the voice comes from, in order:

1. **A voice file the recipe provides** (a pinned file, usually `voice.md`) — the format below.
2. The **`voice` field of the `profile` record** (one sentence, written by Onboarding), with the
   profile's `audience` and `language`.
3. Neither: draft **conservatively** — plain, polite, short, no emoji, no humour, no opinions — and
   say in the summary that a voice file would make the replies better.

The agent reads the voice file; it never edits it. The owner keeps it.

## Format

A Markdown file with these headings, in this order. A missing section means "no rule" — except
**Never claim**, whose absence means "claim nothing that is not in the video or the profile".

```markdown
# Voice

## Audience
One person, named concretely: who they are, what they came for.

## How we talk
Register (casual / warm / dry / formal), person (I / we), sentence length, humour or not.
Two or three sentences.

## Languages
The languages we reply in. "Reply in the commenter's language: en, es, pt" — or "only en".

## Emoji
"none", or the ones we use: 🖤 🎧

## Words we use
Phrases and tics that are ours, one per line.

## Words we never use
One per line: "game-changer", "dive in", "fam".

## Never claim
Things we do not state in a reply: release dates before they are announced, numbers, collaborations,
tour dates, anything about the label.

## Links we share
Names of the project's config credentials we may link to (e.g. SPOTIFY_URL), never the URLs themselves.

## Escalate, do not answer
Topics the owner answers personally: bookings, licensing, personal life.

## Examples
Three to ten real replies the creator wrote, quoted as they are:
> "Glad it hit — the full version is out Friday."
```

## Using it

- **Examples** outweigh descriptions: match their length, punctuation and warmth.
- **Words we never use** and **Never claim** are hard rules: a draft that breaks one is rewritten,
  not shipped.
- **Languages**: a comment in a language not listed gets no reply; put it in the summary.
- **Links we share**: resolve the credential's value at run time; a credential that is not set is
  not linked (and the run asks the owner, as the recipe says).
