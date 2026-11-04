"""The output contract every script keeps, and the parsing of dates, times and durations.

A script prints one JSON document on stdout and nothing else; the agent reads that document, so its
shape is the script's interface. A refusal is `{"ok": false, "error": ...}` with exit code 2.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timezone
from typing import Any, Callable


class Refusal(Exception):
    """An input or a state the script will not work around. The message says what to fix."""


def emit(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def note(message: str) -> None:
    """Diagnostics go to stderr, so stdout stays one parseable document."""
    print(message, file=sys.stderr)


def run(main: Callable[[list[str] | None], Any], argv: list[str] | None = None) -> int:
    """Call main and turn a Refusal into the refusal document and exit code 2."""
    try:
        out = main(argv)
    except Refusal as e:
        emit({"ok": False, "error": str(e)})
        return 2
    emit(out)
    return 0


def parse_date(text: str, name: str = "date") -> date:
    try:
        return date.fromisoformat(str(text).strip()[:10])
    except ValueError:
        raise Refusal(f"{name} must be a date YYYY-MM-DD, got {text!r}") from None


def parse_datetime(text: str, name: str = "time") -> datetime:
    """An ISO date-time; one without a zone is refused rather than assumed to be UTC."""
    raw = str(text).strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise Refusal(f"{name} must be an ISO date-time, got {text!r}") from None
    if parsed.tzinfo is None:
        raise Refusal(f"{name} must carry a time zone, got {text!r}")
    return parsed.astimezone(timezone.utc)


ISO_DURATION = re.compile(
    r"^P(?:(?P<d>\d+)D)?(?:T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+(?:\.\d+)?)S)?)?$"
)


def parse_duration(text: Any, name: str = "duration") -> float:
    """Seconds from a number of seconds or from the API's ISO 8601 form (PT1H2M3S)."""
    raw = str(text).strip()
    try:
        value = float(raw)
    except ValueError:
        m = ISO_DURATION.match(raw)
        if not m or raw in ("P", "PT"):
            raise Refusal(f"{name} must be seconds or ISO 8601 like PT4M13S, got {text!r}") from None
        value = (int(m["d"] or 0) * 86400 + int(m["h"] or 0) * 3600 + int(m["m"] or 0) * 60
                 + float(m["s"] or 0))
    if value <= 0:
        raise Refusal(f"{name} must be positive, got {text!r}")
    return value


def read_json(path: str) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as e:
        raise Refusal(f"cannot read {path}: {e.strerror}") from None
    except json.JSONDecodeError as e:
        raise Refusal(f"{path} is not JSON: {e}") from None


def video_rows(doc: Any) -> list[dict[str, Any]]:
    """The video objects of a document: a list, or an object holding them under `videos`.

    Both shapes appear: youtube-data prints `{"videos": [...]}`, a hand-made list is plain.
    """
    if isinstance(doc, dict):
        doc = doc.get("videos", doc.get("items", []))
    if not isinstance(doc, list):
        raise Refusal("expected a list of videos or an object with a `videos` list")
    return [r for r in doc if isinstance(r, dict)]
