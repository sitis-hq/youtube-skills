import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "youtube-records" / "scripts"))
import records  # noqa: E402
import studio_reach  # noqa: E402

HEADER = "Content,Video title,Video publish time,Impressions,Impressions click-through rate (%)\n"


def run_csv(text: str, *extra: str) -> tuple[int, dict]:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d, "Table data.csv")
        path.write_text(text, encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = studio_reach.main(["--csv", str(path), "--as-of", "2026-11-03", *extra])
    return code, json.loads(buf.getvalue())


class StudioExport(unittest.TestCase):
    def test_a_percentage_becomes_a_fraction_the_record_accepts(self):
        code, out = run_csv(HEADER + "Total,,,12000,4.1\n" + "dQw4w9WgXcQ,Song,\"Nov 1, 2026\",1000,4.5\n")
        self.assertEqual(code, 0, out)
        (row,) = out["rows"]
        self.assertEqual(row["ctr"], 0.045)
        self.assertEqual(row["impressions"], 1000)
        key, data = records.build("studio", row)
        self.assertEqual(key, "studio:dQw4w9WgXcQ")

    def test_the_total_row_is_not_a_video(self):
        _, out = run_csv(HEADER + "Total,,,12000,4.1\n")
        self.assertEqual(out["rows"], [])
        self.assertEqual(out["skipped"][0]["value"], "Total")

    def test_a_video_missing_from_the_export_is_written_as_no_data(self):
        _, out = run_csv(HEADER + "dQw4w9WgXcQ,Song,,1000,4.5\n", "--video", "aaaaaaaaaaa")
        missing = [r for r in out["rows"] if r["video_id"] == "aaaaaaaaaaa"][0]
        self.assertFalse(missing["available"])
        records.build("studio", missing)

    def test_an_empty_cell_is_no_data_not_zero(self):
        _, out = run_csv(HEADER + "dQw4w9WgXcQ,Song,,,\n")
        self.assertEqual(out["rows"][0], {"video_id": "dQw4w9WgXcQ", "as_of": "2026-11-03",
                                          "source": "studio-export", "available": False})

    def test_a_header_without_its_unit_needs_one(self):
        text = "Content,Impressions,Impressions CTR\ndQw4w9WgXcQ,1000,0.045\n"
        code, out = run_csv(text)
        self.assertEqual(code, 2)
        self.assertIn("--ctr-unit", out["error"])
        code, out = run_csv(text, "--ctr-unit", "fraction")
        self.assertEqual(out["rows"][0]["ctr"], 0.045)

    def test_a_wrong_unit_is_caught_not_stored(self):
        code, out = run_csv("Content,Impressions,Impressions CTR\ndQw4w9WgXcQ,1000,4.5\n", "--ctr-unit", "fraction")
        self.assertEqual(code, 2)
        self.assertIn("outside 0..1", out["error"])

    def test_thousands_separators_are_read(self):
        _, out = run_csv(HEADER + 'dQw4w9WgXcQ,Song,,"12,345",3.2\n')
        self.assertEqual(out["rows"][0]["impressions"], 12345)


if __name__ == "__main__":
    unittest.main()
