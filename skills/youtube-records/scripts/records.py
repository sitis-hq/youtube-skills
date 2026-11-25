#!/usr/bin/env python3
"""The memory contract of the YouTube channel recipes: record kinds, their keys and their fields.

Records are how one recipe hands data to another: a recipe writes records into its own memory, and
the recipes that use them read that memory by the writer's template id. A record written with a
key format or a field the reader does not expect is lost without an error, so every write and every
key a reader builds goes through this file — the one place the format is stated.

Commands (all print JSON on stdout; a refusal exits 2 with {"ok": false, "error": ...}):

  records.py schema [KIND]            the kinds, their keys and fields
  records.py key KIND --field ...     the key alone, for a reader that looks a record up
  records.py check KIND --field ...   validate; print {"key", "data"} without writing
  records.py write KIND --field ...   validate, then upsert through `ai-integration`
  records.py validate --key K --data JSON
                                       check a stored record a reader got back

`write` needs the run's ids. It takes --spec-template-id and --spec-id (and --spec-task-id when
known); without them it reads the "Process id" and "Spec id" lines of current-task.md in the
working directory, where the platform writes them for every run.

Standard library only: Python 3.11.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Callable

SCHEMA_VERSION = 1

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
CHANNEL_ID = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
# A top-level comment id, or a reply's "<parent>.<reply>". Neither has a fixed length.
COMMENT_ID = re.compile(r"^[A-Za-z0-9_-]{10,}(\.[A-Za-z0-9_-]{10,})?$")
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class Refusal(Exception):
    """A value the contract does not accept. The message names the field and the rule."""


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not slug:
        raise Refusal(f"cannot make a key from {text!r}: it has no latin letters or digits")
    return slug


# ── field types ────────────────────────────────────────────────────────────────────────────────


def _text(name: str, raw: Any) -> str:
    value = str(raw).strip()
    if not value:
        raise Refusal(f"{name} is empty")
    return value


def _int(lo: int | None = None, hi: int | None = None) -> Callable[[str, Any], int]:
    def parse(name: str, raw: Any) -> int:
        try:
            value = int(str(raw).replace("_", ""))
        except ValueError:
            raise Refusal(f"{name} must be a whole number, got {raw!r}") from None
        if lo is not None and value < lo or hi is not None and value > hi:
            raise Refusal(f"{name} must be within {lo}..{hi}, got {value}")
        return value

    return parse


def _float(lo: float | None = None, hi: float | None = None) -> Callable[[str, Any], float]:
    def parse(name: str, raw: Any) -> float:
        try:
            value = float(raw)
        except ValueError:
            raise Refusal(f"{name} must be a number, got {raw!r}") from None
        if lo is not None and value < lo or hi is not None and value > hi:
            raise Refusal(f"{name} must be within {lo}..{hi}, got {value}")
        return value

    return parse


def _fraction(name: str, raw: Any) -> float:
    # A percentage is refused, not converted: 4.5 could be 4.5 % or a typo, and a reader comparing
    # fractions would take it as 450 %. Studio shows percentages, so the writer divides on purpose.
    return _float(0.0, 1.0)(name, raw)


def _bool(name: str, raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().lower()
    if text in ("true", "yes", "1"):
        return True
    if text in ("false", "no", "0"):
        return False
    raise Refusal(f"{name} must be true or false, got {raw!r}")


def _date(name: str, raw: Any) -> str:
    try:
        return date.fromisoformat(str(raw)).isoformat()
    except ValueError:
        raise Refusal(f"{name} must be a date YYYY-MM-DD, got {raw!r}") from None


def _datetime(name: str, raw: Any) -> str:
    text = str(raw).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise Refusal(f"{name} must be an ISO date-time, got {raw!r}") from None
    if parsed.tzinfo is None:
        raise Refusal(f"{name} must carry a time zone (e.g. 2026-11-04T12:00:00Z), got {raw!r}")
    return parsed.isoformat()


def _match(pattern: re.Pattern[str], what: str) -> Callable[[str, Any], str]:
    def parse(name: str, raw: Any) -> str:
        value = str(raw).strip()
        if not pattern.match(value):
            raise Refusal(f"{name} must be {what}, got {raw!r}")
        return value

    return parse


def _enum(*allowed: str) -> Callable[[str, Any], str]:
    def parse(name: str, raw: Any) -> str:
        value = str(raw).strip()
        if value not in allowed:
            raise Refusal(f"{name} must be one of {', '.join(allowed)}; got {raw!r}")
        return value

    parse.allowed = allowed  # type: ignore[attr-defined]
    return parse


def _list_of(item: Callable[[str, Any], Any]) -> Callable[[str, Any], list[Any]]:
    def parse(name: str, raw: Any) -> list[Any]:
        values = raw if isinstance(raw, list) else [raw]
        if not values:
            raise Refusal(f"{name} is empty")
        return [item(name, v) for v in values]

    parse.repeated = True  # type: ignore[attr-defined]
    return parse


_video = _match(VIDEO_ID, "an 11-character video id")
_channel = _match(CHANNEL_ID, "a channel id starting with UC (24 characters)")
_comment = _match(COMMENT_ID, "a comment id (or parent.reply)")
_slug = _match(SLUG, "a slug of lowercase latin letters, digits and hyphens")
_uuid = _match(re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"), "a uuid")
_hhmm = _match(re.compile(r"^([01]\d|2[0-3]):[0-5]\d$"), "a local time HH:MM")


def _move(name: str, raw: Any) -> dict[str, str]:
    """One move of a release's date: {from, to, at}; given as JSON or as FROM>TO."""
    value = raw
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("{"):
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                raise Refusal(f"{name}: not JSON: {raw!r}") from None
        elif ">" in text:
            a, b = text.split(">", 1)
            value = {"from": a.strip(), "to": b.strip()}
    if not isinstance(value, dict) or set(value) - {"from", "to", "at"} or not {"from", "to"} <= set(value):
        raise Refusal(f"{name}: a move is {{from, to, at}} or FROM>TO, got {raw!r}")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {"from": _date(name, value["from"]), "to": _date(name, value["to"]),
            "at": _datetime(name, value.get("at") or now)}


