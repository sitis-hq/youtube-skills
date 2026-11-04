"""retention.py, deadair.py, title.py and chapters.py — including the upstream bugs they fix."""

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1] / "scripts"))
sys.path.insert(0, str(HERE.parents[3] / "lib"))

import chapters  # noqa: E402
import deadair  # noqa: E402
import retention  # noqa: E402
import title  # noqa: E402
from ytskills.common import Refusal  # noqa: E402


def curve(points, scale=1.0):
    """A curve with a cliff of 10 points between positions 50 and 51 (in percent)."""
    rows = []
    for i in range(1, points + 1):
        x = i * 100 / points
        y = 100 - i * 0.2 - (10 if x > 50 else 0)
        rows.append((x * scale, y))
    return rows


class Tmp(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def file(self, name, text):
        p = Path(self.dir.name) / name
        p.write_text(text, encoding="utf-8")
        return str(p)

    def csv(self, rows, header="position,watching"):
        return self.file("c.csv", header + "\n" + "\n".join(f"{x},{y}" for x, y in rows) + "\n")


class Retention(Tmp):
    def test_api_ratio_axis_equals_percent_axis(self):
        pct = retention.main([self.csv(curve(100)), "--axis", "percent", "--duration", "600"])
        ratio = retention.main([self.csv(curve(100, 0.01)), "--axis", "ratio", "--duration", "600"])
        self.assertEqual(pct["cliffs"], ratio["cliffs"])
        self.assertEqual(pct["cliffs"][0]["at_seconds"], 300.0)
        # The hook is the first 30 s of a 600 s video: 5 % of it, not the whole video.
        self.assertAlmostEqual(pct["hook_leak"], 0.8, places=2)

    def test_ratio_read_as_percent_is_refused_the_other_way(self):
        with self.assertRaises(Refusal):
            retention.main([self.csv(curve(100)), "--axis", "ratio"])

    def test_short_in_seconds_is_not_read_as_percent(self):
        rows = [(s, 100 - s * 0.5 - (20 if s > 20 else 0)) for s in range(0, 45)]
        out = retention.main([self.csv(rows), "--axis", "seconds"])
        self.assertEqual(out["cliffs"][0]["at_seconds"], 20)
        self.assertIn("second", out["units"]["slide"])

    def test_watch_ratio_must_be_declared(self):
        rows = [(x, y / 100) for x, y in curve(100)]
        with self.assertRaises(Refusal):
            retention.main([self.csv(rows), "--axis", "percent"])
        out = retention.main([self.csv(rows), "--axis", "percent", "--watch-unit", "ratio"])
        self.assertAlmostEqual(out["start"], 99.8)

    def test_duration_before_the_csv_is_not_taken_for_a_file(self):
        out = retention.main(["--duration", "600", self.csv(curve(100)), "--axis", "percent"])
        self.assertEqual(out["duration_s"], 600)

    def test_transcript_needs_a_duration_on_a_percent_axis(self):
        srt = self.file("t.srt", "1\n00:04:58,000 --> 00:05:01,000\nand now the sponsor\n")
        with self.assertRaises(Refusal):
            retention.main([self.csv(curve(100)), "--axis", "percent", "--transcript", srt])
        out = retention.main([self.csv(curve(100)), "--axis", "percent", "--duration", "PT10M",
                              "--transcript", srt])
        self.assertEqual(out["cliffs"][0]["said"], "and now the sponsor")

    def test_too_few_points(self):
        with self.assertRaises(Refusal):
            retention.main([self.csv(curve(5)), "--axis", "percent"])


class Deadair(Tmp):
    def test_restart_in_any_script(self):
        srt = self.file("t.srt", "1\n00:00:00,000 --> 00:00:02,000\nсегодня мы поговорим о звуке\n\n"
                                 "2\n00:00:02,100 --> 00:00:04,000\nсегодня мы поговорим о звуке и свете\n")
        out = deadair.main([srt, "--lang", "ru"])
        self.assertEqual([c["kind"] for c in out["cuts"]], ["REPEAT"])
        self.assertIn("unsupported", out)

    def test_dead_air_and_filler(self):
        srt = self.file("t.srt", "1\n00:00:00,000 --> 00:00:01,000\nhello there\n\n"
                                 "2\n00:00:03,000 --> 00:00:03,500\num\n")
        kinds = sorted(c["kind"] for c in deadair.main([srt])["cuts"])
        self.assertEqual(kinds, ["DEAD", "FILLER"])


class Title(unittest.TestCase):
    def test_thumbnail_ceiling_is_three_words(self):
        three = title.check("I spent 30 days on it", "NEVER AGAIN OK")
        four = title.check("I spent 30 days on it", "NEVER AGAIN OK FINE")
        self.assertNotIn("thumb-length", [i["check"] for i in three["issues"]])
        self.assertIn("thumb-length", [i["check"] for i in four["issues"]])

    def test_non_english_is_measured_and_says_what_it_skipped(self):
        r = title.check("Почему я ушёл с YouTube через 3 года", "ушёл навсегда", lang="ru")
        self.assertEqual(r["chars"], 36)
        self.assertEqual(r["unsupported"], ["vague", "front-load"])
        self.assertIn("duplicate", [i["check"] for i in r["issues"]])

    def test_english_checks(self):
        r = title.check("The ultimate guide to everything")
        checks = {i["check"] for i in r["issues"]}
        self.assertTrue({"vague", "no-number"} <= checks)


class Chapters(Tmp):
    def test_valid_block(self):
        d = self.file("d.txt", "Intro text\n0:00 Intro\n0:45 The setup\n2:10 Result\nthanks")
        out = chapters.main(["validate", "--description-file", d, "--duration", "300"])
        self.assertTrue(out["valid"], out["problems"])
        self.assertEqual([c["seconds"] for c in out["chapters"]], [45, 85, 170])

    def test_each_rule(self):
        d = self.file("d.txt", "0:05 Intro\n0:10 Too short next\n0:08 Back in time\n")
        problems = " ".join(chapters.main(["validate", "--description-file", d])["problems"])
        self.assertIn("not 00:00", problems)
        self.assertIn("is not after", problems)
        self.assertIn("minimum is 10", problems)
        d2 = self.file("d2.txt", "0:00 A\n1:00 B\n")
        self.assertIn("at least 3", chapters.main(["validate", "--description-file", d2])["problems"][0])

    def test_draft_respects_the_rules(self):
        lines = []
        for i in range(30):
            topic = "guitar strings tuning" if i < 15 else "drums cymbals rhythm"
            start = i * 5 + (8 if i == 15 else 0)
            lines.append(f"{i + 1}\n00:{start // 60:02d}:{start % 60:02d},000 --> "
                         f"00:{(start + 4) // 60:02d}:{(start + 4) % 60:02d},000\n{topic} part {i}\n")
        out = chapters.main(["draft", self.file("t.srt", "\n".join(lines)), "--target", "3"])
        self.assertTrue(out["valid"])
        self.assertIn(83.0, [c["start"] for c in out["chapters"]])


if __name__ == "__main__":
    unittest.main()
