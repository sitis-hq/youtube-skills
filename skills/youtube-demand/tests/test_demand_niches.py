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


def serp(keyword: str, videos: list[tuple[str, int, int]], title_has_keyword: bool = True) -> dict:
    """A SERP response: videos are (video_id, views, days_old)."""
    items = []
    for rank, (vid, views, days) in enumerate(videos, 1):
        items.append({"type": "youtube_video", "rank_absolute": rank, "video_id": vid,
                      "title": f"{keyword} song {vid}" if title_has_keyword else f"track {vid}",
                      "channel_id": f"UC{vid}", "views_count": views,
                      "timestamp": (NOON - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S +00:00")})
    return {"status_code": 20000, "cost": 0.002, "tasks": [{
        "id": keyword, "status_code": 20000, "data": {"keyword": keyword},
        "result": [{"keyword": keyword, "datetime": "2026-11-05 12:00:00 +00:00", "items": items}]}]}


def labs(volumes: dict[str, int], kd: int = 30) -> dict:
    return {"status_code": 20000, "cost": 0.012, "tasks": [{
        "id": "labs", "status_code": 20000, "result": [{"items": [
            {"keyword": k, "keyword_info": {"search_volume": v, "cpc": 0.5},
             "keyword_properties": {"keyword_difficulty": kd}} for k, v in volumes.items()]}]}]}


def trends(values: dict[str, int], kind: str = "youtube") -> dict:
    kws = list(values)
    return {"status_code": 20000, "cost": 0.011, "tasks": [{
        "id": "tr", "status_code": 20000, "data": {"type": kind},
        "result": [{"keywords": kws, "items": [{"type": "google_trends_graph", "keywords": kws,
                                                 "averages": [values[k] for k in kws], "data": []}]}]}]}


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


class Ranking(Run):
    def test_an_open_niche_outranks_a_crowded_one_of_the_same_demand(self):
        crowded = serp("country pop", [(f"p{i}", 50_000_000, 60) for i in range(20)])
        open_ = serp("cowboy ballads", [(f"c{i}", 3_000, 900) for i in range(20)], title_has_keyword=False)
        code, doc = self.run_niches("--serp", self.file(crowded), "--serp", self.file(open_),
                                    "--labs", self.file(labs({"country pop": 20_000, "cowboy ballads": 20_000})))
        self.assertEqual(code, 0)
        self.assertEqual([n["term"] for n in doc["niches"]], ["cowboy ballads", "country pop"])
        self.assertGreater(doc["niches"][0]["opportunity"]["value"], doc["niches"][1]["opportunity"]["value"])

    def test_the_niche_score_keeps_the_idea_scores_ratio_of_demand_to_opportunity(self):
        from ytskills import scoring
        self.assertEqual(scoring.measured_score(5, 5), 100)
        self.assertEqual(scoring.measured_score(0, 0), 0)
        self.assertAlmostEqual(scoring.measured_score(5, 0), 100 * 0.25 / 0.45)

    def test_a_niche_without_measured_demand_is_listed_but_not_scored(self):
        code, doc = self.run_niches("--serp", self.file(serp("honky tonk", [("h1", 1000, 100)])))
        self.assertEqual(code, 0)
        niche = doc["niches"][0]
        self.assertIsNone(niche["niche_score"])
        self.assertIn("no demand measured", niche["unscored"])
        self.assertIsNotNone(niche["competition"]["yt_competition"])

    def test_what_the_niche_pulls_now_is_reported_with_its_top_videos(self):
        code, doc = self.run_niches("--serp", self.file(serp("bluegrass", [("b1", 10, 300), ("b2", 90_000, 30)])))
        top = doc["niches"][0]["now"]["top_videos"]
        self.assertEqual(top[0]["video_id"], "b2")
        self.assertEqual(top[0]["views_per_day"], 3000.0)


class SameResults(Run):
    def test_two_terms_that_surface_mostly_the_same_videos_are_one_audience(self):
        shared = [(f"s{i}", 1_000_000, 100) for i in range(8)]
        a = serp("country pop", shared + [("a1", 10, 10), ("a2", 10, 10)])
        b = serp("modern country", shared + [("b1", 10, 10)])
        c = serp("bluegrass", [(f"g{i}", 5000, 300) for i in range(10)])
        code, doc = self.run_niches("--serp", self.file(a), "--serp", self.file(b), "--serp", self.file(c))
        self.assertEqual(doc["same_results"], [{"terms": ["country pop", "modern country"], "shared_videos": 8,
                                                "share": round(8 / 9, 3)}])
        pop = self.by_term(doc)["country pop"]
        self.assertEqual(pop["overlap"][0]["term"], "modern country")
        self.assertEqual(self.by_term(doc)["bluegrass"]["overlap"], [])

    def test_a_term_with_data_but_no_results_is_named_not_ranked(self):
        code, doc = self.run_niches("--serp", self.file(serp("country pop", [("p", 100, 10)])),
                                    "--labs", self.file(labs({"country pop": 500, "polka": 900})))
        self.assertEqual([n["term"] for n in doc["niches"]], ["country pop"])
        self.assertTrue(any("'polka'" in w for w in doc["warnings"]))


class TrendsScale(Run):
    def niches_with(self, *trend_docs: dict, anchor: str | None = None) -> tuple[int, dict]:
        argv = ["--serp", self.file(serp("country pop", [("p", 100, 10)])),
                "--serp", self.file(serp("bluegrass", [("b", 100, 10)]))]
        for t in trend_docs:
            argv += ["--trends", self.file(t)]
        if anchor:
            argv += ["--anchor", anchor]
        return self.run_niches(*argv)

    def test_one_request_is_one_scale(self):
        code, doc = self.niches_with(trends({"country pop": 80, "bluegrass": 20}))
        self.assertTrue(doc["interest_comparable"])
        self.assertEqual(self.by_term(doc)["country pop"]["demand"], {
            "tier": 4.0, "basis": "yt_interest", "volume": None, "yt_interest": 80.0, "kd_web": None})

    def test_requests_without_an_anchor_are_not_used_for_demand(self):
        code, doc = self.niches_with(trends({"country pop": 80}), trends({"bluegrass": 90}))
        self.assertFalse(doc["interest_comparable"])
        self.assertIsNone(self.by_term(doc)["bluegrass"]["niche_score"])
        self.assertTrue(any("without an --anchor" in w for w in doc["warnings"]))

    def test_an_anchor_puts_every_request_on_the_first_requests_scale(self):
        code, doc = self.niches_with(trends({"country": 50, "country pop": 40}),
                                     trends({"country": 25, "bluegrass": 30}), anchor="country")
        self.assertTrue(doc["interest_comparable"])
        self.assertEqual(self.by_term(doc)["bluegrass"]["demand"]["yt_interest"], 60.0)
        self.assertEqual(self.by_term(doc)["country pop"]["demand"]["yt_interest"], 40.0)
        self.assertFalse(any("'country'" in w for w in doc["warnings"]))

    def test_an_anchor_missing_from_a_request_is_refused(self):
        code, doc = self.niches_with(trends({"country": 50, "country pop": 40}), trends({"bluegrass": 30}),
                                     anchor="country")
        self.assertEqual(code, 2)
        self.assertIn("not in Trends request(s) [2]", doc["error"])

    def test_web_trends_are_refused(self):
        code, doc = self.niches_with(trends({"country pop": 80}, kind="web"))
        self.assertEqual(code, 2)
        self.assertIn("type", doc["error"])


class Refusals(Run):
    def test_no_serp_is_refused(self):
        code, doc = self.run_niches("--labs", self.file(labs({"x": 1})))
        self.assertEqual(code, 2)

    def test_the_ai_shape_is_refused(self):
        code, doc = self.run_niches("--serp", self.file({"items": []}))
        self.assertEqual(code, 2)
        self.assertIn("noAiMode", doc["error"])

    def test_an_account_error_is_refused(self):
        code, doc = self.run_niches("--serp", self.file({"status_code": 40200, "status_message": "Payment required",
                                                         "tasks": []}))
        self.assertEqual(code, 2)
        self.assertIn("40200", doc["error"])


if __name__ == "__main__":
    unittest.main()