def _zone(name: str, value: Any) -> str:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    text = str(value).strip()
    try:
        ZoneInfo(text)
    except (ZoneInfoNotFoundError, ValueError):
        raise Refusal(f"{name} must be an IANA time zone such as America/New_York, got {value!r}") from None
    if "/" not in text:
        raise Refusal(f"{name} must name a region, such as America/New_York, not {text!r}")
    return text

FORMAT = _enum("long", "short", "live", "post")


# ── kinds ──────────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Field:
    parse: Callable[[str, Any], Any]
    required: bool
    doc: str


@dataclass(frozen=True)
class Kind:
    name: str
    key_doc: str
    writer: str
    readers: str
    doc: str
    fields: dict[str, Field]
    make_key: Callable[[dict[str, Any]], str]
    checks: tuple[Callable[[dict[str, Any]], None], ...] = field(default=())


def req(parse: Callable[[str, Any], Any], doc: str) -> Field:
    return Field(parse, True, doc)


def opt(parse: Callable[[str, Any], Any], doc: str) -> Field:
    return Field(parse, False, doc)


def _studio_available(data: dict[str, Any]) -> None:
    # "No data" is a record, not a missing record: the reader must tell "not exported yet" from
    # "the export failed today", and a missing key says neither.
    # ctr may be absent while impressions are there: the Reporting API's CTR scale is settled from a
    # real file (youtube-data reporting.py), and until then a CTR would be wrong a hundredfold.
    measured = [f for f in ("impressions", "ctr") if f in data]
    if data["available"] and "impressions" not in data:
        raise Refusal("available=true needs impressions (ctr may be left out while its scale is unsettled)")
    if not data["available"] and measured:
        raise Refusal(f"available=false must not carry {', '.join(measured)}")


def _replied_reply_has_text(data: dict[str, Any]) -> None:
    if data["action"] == "reply" and "reply_id" not in data:
        raise Refusal("action=reply needs reply_id — the id YouTube gave the reply")


KINDS: dict[str, Kind] = {}


def kind(k: Kind) -> None:
    KINDS[k.name] = k


kind(Kind(
    name="profile",
    key_doc="profile:channel",
    writer="Onboarding",
    readers="every recipe",
    doc="Who the channel is. Identity tokens are the words demand data never replaces "
        "(an artist, a series, a show); links and handles live in config credentials, not here.",
    fields={
        "channel_id": req(_channel, "the channel id"),
        "title": req(_text, "the channel's name"),
        "language": req(_match(re.compile(r"^[a-z]{2}(-[A-Z]{2})?$"), "a language code like en or pt-BR"),
                        "the language of its videos"),
        "country": opt(_match(re.compile(r"^[A-Z]{2}$"), "a two-letter country code"), "its main audience's country"),
        # One home for the audience's clock: publish hours and every schedule's local hour come from
        # here, not from a zone written into a step (CONTRACT.md, rule 16).
        "timezone": req(_zone, "the main audience's IANA time zone, e.g. America/New_York"),
        "niche": req(_text, "what the channel is about, in a few words"),
        "channel_type": req(_text, "one of the types in youtube-strategy's references (e.g. music-artist)"),
        "identity_token": opt(_list_of(_text), "a name every title keeps as it is; repeat the flag"),
        "audience": opt(_text, "who watches, in one sentence"),
        "voice": opt(_text, "how the channel speaks, in one sentence"),
    },
    make_key=lambda d: "profile:channel",
))

