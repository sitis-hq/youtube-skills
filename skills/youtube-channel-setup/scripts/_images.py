"""Image loading, fitting and writing shared by banner_preview.py and avatar_preview.py.

opencv and numpy are imported lazily so a step without them gets a JSON refusal naming the
attachment instead of a traceback.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ATTACH_HINT = "attach opencv-python-headless==4.14.0.94 and numpy==2.2.6 from the shelf to this step"


class Refusal(Exception):
    pass


def load_cv():
    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
    except ImportError as exc:
        raise Refusal(f"{exc.name} is not available: {ATTACH_HINT}") from exc
    import cv2
    import numpy as np
    return cv2, np


def read_image(cv2, np, path: Path):
    """Decode from bytes: cv2.imread fails silently on some paths and says nothing about why."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise Refusal(f"cannot read {path}: {exc.strerror}") from exc
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise Refusal(f"cannot decode {path} as an image")
    return img


def parse_hex(value: str) -> tuple[int, int, int]:
    """'#RRGGBB' -> a BGR tuple, opencv's channel order."""
    v = value.lstrip("#")
    if len(v) != 6 or any(c not in "0123456789abcdefABCDEF" for c in v):
        raise Refusal(f"{value!r} is not a #RRGGBB colour")
    r, g, b = (int(v[i:i + 2], 16) for i in (0, 2, 4))
    return b, g, r


def border_colour(np, img) -> tuple[int, int, int]:
    edge = np.concatenate([img[0], img[-1], img[:, 0], img[:, -1]])
    return tuple(int(c) for c in np.median(edge, axis=0))


def fit(cv2, np, img, target_w: int, target_h: int, mode: str, pad=None, tolerance: float = 0.01):
    """Bring img to target_w x target_h without distorting it.

    Returns (image, report). An aspect within `tolerance` is scaled; otherwise `mode` decides:
    'none' refuses, 'cover' crops the centre, 'contain' pads with `pad` (default: the border's
    median colour, so the padding continues the edge rather than framing it)."""
    h, w = img.shape[:2]
    want = target_w / target_h
    have = w / h
    report = {"input": f"{w}x{h}", "input_aspect": round(have, 4), "target": f"{target_w}x{target_h}"}
    if abs(have / want - 1) <= tolerance:
        report["action"] = "scaled"
    elif mode == "none":
        lost = (1 - min(have, want) / max(have, want)) * 100
        raise Refusal(
            f"the image is {w}x{h} (aspect {have:.3f}) but needs {want:.3f}; stretching would "
            f"distort it. Pass --fit cover to crop the centre (loses {lost:.0f} % of the "
            f"{'width' if have > want else 'height'}) or --fit contain to pad, or regenerate at the right aspect")
    elif mode == "cover":
        if have > want:
            cw = round(h * want)
            x = (w - cw) // 2
            img = img[:, x:x + cw]
            report["action"] = f"cover: cropped {w - cw} px of width, centred"
        else:
            ch = round(w / want)
            y = (h - ch) // 2
            img = img[y:y + ch]
            report["action"] = f"cover: cropped {h - ch} px of height, centred"
    elif mode == "contain":
        colour = pad if pad is not None else border_colour(np, img)
        if have > want:
            nh = round(w / want)
            top = (nh - h) // 2
            img = cv2.copyMakeBorder(img, top, nh - h - top, 0, 0, cv2.BORDER_CONSTANT, value=colour)
        else:
            nw = round(h * want)
            left = (nw - w) // 2
            img = cv2.copyMakeBorder(img, 0, 0, left, nw - w - left, cv2.BORDER_CONSTANT, value=colour)
        report["action"] = "contain: padded with #%02X%02X%02X" % (colour[2], colour[1], colour[0])
    else:
        raise Refusal(f"unknown fit mode {mode!r}")
    sh, sw = img.shape[:2]
    report["scale"] = round(target_w / sw, 4)
    report["upscaled"] = target_w > sw
    interp = cv2.INTER_AREA if target_w <= sw else cv2.INTER_CUBIC
    return cv2.resize(img, (target_w, target_h), interpolation=interp), report


def write_upload(cv2, img, path_stem: Path, fmt: str, limit_bytes: int):
    """Write the file meant for upload, lowering JPEG quality until it fits the limit."""
    path_stem.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "png":
        ok, buf = cv2.imencode(".png", img, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        quality = None
    else:
        for quality in (95, 90, 85, 80, 75, 70):
            ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
            if len(buf) <= limit_bytes:
                break
    path = path_stem.with_suffix("." + fmt)
    path.write_bytes(buf.tobytes())
    return {"path": str(path), "bytes": len(buf), "within_limit": len(buf) <= limit_bytes,
            "limit_bytes": limit_bytes, "jpeg_quality": quality}


def save_png(cv2, img, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img)
    return str(path)


def label(cv2, img, text: str, org, colour, scale: float = 1.4, thickness: int = 3):
    """Text with a dark outline, readable over any banner."""
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness + 4, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, colour, thickness, cv2.LINE_AA)


def run(fn, args) -> int:
    try:
        result = fn(args)
    except Refusal as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    print(json.dumps(result, indent=2))
    return 0

