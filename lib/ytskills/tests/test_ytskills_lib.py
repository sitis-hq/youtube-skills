import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ytskills import subtitles  # noqa: E402
from ytskills.common import Refusal, parse_datetime, parse_duration, video_rows  # noqa: E402

# The shape yt-dlp writes for YouTube auto-captions: inline word timings, each line shown again
# as the top line of the next cue, and 10 ms "hold" cues that repeat it once more.
AUTO_VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:02.330 align:start position:0%
<SP>
hello<00:00:00.320><c> everyone</c><00:00:00.640><c> welcome</c>

00:00:02.330 --> 00:00:02.340 align:start position:0%
hello everyone welcome
<SP>

00:00:02.340 --> 00:00:05.000 align:start position:0%
hello everyone welcome
to<00:00:02.500><c> the</c><00:00:03.000><c> channel</c>

00:00:05.000 --> 00:00:05.010 align:start position:0%
to the channel
<SP>

00:00:05.010 --> 00:00:08.000 align:start position:0%
to the channel
today&#39;s topic is &amp; retention
""".replace("<SP>", " ")

SRT = """1
00:00:01,000 --> 00:00:02,500
<i>Yeah.</i>

2
00:00:03,000 --> 00:00:04,000
Yeah.
"""

VTT_WITH_IDS = """WEBVTT

NOTE a comment block

intro
00:00:00.000 --> 00:00:01.000
First line

second-cue
00:01.500 --> 00:02.000
Second line
"""


class Subtitles(unittest.TestCase):
    def test_auto_captions_read_once_without_markup(self):
        cues = subtitles.parse_timed_text(AUTO_VTT)
        self.assertEqual([c[2] for c in cues],
                         ["hello everyone welcome", "to the channel", "today's topic is & retention"])
        # The text after the one-space line belongs to its cue, at 0.0 — not orphaned.
        self.assertEqual(cues[0][0], 0.0)
        self.assertEqual(cues[1][0], 2.34)
        self.assertEqual(cues[2][0], 5.01)

    def test_srt_keeps_a_line_said_twice(self):
        cues = subtitles.parse_timed_text(SRT)
        self.assertEqual([c[2] for c in cues], ["Yeah.", "Yeah."])

    def test_vtt_cue_ids_and_notes_are_not_text(self):
        cues = subtitles.parse_timed_text(VTT_WITH_IDS)
        self.assertEqual(cues, [(0.0, 1.0, "First line"), (1.5, 2.0, "Second line")])

    def test_srt_roundtrip(self):
        cues = subtitles.parse_timed_text(AUTO_VTT)
        again = subtitles.parse_timed_text(subtitles.to_srt(cues))
        self.assertEqual([c[2] for c in again], [c[2] for c in cues])
        self.assertAlmostEqual(again[1][0], 2.34)

    def test_whisper_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "w.json"
            p.write_text(json.dumps({"segments": [{"start": 0, "end": 1.5, "text": " hi "}]}))
            self.assertEqual(subtitles.load(str(p)), [(0.0, 1.5, "hi")])

    def test_text_output(self):
        self.assertEqual(subtitles.to_text([(0, 1, "a"), (1, 2, "b")]), "a\nb\n")


class Common(unittest.TestCase):
    def test_duration_iso_and_seconds(self):
        self.assertEqual(parse_duration("PT1H2M3S"), 3723)
        self.assertEqual(parse_duration("PT45S"), 45)
        self.assertEqual(parse_duration("P1DT1S"), 86401)
        self.assertEqual(parse_duration("613"), 613)
        for bad in ("PT", "P0D", "abc", "-5"):
            with self.assertRaises(Refusal):
                parse_duration(bad)

    def test_datetime_needs_zone(self):
        self.assertEqual(parse_datetime("2026-11-04T10:00:00Z").hour, 10)
        with self.assertRaises(Refusal):
            parse_datetime("2026-11-04T10:00:00")

    def test_video_rows_shapes(self):
        self.assertEqual(video_rows([{"a": 1}]), [{"a": 1}])
        self.assertEqual(video_rows({"videos": [{"a": 1}, "x"]}), [{"a": 1}])
        with self.assertRaises(Refusal):
            video_rows("nope")


if __name__ == "__main__":
    unittest.main()