kind(Kind(
    name="seed",
    key_doc="seed:<slug(term)>",
    writer="Onboarding (initial set), Recon (weekly additions)",
    readers="Recon, Planning, the creation recipes",
    doc="A keyword the channel targets, with the demand measured for it. kd_web is DataForSEO's "
        "web keyword difficulty, 0-100, as it comes; there is no YouTube keyword difficulty, so "
        "yt_competition is ours, from the YouTube results (youtube-demand). The same term can sit in "
        "Onboarding's and in Recon's memory: a reader takes the record with the later as_of. "
        "yt_interest compares only within one measurement's anchored set (youtube-demand), so a "
        "ranking across terms reads them from one run's measurement, not from records of different "
        "runs.",
    fields={
        "term": req(_text, "the keyword as searched"),
        "source": req(_text, "where it came from: dataforseo, trends, competitor, owner"),
        "as_of": req(_date, "the day the numbers were read"),
        "volume": opt(_int(0), "Google monthly search volume (web, not YouTube)"),
        "cpc": opt(_float(0), "cost per click, USD"),
        "kd_web": opt(_int(0, 100), "DataForSEO keyword difficulty, 0-100"),
        "yt_interest": opt(_int(0, 100), "Google Trends YouTube-search interest, an index 0-100, not a "
                                          "count; comparable only with terms of the same Trends request"),
        "yt_competition": opt(_float(0, 1), "competition in YouTube results, 0..1 (youtube-demand formula)"),
        "intent": opt(_enum("informational", "navigational", "commercial", "transactional"), "search intent"),
        # A change of niche keeps the old keywords as history instead of deleting or mixing them:
        # readers take the seeds of the profile's niche now (CONTRACT.md, rule 12).
        "niche": req(_text, "profile:channel's niche when the seed was written"),
    },
    make_key=lambda d: f"seed:{slugify(d['term'])}",
))

kind(Kind(
    name="watch",
    key_doc="watch:<videoId>",
    writer="Recon",
    readers="Daily data, Analytics, Planning",
    doc="A competitor video worth following.",
    fields={
        "video_id": req(_video, "the video"),
        "channel_id": req(_channel, "its channel"),
        "source": req(_text, "how it was found: search, trends, competitor-list"),
        "published_at": opt(_datetime, "when it was published"),
        "views": opt(_int(0), "views when it was added"),
        "views_per_day": opt(_float(0), "views divided by days since publication, when added"),
        "score": opt(_float(0), "the candidate score of youtube-metrics, when added"),
        "reason": opt(_text, "why it is followed, one sentence"),
    },
    make_key=lambda d: f"watch:{d['video_id']}",
))

kind(Kind(
    name="velocity",
    key_doc="velocity:<videoId>",
    writer="Daily data",
    readers="Recon, Analytics, Planning",
    doc="Growth of a video, from the latest snapshot. Overwritten daily: as_of tells a fresh value "
        "from a stale one.",
    fields={
        "video_id": req(_video, "the video"),
        "as_of": req(_date, "the snapshot's day"),
        "views_per_day": req(_float(0), "views gained per day between the last two snapshots"),
        "anomaly": req(_enum("none", "spike", "drop"), "the anomaly flag of youtube-metrics"),
        "source": req(_text, "data-api; views-per-age when only one snapshot exists (a lifetime average, "
                             "not a measured rate)"),
    },
    make_key=lambda d: f"velocity:{d['video_id']}",
))

kind(Kind(
    name="studio",
    key_doc="studio:<videoId>",
    writer="Daily data",
    readers="Analytics, Planning",
    doc="Impressions and impression click-through rate of an own video. ctr is a fraction "
        "(0.045 for 4.5 %); available=false records a day without data.",
    fields={
        "video_id": req(_video, "the video"),
        "as_of": req(_date, "the day the numbers describe"),
        "available": req(_bool, "false when the export gave nothing for this video"),
        "impressions": opt(_int(0), "thumbnail impressions"),
        "ctr": opt(_fraction, "impression click-through rate, a fraction 0..1; absent with "
                              "available=true when the Reporting file's scale is not settled yet"),
        "source": req(_enum("reporting-api", "studio-export"), "where the numbers came from"),
    },
    make_key=lambda d: f"studio:{d['video_id']}",
    checks=(_studio_available,),
))

