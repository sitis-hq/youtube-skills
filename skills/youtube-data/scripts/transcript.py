#!/usr/bin/env python3
"""A video's transcript from its YouTube subtitles, through yt-dlp, cleaned.

  transcript.py --id VIDEO_ID --out FILE [--lang en] [--format txt|srt]
  transcript.py --from-file subs.vtt --out FILE [--format txt|srt]     convert a file already fetched

Uploaded subtitles are preferred; auto-captions are the fallback and the answer says which it got
(`auto`). Auto-captions in WebVTT carry inline word timings and show every line twice as it rolls
up; both are removed, so the text reads once and a retention cliff quotes clean speech. `srt` keeps
the timings for retention.py --transcript and deadair.py; `txt` is the words alone.

yt-dlp reads public pages: no token is used, and private or members-only videos have no transcript
here.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from ytskills import subtitles  # noqa: E402
from ytskills.common import Refusal, run  # noqa: E402

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def run_ytdlp(argv: list[str]) -> tuple[int, str]:
    """The one place yt-dlp is started; tests replace it."""
    exe = shutil.which("yt-dlp")
    if not exe:
        raise Refusal("yt-dlp is not on PATH: attach the yt-dlp CLI from the shelf to this step")
    proc = subprocess.run([exe, *argv], capture_output=True, text=True, timeout=300)
    return proc.returncode, (proc.stderr or proc.stdout)[-600:]


def fetch(video_id: str, lang: str, workdir: Path) -> tuple[Path | None, bool | None]:
    """The best subtitle file for the language: uploaded first, then auto-captions."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    # `-orig` is the auto-caption track in the spoken language; regional variants such as en-GB
    # are uploaded tracks. Translated auto-captions are left out: they are machine output twice.
    langs = f"{lang},{lang}-orig,{lang}-[A-Za-z]+"
    for auto in (False, True):
        flag = "--write-auto-subs" if auto else "--write-subs"
        code, tail = run_ytdlp(["--skip-download", flag, "--sub-langs", langs, "--sub-format", "vtt",
                                "--no-progress", "--no-warnings",
                                "-o", str(workdir / "%(id)s.%(ext)s"), url])
        if code != 0 and not list(workdir.glob("*.vtt")):
            raise Refusal(f"yt-dlp failed for {video_id}: {tail.strip()}")
        files = sorted(workdir.glob(f"{video_id}*.vtt"))
        if files:
            def rank(p: Path) -> int:
                code = p.suffixes[-2].lstrip(".") if len(p.suffixes) >= 2 else ""
                return 0 if code == lang else 1 if code == f"{lang}-orig" else 2
            return sorted(files, key=rank)[0], auto
    return None, None


def write(cues: list[subtitles.Cue], out: str, fmt: str) -> None:
    text = subtitles.to_srt(cues) if fmt == "srt" else subtitles.to_text(cues)
    Path(out).write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> dict[str, Any]:
    p = argparse.ArgumentParser(prog="transcript.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--id", help="the video id")
    src.add_argument("--from-file", help="an .srt, .vtt or whisper .json already on disk")
    p.add_argument("--out", required=True, help="where to write the transcript")
    p.add_argument("--format", choices=["txt", "srt"], default="srt",
                   help="srt keeps timings (default; retention.py needs them), txt is words only")
    p.add_argument("--lang", default="en", help="subtitle language code (default en)")
    a = p.parse_args(argv)

    auto: bool | None = None
    source: str
    if a.from_file:
        if not Path(a.from_file).exists():
            raise Refusal(f"no file {a.from_file}")
        cues = subtitles.load(a.from_file)
        source = a.from_file
    else:
        if not VIDEO_ID.match(a.id):
            raise Refusal(f"--id must be an 11-character video id, got {a.id!r}")
        with tempfile.TemporaryDirectory() as tmp:
            path, auto = fetch(a.id, a.lang, Path(tmp))
            if path is None:
                return {"ok": True, "available": False, "video_id": a.id, "lang": a.lang,
                        "reason": f"no uploaded or automatic {a.lang} subtitles"}
            cues = subtitles.load(str(path))
            source = path.name
    if not cues:
        raise Refusal(f"{source} holds no cues")
    write(cues, a.out, a.format)
    return {"ok": True, "available": True, "video_id": a.id, "lang": a.lang, "auto": auto,
            "source": source, "out": a.out, "format": a.format, "cues": len(cues),
            "duration_s": round(cues[-1][1], 3), "words": sum(len(t.split()) for _, _, t in cues)}


if __name__ == "__main__":
    sys.exit(run(main))
