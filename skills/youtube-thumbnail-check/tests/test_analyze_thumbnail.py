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
import analyze_thumbnail as at  # noqa: E402


def run(*argv: str) -> tuple[int, dict]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = at.main(list(argv))
    return code, json.loads(buf.getvalue())


def thumb(w=1280, h=720, colour=(40, 30, 200)):
    img = np.full((h, w, 3), colour, np.uint8)
    cv2.putText(img, "WOW", (w // 10, h // 2), cv2.FONT_HERSHEY_SIMPLEX, w / 160, (255, 255, 255), max(2, w // 64))
    return img


class Base(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.tmp = Path(d.name)
        self.out = self.tmp / "out"

    def save(self, name, img):
        p = self.tmp / name
        ok, buf = cv2.imencode(p.suffix, img)
        self.assertTrue(ok)
        p.write_bytes(buf.tobytes())
        return p


class FaceDetection(Base):
    def test_this_opencv_build_can_detect_faces(self):
        # The pin is chosen for this: opencv 5.x has neither the cascades nor CascadeClassifier.
        cascade = at.face_detector(cv2)
        self.assertFalse(cascade.empty())
        self.assertEqual(len(cascade.detectMultiScale(np.zeros((200, 200), np.uint8))), 0)

    def test_a_build_without_cascades_is_a_refusal_not_a_missing_field(self):
        with mock.patch.object(cv2, "CascadeClassifier", side_effect=AttributeError("no CascadeClassifier")):
            code, out = run(str(self.save("t.png", thumb())), "--out-dir", str(self.out))
        self.assertEqual(code, 2)
        self.assertFalse(out["ok"])
        self.assertIn("--no-faces", out["error"])

    def test_an_empty_cascade_is_a_refusal(self):
        with mock.patch.object(cv2.data, "haarcascades", str(self.tmp) + "/"):
            code, out = run(str(self.save("t.png", thumb())), "--out-dir", str(self.out))
        self.assertEqual(code, 2)
        self.assertIn("did not load", out["error"])

    def test_no_faces_flag_reports_null_explicitly(self):
        code, out = run(str(self.save("t.png", thumb())), "--out-dir", str(self.out), "--no-faces")
        self.assertEqual(code, 0)
        self.assertIsNone(out["faces"])

    def test_faces_block_is_present_with_a_count(self):
        code, out = run(str(self.save("t.png", thumb())), "--out-dir", str(self.out))
        self.assertEqual(code, 0)
        self.assertEqual(out["faces"]["count"], 0)


class Measurements(Base):
    def test_webp_and_upper_case_suffix_are_read(self):
        for name in ("t.webp", "T.JPG"):
            code, out = run(str(self.save(name, thumb())), "--out-dir", str(self.out), "--no-faces")
            self.assertEqual(code, 0, out)
        self.assertEqual(out["format"], "jpeg")

    def test_spec_flags(self):
        _, out = run(str(self.save("t.webp", thumb())), "--out-dir", str(self.out), "--no-faces")
        self.assertTrue(out["spec"]["aspect_ok"])
        self.assertFalse(out["spec"]["format_ok"])  # YouTube takes JPG or PNG
        self.assertFalse(out["spec"]["meets_recommended"])
        _, out = run(str(self.save("small.png", thumb(600, 400))), "--out-dir", str(self.out), "--no-faces")
        self.assertFalse(out["spec"]["aspect_ok"])
        self.assertFalse(out["spec"]["min_side_640_ok"])

    def test_short_kind_expects_portrait(self):
        _, out = run(str(self.save("s.png", thumb(720, 1280))), "--out-dir", str(self.out),
                     "--no-faces", "--kind", "short")
        self.assertTrue(out["spec"]["aspect_ok"])
        self.assertIn("168x299", out["previews"])

    def test_dominant_colour_is_the_background_and_stable(self):
        p = self.save("t.png", thumb())
        a = run(str(p), "--out-dir", str(self.out), "--no-faces")[1]["dominant_colors"]
        b = run(str(p), "--out-dir", str(self.out), "--no-faces")[1]["dominant_colors"]
        self.assertEqual(a, b)
        self.assertEqual(a[0]["hex"], "#C81E28")
        self.assertGreater(a[0]["share"], 0.8)

    def test_flat_image_has_no_contrast_and_one_colour(self):
        _, out = run(str(self.save("flat.png", np.full((720, 1280, 3), 128, np.uint8))),
                     "--out-dir", str(self.out), "--no-faces")
        self.assertEqual(out["luminance"]["contrast_stddev"], 0.0)
        self.assertEqual(len(out["dominant_colors"]), 1)

    def test_previews_go_to_out_dir_with_their_sizes(self):
        _, out = run(str(self.save("t.png", thumb())), "--out-dir", str(self.out), "--no-faces")
        self.assertEqual(set(out["previews"]), {"120x68", "168x94", "246x138", "480x270"})
        for size, path in out["previews"].items():
            self.assertTrue(path.startswith(str(self.out)))
            w, h = map(int, size.split("x"))
            self.assertEqual(cv2.imread(path).shape[:2], (h, w))

    def test_mser_field_is_named_for_what_it_is(self):
        _, out = run(str(self.save("t.png", thumb())), "--out-dir", str(self.out), "--no-faces")
        self.assertIn("mser_region_count", out)
        self.assertNotIn("text_region_estimate", out)


class Refusals(Base):
    def test_missing_file(self):
        code, out = run(str(self.tmp / "nope.png"), "--out-dir", str(self.out))
        self.assertEqual(code, 2)
        self.assertIn("cannot read", out["error"])

    def test_not_an_image(self):
        p = self.tmp / "x.png"
        p.write_bytes(b"not an image")
        code, out = run(str(p), "--out-dir", str(self.out))
        self.assertEqual(code, 2)
        self.assertIn("cannot decode", out["error"])

    def test_missing_opencv_names_the_attachment(self):
        with mock.patch.dict(sys.modules, {"cv2": None}):
            code, out = run(str(self.tmp / "x.png"), "--out-dir", str(self.out))
        self.assertEqual(code, 2)
        self.assertIn("opencv-python-headless==4.14.0.94", out["error"])


class Compare(Base):
    def test_ranks_the_lookalike_first_and_skips_the_target_itself(self):
        target = self.save("target.png", thumb())
        folder = self.tmp / "others"
        folder.mkdir()
        for name, img in (("same.WEBP", thumb()), ("black.jpg", np.zeros((720, 1280, 3), np.uint8)),
                          ("green.png", thumb(colour=(30, 200, 30)))):
            ok, buf = cv2.imencode(Path(name).suffix, img)
            (folder / name).write_bytes(buf.tobytes())
        (folder / "notes.txt").write_text("ignored")
        code, out = run(str(target), "--out-dir", str(self.out), "--no-faces", "--compare-dir", str(folder))
        self.assertEqual(code, 0, out)
        self.assertEqual(out["compare"]["count"], 3)
        self.assertEqual(out["compare"]["most_similar"][0]["file"], "same.WEBP")
        self.assertGreater(out["compare"]["most_similar"][0]["colour_similarity"], 0.95)

    def test_empty_compare_dir_is_a_refusal(self):
        folder = self.tmp / "empty"
        folder.mkdir()
        code, out = run(str(self.save("t.png", thumb())), "--out-dir", str(self.out), "--no-faces",
                        "--compare-dir", str(folder))
        self.assertEqual(code, 2)


class Help(unittest.TestCase):
    def test_every_argument_has_help(self):
        for action in at.parser()._actions:
            self.assertTrue(action.help, action.dest)


if __name__ == "__main__":
    unittest.main()