IDEA_STATUS = _enum("new", "shortlisted", "planned", "rejected", "published")
PRODUCTION = _enum("new", "version", "compilation", "clip", "cover", "other")

kind(Kind(
    name="idea",
    key_doc="idea:<slug(title)>",
    writer="Recon",
    readers="Planning, Analytics, the creation recipes",
    doc="A video idea grounded in a keyword. Recon alone moves its status, from Planning's plan, the "
        "creation recipes' take and publish records: forward only, except that an idea whose only plans "
        "and takes were dropped (and that was never published) goes back to shortlisted. Planning and "
        "the creation recipes write their own records rather than editing this one (one writer per "
        "record).",
    fields={
        "title": req(_text, "the working title"),
        "keyword": req(_text, "the seed keyword it targets"),
        "hook": req(_text, "the first seconds, one sentence"),
        "thumbnail": req(_text, "the thumbnail concept, one sentence"),
        "format": req(FORMAT, "long, short, live or post"),
        "status": req(IDEA_STATUS, "new, shortlisted, planned, rejected, published"),
        "source": req(_text, "what grounded it: watch:<id>, trend, seed:<slug>, owner, community"),
        "score": opt(_float(0, 100), "0-100, from youtube-strategy's score_idea.py"),
        "note": opt(_text, "anything the next reader needs"),
        # What kind of work the idea is, so each creation recipe offers only what it can make; the
        # values are the same for every channel type, and channel-types.md says what each means there.
        "production": opt(PRODUCTION, "new, version, compilation, clip, cover or other"),
    },
    make_key=lambda d: f"idea:{slugify(d['title'])}",
))

kind(Kind(
    name="take",
    key_doc="take:<slug(idea)>",
    writer="the creation recipes",
    readers="Recon, Planning, Analytics, the creation recipes",
    doc="An idea a creation recipe took into work. Keyed by the idea, so one idea is taken once: Recon "
        "moves the idea to planned while the take is in-work, Planning plans nothing else for it, and "
        "the creation recipes stop offering it. The taker moves it to published with the video, or to "
        "dropped when the work is abandoned, which gives the idea back.",
    fields={
        "idea": req(_slug, "the idea's slug, without the idea: prefix"),
        "status": req(_enum("in-work", "published", "dropped"), "where the work stands"),
        "taken_at": req(_datetime, "when it was taken"),
        "source": req(_text, "the recipe that took it"),
        "title": opt(_text, "the working title of what is being made"),
        "plan": opt(_match(re.compile(r"^plan:\d{4}-\d{2}-\d{2}:[a-z0-9-]+$"), "a plan key"),
                    "the plan slot it fills, as its full key, when it came from one"),
        "video_id": opt(_video, "the video it became, with status published"),
        "note": opt(_text, "why it was dropped, or anything the next reader needs"),
    },
    make_key=lambda d: f"take:{d['idea']}",
))

kind(Kind(
    name="release",
    key_doc="release:<Spec id>",
    writer="a creation recipe with its own cadence (Create Music Release)",
    readers="Planning, Recon, Analytics, Pitch a Song on Spotify, the creation recipes",
    doc="One release a creation recipe with its own cadence is making, keyed by its instance, so the "
        "date is a field and can move. held = date chosen, nothing external done; committed = the "
        "first external act (a scheduled upload, a distributor submit) is about to happen or happened; "
        "dropped = abandoned. Released is not stored: see `records.py state` (CONTRACT.md, rule 17).",
    fields={
        "spec": req(_uuid, "the release's instance (Spec id); the key is release:<spec>"),
        "date": req(_date, "the release day, in profile:channel's timezone"),
        "time": req(_hhmm, "the release hour, local HH:MM in profile:channel's timezone"),
        "title": req(_text, "the song's title (not the YouTube title)"),
        "focus": req(_bool, "true for the release the channel promotes hardest (pitched)"),
        "status": req(_enum("held", "committed", "dropped"), "held, committed or dropped"),
        "held_at": req(_datetime, "when the date was first chosen"),
        "source": req(_text, "the recipe that makes it"),
        "idea": opt(_slug, "the idea made, without the idea: prefix; none for an own topic"),
        "submitted_at": opt(_datetime, "when it went to the distributor"),
        "video_id": opt(_video, "the main video, once uploaded"),
        "moves": opt(_list_of(_move), "every change of date: {from, to, at} or FROM>TO; repeat the flag"),
        "note": opt(_text, "why it was dropped, or anything the next reader needs"),
    },
    make_key=lambda d: f"release:{d['spec']}",
))

