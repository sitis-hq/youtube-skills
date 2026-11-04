#!/usr/bin/env python3
# Derived from youtube-seo-skills, scripts/analyze_thumbnail.py
#   https://github.com/deeployCO/youtube-seo-skills
#   commit 779b0f130ad18c645730701d7884ef4ed0ec0d73
#   Copyright (c) 2026 Deeploy — MIT licence, full text in licenses/youtube-seo-skills.txt
# Changed here:
#   - the CLIP/torch similarity (--serp-dir) is removed; --compare-dir compares with opencv/numpy only
#     (colour histograms and a coarse layout correlation), without a verdict threshold;
#   - previews go to --out-dir, named after the input, instead of a fixed /tmp directory;
#   - images are decoded from bytes, so .webp, .JPG, .avif, non-ASCII paths and the like are read;
#   - faces are found by YuNet (cv2.FaceDetectorYN with the model in ../models), not the Haar
#     cascade: opencv 5.x dropped the cascades, and YuNet also finds turned and smaller faces;
#   - face detection that cannot run is a refusal (exit 2), not a silently missing field;
#   - the MSER count is reported as mser_region_count, not as a text or word estimate;
#   - checks follow YouTube's current thumbnail specification; every argument has help text;
#   - k-means is seeded, so the same image gives the same colours.
"""Measure a YouTube thumbnail: size and format against the specification, luminance and
contrast, dominant colours, faces, MSER region count, and small-size previews to look at.

Prints JSON on stdout. A refusal (unreadable image, face detection unavailable, opencv missing)
exits 2 with {"ok": false, "error": ...}.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ATTACH_HINT = "attach opencv-python-headless (4.8 or later, 5.x included) from the shelf to this step"

# YuNet, from opencv_zoo models/face_detection_yunet (commit f12e127, 2023-06-06), MIT licence in
# licenses/opencv-zoo-yunet.txt. The digest guards against a truncated copy or a git-LFS pointer
# file standing in for the model: either would load as garbage or not at all.
FACE_MODEL = Path(__file__).resolve().parents[1] / "models" / "face_detection_yunet_2023mar.onnx"
FACE_MODEL_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
# YuNet is trained on small inputs; a 4K thumbnail is scaled down first, which keeps it fast and
# loses nothing a viewer would see in a feed.
FACE_INPUT_MAX_SIDE = 1280
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".avif"}

# YouTube Help "Add video thumbnails" (support.google.com/youtube/answer/72431), read 2026-11-04:
# 3840x2160 recommended, minimum width 640 px, JPG or PNG, 16:9 for videos and 9:16 for Shorts,
# 2 MB when uploaded from the mobile app, 50 MB from desktop and through thumbnails.set.
SPEC = {
    "video": {"aspect": 16 / 9, "recommended": (3840, 2160)},
    "short": {"aspect": 9 / 16, "recommended": (2160, 3840)},
}
MIN_SIDE = 640
MOBILE_LIMIT = 2 * 1024 * 1024
DESKTOP_LIMIT = 50 * 1024 * 1024

# Sizes a viewer meets: the smallest list/suggested rows (~120 px wide), the phone feed rows,
# and a mid-size desktop grid. Shorts shelves show tall cards of comparable widths.
PREVIEW_WIDTHS = (120, 168, 246, 480)


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


def sniff_format(head: bytes) -> str:
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if head[:2] == b"BM":
        return "bmp"
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    if head[4:12] in (b"ftypavif", b"ftypavis"):
        return "avif"
    return "unknown"


def read_image(cv2, np, path: Path):
    """Decode from bytes: cv2.imread fails on non-ASCII paths on some platforms and says nothing."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise Refusal(f"cannot read {path}: {exc.strerror}") from exc
    fmt = sniff_format(data[:16])
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise Refusal(f"cannot decode {path} (detected format: {fmt})")
    return img, fmt, len(data)


def face_detector(cv2):
    """YuNet through cv2.FaceDetectorYN — in opencv-python(-headless) 4.8+ and 5.x alike. A detector
    that cannot load is a refusal, never a missing field."""
    if not hasattr(cv2, "FaceDetectorYN"):
        raise Refusal(f"this opencv build ({cv2.__version__}) has no FaceDetectorYN; {ATTACH_HINT}, "
                      "or pass --no-faces to measure without faces")
    try:
        data = FACE_MODEL.read_bytes()
    except OSError as exc:
        raise Refusal(f"the face model is missing at {FACE_MODEL} ({exc.strerror}); "
                      "or pass --no-faces to measure without faces") from exc
    if hashlib.sha256(data).hexdigest() != FACE_MODEL_SHA256:
        raise Refusal(f"the face model at {FACE_MODEL} is not the expected file (digest differs); "
                      "or pass --no-faces to measure without faces")
    try:
        return cv2.FaceDetectorYN.create(str(FACE_MODEL), "", (320, 320), 0.6, 0.3, 50)
    except cv2.error as exc:
        raise Refusal(f"opencv {cv2.__version__} could not load the YuNet model ({exc}); "
                      f"{ATTACH_HINT}, or pass --no-faces to measure without faces") from exc


