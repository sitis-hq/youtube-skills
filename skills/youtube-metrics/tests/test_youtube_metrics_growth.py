"""velocity.py, candidates.py, swipe.py and ypp.py."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1] / "scripts"))
sys.path.insert(0, str(HERE.parents[3] / "lib"))
sys.path.insert(0, str(HERE.parents[2] / "youtube-records" / "scripts"))

import candidates  # noqa: E402
import records  # noqa: E402
import swipe  # noqa: E402
import velocity  # noqa: E402
import ypp  # noqa: E402
from ytskills.common import Refusal  # noqa: E402

A = "aaaaaaaaaaa"
CH = "UC" + "c" * 22


class Files(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, doc):
        p = Path(self.dir.name) / name
        p.write_text(json.dumps(doc))
        return str(p)

    def snapshots(self, views, published="2026-09-01T00:00:00Z", start_day=1):
        return [self.write(f"s{i}.json", {"as_of": f"2026-10-{start_day + i:02d}",
                                          "videos": [{"video_id": A, "views": v, "published_at": published}]})
                for i, v in enumerate(views)]


class Velocity(Files):
    def one(self, views, **kw):
        out = velocity.main(self.snapshots(views, **kw))
        return out["videos"][0]

    def test_steady_growth_is_none(self):
        r = self.one([1000, 1100, 1200, 1300, 1400])
        self.assertEqual((r["views_per_day"], r["anomaly"], r["baseline_views_per_day"]), (100, "none", 100))

    def test_spike_against_own_median(self):
        r = self.one([1000, 1100, 1200, 1300, 1600])
        self.assertEqual((r["views_per_day"], r["anomaly"]), (300, "spike"))

    def test_drop_against_own_median(self):
        r = self.one([1000, 1100, 1200, 1300, 1340])
        self.assertEqual(r["anomaly"], "drop")

    def test_small_numbers_are_not_anomalies(self):
        r = self.one([10, 12, 14, 16, 22])  # 3x the median, but 4 views a day more
        self.assertEqual(r["anomaly"], "none")

    def test_one_odd_day_does_not_move_the_baseline(self):
        r = self.one([0, 100, 1100, 1200, 1300, 1400])  # one 1000-view day in the history
        self.assertEqual((r["baseline_views_per_day"], r["anomaly"]), (100, "none"))

    def test_gap_days_divide(self):
        files = self.snapshots([1000, 1100, 1200, 1300])
        files.append(self.write("late.json", {"as_of": "2026-10-07", "videos": [
            {"video_id": A, "views": 1600, "published_at": "2026-09-01T00:00:00Z"}]}))
        r = velocity.main(files)["videos"][0]
        self.assertEqual((r["views_per_day"], r["days"], r["anomaly"]), (100, 3, "none"))

    def test_short_history_flags_spikes_against_lifetime_average_only(self):
        # 3000 views at 30 days old is 100/day; 500 in a day is a spike, 0 is not a "drop".
        spike = self.one([3000, 3500], published="2026-09-01T00:00:00Z", start_day=1)
        self.assertEqual((spike["anomaly"], spike["baseline_basis"]), ("spike", "lifetime views/age (spike only)"))
        flat = self.one([3000, 3000], published="2026-09-01T00:00:00Z", start_day=1)
        self.assertEqual(flat["anomaly"], "none")

    def test_young_video_with_short_history_is_none(self):
        r = self.one([10, 5000], published="2026-09-29T00:00:00Z", start_day=1)
        self.assertEqual((r["anomaly"], r["baseline_views_per_day"]), ("none", None))

    def test_single_snapshot_is_a_labelled_proxy(self):
        r = self.one([3000], published="2026-09-01T00:00:00Z", start_day=1)  # 30 days
        self.assertEqual(r["record"], {"video_id": A, "as_of": "2026-10-01", "views_per_day": 100.0,
                                       "anomaly": "none", "source": "views-per-age"})

    def test_falling_count_gives_zero_not_negative(self):
        r = self.one([1000, 1100, 1200, 1300, 1250])
        self.assertEqual(r["views_per_day"], 0)
        self.assertEqual(r["views_delta"], -50)
        self.assertIn("note", r)

    def test_records_are_valid_velocity_records(self):
        for views in ([1000, 1100, 1200, 1300, 1600], [3000], [1000, 1100, 1200, 1300, 1250]):
            r = self.one(views)
            key, data = records.build("velocity", r["record"])
            self.assertEqual(key, f"velocity:{A}")

    def test_video_gone_from_latest_snapshot_is_skipped(self):
        files = self.snapshots([1, 2])
        files.append(self.write("x.json", {"as_of": "2026-10-09", "videos": [{"video_id": "b" * 11, "views": 5}]}))
        out = velocity.main(files)
        self.assertIn("skipped", [v for v in out["videos"] if v["video_id"] == A][0])

    def test_rows_without_a_date_are_refused(self):
        with self.assertRaises(Refusal):
            velocity.main([self.write("n.json", [{"video_id": A, "views": 1}])])


class Candidates(Files):
    def test_score_is_views_per_day_over_channel_median(self):
        base = [{"video_id": f"b{i:010d}", "channel_id": CH, "views": 100 * 10,
                 "published_at": "2026-10-21T00:00:00Z"} for i in range(4)]  # 100/day each
        cand = {"fetched_at": "2026-10-31T00:00:00+00:00", "videos": [
            {"video_id": A, "channel_id": CH, "views": 5000, "published_at": "2026-10-21T00:00:00Z",
             "title": "x"},
            {"video_id": "z" * 11, "channel_id": "UC" + "d" * 22, "views": 99999,
             "published_at": "2026-10-30T12:00:00Z"}]}
        out = candidates.main([self.write("c.json", cand), "--source", "search",
                               "--baseline", self.write("b.json", {"fetched_at": "2026-10-31T00:00:00Z",
                                                                   "videos": base})])
        first, second = out["candidates"]
        self.assertEqual((first["video_id"], first["views_per_day"], first["score"]), (A, 500, 5.0))
        # Half a day old counts as one day; no median for its channel, so it ranks after.
        self.assertEqual((second["views_per_day"], second["score"]), (99999, None))
        self.assertEqual(out["need_baseline"], ["UC" + "d" * 22])
        key, data = records.build("watch", first["record"])
        self.assertEqual(data["score"], 5.0)
        records.build("watch", second["record"])


def vids(channel, views_list):
    return [{"channel": channel, "title": f"{channel} video {i}", "views": v} for i, v in enumerate(views_list)]


class Swipe(Files):
    def test_up_and_down(self):
        rows = vids("A", [100, 100, 100, 100, 400, 20]) + vids("B", [5, 5, 5])
        path = self.write("v.json", rows)
        out = swipe.main([path, "--direction", "both"])
        self.assertEqual([r["multiple"] for r in out["outliers_up"]], [4.0])
        self.assertEqual([r["multiple"] for r in out["outliers_down"]], [0.2])
        self.assertEqual(out["skipped_thin_channels"], [{"channel": "B", "videos": 3}])

    def test_zero_median_channel_is_reported_not_scored(self):
        out = swipe.main([self.write("v.json", vids("Z", [0, 0, 0, 5]))])
        self.assertEqual(out["skipped_zero_median_channels"], ["Z"])

    def test_formula_and_language(self):
        f = swipe.load_formulas()
        self.assertEqual(swipe.classify("I tried 30 days of cold showers", f), "I Tried It")
        self.assertEqual(swipe.classify("Почему 90% каналов умирают?", f), "unsupported-language")
        self.assertEqual(swipe.classify("Why it works?", f, lang="es"), "unsupported-language")

    def test_reads_youtube_data_rows(self):
        rows = [{"video_id": f"v{i:010d}", "channel_id": CH, "title": "t", "views": v}
                for i, v in enumerate([10, 10, 10, 10, 50])]
        out = swipe.main([self.write("v.json", {"videos": rows})])
        self.assertEqual(out["outliers_up"][0]["url"], "https://www.youtube.com/watch?v=v0000000004")

    def test_threshold_sanity(self):
        with self.assertRaises(Refusal):
            swipe.main([self.write("v.json", []), "--min", "0.5"])


class YPP(unittest.TestCase):
    def test_thresholds_change_on_2027_02_01(self):
        before = ypp.main(["--subscribers", "1200", "--watch-hours", "5000", "--on", "2027-01-31"])
        after = ypp.main(["--subscribers", "1200", "--watch-hours", "5000", "--on", "2027-02-01"])
        self.assertTrue(before["tiers"][0]["met"])
        self.assertFalse(after["tiers"][0]["met"])
        self.assertEqual(after["tiers"][0]["missing"]["either"]["watch_hours"], 3000)

    def test_shorts_route_and_unknowns(self):
        out = ypp.main(["--subscribers", "600", "--shorts-views", "4000000", "--on", "2026-11-04"])
        fan = out["tiers"][1]
        self.assertIsNone(fan["met"])  # uploads in 90 days not given
        self.assertEqual((fan["route"], fan["unknown"]), ("shorts", ["uploads_90d"]))
        self.assertTrue(all(t["source"] and t["read"] for t in out["tiers"]))


if __name__ == "__main__":
    unittest.main()
