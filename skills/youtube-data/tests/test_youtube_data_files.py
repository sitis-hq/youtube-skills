"""transcript.py and thumbnails.py with yt-dlp and the network replaced."""

import struct
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1] / "scripts"))
sys.path.insert(0, str(HERE.parents[3] / "lib"))

import thumbnails  # noqa: E402
import transcript  # noqa: E402
from ytskills.common import Refusal  # noqa: E402

VID = "abcdefghijk"
AUTO_VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:02.000 align:start position:0%
<SP>
so<00:00:00.500><c> today</c>

00:00:02.000 --> 00:00:04.000 align:start position:0%
so today
we<00:00:02.500><c> talk</c>
""".replace("<SP>", " ")


class Transcript(unittest.TestCase):
    def fake_ytdlp(self, manual: bool, auto: bool):
        calls = []

        def run(argv):
            calls.append(argv)
            out = Path(argv[argv.index("-o") + 1]).parent
            if ("--write-subs" in argv and manual) or ("--write-auto-subs" in argv and auto):
                (out / f"{VID}.en.vtt").write_text(AUTO_VTT)
            return 0, ""
        saved = transcript.run_ytdlp
        transcript.run_ytdlp = run
        self.addCleanup(setattr, transcript, "run_ytdlp", saved)
        return calls

    def test_auto_captions_are_the_fallback_and_come_out_clean(self):
        calls = self.fake_ytdlp(manual=False, auto=True)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "t.txt"
            res = transcript.main(["--id", VID, "--out", str(out), "--format", "txt"])
            self.assertEqual(out.read_text(), "so today\nwe talk\n")
        self.assertTrue(res["auto"])
        self.assertEqual(len(calls), 2)
        self.assertIn("--write-subs", calls[0])

    def test_uploaded_subtitles_first(self):
        calls = self.fake_ytdlp(manual=True, auto=True)
        with tempfile.TemporaryDirectory() as d:
            res = transcript.main(["--id", VID, "--out", str(Path(d) / "t.srt")])
            self.assertIn("00:00:02,000 --> 00:00:04,000", (Path(d) / "t.srt").read_text())
        self.assertFalse(res["auto"])
        self.assertEqual(len(calls), 1)

    def test_no_subtitles_is_reported_not_refused(self):
        self.fake_ytdlp(manual=False, auto=False)
        res = transcript.main(["--id", VID, "--out", "/nonexistent/x"])
        self.assertFalse(res["available"])

    def test_missing_ytdlp_names_the_attachment(self):
        saved = transcript.shutil.which
        transcript.shutil.which = lambda name: None
        self.addCleanup(setattr, transcript.shutil, "which", saved)
        with self.assertRaises(Refusal) as e:
            transcript.run_ytdlp(["--version"])
        self.assertIn("attach the yt-dlp CLI", str(e.exception))

    def test_from_file(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "a.vtt"
            src.write_text(AUTO_VTT)
            res = transcript.main(["--from-file", str(src), "--out", str(Path(d) / "o.srt")])
        self.assertEqual((res["cues"], res["words"]), (2, 4))


def jpeg(w: int, h: int) -> bytes:
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 17, 8, h, w, 3) + b"\x00" * 9
    return b"\xff\xd8" + app0 + sof + b"\xff\xd9"


def webp_vp8x(w: int, h: int) -> bytes:
    body = b"VP8X" + struct.pack("<I", 10) + b"\x00\x00\x00\x00" + (w - 1).to_bytes(3, "little") \
        + (h - 1).to_bytes(3, "little")
    return b"RIFF" + struct.pack("<I", len(body) + 4) + b"WEBP" + body


class Thumbnails(unittest.TestCase):
    def serve(self, files):
        asked = []

        def get(url):
            asked.append(url)
            return (200, files[url]) if url in files else (404, b"")
        saved = thumbnails.http_get
        thumbnails.http_get = get
        self.addCleanup(setattr, thumbnails, "http_get", saved)
        return asked

    def test_image_sizes_are_read_from_bytes(self):
        self.assertEqual(thumbnails.image_info(jpeg(1280, 720)), ("jpg", 1280, 720))
        self.assertEqual(thumbnails.image_info(webp_vp8x(1280, 720)), ("webp", 1280, 720))
        self.assertIsNone(thumbnails.image_info(b"<html>"))

    def test_falls_back_past_missing_maxres_and_placeholder(self):
        base = f"https://i.ytimg.com/vi/{VID}/"
        asked = self.serve({base + "maxresdefault.jpg": jpeg(120, 90), base + "sddefault.jpg": jpeg(640, 480)})
        with tempfile.TemporaryDirectory() as d:
            res = thumbnails.main(["--id", VID, "--out-dir", d])
            t = res["thumbnails"][0]
            self.assertTrue(Path(t["path"]).exists())
        self.assertEqual((t["width"], t["format"]), (640, "jpg"))
        self.assertEqual(len(asked), 3)

    def test_webp_keeps_its_extension(self):
        self.serve({f"https://i.ytimg.com/vi_webp/{VID}/maxresdefault.webp": webp_vp8x(1280, 720)})
        with tempfile.TemporaryDirectory() as d:
            t = thumbnails.main(["--id", VID, "--out-dir", d])["thumbnails"][0]
        self.assertTrue(t["path"].endswith(f"{VID}.webp"))

    def test_nothing_found_is_reported_per_video(self):
        self.serve({})
        with tempfile.TemporaryDirectory() as d:
            res = thumbnails.main(["--id", VID, "--out-dir", d])
        self.assertEqual((res["downloaded"], res["failed"]), (0, 1))
        self.assertEqual(len(res["thumbnails"][0]["tried"]), 6)


if __name__ == "__main__":
    unittest.main()
