import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
sys.path.insert(0, str(HERE.parents[0] / "scripts"))
import yt_competition as yc  # noqa: E402

NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)


def run(*argv: str) -> tuple[int, dict]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = yc.main(list(argv))
    return code, json.loads(out.getvalue())


def video(title: str, views: int, days_old: float, channel: str = "UCx", subs: int | None = None) -> dict:
    ts = datetime.fromtimestamp(NOW.timestamp() - days_old * 86400, tz=timezone.utc)
    v = {"title": title, "views": views, "published_at": ts.isoformat(), "channel_id": channel}
    if subs is not None:
        v["channel_subscribers"] = subs
    return v


class Formula(unittest.TestCase):
    def test_a_crowded_keyword_scores_higher_than_an_open_one(self):
        crowded = [video("sad phonk mix", 5_000_000, 200, f"UC{i}", 2_000_000) for i in range(20)]
        open_ = [video("random beats", 300, 900, f"UC{i}", 500) for i in range(20)]
        hi = yc.score("sad phonk", crowded, NOW)["yt_competition"]
        lo = yc.score("sad phonk", open_, NOW)["yt_competition"]
        self.assertGreater(hi, 0.8)
        self.assertLess(lo, 0.1)

    def test_the_value_stays_within_0_and_1_at_the_extremes(self):
        huge = [video("x", 10**12, 0.01, "UC", 10**10) for _ in range(20)]
        tiny = [video("y", 0, 5000, "UC", 0) for _ in range(20)]
        for vids, kw in ((huge, "x"), (tiny, "z")):
            c = yc.score(kw, vids, NOW)["yt_competition"]
            self.assertTrue(0.0 <= c <= 1.0, c)

    def test_without_subscribers_authority_is_left_out_and_weights_rescaled(self):
        vids = [video("sad phonk", 10_000, 100) for _ in range(10)]
        out = yc.score("sad phonk", vids, NOW)
        self.assertNotIn("authority", out["components"])
        self.assertAlmostEqual(sum(out["weights"].values()), 1.0, places=3)
        self.assertEqual(out["weights"]["traffic"], round(0.45 / 0.70, 4))

    def test_title_targeting_folds_case_and_accents_and_needs_every_word(self):
        self.assertTrue(yc.title_matches("cafe phonk", "CAFÉ — Phonk mix"))
        self.assertFalse(yc.title_matches("sad phonk", "phonk drift"))

    def test_an_old_video_counts_less_than_a_fresh_one_with_the_same_views(self):
        old = yc.score("k", [video("k", 100_000, 3000) for _ in range(10)], NOW)["components"]["traffic"]
        new = yc.score("k", [video("k", 100_000, 10) for _ in range(10)], NOW)["components"]["traffic"]
        self.assertGreater(new, old)

    def test_few_results_are_low_confidence_and_none_is_zero(self):
        self.assertEqual(yc.score("k", [video("k", 10, 10)], NOW)["confidence"], "low")
        empty = yc.score("k", [], NOW)
        self.assertEqual((empty["yt_competition"], empty["confidence"]), (0.0, "low"))

    def test_relative_publication_dates_are_understood(self):
        self.assertAlmostEqual(yc.age_days({"publication_date": "Streamed 2 weeks ago"}, NOW), 14)
        self.assertIsNone(yc.age_days({"publication_date": "yesterday-ish"}, NOW))


class Serp(unittest.TestCase):
    def test_serp_reads_only_organic_videos_in_rank_order(self):
        code, out = run("--serp", str(FIX / "serp_youtube.json"))
        self.assertEqual(code, 0)
        k = out["keywords"][0]
        self.assertEqual(k["keyword"], "sad phonk")
        self.assertEqual(k["n_videos"], 3)                 # the channel and the paid video are not counted
        self.assertEqual(k["title_match_share"], round(2 / 3, 3))
        self.assertEqual(k["shorts_share"], round(1 / 3, 3))

    def test_title_match_counts_words_not_order(self):
        k = run("--serp", str(FIX / "serp_youtube.json"))[1]["keywords"][0]
        # "SAD PHONK mix 2026" and "Café phonk — sad edition" both contain "sad" and "phonk".
        self.assertEqual(k["components"]["targeting"], round(2 / 3, 3))

    def test_channels_file_supplies_subscribers(self):
        k = run("--serp", str(FIX / "serp_youtube.json"), "--channels", str(FIX / "channels.json"))[1]["keywords"][0]
        self.assertIn("authority", k["components"])
        self.assertEqual(k["subscribers_known"], 2)

    def test_videos_mode_needs_the_keyword(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "v.json"
            p.write_text(json.dumps({"ok": True, "videos": [video("sad phonk", 1000, 30)]}))
            self.assertEqual(run("--videos", str(p))[0], 2)
            code, out = run("--videos", str(p), "--keyword", "sad phonk", "--as-of", "2026-11-04")
            self.assertEqual(code, 0)
            self.assertEqual(out["keywords"][0]["n_videos"], 1)

    def test_a_non_dataforseo_file_is_refused(self):
        code, out = run("--serp", str(FIX / "ai_shape.json"))
        self.assertEqual(code, 2)
        self.assertIn("noAiMode", out["error"])


if __name__ == "__main__":
    unittest.main()
