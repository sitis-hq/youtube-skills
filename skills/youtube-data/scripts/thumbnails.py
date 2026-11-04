#!/usr/bin/env python3
"""Download the thumbnails of any public videos — competitors' included — by video id.

  thumbnails.py --id ID [--id ID ...] | --ids-file F  --out-dir DIR

Thumbnails are public files on i.ytimg.com: no token, no API key, no quota. Each video is tried at
the largest size first — maxresdefault (1280x720, absent on many older or small uploads), then
sddefault (640x480), then hqdefault (480x360, always present) — as JPEG and as WebP. The file's
extension follows its real format, read from its first bytes, not from the URL. A missing size
answers 404, or on some edges a 120x90 grey placeholder, which is refused like a 404.
"""

from __future__ import annotations

import argparse
import struct
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from data_api import collect_ids  # noqa: E402
from ytskills.common import Refusal, run  # noqa: E402

SIZES = ["maxresdefault", "sddefault", "hqdefault"]


def candidates(video_id: str) -> list[str]:
    urls = []
    for size in SIZES:
        urls.append(f"https://i.ytimg.com/vi/{video_id}/{size}.jpg")
        urls.append(f"https://i.ytimg.com/vi_webp/{video_id}/{size}.webp")
    return urls


def http_get(url: str) -> tuple[int, bytes]:
    """The one place the network is touched; tests replace it."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except urllib.error.URLError as e:
        raise Refusal(f"cannot reach i.ytimg.com: {e.reason}") from None


def image_info(data: bytes) -> tuple[str, int, int] | None:
    """(format, width, height) from the header bytes of a JPEG, PNG or WebP; None otherwise."""
    if data[:3] == b"\xff\xd8\xff":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            length = struct.unpack(">H", data[i + 2:i + 4])[0]
            # Start-of-frame markers carry the size; C4, C8 and CC share the range but are not frames.
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return "jpg", w, h
            i += 2 + length
        return "jpg", 0, 0
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return "png", w, h
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        chunk = data[12:16]
        if chunk == b"VP8 " and len(data) >= 30:
            w, h = struct.unpack("<HH", data[26:30])
            return "webp", w & 0x3FFF, h & 0x3FFF
        if chunk == b"VP8L" and len(data) >= 25:
            b = data[21:25]
            w = 1 + (((b[1] & 0x3F) << 8) | b[0])
            h = 1 + (((b[3] & 0x0F) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
            return "webp", w, h
        if chunk == b"VP8X" and len(data) >= 30:
            w = 1 + int.from_bytes(data[24:27], "little")
            h = 1 + int.from_bytes(data[27:30], "little")
            return "webp", w, h
        return "webp", 0, 0
    return None


def download(video_id: str, out_dir: Path) -> dict[str, Any]:
    tried = []
    for url in candidates(video_id):
        status, data = http_get(url)
        info = image_info(data) if status == 200 else None
        if info is None or (info[1] and info[1] <= 120):
            tried.append(f"{url.rsplit('/', 2)[-2]}/{url.rsplit('/', 1)[-1]}: "
                         + (f"HTTP {status}" if status != 200 else "placeholder or not an image"))
            continue
        fmt, w, h = info
        path = out_dir / f"{video_id}.{fmt}"
        path.write_bytes(data)
        return {"video_id": video_id, "ok": True, "path": str(path), "url": url, "format": fmt,
                "width": w, "height": h, "bytes": len(data)}
    return {"video_id": video_id, "ok": False, "tried": tried,
            "reason": "no thumbnail at any size — the video may be deleted or private"}


def main(argv: list[str] | None = None) -> dict[str, Any]:
    p = argparse.ArgumentParser(prog="thumbnails.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--id", action="append", help="a video id or a comma list; repeatable")
    p.add_argument("--ids-file", help="ids: one per line, a JSON list, or JSON with video_id fields")
    p.add_argument("--out-dir", required=True, help="where the images go (created if missing)")
    a = p.parse_args(argv)
    ids = collect_ids(a.id, a.ids_file)
    if not ids:
        raise Refusal("no video ids: pass --id or --ids-file")
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = [download(v, out_dir) for v in ids]
    return {"ok": True, "downloaded": sum(r["ok"] for r in results),
            "failed": sum(not r["ok"] for r in results), "thumbnails": results}


if __name__ == "__main__":
    sys.exit(run(main))
