import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import avatar_preview  # noqa: E402
import banner_preview  # noqa: E402


def run(module, *argv: str) -> tuple[int, dict]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = module.main(list(argv))
    return code, json.loads(buf.getvalue())


class Base(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.tmp = Path(d.name)
        self.out = self.tmp / "out"

    def save(self, name, img):
        ok, buf = cv2.imencode(Path(name).suffix, img)
        self.assertTrue(ok)
        p = self.tmp / name
        p.write_bytes(buf.tobytes())
        return p


def noise(h, w, seed=1):
    return np.random.default_rng(seed).integers(0, 256, (h, w, 3), dtype=np.uint8)


class Banner(Base):
    def test_zone_sizes_are_youtubes(self):
        zones = {name: (w, h) for name, w, h, _ in banner_preview.ZONES}
        self.assertEqual(zones, {"TV": (2560, 1440), "desktop": (2560, 423),
                                 "tablet": (1855, 423), "mobile / safe area": (1546, 423)})
        # The help page states the safe area at the 2048x1152 minimum; scaled to 2560 it must match.
        self.assertAlmostEqual(1235 * 2560 / 2048, 1546, delta=3)
        self.assertAlmostEqual(338 * 2560 / 2048, 423, delta=1)

    def test_a_16_9_image_is_scaled_and_every_preview_has_its_size(self):
        code, out = run(banner_preview, str(self.save("b.webp", noise(1152, 2048))), "--out-dir", str(self.out))
        self.assertEqual(code, 0, out)
        self.assertEqual(out["fit"]["action"], "scaled")
        self.assertEqual(cv2.imread(out["upload"]["path"]).shape[:2], (1440, 2560))
        expect = {"zones": (1440, 2560), "desktop": (423, 2560), "mobile": (423, 1546), "phone": (107, 390)}
        for key, shape in expect.items():
            self.assertEqual(cv2.imread(out["previews"][key]).shape[:2], shape, key)
        self.assertEqual(out["warnings"], [])
        self.assertIn("banner-zones", out["approval"])

    def test_another_aspect_is_refused_rather_than_stretched(self):
        code, out = run(banner_preview, str(self.save("b.png", noise(1000, 1000))), "--out-dir", str(self.out))
        self.assertEqual(code, 2)
        self.assertIn("--fit cover", out["error"])
        self.assertFalse(self.out.exists())

    def test_cover_crops_the_centre(self):
        img = np.zeros((1000, 3000, 3), np.uint8)
        img[:, 1400:1600] = 255  # a white bar in the centre must survive the crop, centred
        code, out = run(banner_preview, str(self.save("b.png", img)), "--out-dir", str(self.out), "--fit", "cover")
        self.assertEqual(code, 0, out)
        self.assertIn("cover", out["fit"]["action"])
        up = cv2.imread(out["upload"]["path"], cv2.IMREAD_GRAYSCALE)
        cols = np.where(up[720] > 128)[0]
        self.assertAlmostEqual((cols.min() + cols.max()) / 2, 1280, delta=4)

    def test_contain_pads_with_the_given_colour(self):
        code, out = run(banner_preview, str(self.save("b.png", noise(1440, 1440))), "--out-dir", str(self.out),
                        "--fit", "contain", "--pad-color", "#FF0000", "--format", "png")
        self.assertEqual(code, 0, out)
        up = cv2.imread(out["upload"]["path"])
        self.assertEqual(tuple(int(v) for v in up[720, 5]), (0, 0, 255))

    def test_small_source_warns_about_youtubes_minimum(self):
        _, out = run(banner_preview, str(self.save("b.png", noise(720, 1280))), "--out-dir", str(self.out))
        self.assertTrue(out["fit"]["upscaled"])
        self.assertTrue(any("2048x1152" in w for w in out["warnings"]))

    def test_upload_stays_under_6_mb_even_for_noise(self):
        _, out = run(banner_preview, str(self.save("b.png", noise(1440, 2560))), "--out-dir", str(self.out))
        self.assertTrue(out["upload"]["within_limit"], out["upload"])
        self.assertLessEqual(out["upload"]["bytes"], 6 * 1024 * 1024)

    def test_overlay_dims_outside_the_safe_area_only(self):
        _, out = run(banner_preview, str(self.save("b.png", np.full((1440, 2560, 3), 200, np.uint8))),
                     "--out-dir", str(self.out), "--format", "png")
        z = cv2.imread(out["previews"]["zones"], cv2.IMREAD_GRAYSCALE)
        self.assertGreater(z[720, 1280], 190)   # centre of the safe area: untouched
        self.assertLess(z[1200, 1280], 90)      # TV-only area: dimmed

    def test_detail_outside_the_safe_area_is_reported(self):
        img = np.full((1440, 2560, 3), 30, np.uint8)
        cv2.putText(img, "TEXT", (40, 760), cv2.FONT_HERSHEY_SIMPLEX, 4, (255, 255, 255), 8)
        _, out = run(banner_preview, str(self.save("b.png", img)), "--out-dir", str(self.out))
        self.assertGreater(out["detail"]["desktop_strip_edges_outside_safe"], 0.9)
        img = np.full((1440, 2560, 3), 30, np.uint8)
        cv2.putText(img, "TEXT", (1100, 760), cv2.FONT_HERSHEY_SIMPLEX, 4, (255, 255, 255), 8)
        _, out = run(banner_preview, str(self.save("c.png", img)), "--out-dir", str(self.out))
        self.assertEqual(out["detail"]["desktop_strip_edges_outside_safe"], 0.0)


class Avatar(Base):
    def test_square_image_gives_upload_circle_and_sizes(self):
        code, out = run(avatar_preview, str(self.save("a.jpg", noise(1024, 1024))), "--out-dir", str(self.out))
        self.assertEqual(code, 0, out)
        self.assertEqual(cv2.imread(out["upload"]["path"]).shape[:2], (800, 800))
        self.assertEqual(cv2.imread(out["previews"]["circle"]).shape[:2], (400, 800))
        for n in (98, 48, 36):
            self.assertEqual(cv2.imread(out["previews"][str(n)]).shape[:2], (n, n))
        self.assertIn("contrast_stddev_at_36px", out["detail"])

    def test_circle_preview_shows_the_theme_backgrounds_in_the_corners(self):
        _, out = run(avatar_preview, str(self.save("a.png", np.full((800, 800, 3), 128, np.uint8))),
                     "--out-dir", str(self.out))
        c = cv2.imread(out["previews"]["circle"])
        self.assertEqual(tuple(int(v) for v in c[2, 2]), (255, 255, 255))
        self.assertEqual(tuple(int(v) for v in c[2, 402]), (15, 15, 15))
        self.assertEqual(tuple(int(v) for v in c[200, 200]), (128, 128, 128))

    def test_detail_in_the_corners_is_reported(self):
        img = np.full((800, 800, 3), 40, np.uint8)
        cv2.putText(img, "LOGO", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 5)
        _, out = run(avatar_preview, str(self.save("a.png", img)), "--out-dir", str(self.out))
        self.assertGreater(out["detail"]["edges_outside_circle"], 0.5)
        img = np.full((800, 800, 3), 40, np.uint8)
        cv2.circle(img, (400, 400), 200, (255, 255, 255), -1)
        _, out = run(avatar_preview, str(self.save("b.png", img)), "--out-dir", str(self.out))
        self.assertEqual(out["detail"]["edges_outside_circle"], 0.0)

    def test_flat_avatar_has_no_contrast_at_small_size(self):
        _, out = run(avatar_preview, str(self.save("a.png", np.full((800, 800, 3), 90, np.uint8))),
                     "--out-dir", str(self.out), "--sizes", "24")
        self.assertEqual(out["detail"]["contrast_stddev_at_24px"], 0.0)

    def test_non_square_is_refused_unless_fit_is_given(self):
        p = self.save("a.png", noise(600, 900))
        code, out = run(avatar_preview, str(p), "--out-dir", str(self.out))
        self.assertEqual(code, 2)
        code, out = run(avatar_preview, str(p), "--out-dir", str(self.out), "--fit", "cover")
        self.assertEqual(code, 0)
        self.assertTrue(any("smaller than 800x800" in w for w in out["warnings"]))

    def test_bad_sizes_are_refused(self):
        code, out = run(avatar_preview, str(self.save("a.png", noise(800, 800))), "--out-dir", str(self.out),
                        "--sizes", "big")
        self.assertEqual(code, 2)


class Shared(Base):
    def test_missing_opencv_names_the_attachment(self):
        for module in (banner_preview, avatar_preview):
            with mock.patch.dict(sys.modules, {"cv2": None}):
                code, out = run(module, str(self.tmp / "x.png"), "--out-dir", str(self.out))
            self.assertEqual(code, 2)
            self.assertIn("opencv-python-headless==4.14.0.94", out["error"])

    def test_unreadable_input_is_a_refusal(self):
        p = self.tmp / "x.png"
        p.write_bytes(b"nope")
        for module in (banner_preview, avatar_preview):
            code, out = run(module, str(p), "--out-dir", str(self.out))
            self.assertEqual(code, 2)
            self.assertIn("cannot decode", out["error"])

    def test_every_argument_has_help(self):
        for module in (banner_preview, avatar_preview):
            for action in module.parser()._actions:
                self.assertTrue(action.help, f"{module.__name__} {action.dest}")


if __name__ == "__main__":
    unittest.main()