kind(Kind(
    name="plan",
    key_doc="plan:<YYYY-MM-DD>:<slot>",
    writer="Planning",
    readers="the creation recipes, Analytics, Recon",
    doc="A slot in the calendar. Several per day are allowed: the slot names it (main, short-1). "
        "Planning sets published itself when it finds the matching publish record.",
    fields={
        "date": req(_date, "the day of release"),
        "slot": req(_slug, "the slot of that day: main, short-1, live"),
        "title": req(_text, "the planned title"),
        "format": req(FORMAT, "long, short, live or post"),
        "status": req(_enum("planned", "in-progress", "published", "dropped"),
                      "where it stands; in-progress is reserved (no recipe of the set writes it). A slot "
                      "with no publish 14 days after its date is dropped; a later publish moves it to "
                      "published"),
        "idea": opt(_slug, "the idea's slug, when it comes from one"),
        "source": req(_text, "planning"),
    },
    make_key=lambda d: f"plan:{d['date']}:{d['slot']}",
))

kind(Kind(
    name="publish",
    key_doc="publish:<videoId>",
    writer="the creation recipes (e.g. Create Music Release)",
    readers="Analytics, Planning, Recon",
    doc="A video this channel published, with what it came from — the link that lets Analytics "
        "judge an idea and Planning close its slot.",
    fields={
        "video_id": req(_video, "the published video"),
        "published_at": req(_datetime, "when"),
        "format": req(FORMAT, "long, short, live or post"),
        "title": req(_text, "the title it went out with"),
        "plan": opt(_match(re.compile(r"^plan:\d{4}-\d{2}-\d{2}:[a-z0-9-]+$"), "a plan key"),
                    "the plan slot, as its full key plan:<date>:<slot>"),
        "idea": opt(_slug, "the idea's slug, without the idea: prefix"),
        "release": opt(_uuid, "the release (its Spec id) this video belongs to, when one does"),
        "source": req(_text, "the recipe that published it"),
    },
    make_key=lambda d: f"publish:{d['video_id']}",
))

kind(Kind(
    name="replied",
    key_doc="replied:<commentId>:<action>",
    writer="Community",
    readers="Community",
    doc="An action the channel took on a comment, so a later run does not take it twice. One record "
        "per action: a comment answered and then pinned has two, and neither overwrites the other.",
    fields={
        "comment_id": req(_comment, "the comment acted on"),
        "video_id": req(_video, "its video"),
        "action": req(_enum("reply", "pin", "heart", "hide", "report"), "what was done"),
        "at": req(_datetime, "when"),
        "reply_id": opt(_comment, "the reply's own id, for action=reply"),
        "source": req(_text, "community"),
    },
    make_key=lambda d: f"replied:{d['comment_id']}:{d['action']}",
    checks=(_replied_reply_has_text,),
))


# ── validation ─────────────────────────────────────────────────────────────────────────────────


def key_only(kind_name: str, raw: dict[str, Any]) -> str:
    """The key from just the fields that form it — what a reader has before it reads the record."""
    if kind_name not in KINDS:
        raise Refusal(f"unknown kind {kind_name!r}; known: {', '.join(KINDS)}")
    k = KINDS[kind_name]
    data = {n: k.fields[n].parse(n, v) for n, v in raw.items() if n in k.fields}
    try:
        return k.make_key(data)
    except KeyError as e:
        raise Refusal(f"the key of {kind_name} ({k.key_doc}) needs --{e.args[0].replace('_', '-')}") from None


