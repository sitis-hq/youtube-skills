#!/usr/bin/env python3
"""Prepare a YouTube profile picture and show it the way YouTube shows it: as a circle, small.

Takes any image, brings it to 800x800 without distorting it (a non-square image is refused unless
--fit says how to handle it), and writes into --out-dir:

  avatar-upload.<png|jpg>   the square file to upload
  avatar-circle.png         the circular crop at 400 px, on YouTube's light and dark backgrounds
  avatar-sizes.png          the circle at each --sizes width at real pixel size, light and dark rows
  avatar-<N>.png            each size alone, on the light background

Prints JSON on stdout; a refusal exits 2 with {"ok": false, "error": ...}.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _images import Refusal, fit, load_cv, parse_hex, read_image, run, save_png, write_upload  # noqa: E402

SIDE = 800
# YouTube Help "Manage your channel branding" (support.google.com/youtube/answer/10456525), read
# 2026-11-04: JPG, GIF, BMP or PNG (no animated GIF), up to 15 MB, "renders at 98 x 98 px".
# 800x800 is the upload size YouTube's uploader has long recommended; the picture is cropped to a
# circle everywhere it appears.
LIMIT = 15 * 1024 * 1024
DEFAULT_SIZES = "98,48,36"
# YouTube's page backgrounds in the light and dark themes.
LIGHT = (255, 255, 255)
DARK = (15, 15, 15)


def circle_mask(np, n: int):
    yy, xx = np.mgrid[0:n, 0:n]
    c = (n - 1) / 2
    return (xx - c) ** 2 + (yy - c) ** 2 <= (n / 2) ** 2


def on_background(cv2, np, img, n: int, bg):
    small = cv2.resize(img, (n, n), interpolation=cv2.INTER_AREA)
    out = np.empty_like(small)
    out[:] = bg
    m = circle_mask(np, n)
    out[m] = small[m]
    return out


def sizes_sheet(cv2, np, img, sizes):
    pad = 16
    width = sum(sizes) + pad * (len(sizes) + 1)
    row_h = max(sizes) + pad * 2
    sheet = np.empty((row_h * 2, width, 3), np.uint8)
    sheet[:row_h] = LIGHT
    sheet[row_h:] = DARK
    x = pad
    for n in sizes:
        for row, bg in enumerate((LIGHT, DARK)):
            y = row * row_h + pad + (max(sizes) - n) // 2
            sheet[y:y + n, x:x + n] = on_background(cv2, np, img, n, bg)
        x += n + pad
    return sheet


def measures(cv2, np, img, smallest: int):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200) > 0
    total = int(edges.sum())
    outside = int(edges[~circle_mask(np, img.shape[0])].sum())
    tiny = cv2.cvtColor(cv2.resize(img, (smallest, smallest), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    inner = circle_mask(np, smallest)
    return {
        # The corners hold 21.5 % of the square; detail there is cut off by the circle.
        "edges_outside_circle": round(outside / total, 3) if total else 0.0,
        f"contrast_stddev_at_{smallest}px": round(float(tiny[inner].std()), 2),
        "note": "edges_outside_circle is the share of Canny edges (detail, often text or a logo's "
                "parts) in the corners the circle removes; contrast is luminance stddev 0-255 "
                "inside the circle at the smallest size — near 0 means it reads as a flat dot",
    }


def build(args) -> dict:
    cv2, np = load_cv()
    try:
        sizes = sorted({int(s) for s in args.sizes.split(",") if s.strip()}, reverse=True)
    except ValueError as exc:
        raise Refusal(f"--sizes must be comma-separated integers, got {args.sizes!r}") from exc
    if not sizes or min(sizes) < 8 or max(sizes) > 400:
        raise Refusal("--sizes must list widths between 8 and 400 px")
    src = read_image(cv2, np, args.image)
    h, w = src.shape[:2]
    img, report = fit(cv2, np, src, SIDE, SIDE, args.fit,
                      parse_hex(args.pad_color) if args.pad_color else None)
    warnings = []
    if min(w, h) < SIDE:
        warnings.append(f"the source is {w}x{h}, smaller than 800x800; it was upscaled")
    out = args.out_dir
    upload = write_upload(cv2, img, out / "avatar-upload", args.format, LIMIT)
    circle = np.hstack([on_background(cv2, np, img, 400, LIGHT), on_background(cv2, np, img, 400, DARK)])
    previews = {
        "circle": save_png(cv2, circle, out / "avatar-circle.png"),
        "sizes": save_png(cv2, sizes_sheet(cv2, np, img, sizes), out / "avatar-sizes.png"),
    }
    for n in sizes:
        previews[str(n)] = save_png(cv2, on_background(cv2, np, img, n, LIGHT), out / f"avatar-{n}.png")
    return {
        "ok": True,
        "source": str(args.image),
        "fit": report,
        "upload": upload,
        "previews": previews,
        "detail": measures(cv2, np, img, min(sizes)),
        "spec_source": "support.google.com/youtube/answer/10456525, read 2026-11-04",
        "warnings": warnings,
        "approval": "send avatar-circle and avatar-sizes to the owner",
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__.split("\n\n", 1)[1])
    p.add_argument("image", type=Path, help="the profile picture source, any common format")
    p.add_argument("--out-dir", type=Path, required=True,
                   help="directory for the upload file and previews (the step's artifact directory)")
    p.add_argument("--fit", choices=["none", "cover", "contain"], default="none",
                   help="what to do when the image is not square: none refuses (default), cover crops "
                        "the centre, contain pads it (for a logo on a plain background)")
    p.add_argument("--pad-color", help="#RRGGBB for --fit contain; default: the median colour of the image's border")
    p.add_argument("--sizes", default=DEFAULT_SIZES,
                   help=f"comma-separated display widths in px to preview (default {DEFAULT_SIZES}: 98 is "
                        "the size YouTube says it renders at; 48 and 36 approximate comment rows "
                        "and small lists)")
    p.add_argument("--format", choices=["png", "jpg"], default="png", help="format of the upload file (default png)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    args.image = args.image.resolve()
    args.out_dir = args.out_dir.resolve()
    return run(build, args)


if __name__ == "__main__":
    sys.exit(main())