def detect_faces(cv2, detector, img):
    h, w = img.shape[:2]
    scale = min(1.0, FACE_INPUT_MAX_SIDE / max(h, w))
    small = cv2.resize(img, (max(1, round(w * scale)), max(1, round(h * scale))),
                       interpolation=cv2.INTER_AREA) if scale < 1.0 else img
    detector.setInputSize((small.shape[1], small.shape[0]))
    _, found = detector.detect(small)
    # Faces smaller than ~5 % of the short side vanish in a feed row, so they are not counted.
    side = max(12, int(min(h, w) * 0.05))
    faces = []
    for row in (found if found is not None else []):
        x, y, bw, bh = (int(round(v / scale)) for v in row[:4])
        if min(bw, bh) >= side:
            faces.append({"box": [x, y, bw, bh], "score": round(float(row[14]), 3)})
    faces.sort(key=lambda f: f["box"][2] * f["box"][3], reverse=True)
    area = sum(f["box"][2] * f["box"][3] for f in faces)
    return {
        "detector": "YuNet (opencv FaceDetectorYN, face_detection_yunet_2023mar), score >= 0.6",
        "count": len(faces),
        "area_pct": round(area / (w * h) * 100, 2),
        "largest_pct": round(faces[0]["box"][2] * faces[0]["box"][3] / (w * h) * 100, 2) if faces else 0.0,
        "boxes_xywh": [f["box"] for f in faces],
        "scores": [f["score"] for f in faces],
        "note": "photographic faces, frontal and turned; drawn and heavily stylised faces can be "
                "missed — look at the image before relying on count 0",
    }


def dominant_colours(cv2, np, img, k: int = 3):
    # k-means on a downscaled copy: the colours a viewer sees do not need every pixel, and a
    # 4K thumbnail would otherwise take seconds.
    small = cv2.resize(img, (160, max(1, int(160 * img.shape[0] / img.shape[1]))),
                       interpolation=cv2.INTER_AREA)
    pixels = small.reshape(-1, 3).astype("float32")
    k = min(k, len(np.unique(pixels, axis=0)))
    cv2.setRNGSeed(7)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=k)
    out = []
    for i in counts.argsort()[::-1]:
        b, g, r = (int(round(v)) for v in centers[i])
        out.append({"hex": f"#{r:02X}{g:02X}{b:02X}", "share": round(float(counts[i]) / len(labels), 3)})
    return out