def build(kind_name: str, raw: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Validate raw fields of a kind; return its key and the data to store."""
    if kind_name not in KINDS:
        raise Refusal(f"unknown kind {kind_name!r}; known: {', '.join(KINDS)}")
    k = KINDS[kind_name]
    unknown = sorted(set(raw) - set(k.fields))
    if unknown:
        raise Refusal(f"{kind_name} has no field {', '.join(unknown)}")
    data: dict[str, Any] = {}
    for name, spec in k.fields.items():
        if name not in raw or raw[name] is None:
            if spec.required:
                raise Refusal(f"{kind_name} needs {name}: {spec.doc}")
            continue
        data[name] = spec.parse(name, raw[name])
    for check in k.checks:
        check(data)
    data["v"] = SCHEMA_VERSION
    return k.make_key(data), data


_V, _C, _S = r"[A-Za-z0-9_-]{11}", r"[A-Za-z0-9_-]{10,}(\.[A-Za-z0-9_-]{10,})?", r"[a-z0-9]+(-[a-z0-9]+)*"
# The shape of each kind's key. A key under a kind's prefix that does not have this shape is not a
# record of this contract at all — another recipe's own state that happens to share the prefix
# (Create Music Release keeps publish:distrokid:<song>) — so it is foreign: skipped and counted,
# never a reason to stop.
KEY_SHAPES = {
    "profile": re.compile(r"^profile:channel$"),
    "seed": re.compile(rf"^seed:{_S}$"),
    "watch": re.compile(rf"^watch:{_V}$"),
    "velocity": re.compile(rf"^velocity:{_V}$"),
    "studio": re.compile(rf"^studio:{_V}$"),
    "idea": re.compile(rf"^idea:{_S}$"),
    "plan": re.compile(rf"^plan:\d{{4}}-\d{{2}}-\d{{2}}:{_S}$"),
    "publish": re.compile(rf"^publish:{_V}$"),
    "take": re.compile(rf"^take:{_S}$"),
    "release": re.compile(r"^release:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"),
    "replied": re.compile(rf"^replied:{_C}:(reply|pin|heart|hide|report)$"),
}


class Foreign(Refusal):
    """A key that only shares a kind's prefix; the reader skips it."""


def validate_stored(key: str, data: dict[str, Any]) -> str:
    """Check a record read back from memory; return its kind."""
    kind_name = key.split(":", 1)[0]
    shape = KEY_SHAPES.get(kind_name)
    if shape is None or not shape.match(key):
        raise Foreign(f"{key!r} is not a {kind_name} record of this contract "
                      f"({KINDS[kind_name].key_doc if kind_name in KINDS else 'unknown kind'}): skip it and count it")
    if data.get("v") != SCHEMA_VERSION:
        raise Refusal(f"{key} has schema version {data.get('v')!r}; this file reads {SCHEMA_VERSION}")
    fields = {k: v for k, v in data.items() if k != "v"}
    rebuilt_key, _ = build(kind_name, fields)
    if rebuilt_key != key:
        raise Refusal(f"stored under {key!r} but its fields make {rebuilt_key!r}")
    return kind_name


def schema(kind_name: str | None = None) -> dict[str, Any]:
    names = [kind_name] if kind_name else list(KINDS)
    out: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "kinds": {}}
    for name in names:
        if name not in KINDS:
            raise Refusal(f"unknown kind {name!r}; known: {', '.join(KINDS)}")
        k = KINDS[name]
        out["kinds"][name] = {
            "key": k.key_doc,
            "writer": k.writer,
            "readers": k.readers,
            "doc": k.doc,
            "fields": {
                f: {"required": s.required, "doc": s.doc,
                    **({"one_of": list(s.parse.allowed)} if hasattr(s.parse, "allowed") else {}),
                    **({"repeatable": True} if hasattr(s.parse, "repeated") else {})}
                for f, s in k.fields.items()
            },
        }
    return out


# ── writing ────────────────────────────────────────────────────────────────────────────────────

ID_LINES = {
    "spec_template_id": re.compile(r"^Process id.*?`([0-9a-f-]{36})`", re.M),
    "spec_id": re.compile(r"^Spec id.*?`([0-9a-f-]{36})`", re.M),
}
PROJECT_LINE = re.compile(r"^Project id.*?`([0-9a-f-]{36})`", re.M)


class Conflict(Refusal):
    """A conditional write lost: the record exists already, or changed since it was read."""

    def __init__(self, message: str, current: Any = None):
        super().__init__(message)
        self.current = current


