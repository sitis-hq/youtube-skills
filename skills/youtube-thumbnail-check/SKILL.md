---
name: youtube-thumbnail-check
description: Measures a YouTube thumbnail with computer vision (size and format against YouTube's spec, contrast, dominant colours, frontal faces, small-size previews, similarity to a folder of competitor thumbnails) and gives the checklist for judging it, writing a redesign brief and planning a Test & Compare A/B test. Use when a step evaluates, compares, redesigns or A/B-tests a video or Shorts thumbnail.
---

# YouTube thumbnail check

A thumbnail is judged by a person looking at it small, next to its title and its competitors. The
script supplies the measurements and the small previews to look at; the judgement follows
`references/checklist.md`. Read the checklist before scoring, writing a redesign brief or an A/B plan.

## Measure

```bash
python3 <base>/scripts/analyze_thumbnail.py <image> --out-dir <step artifact dir>/thumb-check \
    [--kind video|short] [--compare-dir <folder of competitor thumbnails>] [--no-faces]
```

Needs `opencv-python-headless==4.14.0.94` and `numpy==2.2.6` attached to the step; without them the
script refuses and names them. Any common image format is read (jpg, png, webp, gif, bmp, tiff, avif).

| Output | Meaning |
| --- | --- |
| `spec.*` | against YouTube's current spec (Help 72431, read 2026-11-04): 16:9 (9:16 for Shorts), JPG or PNG, at least 640 px, 3840×2160 recommended, ≤ 2 MB from the phone app, ≤ 50 MB from desktop and `thumbnails.set` |
| `luminance.contrast_stddev` | standard deviation of luminance 0–255, full size and at 168 px wide. Use it to compare variants of one design, not as an absolute grade |
| `dominant_colors` | three k-means colours with their share of the frame |
| `faces` | frontal photographic faces (Haar): count, `area_pct`, boxes. It misses turned, drawn and stylised faces — typical of generated art — so `count: 0` means "look", not "no face" |
| `mser_region_count` | number of MSER blobs. It grows with any fine detail: a busy background gives hundreds. **It is not a count of words or of text** |
| `previews` | PNGs at 120, 168, 246 and 480 px wide, with the duration stamp drawn bottom-right. **Open them and look** — this is the legibility test |
| `compare` | colour-histogram and coarse-layout correlation (-1..1) with each image of `--compare-dir`, mean and top 3. Ranking only: there is no calibrated "too similar" threshold |

A refusal exits 2 with `{"ok": false, "error": ...}`. If face detection cannot run the script
refuses rather than dropping the field; pass `--no-faces` only when faces do not matter for the
judgement (the output then carries `"faces": null` — say so in the report).

## Judge

1. Open the 120 px and 168 px previews. Subject, text and emotion must read there — a fail at
   168 px is a critical issue whatever the full-size image looks like.
2. Put the title next to the thumbnail text: the text must not repeat the title.
3. Walk the checklist (`references/checklist.md` → "Judging"); report issues Critical → Low with the
   measurement or preview that shows each one.
4. Competitor comparison: download their thumbnails into one folder (`youtube-data`'s
   `scripts/thumbnails.py` downloads them), run with `--compare-dir`, and look at the `most_similar` files yourself.

## A/B tests

YouTube's Test & Compare (Studio, desktop only, no API) shows up to three variants and picks the
winner by **watch-time share, not CTR**. Each variant changes exactly one variable. Eligibility,
duration and the result labels are in `references/checklist.md` → "Test & Compare". Starting a test
is an irreversible Studio action: it goes through `youtube-studio` and an intent reservation.

## What not to claim

The script does not read text, count words, recognise emotions or judge composition — you do, from
the previews. Do not cite CTR lifts ("faces +30 %") without a source; the checklist has none to give.
