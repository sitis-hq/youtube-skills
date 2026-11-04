---
name: youtube-records
description: The memory contract between the YouTube channel recipes — record kinds (profile, seed, watch, velocity, studio, idea, plan, publish, replied), their keys, fields and units. Use whenever a step writes a record to template memory or looks one up that another YouTube recipe wrote; never write or build such a key by hand.
---

# YouTube records

The YouTube recipes hand data to each other through template memory: each recipe writes records into
its **own** memory, and a recipe that needs them reads the writer's memory by the writer's template
id (`query-template-records` / `get-template-record` with `--spec-template-id <writer>`). A record whose
key or fields differ from what the reader expects is not an error anywhere — it is simply never found.
So every key and every record goes through `scripts/records.py`, the one place the format is stated.

## Commands

Call the script by its path from this skill's base directory.

| Need | Command |
| --- | --- |
| See every kind, its key, writer, readers and fields | `python3 <base>/scripts/records.py schema` (or `schema <kind>`) |
| Write a record into this recipe's memory | `python3 <base>/scripts/records.py write <kind> --field value ...` |
| Validate without writing (a dry run, or to show the owner) | `python3 <base>/scripts/records.py check <kind> --field value ...` |
| Build the key of a record to look up | `python3 <base>/scripts/records.py key <kind> --field value` — only the key's fields |
| Check a record read back from another recipe | `python3 <base>/scripts/records.py validate --key <key> --data '<json>'` |

`write` takes this run's ids from the `Process id` and `Spec id` lines of `current-task.md`, or from
`--spec-template-id` / `--spec-id`; pass `--spec-task-id` when you know the step. It validates first and
calls `ai-integration upsert-template-record` only for a valid record. Output is JSON; exit code 2 with
`{"ok": false, "error": ...}` is a refusal — fix the value, do not work around the script.

## Kinds

| Kind | Key | Writer | Readers |
| --- | --- | --- | --- |
| `profile` | `profile:channel` | Onboarding | every recipe |
| `seed` | `seed:<slug(term)>` | Onboarding, Recon | Recon, Planning, creation recipes |
| `watch` | `watch:<videoId>` | Recon | Daily data, Analytics, Planning |
| `velocity` | `velocity:<videoId>` | Daily data | Recon, Analytics, Planning |
| `studio` | `studio:<videoId>` | Daily data | Analytics, Planning |
| `idea` | `idea:<slug(title)>` | Recon | Planning, creation recipes |
| `plan` | `plan:<date>:<slot>` | Planning | creation recipes, Analytics |
| `publish` | `publish:<videoId>` | creation recipes | Analytics, Planning |
| `replied` | `replied:<commentId>:<action>` | Community | Community |

`schema` gives each kind's fields with their meaning; read it before writing a kind for the first time.

## Rules the script cannot check for you

- **One writer per record.** A recipe never edits a record another recipe wrote. Planning does not move
  an idea's status; it writes its own `plan` record that names the idea.
- **Read the writer's memory, not your own.** The writer's template id comes from the run context
  (declared reads) or from `find-spec-template`.
- **Units are part of the contract.** `ctr` is a fraction (Studio shows 4.5 %; write `0.045`);
  `kd_web` is DataForSEO's 0–100 as it comes; `yt_interest` is a Google Trends index 0–100, not a
  number of searches; dates are `YYYY-MM-DD`, times carry a zone.
- **"No data" is written, not skipped**: a `studio` record with `--available false` tells the reader the
  export ran and gave nothing, which a missing record cannot.
- **Links, handles and other channel settings are config credentials of the project, not records.**
  A recipe that needs them declares them, and a run without them pauses and asks the owner.
- A record carries `"v": 1`. A reader that meets another version stops and reports it rather than
  guessing.
