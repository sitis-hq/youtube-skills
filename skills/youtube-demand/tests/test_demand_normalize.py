import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
sys.path.insert(0, str(HERE.parents[0] / "scripts"))
import normalize  # noqa: E402

RECORDS = HERE.parents[1] / "youtube-records" / "scripts" / "records.py"


def run(*argv: str) -> tuple[int, dict]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = normalize.main(list(argv))
    return code, json.loads(out.getvalue())


def f(name: str) -> str:
    return str(FIX / name)


def by_term(out: dict) -> dict:
    return {r["term"]: r for r in out["rows"]}


class Labs(unittest.TestCase):
    def test_keyword_overview_gives_volume_cpc_kd_and_intent_in_record_units(self):
        code, out = run("--labs", f("labs_keyword_overview.json"), "--as-of", "2026-11-04")
        self.assertEqual(code, 0)
        row = by_term(out)["sad phonk"]
        self.assertEqual(row["volume"], 1900)
        self.assertEqual(row["cpc"], 0.42)
        self.assertEqual(row["kd_web"], 31)          # 0-100 as it comes, not rescaled
        self.assertEqual(row["intent"], "informational")
        self.assertEqual(row["as_of"], "2026-11-04")
        self.assertEqual(row["source"], "dataforseo")
        self.assertAlmostEqual(out["cost_usd"], 0.01236)

    def test_a_keyword_without_data_keeps_only_what_it_has(self):
        row = by_term(run("--labs", f("labs_keyword_overview.json"), "--as-of", "2026-11-04")[1])["phonk drift"]
        for missing in ("volume", "cpc", "kd_web", "intent"):
            self.assertNotIn(missing, row)

    def test_related_keywords_are_read_one_level_down_and_terms_are_folded(self):
        rows = by_term(run("--labs", f("labs_related_keywords.json"), "--as-of", "2026-11-04")[1])
        self.assertEqual(rows["lofi beats to study"]["kd_web"], 22)
        # "Lofi  Beats" is the same term as "lofi beats"; its out-of-range KD and unknown intent are dropped.
        self.assertIn("lofi beats", rows)
        self.assertNotIn("kd_web", rows["lofi beats"])
        self.assertNotIn("intent", rows["lofi beats"])

    def test_google_ads_volume_is_the_fallback_shape(self):
        row = by_term(run("--labs", f("google_ads_search_volume.json"), "--as-of", "2026-11-04")[1])["sad phonk"]
        self.assertEqual((row["volume"], row["cpc"]), (2400, 0.5))

    def test_only_keeps_the_asked_terms(self):
        out = run("--labs", f("labs_keyword_overview.json"), "--only", "Sad Phonk", "--as-of", "2026-11-04")[1]
        self.assertEqual([r["term"] for r in out["rows"]], ["sad phonk"])


class Trends(unittest.TestCase):
    def test_yt_interest_is_the_mean_of_the_series_skipping_missing_points(self):
        code, out = run("--trends", f("trends_youtube.json"), "--as-of", "2026-11-04")
        self.assertEqual(code, 0)
        rows = by_term(out)
        self.assertEqual(rows["sad phonk"]["yt_interest"], 67)   # (40+60+100)/3, the missing week is not a zero
        self.assertEqual(rows["phonk drift"]["yt_interest"], 20)
        self.assertEqual(rows["sad phonk"]["source"], "trends")
        self.assertEqual(out["trends_batches"], [["sad phonk", "phonk drift"]])

    def test_related_queries_are_candidates_not_rows(self):
        out = run("--trends", f("trends_youtube.json"), "--as-of", "2026-11-04")[1]
        self.assertIn({"query": "sad phonk slowed", "kind": "rising", "value": 250,
                       "from": ["sad phonk", "phonk drift"]}, out["related"])
        self.assertNotIn("sad phonk slowed", by_term(out))

    def test_web_trends_are_refused_as_yt_interest(self):
        code, out = run("--trends", f("trends_web.json"))
        self.assertEqual(code, 2)
        self.assertIn("youtube", out["error"])

    def test_labs_and_trends_merge_into_one_row(self):
        out = run("--labs", f("labs_keyword_overview.json"), "--trends", f("trends_youtube.json"),
                  "--as-of", "2026-11-04")[1]
        row = by_term(out)["sad phonk"]
        self.assertEqual((row["volume"], row["yt_interest"], row["source"]), (1900, 67, "dataforseo"))