def write_previews(cv2, img, out_dir: Path, stem: str, kind: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    h, w = img.shape[:2]
    paths = {}
    for pw in PREVIEW_WIDTHS:
        ph = round(pw * 9 / 16) if kind == "video" else round(pw * 16 / 9)
        small = cv2.resize(img, (pw, ph), interpolation=cv2.INTER_AREA)
        if kind == "video":
            # The player stamps the duration in the bottom-right corner; drawing it shows what
            # it covers at that size.
            bw, bh = max(18, pw // 7), max(8, ph // 9)
            m = max(2, pw // 60)
            cv2.rectangle(small, (pw - m - bw, ph - m - bh), (pw - m, ph - m), (20, 20, 20), -1)
        p = out_dir / f"{stem}-{pw}x{ph}.png"
        cv2.imwrite(str(p), small)
        paths[f"{pw}x{ph}"] = str(p)
    return paths


def layout_vector(cv2, np, img):
    g = cv2.cvtColor(cv2.resize(img, (32, 18), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    v = g.astype("float32").ravel()
    v -= v.mean()
    n = float(np.linalg.norm(v))
    return v / n if n else v


def hsv_hist(cv2, img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1], None, [30, 16], [0, 180, 0, 256])
    cv2.normalize(h, h)
    return h


def compare(cv2, np, img, target: Path, folder: Path):
    if not folder.is_dir():
        raise Refusal(f"--compare-dir {folder} is not a directory")
    others = sorted(p for p in folder.iterdir()
                    if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
                    and p.resolve() != target.resolve())
    if not others:
        raise Refusal(f"--compare-dir {folder} has no images ({', '.join(sorted(IMAGE_SUFFIXES))})")
    t_hist, t_lay = hsv_hist(cv2, img), layout_vector(cv2, np, img)
    rows, skipped = [], []
    for p in others:
        try:
            o, _, _ = read_image(cv2, np, p)
        except Refusal as exc:
            skipped.append({"file": p.name, "error": str(exc)})
            continue
        rows.append({
            "file": p.name,
            "colour_similarity": round(float(cv2.compareHist(t_hist, hsv_hist(cv2, o), cv2.HISTCMP_CORREL)), 3),
            "layout_similarity": round(float(np.dot(t_lay, layout_vector(cv2, np, o))), 3),
        })
    if not rows:
        raise Refusal(f"no image in --compare-dir {folder} could be decoded")
    mean = lambda key: round(sum(r[key] for r in rows) / len(rows), 3)  # noqa: E731
    return {
        "count": len(rows),
        "mean_colour_similarity": mean("colour_similarity"),
        "mean_layout_similarity": mean("layout_similarity"),
        "most_similar": sorted(rows, key=lambda r: r["colour_similarity"] + r["layout_similarity"],
                               reverse=True)[:3],
        "all": rows,
        "skipped": skipped,
        "note": "correlations in -1..1 for ranking within this set; there is no calibrated "
                "threshold for 'too similar' — look at the most similar files",
    }


def analyze(path: Path, out_dir: Path, kind: str = "video", faces: bool = True,
            compare_dir: Path | None = None) -> dict:
    cv2, np = load_cv()
    detector = face_detector(cv2) if faces else None
    img, fmt, size = read_image(cv2, np, path)
    h, w = img.shape[:2]
    spec = SPEC[kind]
    aspect = w / h
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    small_gray = cv2.cvtColor(cv2.resize(img, (168, 94) if kind == "video" else (94, 168),
                                         interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    result = {
        "ok": True,
        "path": str(path),
        "kind": kind,
        "format": fmt,
        "file_size_bytes": size,
        "width": w,
        "height": h,
        "aspect_ratio": round(aspect, 4),
        "spec": {
            "aspect_ok": abs(aspect / spec["aspect"] - 1) <= 0.01,
            "format_ok": fmt in ("jpeg", "png"),
            "min_side_640_ok": min(w, h) >= MIN_SIDE,
            "meets_recommended": w >= spec["recommended"][0] and h >= spec["recommended"][1],
            "recommended": "x".join(map(str, spec["recommended"])),
            "under_2mb_mobile_upload": size <= MOBILE_LIMIT,
            "under_50mb_desktop_and_api": size <= DESKTOP_LIMIT,
            "source": "support.google.com/youtube/answer/72431, read 2026-11-04",
        },
        "luminance": {
            "mean": round(float(gray.mean()), 2),
            "contrast_stddev": round(float(gray.std()), 2),
            "contrast_stddev_at_168px": round(float(small_gray.std()), 2),
            "scale": "0-255",
        },
        "dominant_colors": dominant_colours(cv2, np, img),
        "faces": detect_faces(cv2, detector, img) if detector is not None else None,
        "mser_region_count": len(cv2.MSER_create().detectRegions(gray)[0]),
        "previews": write_previews(cv2, img, out_dir, path.stem, kind),
    }
    if compare_dir is not None:
        result["compare"] = compare(cv2, np, img, path, compare_dir)
    return result


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Measure a YouTube thumbnail and write small-size previews. JSON on stdout; "
                    "exit 2 with {ok:false,error} on refusal.")
    p.add_argument("image", help="the thumbnail file: jpg, png, webp, gif, bmp, tiff or avif")
    p.add_argument("--out-dir", required=True,
                   help="directory for the previews (use the step's artifact directory); created if missing")
    p.add_argument("--kind", choices=sorted(SPEC), default="video",
                   help="video (16:9) or short (9:16); sets the aspect check and preview shapes")
    p.add_argument("--compare-dir",
                   help="directory of other thumbnails (e.g. competitors'); adds colour and layout "
                        "similarity of the image to each, for ranking only")
    p.add_argument("--no-faces", action="store_true",
                   help="skip face detection (faces is null); without it a build that cannot detect "
                        "faces is a refusal")
    p.epilog = ("Fields: mser_region_count is the number of MSER blobs (stable regions), which "
                "grows with any fine detail — it is not a count of words or text. "
                "contrast_stddev is the standard deviation of luminance, 0-255.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        # Absolute paths in the output: the agent passes them on to other tools from another cwd.
        result = analyze(Path(args.image).resolve(), Path(args.out_dir).resolve(), args.kind,
                         not args.no_faces,
                         Path(args.compare_dir).resolve() if args.compare_dir else None)
    except Refusal as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
