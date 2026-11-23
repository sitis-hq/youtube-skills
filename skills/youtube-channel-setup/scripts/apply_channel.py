#!/usr/bin/env python3
"""Apply the channel's branding, banner and watermark through the Data API, each under an intent.

  apply_channel.py branding --desired desired.json [--dry-run]
      Bring brandingSettings.channel to a desired state. The file holds only the fields to set,
      out of: description, keywords, country, defaultLanguage, unsubscribedTrailer. The script reads
      the whole brandingSettings part, merges the desired fields into it and sends the whole part
      back (channels.update deletes every mutable property the request leaves out), then re-reads
      and checks every desired field. Nothing differs → no claim, no write. Key:
      settings:channel:<digest of the desired state>.

  apply_channel.py banner --image banner-upload.jpg
      channelBanners.insert, then channels.update with brandingSettings.image.bannerExternalUrl =
      the url it returned, then a re-read. The file is checked against YouTube's limits first.
      Key: branding:banner:<digest of the file>.

  apply_channel.py watermark --image mark.png --timing offsetFromEnd --offset-ms 15000 [--duration-ms N]
      watermarks.set for the connection's own channel. Key: branding:watermark:<digest of the file
      and the timing> — the same image with another timing is a new action.

  apply_channel.py playlist --spec playlist.json
      Create one playlist and add its videos in order. The file holds {"title", "description"?,
      "privacy": "public"|"unlisted"|"private", "videos": [video ids]}. The title is the playlist's
      identity: if the channel already has a playlist with exactly this title, nothing is created
      and the output names it. Otherwise playlists.insert, playlistItems.insert per video, then a
      re-read of the items. Key: playlist:create:<slug of the title>.

Not here: home sections and the profile picture — Studio playbooks in youtube-studio
(references/home-tab.md, references/channel-profile.md).

Re-reads wait for YouTube. Its read side can lag a write: on 2026-11-06 a banner set by this script
was live in Studio while channels.list still returned the old bannerExternalUrl. So a re-read that
does not show the change yet is repeated after REREAD_WAITS seconds before the outcome is called
uncertain; each try costs 1 unit.

Failure semantics (as youtube-community's comments.py): a 4xx answer means YouTube refused and
nothing changed → the intent is failed, a later run may retry; a missing scope adds
"fallback": "studio" and the playbook. A 5xx, a lost answer, a 2xx without the expected field or a
re-read that does not show the change → the claim stays open and the output says "uncertain": do not
retry, check on YouTube. A claim already committed → skipped and said so.

Data API v3 reference read 2026-11-04:
  https://developers.google.com/youtube/v3/docs/channels/update — PUT, part=brandingSettings, body
    needs id; omitting a property that has a value deletes it; 50 units.
  https://developers.google.com/youtube/v3/docs/channelBanners/insert — POST to the upload URL, no
    request body besides the media; image/jpeg or image/png, 16:9, at least 2048x1152, at most 6 MB;
    the answer's `url` goes to brandingSettings.image.bannerExternalUrl; 50 units.
  https://developers.google.com/youtube/v3/docs/watermarks/set — POST to the upload URL with
    channelId; the body is a watermark resource {timing: {type: offsetFromStart|offsetFromEnd,
    offsetMs, durationMs?}} plus the image (image/jpeg or image/png); offsetMs at least 1000 for
    offsetFromEnd; durationMs at least 1000 and, for offsetFromEnd, not above offsetMs; success is
    204 No Content; 50 units. `position` is deprecated and ignored.
  channels.list costs 1 unit.
  https://developers.google.com/youtube/v3/docs/playlists/insert — POST, part=snippet,status;
    snippet.title required, snippet.description and status.privacyStatus (private, public,
    unlisted) settable; 50 units. playlists.list mine=true, maxResults up to 50: 1 unit.
  https://developers.google.com/youtube/v3/docs/playlistItems/insert — POST, part=snippet,
    snippet.playlistId and snippet.resourceId {kind: youtube#video, videoId}; 50 units.
    playlistItems.list playlistId, maxResults up to 50: 1 unit. (Read 2026-11-23; the reference
    states no length limit for a playlist title or description, so none is checked here: a refusal
    is YouTube's 4xx.)

All output is JSON on stdout; a refusal exits 2 with {"ok": false, "error": ...}. The access token
comes from `ai-integration oauth-token` at the moment of use and is never printed or written.
Standard library only: Python 3.11.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
STUDIO_SCRIPTS = HERE.parents[1] / "youtube-studio" / "scripts"
sys.path.insert(0, str(STUDIO_SCRIPTS))
try:
    import intent  # noqa: E402
except ImportError:  # pragma: no cover - only when the tree is incomplete
    print(json.dumps({"ok": False, "error": f"youtube-studio's intent.py is missing at {STUDIO_SCRIPTS}"}))
    sys.exit(2)

API = "https://www.googleapis.com/youtube/v3/"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3/"
COST = {"channels.list": 1, "channels.update": 50, "channelBanners.insert": 50, "watermarks.set": 50,
        "playlists.list": 1, "playlists.insert": 50, "playlistItems.insert": 50, "playlistItems.list": 1}
# Seconds to wait before each repeated re-read (see the module docstring). Tests replace SLEEP.
REREAD_WAITS = (5, 15, 30)
SLEEP = time.sleep
PRIVACY = ("public", "unlisted", "private")
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
PLAYBOOK = "youtube-studio/references/channel-profile.md"

FIELDS = ("description", "keywords", "country", "defaultLanguage", "unsubscribedTrailer")
# Description: references/settings.md (the About text limit). Keywords: 500 characters, the cap
# Studio puts on the channel keywords field; the Data API reference does not state one.
LIMITS = {"description": 1000, "keywords": 500}

# Banner: channelBanners.insert reference and YouTube Help 10456525, read 2026-11-04 — the same
# limits banner_preview.py writes its upload file to.
BANNER_MIN = (2048, 1152)
BANNER_BYTES = 6 * 1024 * 1024
# Watermark: YouTube Help 10456525, read 2026-11-04 — square, at least 150x150, under 1 MB. The API
# accepts up to 10 MB; the stricter Help limit is what Studio shows the owner, so it is the one kept.
MARK_MIN = 150
MARK_BYTES = 1024 * 1024
SAY_UNCERTAIN = "Outcome unknown — do not retry. Check the channel on YouTube and tell the owner."


class Refusal(Exception):
    pass


class ApiError(Exception):
    """A Data API answer other than success. status None: the request may not have arrived or its
    answer was lost, so the outcome is unknown."""

    def __init__(self, status: int | None, reason: str, message: str):
        super().__init__(f"{status or 'no answer'} {reason}: {message}")
        self.status, self.reason, self.message = status, reason, message

    @property
    def certain_not_done(self) -> bool:
        return self.status is not None and 400 <= self.status < 500

    @property
    def scope_missing(self) -> bool:
        return self.status in (401, 403) and self.reason in (
            "insufficientPermissions", "ACCESS_TOKEN_SCOPE_INSUFFICIENT", "forbidden", "authError")


# ── the network, behind two functions the tests replace ─────────────────────────────────────────


def access_token(connection: str) -> str:
    cmd = [os.environ.get("AI_INTEGRATION_BIN", "ai-integration"), "oauth-token",
           "--connection", connection, "--field", "accessToken"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise Refusal(f"{cmd[0]} is not on PATH — this works only inside a Sitis run") from None
    token = proc.stdout.strip()
    if proc.returncode != 0 or not token or token.startswith("{"):
        # The verb prints its error as JSON; pass its message on, never the token.
        try:
            msg = json.loads(token).get("error", {}).get("message", "")
        except (json.JSONDecodeError, AttributeError):
            msg = proc.stderr.strip()[:300]
        raise Refusal(f"no access token for connection {connection}: {msg or 'empty answer'}")
    return token


def http(method: str, url: str, headers: dict[str, str], body: bytes | None) -> tuple[int, bytes]:
    """The one place the network is touched. A lost answer raises ApiError(None, ...)."""
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ApiError(None, "network", str(e)) from None


class Client:
    def __init__(self, connection: str):
        self.connection = connection
        self.token: str | None = None
        self.units = 0

    def call(self, name: str, method: str, url: str, params: dict[str, Any],
             body: bytes | None = None, content_type: str | None = None) -> dict[str, Any]:
        if self.token is None:
            self.token = access_token(self.connection)
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        # Counted before the call: a refused request still spends its quota.
        self.units += COST[name]
        status, raw = http(method, url + "?" + urllib.parse.urlencode(params), headers, body)
        if status >= 400:
            try:
                err = json.loads(raw).get("error", {})
            except (json.JSONDecodeError, ValueError, AttributeError):
                err = {}
            reason = (err.get("errors") or [{}])[0].get("reason") or err.get("status") or "error"
            raise ApiError(status, reason, err.get("message") or raw[:200].decode("utf-8", "replace"))
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # A 2xx we cannot read: for a write the change may have happened.
            raise ApiError(None, "unreadable", f"{name} answered {status} with a body that is not JSON") from None

    def branding(self) -> dict[str, Any]:
        page = self.call("channels.list", "GET", API + "channels", {"part": "brandingSettings", "mine": "true"})
        items = page.get("items") or []
        if not items:
            raise Refusal("channels.list mine=true found no channel for this connection")
        return items[0]

    def update_branding(self, channel_id: str, branding: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps({"id": channel_id, "brandingSettings": branding}).encode("utf-8")
        return self.call("channels.update", "PUT", API + "channels", {"part": "brandingSettings"},
                         body, "application/json")

    def playlist_titles(self) -> dict[str, str]:
        """Title → id of every playlist the channel owns."""
        found: dict[str, str] = {}
        params: dict[str, Any] = {"part": "snippet", "mine": "true", "maxResults": 50}
        while True:
            page = self.call("playlists.list", "GET", API + "playlists", params)
            for item in page.get("items") or []:
                found.setdefault((item.get("snippet") or {}).get("title") or "", item.get("id"))
            if not page.get("nextPageToken"):
                return found
            params["pageToken"] = page["nextPageToken"]

    def playlist_videos(self, playlist_id: str) -> list[str]:
        videos: list[str] = []
        params: dict[str, Any] = {"part": "snippet", "playlistId": playlist_id, "maxResults": 50}
        while True:
            page = self.call("playlistItems.list", "GET", API + "playlistItems", params)
            for item in page.get("items") or []:
                videos.append(((item.get("snippet") or {}).get("resourceId") or {}).get("videoId"))
            if not page.get("nextPageToken"):
                return videos
            params["pageToken"] = page["nextPageToken"]


def reread(read, missing) -> tuple[Any, Any, int]:
    """Read until `missing(read())` is empty, waiting REREAD_WAITS between tries.

    Returns the last read, what it still misses, and the number of reads. An ApiError from a read
    propagates: the caller decides what an unreadable re-read means.
    """
    after = read()
    left = missing(after)
    tries = 1
    for wait in REREAD_WAITS:
        if not left:
            break
        SLEEP(wait)
        after = read()
        left = missing(after)
        tries += 1
    return after, left, tries


# ── validation ─────────────────────────────────────────────────────────────────────────────────


def load_desired(path: str) -> dict[str, str]:
    try:
        with open(path, encoding="utf-8") as fh:
            desired = json.load(fh)
    except OSError as e:
        raise Refusal(f"cannot read {path}: {e.strerror}") from None
    except json.JSONDecodeError as e:
        raise Refusal(f"{path} is not JSON: {e}") from None
    if not isinstance(desired, dict) or not desired:
        raise Refusal(f"{path} must hold a JSON object with at least one of {', '.join(FIELDS)}")
    unknown = sorted(set(desired) - set(FIELDS))
    if unknown:
        raise Refusal(f"{', '.join(unknown)}: not set by this command (only {', '.join(FIELDS)}); "
                      "name and handle, links and the picture are Studio work — " + PLAYBOOK)
    for name, value in desired.items():
        if not isinstance(value, str):
            raise Refusal(f"{name} must be a string, got {type(value).__name__}")
        if name in LIMITS and len(value) > LIMITS[name]:
            raise Refusal(f"{name} is {len(value)} characters; YouTube allows {LIMITS[name]}")
    if "country" in desired and not re.match(r"^[A-Z]{2}$", desired["country"]):
        raise Refusal(f"country must be an ISO 3166-1 alpha-2 code like 'AR', got {desired['country']!r}")
    if "unsubscribedTrailer" in desired and not re.match(r"^[A-Za-z0-9_-]{11}$", desired["unsubscribedTrailer"]):
        raise Refusal(f"unsubscribedTrailer must be an 11-character video id, got {desired['unsubscribedTrailer']!r}")
    if "keywords" in desired:
        try:
            shlex.split(desired["keywords"])
        except ValueError as e:
            raise Refusal(f"keywords: {e} — phrases go in double quotes, separated by spaces") from None
    return desired


def image_info(path: str) -> dict[str, Any]:
    """Type and size from the file header: exact for PNG and JPEG, and needs no image library."""
    try:
        data = Path(path).read_bytes()
    except OSError as e:
        raise Refusal(f"cannot read {path}: {e.strerror}") from None
    if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        w, h = struct.unpack(">II", data[16:24])
        return {"mime": "image/png", "width": w, "height": h, "bytes": len(data), "data": data}
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7 or marker == 0xFF:
                i += 1 if marker == 0xFF else 2
                continue
            seg = struct.unpack(">H", data[i + 2:i + 4])[0]
            # Start-of-frame markers carry the size; C4, C8 and CC are tables, not frames.
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return {"mime": "image/jpeg", "width": w, "height": h, "bytes": len(data), "data": data}
            i += 2 + seg
        raise Refusal(f"{path}: a JPEG without a frame header")
    raise Refusal(f"{path} is neither PNG nor JPEG; YouTube takes only those")


def check_banner(path: str) -> dict[str, Any]:
    info = image_info(path)
    w, h = info["width"], info["height"]
    problems = []
    if abs((w / h) / (16 / 9) - 1) > 0.01:  # banner_preview.py's tolerance
        problems.append(f"{w}x{h} is not 16:9")
    if w < BANNER_MIN[0] or h < BANNER_MIN[1]:
        problems.append(f"{w}x{h} is below {BANNER_MIN[0]}x{BANNER_MIN[1]}")
    if info["bytes"] > BANNER_BYTES:
        problems.append(f"{info['bytes']} bytes is over 6 MB")
    if problems:
        raise Refusal(f"{path}: {'; '.join(problems)} — make the upload file with banner_preview.py")
    return info


def check_watermark(path: str) -> dict[str, Any]:
    info = image_info(path)
    w, h = info["width"], info["height"]
    problems = []
    if w != h:
        problems.append(f"{w}x{h} is not square")
    if min(w, h) < MARK_MIN:
        problems.append(f"{w}x{h} is below {MARK_MIN}x{MARK_MIN}")
    if info["bytes"] >= MARK_BYTES:
        problems.append(f"{info['bytes']} bytes is not under 1 MB")
    if problems:
        raise Refusal(f"{path}: {'; '.join(problems)}")
    return info


def check_timing(timing: str, offset_ms: int, duration_ms: int | None) -> dict[str, Any]:
    if offset_ms < 0:
        raise Refusal("--offset-ms cannot be negative")
    if timing == "offsetFromEnd" and offset_ms < 1000:
        raise Refusal("--offset-ms must be at least 1000 with offsetFromEnd")
    out: dict[str, Any] = {"type": timing, "offsetMs": offset_ms}
    if duration_ms is not None:
        if duration_ms < 1000:
            raise Refusal("--duration-ms must be at least 1000")
        if timing == "offsetFromEnd" and duration_ms > offset_ms:
            raise Refusal("--duration-ms cannot exceed --offset-ms with offsetFromEnd")
        out["durationMs"] = duration_ms
    return out


# ── the comparisons ────────────────────────────────────────────────────────────────────────────


def same(name: str, a: Any, b: Any) -> bool:
    if name == "keywords":
        # YouTube re-spaces and re-quotes keywords; the list of terms is what was asked for.
        try:
            return shlex.split(a or "") == shlex.split(b or "")
        except ValueError:
            return a == b
    return (a or "") == (b or "")


def diff(current: dict[str, Any], desired: dict[str, str]) -> list[dict[str, Any]]:
    return [{"field": f"brandingSettings.channel.{k}", "from": current.get(k), "to": v}
            for k, v in desired.items() if not same(k, current.get(k), v)]


# ── actions behind an intent ───────────────────────────────────────────────────────────────────


def _api_failure(key: str, ids: dict[str, str], e: ApiError, client: Client, **extra: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False, "key": key, "error": str(e), "units_used": client.units, **extra}
    if e.certain_not_done:
        intent.fail(key, ids, f"Data API refused: {e}")
        out["intent"] = "failed"
        if e.scope_missing:
            out.update(fallback="studio", playbook=PLAYBOOK,
                       say="The connection cannot do this through the API; do it in Studio under a new claim.")
    else:
        out.update(intent="claimed", uncertain=True, say=SAY_UNCERTAIN)
    return out


def _uncertain(key: str, client: Client, error: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "key": key, "intent": "claimed", "uncertain": True, "error": error,
            "units_used": client.units, "say": SAY_UNCERTAIN, **extra}


def _skipped(key: str, claimed: dict[str, Any], client: Client) -> dict[str, Any]:
    return {"ok": True, "key": key, "acted": False, "claim": claimed, "units_used": client.units,
            "say": claimed["say"]}


def apply_branding(client: Client, ids_fn, desired_path: str, dry_run: bool) -> dict[str, Any]:
    desired = load_desired(desired_path)
    key = intent.build_key("settings", area="channel", state_file=desired_path)
    channel = client.branding()
    branding = channel.get("brandingSettings") or {}
    changes = diff(branding.get("channel") or {}, desired)
    if not changes:
        return {"ok": True, "changed": False, "key": key, "units_used": client.units}
    if dry_run:
        return {"ok": True, "dry_run": True, "changed": True, "key": key, "diff": changes,
                "units_used": client.units}
    ids = ids_fn()
    claimed = intent.claim(key, ids)
    if not claimed["act"]:
        out = _skipped(key, claimed, client)
        out["diff"] = changes
        if claimed.get("status") == "committed":
            out["say"] += (" The channel differs from that state again: someone changed it since; "
                           "a new desired state (a new file content) makes a new intention.")
        return out
    # The whole part goes back: every value YouTube holds now, with only the desired fields replaced.
    merged = json.loads(json.dumps(branding))
    merged.setdefault("channel", {}).update(desired)
    try:
        client.update_branding(channel["id"], merged)
    except ApiError as e:
        return _api_failure(key, ids, e, client, diff=changes)
    try:
        _, left, tries = reread(
            client.branding,
            lambda after: diff((after.get("brandingSettings") or {}).get("channel") or {}, desired))
    except ApiError as e:
        # The update answered 2xx: a failed re-read says nothing about whether it took.
        return _uncertain(key, client, f"the re-read failed: {e}", diff=changes)
    if left:
        return _uncertain(key, client, f"{tries} re-reads do not show every desired field", diff=changes,
                          not_applied=left)
    intent.commit(key, ids, {"diff": changes})
    return {"ok": True, "changed": True, "acted": True, "key": key, "diff": changes, "units_used": client.units}


def apply_banner(client: Client, ids_fn, image: str) -> dict[str, Any]:
    info = check_banner(image)
    key = intent.build_key("branding", part="banner", file=image)
    ids = ids_fn()
    claimed = intent.claim(key, ids)
    if not claimed["act"]:
        return _skipped(key, claimed, client)
    try:
        made = client.call("channelBanners.insert", "POST", UPLOAD + "channelBanners/insert",
                           {"uploadType": "media"}, info["data"], info["mime"])
    except ApiError as e:
        return _api_failure(key, ids, e, client)
    url = made.get("url")
    if not url:
        return _uncertain(key, client, "channelBanners.insert answered without a url")
    try:
        channel = client.branding()
        branding = json.loads(json.dumps(channel.get("brandingSettings") or {}))
        branding.setdefault("image", {})["bannerExternalUrl"] = url
        client.update_branding(channel["id"], branding)
    except ApiError as e:
        # An uploaded banner that was never set shows nowhere: a refused update leaves the channel
        # as it was, so the same failure rule holds.
        return _api_failure(key, ids, e, client, banner_url=url)
    shown_url = lambda after: ((after.get("brandingSettings") or {}).get("image") or {}).get("bannerExternalUrl")
    try:
        after, left, tries = reread(client.branding, lambda after: shown_url(after) != url)
    except ApiError as e:
        return _uncertain(key, client, f"the re-read failed: {e}", banner_url=url)
    if left:
        return _uncertain(key, client, f"{tries} re-reads do not show the new banner url", banner_url=url,
                          read_back=shown_url(after),
                          check="Studio > Customization > Branding shows the live banner; the API can lag it")
    intent.commit(key, ids, {"banner_url": url})
    return {"ok": True, "acted": True, "key": key, "banner_url": url, "units_used": client.units,
            "say": "Applied. Open the channel page to see it; YouTube can take a while to show a new banner."}


def apply_watermark(client: Client, ids_fn, image: str, timing: dict[str, Any]) -> dict[str, Any]:
    info = check_watermark(image)
    spec = f"{timing['type']}:{timing['offsetMs']}" + (f":{timing['durationMs']}" if "durationMs" in timing else "")
    key = intent.build_key("watermark", file=image, timing=spec)
    ids = ids_fn()
    # A read, so before the claim: a refusal here changes nothing and needs no intent.
    page = client.call("channels.list", "GET", API + "channels", {"part": "id", "mine": "true"})
    items = page.get("items") or []
    if not items:
        raise Refusal("channels.list mine=true found no channel for this connection")
    claimed = intent.claim(key, ids)
    if not claimed["act"]:
        return _skipped(key, claimed, client)
    boundary = "apply-channel-" + uuid.uuid4().hex
    meta = json.dumps({"timing": timing}).encode("utf-8")
    body = b"".join([
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode(), meta,
        f"\r\n--{boundary}\r\nContent-Type: {info['mime']}\r\n\r\n".encode(), info["data"],
        f"\r\n--{boundary}--\r\n".encode()])
    try:
        client.call("watermarks.set", "POST", UPLOAD + "watermarks/set",
                    {"channelId": items[0]["id"], "uploadType": "multipart"}, body,
                    f"multipart/related; boundary={boundary}")
    except ApiError as e:
        return _api_failure(key, ids, e, client)
    # The Data API has no method that reads a watermark back: the 2xx answer is the only evidence.
    intent.commit(key, ids, {"timing": timing})
    return {"ok": True, "acted": True, "key": key, "timing": timing, "units_used": client.units,
            "say": "Set. The API cannot read a watermark back: check a video's player on YouTube."}


def load_playlist(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as fh:
            spec = json.load(fh)
    except OSError as e:
        raise Refusal(f"cannot read {path}: {e.strerror}") from None
    except json.JSONDecodeError as e:
        raise Refusal(f"{path} is not JSON: {e}") from None
    if not isinstance(spec, dict):
        raise Refusal(f"{path} must hold an object with title, privacy and videos")
    unknown = set(spec) - {"title", "description", "privacy", "videos"}
    if unknown:
        raise Refusal(f"{path}: unknown fields {sorted(unknown)}; allowed: title, description, privacy, videos")
    title = spec.get("title")
    if not isinstance(title, str) or not title.strip():
        raise Refusal("the playlist needs a non-empty title")
    if spec.get("privacy") not in PRIVACY:
        raise Refusal(f"privacy must be one of {', '.join(PRIVACY)}, got {spec.get('privacy')!r}")
    if "description" in spec and not isinstance(spec["description"], str):
        raise Refusal("description must be text")
    videos = spec.get("videos")
    if not isinstance(videos, list) or not videos:
        raise Refusal("videos must be a non-empty list of video ids, in the playlist's order")
    bad = [v for v in videos if not isinstance(v, str) or not VIDEO_ID.match(v)]
    if bad:
        raise Refusal(f"not video ids: {bad}")
    if len(set(videos)) != len(videos):
        raise Refusal("a video is listed twice")
    return {"title": title.strip(), "description": spec.get("description", ""), "privacy": spec["privacy"],
            "videos": videos}


def apply_playlist(client: Client, ids_fn, spec_path: str) -> dict[str, Any]:
    spec = load_playlist(spec_path)
    key = intent.build_key("playlist", title=spec["title"])
    # A read, so before the claim. The title is the playlist's identity: one already there is never
    # created again, whoever made it — a claim alone would not see one the owner made by hand.
    existing = client.playlist_titles().get(spec["title"])
    if existing:
        return {"ok": True, "acted": False, "key": key, "playlist_id": existing, "units_used": client.units,
                "say": "The channel already has a playlist with this title; nothing was created."}
    ids = ids_fn()
    claimed = intent.claim(key, ids)
    if not claimed["act"]:
        return _skipped(key, claimed, client)
    body = json.dumps({"snippet": {"title": spec["title"], "description": spec["description"]},
                       "status": {"privacyStatus": spec["privacy"]}}).encode("utf-8")
    try:
        made = client.call("playlists.insert", "POST", API + "playlists", {"part": "snippet,status"},
                           body, "application/json")
    except ApiError as e:
        return _api_failure(key, ids, e, client)
    playlist_id = made.get("id")
    if not playlist_id:
        return _uncertain(key, client, "playlists.insert answered without an id")
    refused: list[dict[str, str]] = []
    unknown: list[str] = []
    for video in spec["videos"]:
        item = json.dumps({"snippet": {"playlistId": playlist_id,
                                       "resourceId": {"kind": "youtube#video", "videoId": video}}}).encode("utf-8")
        try:
            client.call("playlistItems.insert", "POST", API + "playlistItems", {"part": "snippet"},
                        item, "application/json")
        except ApiError as e:
            if e.certain_not_done:
                refused.append({"video": video, "error": str(e)})
            else:
                unknown.append(video)
    if refused or unknown:
        # The playlist exists, so the claim stays open whatever happened to its items: a retry under
        # the same title would find it and stop, and the owner decides what to add by hand.
        return _uncertain(key, client, "not every video was added", playlist_id=playlist_id,
                          refused=refused, unknown=unknown)
    try:
        listed, left, tries = reread(lambda: client.playlist_videos(playlist_id),
                                     lambda got: [v for v in spec["videos"] if v not in got])
    except ApiError as e:
        return _uncertain(key, client, f"the re-read failed: {e}", playlist_id=playlist_id)
    if left:
        return _uncertain(key, client, f"{tries} re-reads do not show every video", playlist_id=playlist_id,
                          not_listed=left)
    intent.commit(key, ids, {"playlist_id": playlist_id, "videos": spec["videos"]})
    return {"ok": True, "acted": True, "key": key, "playlist_id": playlist_id, "videos": len(spec["videos"]),
            "units_used": client.units}


# ── command line ───────────────────────────────────────────────────────────────────────────────


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="apply_channel.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)
    b = sub.add_parser("branding", help="bring brandingSettings.channel to a desired state")
    b.add_argument("--desired", required=True,
                   help="JSON object with any of: " + ", ".join(FIELDS))
    b.add_argument("--dry-run", action="store_true", help="print the diff only; no claim, no write")
    n = sub.add_parser("banner", help="upload and set the channel banner")
    n.add_argument("--image", required=True, help="JPEG or PNG, 16:9, >= 2048x1152, <= 6 MB")
    w = sub.add_parser("watermark", help="set the video watermark")
    w.add_argument("--image", required=True, help="JPEG or PNG, square, >= 150x150, < 1 MB")
    w.add_argument("--timing", required=True, choices=["offsetFromEnd", "offsetFromStart"])
    w.add_argument("--offset-ms", required=True, type=int,
                   help="from the start, or before the end (>= 1000 with offsetFromEnd)")
    w.add_argument("--duration-ms", type=int, help="how long it shows (>= 1000); omitted: to the end")
    pl = sub.add_parser("playlist", help="create a playlist and add its videos")
    pl.add_argument("--spec", required=True, help="JSON: title, description?, privacy, videos")
    for sp in sub.choices.values():
        sp.add_argument("--spec-template-id", help="this run's Process id")
        sp.add_argument("--project-id", help="this run's Project id")
        sp.add_argument("--connection", default="YOUTUBE", help="the OAuth connection name (default YOUTUBE)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    client = Client(args.connection)

    def ids_fn() -> dict[str, str]:
        return intent.run_ids(args.spec_template_id, args.project_id)

    try:
        if args.command == "branding":
            out = apply_branding(client, ids_fn, args.desired, args.dry_run)
        elif args.command == "banner":
            out = apply_banner(client, ids_fn, args.image)
        elif args.command == "playlist":
            out = apply_playlist(client, ids_fn, args.spec)
        else:
            timing = check_timing(args.timing, args.offset_ms, args.duration_ms)
            out = apply_watermark(client, ids_fn, args.image, timing)
    except ApiError as e:
        # Only reads happen outside a claim, so nothing changed.
        out = {"ok": False, "error": str(e), "units_used": client.units}
        if e.scope_missing:
            out.update(fallback="studio", playbook=PLAYBOOK)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 2
    except (Refusal, intent.Refusal) as e:
        print(json.dumps({"ok": False, "error": str(e), "units_used": client.units}, ensure_ascii=False))
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