class SerpAndRecords(unittest.TestCase):
    def test_serp_adds_yt_competition_to_the_row(self):
        out = run("--labs", f("labs_keyword_overview.json"), "--serp", f("serp_youtube.json"),
                  "--as-of", "2026-11-04")[1]
        c = by_term(out)["sad phonk"]["yt_competition"]
        self.assertTrue(0 <= c <= 1)

    def test_every_row_is_accepted_by_the_records_contract(self):
        out = run("--labs", f("labs_keyword_overview.json"), "--labs", f("labs_related_keywords.json"),
                  "--trends", f("trends_youtube.json"), "--serp", f("serp_youtube.json"),
                  "--as-of", "2026-11-04")[1]
        self.assertTrue(out["rows"])
        for row in out["rows"]:
            p = subprocess.run([sys.executable, str(RECORDS), "check", "seed", *row["write_args"]],
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, (row, p.stdout, p.stderr))


class Refusals(unittest.TestCase):
    def test_an_account_error_is_a_refusal(self):
        code, out = run("--labs", f("error_unauthorized.json"))
        self.assertEqual(code, 2)
        self.assertIn("40100", out["error"])

    def test_all_tasks_failed_is_a_refusal(self):
        code, out = run("--labs", f("task_failed.json"))
        self.assertEqual(code, 2)
        self.assertIn("40501", out["error"])

    def test_the_ai_shape_is_refused_with_the_way_out(self):
        code, out = run("--labs", f("ai_shape.json"))
        self.assertEqual(code, 2)
        self.assertIn("noAiMode", out["error"])

    def test_a_warning_line_before_the_body_is_tolerated(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d) / "with_warning.json"
            tmp.write_text("Warning: Live endpoints allow only 1 task per request.\n"
                           + (FIX / "labs_keyword_overview.json").read_text())
            self.assertEqual(run("--labs", str(tmp), "--as-of", "2026-11-04")[0], 0)

    def test_nothing_to_read(self):
        self.assertEqual(run()[0], 2)


def trends_file(tmp: str, name: str, values: dict) -> str:
    kws = list(values)
    doc = {"status_code": 20000, "cost": 0.011, "tasks": [{
        "id": name, "status_code": 20000, "data": {"type": "youtube"},
        "result": [{"keywords": kws, "items": [{"type": "google_trends_graph", "keywords": kws,
                                                 "averages": [values[k] for k in kws], "data": []}]}]}]}
    path = Path(tmp) / f"{name}.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return str(path)


class TrendsOnOneScale(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_two_requests_without_an_anchor_are_refused(self):
        # A seed's yt_interest is read later without its request; two scales side by side would lie.
        a = trends_file(self.tmp.name, "a", {"honky tonk": 68, "outlaw country": 65})
        b = trends_file(self.tmp.name, "b", {"texas country": 73, "alt country": 1})
        code, out = run("--trends", a, "--trends", b, "--as-of", "2026-11-05")
        self.assertEqual(code, 2)
        self.assertIn("--anchor", out["error"])

    def test_an_anchor_puts_every_request_on_one_scale_with_the_top_at_100(self):
        a = trends_file(self.tmp.name, "a", {"outlaw country": 50, "honky tonk": 80})
        b = trends_file(self.tmp.name, "b", {"outlaw country": 25, "texas country": 60})
        code, out = run("--trends", a, "--trends", b, "--anchor", "outlaw country", "--as-of", "2026-11-05")
        self.assertEqual(code, 0, out)
        rows = by_term(out)
        # texas country rescales to 120 on request a's scale; the set is then divided so it reads 100.
        self.assertEqual({t: rows[t]["yt_interest"] for t in rows},
                         {"texas country": 100, "honky tonk": 67, "outlaw country": 42})

    def test_one_request_needs_no_anchor(self):
        a = trends_file(self.tmp.name, "a", {"honky tonk": 68, "outlaw country": 65})
        code, out = run("--trends", a, "--as-of", "2026-11-05")
        self.assertEqual(code, 0, out)
        self.assertEqual(by_term(out)["honky tonk"]["yt_interest"], 68)


if __name__ == "__main__":
    unittest.main()
