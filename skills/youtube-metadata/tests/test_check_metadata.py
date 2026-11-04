import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_metadata as cm  # noqa: E402

GOOD_DESC = """Sad phonk for late drives: a 20-minute mix of slowed tracks.

0:00 Intro
1:30 Night Drive
4:10 Rain

#phonk #sadphonk"""


def lint(**meta) -> dict:
    meta.setdefault("tags", [])
    return cm.check(meta)


def checks(result: dict, level: str = "errors") -> list[str]:
    return [e["check"] for e in result[level]]


def run(*argv: str) -> tuple[int, dict]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cm.main(list(argv))
    return code, json.loads(buf.getvalue())


class HardLimits(unittest.TestCase):
    def test_a_clean_set_passes(self):
        r = lint(title="Sad Phonk Mix for Night Drives | Dante Ray", description=GOOD_DESC,
                 tags=["sad phonk", "phonk mix"], keyword="sad phonk", duration=1200,
                 require_tokens=["Dante Ray"])
        self.assertEqual(r["errors"], [])
        self.assertEqual(r["warnings"], [])

    def test_title_over_100_characters(self):
        self.assertIn("title.length", checks(lint(title="x" * 101)))
        self.assertNotIn("title.length", checks(lint(title="x" * 100)))

    def test_description_limit_is_bytes_not_characters(self):
        # 2600 Cyrillic letters are 5200 bytes: under 5000 characters, over the limit.
        self.assertIn("description.length", checks(lint(title="t", description="я" * 2600)))
        self.assertNotIn("description.length", checks(lint(title="t", description="a" * 5000)))

    def test_angle_brackets_are_refused_by_youtube(self):
        r = lint(title="a <b>", description="c > d")
        self.assertIn("title.angle_brackets", checks(r))
        self.assertIn("description.angle_brackets", checks(r))

    def test_tags_are_counted_the_data_api_way(self):
        self.assertEqual(cm.tags_length(["Foo-Baz"]), 7)
        self.assertEqual(cm.tags_length(["Foo Baz"]), 9)          # quotes count
        self.assertEqual(cm.tags_length(["ab", "cd"]), 5)         # the comma counts
        # 50 tags of 9 characters: 450 + 49 commas = 499; 500 is still within, 501 is over.
        tags = ["abcdefghi"] * 50
        self.assertNotIn("tags.length", checks(lint(title="t", tags=tags[:-1] + ["abcdefghij"])))
        self.assertIn("tags.length", checks(lint(title="t", tags=tags[:-1] + ["abcdefghijk"])))

    def test_more_than_60_hashtags_are_all_ignored(self):
        many = " ".join(f"#tag{i}x" for i in range(61))
        self.assertIn("hashtags.count", checks(lint(title="t", description=many)))
        self.assertNotIn("hashtags.count", checks(lint(title="t", description=many.rsplit(" ", 1)[0])))

    def test_numbers_and_entities_are_not_hashtags(self):
        r = lint(title="Track #1", description="It&#39;s #2 on the chart, mail a#b, #Phonk and #phonk")
        self.assertEqual(r["facts"]["hashtags"], ["#Phonk"])

    def test_identity_tokens_are_kept_verbatim(self):
        self.assertIn("title.identity_token", checks(lint(title="dante ray – Rain", require_tokens=["Dante Ray"])))


class Chapters(unittest.TestCase):
    def test_first_chapter_must_be_zero(self):
        d = "0:05 Intro\n1:00 A\n2:00 B"
        self.assertIn("chapters.first", checks(lint(title="t", description=d)))

    def test_at_least_three(self):
        self.assertIn("chapters.count", checks(lint(title="t", description="0:00 A\n1:00 B")))

    def test_ascending_and_at_least_ten_seconds(self):
        r = lint(title="t", description="0:00 A\n2:00 B\n1:00 C")
        self.assertIn("chapters.order", checks(r))
        r = lint(title="t", description="0:00 A\n0:05 B\n1:00 C")
        self.assertIn("chapters.short", checks(r))

    def test_the_last_chapter_is_checked_against_the_duration(self):
        d = "0:00 A\n1:00 B\n2:00 C"
        self.assertIn("chapters.beyond_end", checks(lint(title="t", description=d, duration=120)))
        self.assertIn("chapters.short", checks(lint(title="t", description=d, duration=125)))
        self.assertEqual(checks(lint(title="t", description=d, duration=180)), [])

    def test_hour_timestamps_and_bracketed_forms(self):
        d = "(00:00) Intro\n[10:00] Part two\n1:02:03 - Finale"
        r = lint(title="t", description=d)
        self.assertEqual([c["start"] for c in r["facts"]["chapters"]], ["00:00", "10:00", "1:02:03"])
        self.assertEqual(r["errors"], [])


class OurRules(unittest.TestCase):
    def test_keyword_must_open_the_description(self):
        d = "x" * 160 + " sad phonk"
        self.assertIn("keyword.description", checks(lint(title="sad phonk", description=d, keyword="sad phonk"),
                                                     "warnings"))

    def test_keyword_matching_folds_case_accents_and_punctuation(self):
        r = lint(title="CAFÉ-Phonk: the mix", description="Café phonk, all night.", keyword="cafe phonk")
        self.assertEqual(r["warnings"], [])
        self.assertEqual(r["facts"]["keyword_position_title"], 0)

    def test_keyword_late_in_the_title_is_reported_with_its_position(self):
        title = "An extremely long and winding opening for a title about sad phonk"
        r = lint(title=title, description="sad phonk", keyword="sad phonk")
        self.assertIn("keyword.title_front", checks(r, "warnings"))
        self.assertEqual(r["facts"]["keyword_position_title"], title.index("sad phonk"))

    def test_tags_that_are_hashtags_and_duplicates(self):
        r = lint(title="t", tags=["#phonk", "Phonk", "phonk"])
        self.assertIn("tags.hashtag", checks(r, "warnings"))
        self.assertIn("tags.duplicate", checks(r, "warnings"))

    def test_links_in_a_short_are_flagged(self):
        r = lint(title="t", description="Full video: https://youtu.be/x", format="short")
        self.assertIn("short.link", checks(r, "warnings"))
        self.assertNotIn("short.link", checks(lint(title="t", description="https://youtu.be/x"), "warnings"))


class Cli(unittest.TestCase):
    def test_exit_codes(self):
        self.assertEqual(run("--title", "ok")[0], 0)
        code, out = run("--title", "x" * 101)
        self.assertEqual((code, out["ok"]), (1, False))
        self.assertEqual(run("--title", "t", "--keyword", "zzz", "--strict")[0], 1)
        code, out = run("--description", "no title")
        self.assertEqual(code, 2)
        self.assertIn("title", out["error"])

    def test_file_input_with_description_file_and_tag_forms(self):
        with tempfile.TemporaryDirectory() as d:
            meta = Path(d) / "m.json"
            meta.write_text(json.dumps({"title": "Sad phonk mix", "tags": "a, b", "keyword": "sad phonk"}))
            desc = Path(d) / "d.txt"
            desc.write_text(GOOD_DESC, encoding="utf-8")
            code, out = run("--file", str(meta), "--description-file", str(desc), "--tags", '["x", "y z"]')
            self.assertEqual(code, 0, out)
            self.assertEqual(out["facts"]["tags_length"], 7)
            self.assertEqual(len(out["facts"]["chapters"]), 3)


if __name__ == "__main__":
    unittest.main()
