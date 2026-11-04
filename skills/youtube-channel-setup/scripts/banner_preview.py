#!/usr/bin/env python3
"""Prepare a YouTube channel banner and show it the way devices crop it.

Takes any image, brings it to 2560x1440 without distorting it (an image of another aspect is
refused unless --fit says how to handle it), and writes into --out-dir:

  banner-upload.<jpg|png>   the file to upload, under YouTube's 6 MB limit
  banner-zones.png          the same image with the device areas drawn and labelled, the outside
                            of the area every device shows dimmed
  banner-desktop.png        the strip a desktop browser shows (2560x423)
  banner-mobile.png         the area every device shows (1546x423)
  banner-phone.png          that area at a phone's width (390 px), to judge text size

The owner approves a banner by looking at banner-upload and banner-zones together.

Prints JSON on stdout; a refusal exits 2 with {"ok": false, "error": ...}.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _images import fit, label, load_cv, parse_hex, read_image, run, save_png, write_upload  # noqa: E402

CANVAS = (2560, 1440)
# YouTube Help "Manage your channel branding" (support.google.com/youtube/answer/10456525), read
# 2026-11-04: recommended 2560x1440, minimum 2048x1152 at 16:9, 6 MB or smaller, and "at the minimum
# dimension, the safe area for text and logos: 1235 x 338 px". Scaled to 2560x1440 (x1.25) that is
# 1544x423, the 1546x423 of YouTube's earlier channel-art template. The per-device widths below come
# from that template; the current help page no longer lists them (third-party guides still agree,
# checked 2026-11-04). All areas are centred.
ZONES = [
    # name, width, height, BGR colour of its outline
    ("TV", 2560, 1440, (200, 200, 200)),
    ("desktop", 2560, 423, (255, 170, 0)),
    ("tablet", 1855, 423, (0, 200, 255)),
    ("mobile / safe area", 1546, 423, (60, 230, 60)),
]
SAFE = (1546, 423)
MIN_UPLOAD = (2048, 1152)
LIMIT = 6 * 1024 * 1024
PHONE_WIDTH = 390


def centred(w: int, h: int, cw: int = CANVAS[0], ch: int = CANVAS[1]):
    x, y = (cw - w) // 2, (ch - h) // 2
    return x, y, x + w, y + h


def zones_overlay(cv2, np, img):
    out = img.copy()
    x0, y0, x1, y1 = centred(*SAFE)
    # Darken everything outside the safe area: what remains bright is what every viewer sees.
    mask = np.ones(out.shape[:2], bool)
    mask[y0:y1, x0:x1] = False
    out[mask] = (out[mask] * 0.35).astype(out.dtype)
    for i, (name, w, h, colour) in enumerate(ZONES):
        a, b, c, d = centred(w, h)
        inset = 4 if w == CANVAS[0] else 0
        cv2.rectangle(out, (a + inset, b + inset), (c - 1 - inset, d - 1 - inset), colour, 6)
        # Labels stack above the shared 423 px band so they do not cover the safe area's content.
        ty = b - 18 if h < CANVAS[1] else 60
        if h < CANVAS[1]:
            ty = b - 18 - 52 * (len(ZONES) - 1 - i)
        label(cv2, out, f"{name} {w}x{h}", (a + 16, ty), colour)
    return out


def edge_shares(cv2, np, img):
    """Where the fine detail is. Text and logos make dense edges; a share of the desktop strip's
    edges outside the safe area hints that something meant to be read sits where phones crop it."""
    edges = cv2.Canny(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 100, 200) > 0
    total = int(edges.sum())
    sx0, sy0, sx1, sy1 = centred(*SAFE)
    dx0, dy0, dx1, dy1 = centred(2560, 423)
    strip = edges[dy0:dy1, dx0:dx1]
    inside = int(edges[sy0:sy1, sx0:sx1].sum())
    strip_total = int(strip.sum())
    return {
        "desktop_strip_edges_outside_safe": round((strip_total - inside) / strip_total, 3) if strip_total else 0.0,
        "edges_only_on_tv": round((total - strip_total) / total, 3) if total else 0.0,
        "note": "shares of Canny edges, 0..1: detail, not necessarily text. A high first value "
                "means look at banner-zones.png for text or logos outside the green box",
    }


def build(args) -> dict:
    cv2, np = load_cv()
    src = read_image(cv2, np, args.image)
    h, w = src.shape[:2]
    pad = parse_hex(args.pad_color) if args.pad_color else None
    img, report = fit(cv2, np, src, *CANVAS, args.fit, pad)
    warnings = []
    if w < MIN_UPLOAD[0] or h < MIN_UPLOAD[1]:
        warnings.append(f"the source is {w}x{h}, below YouTube's 2048x1152 minimum; it was upscaled "
                        "and will look soft on TV — regenerate larger if possible")
    out = args.out_dir
    upload = write_upload(cv2, img, out / "banner-upload", args.format, LIMIT)
    if not upload["within_limit"]:
        warnings.append("the upload file is over 6 MB even at JPEG quality 70; YouTube will refuse it")
    sx0, sy0, sx1, sy1 = centred(*SAFE)
    dx0, dy0, dx1, dy1 = centred(2560, 423)
    safe = img[sy0:sy1, sx0:sx1]
    phone = cv2.resize(safe, (PHONE_WIDTH, round(PHONE_WIDTH * SAFE[1] / SAFE[0])), interpolation=cv2.INTER_AREA)
    return {
        "ok": True,
        "source": str(args.image),
        "fit": report,
        "upload": upload,
        "previews": {
            "zones": save_png(cv2, zones_overlay(cv2, np, img), out / "banner-zones.png"),
            "desktop": save_png(cv2, img[dy0:dy1, dx0:dx1], out / "banner-desktop.png"),
            "mobile": save_png(cv2, safe, out / "banner-mobile.png"),
            "phone": save_png(cv2, phone, out / "banner-phone.png"),
        },
        "zones": {name: f"{zw}x{zh}" for name, zw, zh, _ in ZONES},
        "zones_source": "support.google.com/youtube/answer/10456525 (2048x1152 min, 1235x338 safe at "
                        "minimum, 6 MB), read 2026-11-04; device widths from YouTube's channel-art template",
        "detail": edge_shares(cv2, np, img),
        "warnings": warnings,
        "approval": "send banner-upload and banner-zones to the owner together",
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__.split("\n\n", 1)[1])
    p.add_argument("image", type=Path, help="the banner source image, any common format and size")
    p.add_argument("--out-dir", type=Path, required=True,
                   help="directory for the upload file and previews (the step's artifact directory)")
    p.add_argument("--fit", choices=["none", "cover", "contain"], default="none",
                   help="what to do when the image is not 16:9: none refuses (default), cover crops "
                        "the centre, contain pads the sides or top and bottom")
    p.add_argument("--pad-color", help="#RRGGBB for --fit contain; default: the median colour of the image's border")
    p.add_argument("--format", choices=["jpg", "png"], default="jpg",
                   help="format of the upload file (default jpg; png for flat graphics if it stays under 6 MB)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    args.image = args.image.resolve()
    args.out_dir = args.out_dir.resolve()
    return run(build, args)


if __name__ == "__main__":
    sys.exit(main())
