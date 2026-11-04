import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "scripts"))
import score_idea as si  # noqa: E402

RECORDS = HERE.parents[1] / "youtube-records" / "scripts" / "records.py"
JUDGED = {"fit": 4, "packaging": 3, "feasibility": 4}


def run(*argv: str) -> tuple[int, dict]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = si.main(list(argv))
    return code, json.loads(buf.getvalue())


class Scale(unittest.TestCase):
    def test_volume_tiers_have_defined_edges(self):
        self.assertEqual([si.volume_tier(v) for v in (0, 1, 99, 100, 999, 1000, 9999, 10_000, 99_999, 100_000)],
                         [0, 1, 1, 2, 2, 3, 3, 4, 4, 5])

    def test_the_score_is_the_weighted_sum_on_0_to_100(self):
        out = si.score_one({"volume": 5000, "yt_competition": 0.4, **JUDGED})
        # demand 3, opportunity 3.0: 20*(0.25*3 + 0.2*3 + 0.25*4 + 0.15*3 + 0.15*4) = 68
        self.assertEqual(out["score"], 68.0)
        self.assertEqual(out["basis"]["opportunity"], "seed:yt_competition")

    def test_extremes_are_0_and_100(self):
        best = si.score_one({"volume": 10**6, "yt_competition": 0, "fit": 5, "packaging": 5, "feasibility": 5})
        self.assertEqual(best["score"], 100.0)
        worst = si.score_one({"volume": 0, "yt_competition": 1, "fit": 1, "packaging": 0, "feasibility": 1})
        self.assertGreaterEqual(worst["score"], 0)

    def test_demand_takes_the_larger_of_volume_and_interest(self):
        # A music mix: little web volume, strong YouTube interest.
        out = si.score_one({"volume": 50, "yt_interest": 80, "kd_web": 20, **JUDGED})
        self.assertEqual(out["components"]["demand"], 4)

    def test_kd_web_is_only_a_fallback_and_says_so(self):
        out = si.score_one({"volume": 5000, "kd_web": 40, **JUDGED})
        self.assertEqual(out["components"]["opportunity"], 3.0)
        self.assertIn("web proxy", out["basis"]["opportunity"])
        both = si.score_one({"volume": 5000, "kd_web": 90, "yt_competition": 0.2, **JUDGED})
        self.assertEqual(both["components"]["opportunity"], 4.0)

    def test_off_niche_or_unmakeable_ideas_are_vetoed(self):
        out = si.score_one({"volume": 10**6, "yt_competition": 0, "fit": 0, "packaging": 5, "feasibility": 5})
        self.assertEqual((out["score"], out["vetoed"]), (0.0, "fit"))

    def test_seed_fields_can_come_nested_as_read_from_the_record(self):
        out = si.score_one({"title": "T", "seed": {"term": "x", "volume": 5000, "yt_competition": 0.4}, **JUDGED})
        self.assertEqual(out["score"], 68.0)


class Refusals(unittest.TestCase):
    def test_a_judged_dimension_is_never_defaulted(self):
        code, out = run("--volume", "100", "--yt-competition", "0.5", "--fit", "3", "--packaging", "3")
        self.assertEqual(code, 2)
        self.assertIn("feasibility", out["error"])

    def test_no_demand_data_asks_for_measurement_or_a_judgement(self):
        code, out = run("--yt-competition", "0.5", "--fit", "3", "--packaging", "3", "--feasibility", "3")
        self.assertEqual(code, 2)
        self.assertIn("youtube-demand", out["error"])
        self.assertEqual(run("--demand", "2", "--yt-competition", "0.5", "--fit", "3",
                             "--packaging", "3", "--feasibility", "3")[0], 0)

    def test_out_of_scale_values_are_refused(self):
        self.assertEqual(run("--volume", "1", "--yt-competition", "1.5", "--fit", "3", "--packaging", "3",
                             "--feasibility", "3")[0], 2)
        self.assertEqual(run("--volume", "1", "--yt-competition", "0.5", "--fit", "6", "--packaging", "3",
                             "--feasibility", "3")[0], 2)


class Batch(unittest.TestCase):
    def test_file_is_ranked_and_the_score_fits_the_idea_record(self):
        ideas = [{"title": "Low", "volume": 10, "yt_competition": 0.9, **JUDGED},
                 {"title": "High", "volume": 50_000, "yt_competition": 0.1, **JUDGED}]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ideas.json"
            p.write_text(json.dumps(ideas))
            code, out = run("--file", str(p))
        self.assertEqual(code, 0)
        self.assertEqual([i["title"] for i in out["ideas"]], ["High", "Low"])
        top = out["ideas"][0]
        r = subprocess.run([sys.executable, str(RECORDS), "check", "idea", "--title", "High", "--keyword", "k",
                            "--hook", "h", "--thumbnail", "t", "--format", "long", "--status", "new",
                            "--source", "seed:k", "--score", str(top["score"])], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
