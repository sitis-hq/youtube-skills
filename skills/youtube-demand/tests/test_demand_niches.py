import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "scripts"))
import niches  # noqa: E402

AS_OF = "2026-11-05"
NOON = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)   # --as-of counts ages to noon of that day


def serp(keyword: str, videos: list[tuple]) -> dict:
    """A SERP response; videos are (video_id, channel_id, views, days_old)."""
    items = []
    for rank, (vid, channel, views, days) in enumerate(videos, 1):
        items.append({"type": "youtube_video", "rank_absolute": rank, "video_id": vid,
                      "title": f"{keyword} {vid}", "channel_id": channel, "views_count": views,
                      "timestamp": (NOON - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S +00:00")})
    return {"status_code": 20000, "cost": 0.002, "tasks": [{
        "id": keyword, "status_code": 20000, "data": {"keyword": keyword},
        "result": [{"keyword": keyword, "datetime": "2026-11-05 12:00:00 +00:00", "items": items}]}]}


def baselines(rows: dict[str, tuple]) -> dict:
    """channel_id -> (subscribers, median views, uploads read)."""
    return {"channels": {cid: {"title": cid, "subscribers": subs, "median_views": med, "videos_read": n}
                         for cid, (subs, med, n) in rows.items()}, "failed": {}}


def labs(volumes: dict[str, int]) -> dict:
    return {"status_code": 20000, "cost": 0.012, "tasks": [{
        "id": "labs", "status_code": 20000, "result": [{"items": [
            {"keyword": k, "keyword_info": {"search_volume": v}, "keyword_properties": {"keyword_difficulty": 30}}
            for k, v in volumes.items()]}]}]}


def trends(values: dict[str, int], kind: str = "youtube") -> dict:
    kws = list(values)
    return {"status_code": 20000, "cost": 0.011, "tasks": [{
        "id": "tr", "status_code": 20000, "data": {"type": kind},
        "result": [{"keywords": kws, "items": [{"type": "google_trends_graph", "keywords": kws,
                                                 "averages": [values[k] for k in kws], "data": []}]}]}]}


# An open niche: twenty channels, fresh videos, small channels far above their own median.
OPEN = [(f"o{i}", f"UCopen{i}", 50_000, 60) for i in range(20)]
OPEN_BASE = {f"UCopen{i}": (5_000, 2_000, 30) for i in range(20)}
# A closed niche of the same demand: three big channels, old videos, nobody above their median.
CLOSED = [(f"c{i}", f"UCbig{i % 3}", 50_000, 2000) for i in range(20)]
CLOSED_BASE = {f"UCbig{i}": (5_000_000, 60_000, 30) for i in range(3)}


class Run(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.n = 0

    def file(self, doc: dict) -> str:
        self.n += 1
        path = Path(self.dir.name) / f"r{self.n}.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        return str(path)

    def run_niches(self, *argv: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = niches.main([*argv, "--as-of", AS_OF])
        return code, json.loads(out.getvalue())

    def by_term(self, doc: dict) -> dict:
        return {n["term"]: n for n in doc["niches"]}


class Openness(Run):
    def test_an_open_niche_outranks_a_closed_one_of_the_same_demand(self):
        code, doc = self.run_niches("--serp", self.file(serp("closed", CLOSED)), "--serp", self.file(serp("open", OPEN)),
                                    "--baselines", self.file(baselines({**OPEN_BASE, **CLOSED_BASE})))
        self.assertEqual(code, 0)
        self.assertEqual([n["term"] for n in doc["niches"]], ["open", "closed"])
        open_, closed = self.by_term(doc)["open"], self.by_term(doc)["closed"]
        self.assertEqual(open_["parts"], {"breakouts": 1.0, "spread": 0.85, "freshness": 1.0})
        self.assertEqual(closed["parts"], {"breakouts": 0.0, "spread": 0.0, "freshness": 0.0})
        self.assertEqual(open_["openness"], 95.0)
        self.assertEqual(closed["openness"], 0.0)

    def test_a_breakout_is_a_small_channel_at_three_times_its_own_median(self):
        videos = [("big", "UCbig", 900_000, 30), ("small2x", "UCs2", 20_000, 30), ("small3x", "UCs3", 30_000, 30),
                  ("few", "UCfew", 900_000, 30)]
        base = baselines({"UCbig": (2_000_000, 100_000, 30), "UCs2": (8_000, 10_000, 30),
                          "UCs3": (8_000, 10_000, 30), "UCfew": (500, 10, 3)})
        code, doc = self.run_niches("--serp", self.file(serp("n", videos)), "--baselines", self.file(base))
        niche = doc["niches"][0]
        self.assertEqual([b["video_id"] for b in niche["breakouts"]], ["small3x"])
        self.assertEqual(niche["breakouts"][0]["multiple"], 3.0)
        # The big channel's 9x is not a door for a new channel; the 3-upload channel has no median.
        self.assertEqual(niche["breakout_share"], round(1 / 3, 3))
        self.assertEqual(niche["baseline_coverage"], 0.75)

    def test_with_medians_for_under_half_the_top_breakouts_are_left_out(self):
        code, doc = self.run_niches("--serp", self.file(serp("n", OPEN)),
                                    "--baselines", self.file(baselines({"UCopen0": (5_000, 2_000, 30)})))
        niche = doc["niches"][0]
        self.assertIsNone(niche["parts"]["breakouts"])
        self.assertEqual(niche["confidence"], "low")
        self.assertEqual(niche["openness"], round(100 * (0.85 + 1.0) / 2, 1))

    def test_without_baselines_a_warning_says_what_is_missing(self):
        code, doc = self.run_niches("--serp", self.file(serp("n", OPEN)))
        self.assertEqual(code, 0)
        self.assertTrue(any("no --baselines" in w for w in doc["warnings"]))
        self.assertEqual(doc["niches"][0]["confidence"], "low")

    def test_a_niche_under_the_demand_floor_ranks_after_every_niche_over_it(self):
        tiny_open = [(f"t{i}", f"UCt{i}", 300, 30) for i in range(20)]
        tiny_base = {f"UCt{i}": (100, 50, 30) for i in range(20)}
        code, doc = self.run_niches("--serp", self.file(serp("tiny", tiny_open)), "--serp", self.file(serp("closed", CLOSED)),
                                    "--baselines", self.file(baselines({**tiny_base, **CLOSED_BASE})))
        self.assertEqual([n["term"] for n in doc["niches"]], ["closed", "tiny"])
        self.assertTrue(self.by_term(doc)["tiny"]["demand"]["below_floor"])
        self.assertGreater(self.by_term(doc)["tiny"]["openness"], self.by_term(doc)["closed"]["openness"])

    def test_search_numbers_are_reported_and_do_not_rank(self):
        code, doc = self.run_niches("--serp", self.file(serp("closed", CLOSED)), "--serp", self.file(serp("open", OPEN)),
                                    "--baselines", self.file(baselines({**OPEN_BASE, **CLOSED_BASE})),
                                    "--labs", self.file(labs({"closed": 900_000, "open": 10})))
        self.assertEqual(doc["niches"][0]["term"], "open")
        self.assertEqual(self.by_term(doc)["closed"]["search"]["volume"], 900_000)


class SameResults(Run):
    def test_two_terms_that_surface_mostly_the_same_videos_are_one_audience(self):
        shared = [(f"s{i}", f"UC{i}", 1_000_000, 100) for i in range(8)]
        a = serp("country pop", shared + [("a1", "UCa", 10, 10), ("a2", "UCb", 10, 10)])
        b = serp("modern country", shared + [("b1", "UCc", 10, 10)])
        c = serp("bluegrass", [(f"g{i}", f"UCg{i}", 5000, 300) for i in range(10)])
        code, doc = self.run_niches("--serp", self.file(a), "--serp", self.file(b), "--serp", self.file(c))
        self.assertEqual(doc["same_results"], [{"terms": ["country pop", "modern country"], "shared_videos": 8,
                                                "share": round(8 / 9, 3)}])
        self.assertEqual(self.by_term(doc)["country pop"]["overlap"][0]["term"], "modern country")
        self.assertEqual(self.by_term(doc)["bluegrass"]["overlap"], [])

    def test_a_term_with_data_but_no_results_is_named_not_ranked(self):
        code, doc = self.run_niches("--serp", self.file(serp("country pop", [("p", "UCp", 100, 10)])),
                                    "--labs", self.file(labs({"country pop": 500, "polka": 900})))
        self.assertEqual([n["term"] for n in doc["niches"]], ["country pop"])
        self.assertTrue(any("'polka'" in w for w in doc["warnings"]))


class TrendsScale(Run):
    def niches_with(self, *trend_docs: dict, anchor: str | None = None) -> tuple[int, dict]:
        argv = ["--serp", self.file(serp("country pop", [("p", "UCp", 100, 10)])),
                "--serp", self.file(serp("bluegrass", [("b", "UCb", 100, 10)]))]
        for t in trend_docs:
            argv += ["--trends", self.file(t)]
        if anchor:
            argv += ["--anchor", anchor]
        return self.run_niches(*argv)

    def test_requests_without_an_anchor_do_not_compare(self):
        code, doc = self.niches_with(trends({"country pop": 80}), trends({"bluegrass": 90}))
        self.assertFalse(doc["interest_comparable"])
        self.assertTrue(any("without an --anchor" in w for w in doc["warnings"]))

    def test_an_anchor_puts_every_request_on_the_first_requests_scale(self):
        code, doc = self.niches_with(trends({"country": 50, "country pop": 40}),
                                     trends({"country": 25, "bluegrass": 30}), anchor="country")
        self.assertTrue(doc["interest_comparable"])
        self.assertEqual(self.by_term(doc)["bluegrass"]["search"]["yt_interest"], 60.0)
        self.assertEqual(self.by_term(doc)["country pop"]["search"]["yt_interest"], 40.0)

    def test_an_anchor_missing_from_a_request_is_refused(self):
        code, doc = self.niches_with(trends({"country": 50, "country pop": 40}), trends({"bluegrass": 30}),
                                     anchor="country")
        self.assertEqual(code, 2)
        self.assertIn("not in Trends request(s) [2]", doc["error"])

    def test_web_trends_are_refused(self):
        code, doc = self.niches_with(trends({"country pop": 80}, kind="web"))
        self.assertEqual(code, 2)


class Refusals(Run):
    def test_no_serp_is_refused(self):
        code, doc = self.run_niches("--labs", self.file(labs({"x": 1})))
        self.assertEqual(code, 2)

    def test_the_ai_shape_is_refused(self):
        code, doc = self.run_niches("--serp", self.file({"items": []}))
        self.assertEqual(code, 2)
        self.assertIn("noAiMode", doc["error"])

    def test_baselines_of_another_shape_are_refused(self):
        code, doc = self.run_niches("--serp", self.file(serp("n", OPEN)), "--baselines", self.file({"rows": []}))
        self.assertEqual(code, 2)
        self.assertIn("channel_baselines", doc["error"])


if __name__ == "__main__":
    unittest.main()