def run_ids(args: argparse.Namespace, task_file: str = "current-task.md") -> dict[str, str]:
    ids = {"spec_template_id": args.spec_template_id, "spec_id": args.spec_id}
    if all(ids.values()):
        return ids  # type: ignore[return-value]
    try:
        with open(task_file, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        text = ""
    for name, pattern in ID_LINES.items():
        if not ids[name]:
            m = pattern.search(text)
            ids[name] = m.group(1) if m else None
    missing = [f"--{n.replace('_', '-')}" for n, v in ids.items() if not v]
    if missing:
        raise Refusal(f"write needs {' and '.join(missing)} (or the lines in {task_file})")
    return ids  # type: ignore[return-value]


def _platform_error(stdout: str) -> dict[str, Any]:
    try:
        doc = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    err = doc.get("error") if isinstance(doc, dict) else None
    return err if isinstance(err, dict) else {}


def upsert(key: str, data: dict[str, Any], ids: dict[str, str], spec_task_id: str | None,
           if_absent: bool = False, if_updated_at: str | None = None) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
        path = fh.name
    try:
        cmd = [
            os.environ.get("AI_INTEGRATION_BIN", "ai-integration"), "upsert-template-record",
            "--spec-template-id", ids["spec_template_id"],
            "--spec-id", ids["spec_id"],
            "--key", key,
            "--data-file", path,
        ]
        if spec_task_id:
            cmd += ["--spec-task-id", spec_task_id]
        # The condition is the platform's, in one statement: a read here and a write later could
        # not stop two steps of one release from overwriting each other.
        if if_absent:
            cmd += ["--if-absent"]
        if if_updated_at:
            cmd += ["--if-updated-at", if_updated_at]
        proc = subprocess.run(cmd, capture_output=True, text=True)
    finally:
        os.unlink(path)
    if proc.returncode != 0:
        err = _platform_error(proc.stdout)
        if err.get("type") == "ConflictError":
            raise Conflict(f"{key}: {err.get('message') or 'the condition of the write was not met'}",
                           err.get("current") or err.get("details"))
        raise Refusal(f"ai-integration refused the write (exit {proc.returncode}): "
                      f"{(proc.stdout or proc.stderr).strip()[:500]}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"raw": proc.stdout.strip()[:500]}


def get_record(key: str, ids: dict[str, str], project_id: str) -> dict[str, Any] | None:
    """The stored record as the platform returns it ({key, data, updatedAt, …}), or None."""
    cmd = [os.environ.get("AI_INTEGRATION_BIN", "ai-integration"), "get-template-record",
           "--spec-template-id", ids["spec_template_id"], "--project-id", project_id, "--key", key]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise Refusal(f"ai-integration refused the read (exit {proc.returncode}): "
                      f"{(proc.stdout or proc.stderr).strip()[:500]}")
    try:
        doc = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise Refusal(f"ai-integration answered something that is not JSON: {proc.stdout[:200]}") from None
    rec = doc.get("data") if isinstance(doc, dict) and "data" in doc else doc
    return rec if isinstance(rec, dict) and rec else None


def update(key: str, sets: list[str], appends: list[str], ids: dict[str, str], project_id: str,
           spec_task_id: str | None) -> dict[str, Any]:
    """Read, merge, write only if nobody changed it meanwhile; one retry, then refuse."""
    kind_name = key.split(":", 1)[0]
    if kind_name not in KINDS:
        raise Refusal(f"unknown kind {kind_name!r}")
    for attempt in (1, 2):
        rec = get_record(key, ids, project_id)
        if rec is None:
            raise Refusal(f"{key} does not exist: write it first")
        data = {k: v for k, v in (rec.get("data") or {}).items() if k != "v"}
        for item in sets:
            field, sep, value = item.partition("=")
            if not sep:
                raise Refusal(f"--set takes field=value, got {item!r}")
            data[field.strip()] = value
        for item in appends:
            field, sep, value = item.partition("=")
            if not sep:
                raise Refusal(f"--append takes field=value, got {item!r}")
            current = data.get(field.strip()) or []
            data[field.strip()] = [*current, value] if isinstance(current, list) else [current, value]
        new_key, built = build(kind_name, data)
        if new_key != key:
            raise Refusal(f"the change moves the record to {new_key!r}; a key field cannot change")
        try:
            written = upsert(key, built, ids, spec_task_id, if_updated_at=str(rec.get("updatedAt") or ""))
            return {"ok": True, "key": key, "data": built, "written": written, "attempts": attempt}
        except Conflict:
            if attempt == 2:
                raise
    raise Refusal("unreachable")


def release_state(release: dict[str, Any], publishes: list[dict[str, Any]], today: str) -> str:
    """active, released or dropped — the contract's rule, in one place (CONTRACT.md, rule 17)."""
    status = release.get("status")
    if status == "dropped":
        return "dropped"
    day = date.fromisoformat(release["date"])
    now = date.fromisoformat(today)
    if status == "held" and (now - day).days > 14:
        return "dropped"
    spec = release.get("spec")
    if status == "committed" and day <= now and any(p.get("release") == spec for p in publishes):
        return "released"
    return "active"


# ── command line ───────────────────────────────────────────────────────────────────────────────


def add_kind_parsers(sub: argparse._SubParsersAction, command: str, help_text: str) -> None:
    p = sub.add_parser(command, help=help_text)
    kinds = p.add_subparsers(dest="kind", required=True, metavar="KIND")
    for name, k in KINDS.items():
        # argparse formats help with %, and the docs speak in percentages.
        kp = kinds.add_parser(name, help=k.doc.replace("%", "%%"))
        for fname, spec in k.fields.items():
            flag = "--" + fname.replace("_", "-")
            if hasattr(spec.parse, "repeated"):
                kp.add_argument(flag, dest=fname, action="append", help=spec.doc.replace("%", "%%"))
            else:
                kp.add_argument(flag, dest=fname, help=spec.doc.replace("%", "%%"))
        if command == "write":
            kp.add_argument("--spec-template-id", help="this run's Process id")
            kp.add_argument("--spec-id", help="this run's Spec id")
            kp.add_argument("--spec-task-id", help="this run's step, when known")
            cond = kp.add_mutually_exclusive_group()
            cond.add_argument("--if-absent", action="store_true",
                              help="write only if the record does not exist yet (exit 4 if it does)")
            cond.add_argument("--if-updated-at", help="write only if the record is still at this updatedAt")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="records.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)
    sp = sub.add_parser("schema", help="the kinds, their keys and fields")
    sp.add_argument("kind", nargs="?")
    add_kind_parsers(sub, "key", "print the key alone")
    add_kind_parsers(sub, "check", "validate and print, without writing")
    add_kind_parsers(sub, "write", "validate and upsert into this recipe's memory")
    up = sub.add_parser("update", help="change fields of a stored record, only if nobody changed it meanwhile")
    up.add_argument("--key", required=True)
    up.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE")
    up.add_argument("--append", action="append", default=[], metavar="FIELD=VALUE",
                    help="add one item to a list field (e.g. moves=2026-11-28>2026-12-05)")
    up.add_argument("--spec-template-id", help="this run's Process id")
    up.add_argument("--spec-id", help="this run's Spec id")
    up.add_argument("--project-id", help="this run's Project id")
    up.add_argument("--spec-task-id", help="this run's step, when known")
    st = sub.add_parser("state", help="active, released or dropped, for a release record")
    st.add_argument("--data", required=True, help="the release record's data as JSON")
    st.add_argument("--publishes", help="a JSON file: the publish records' data (a list)")
    st.add_argument("--today", help="YYYY-MM-DD in profile:channel's timezone (default: today, UTC)")
    vp = sub.add_parser("validate", help="check a stored record")
    vp.add_argument("--key", required=True)
    vp.add_argument("--data", required=True, help="the record's data as JSON")
    return p


RUN_FLAGS = {"command", "kind", "spec_template_id", "spec_id", "spec_task_id", "if_absent", "if_updated_at"}


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "schema":
            out: Any = schema(args.kind)
        elif args.command == "validate":
            try:
                data = json.loads(args.data)
            except json.JSONDecodeError as e:
                raise Refusal(f"--data is not JSON: {e}") from None
            if not isinstance(data, dict):
                raise Refusal("--data must be a JSON object")
            out = {"ok": True, "kind": validate_stored(args.key, data)}
        elif args.command == "update":
            ids = run_ids(args)
            project_id = args.project_id
            if not project_id:
                try:
                    with open("current-task.md", encoding="utf-8") as fh:
                        m = PROJECT_LINE.search(fh.read())
                    project_id = m.group(1) if m else None
                except OSError:
                    project_id = None
            if not project_id:
                raise Refusal("update needs --project-id (or the Project id line in current-task.md)")
            out = update(args.key, args.set, args.append, ids, project_id, args.spec_task_id)
        elif args.command == "state":
            try:
                rel = json.loads(args.data)
                pubs = json.load(open(args.publishes, encoding="utf-8")) if args.publishes else []
            except (OSError, json.JSONDecodeError) as e:
                raise Refusal(f"cannot read the input: {e}") from None
            today = args.today or datetime.now(timezone.utc).date().isoformat()
            out = {"ok": True, "state": release_state(rel, pubs if isinstance(pubs, list) else [], today)}
        else:
            raw = {k: v for k, v in vars(args).items() if k not in RUN_FLAGS and v is not None}
            if args.command == "key":
                print(json.dumps({"key": key_only(args.kind, raw)}, ensure_ascii=False, indent=2))
                return 0
            key, data = build(args.kind, raw)
            if args.command == "check":
                out = {"key": key, "data": data}
            else:
                ids = run_ids(args)
                result = upsert(key, data, ids, args.spec_task_id,
                                if_absent=args.if_absent, if_updated_at=args.if_updated_at)
                out = {"ok": True, "key": key, "data": data, "written": result}
    except Conflict as e:
        # Exit 4: the write was conditional and lost — re-read and decide, never retry blindly.
        print(json.dumps({"ok": False, "conflict": True, "error": str(e), "current": e.current},
                         ensure_ascii=False))
        return 4
    except Foreign as e:
        # Exit 3, apart from 2: a reader skips a foreign key and goes on; it stops only on a version.
        print(json.dumps({"ok": False, "foreign": True, "error": str(e)}, ensure_ascii=False))
        return 3
    except Refusal as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
