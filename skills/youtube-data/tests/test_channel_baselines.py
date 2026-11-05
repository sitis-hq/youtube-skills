import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "scripts"))
import channel_baselines as cb  # noqa: E402

A = "UC" + "a" * 22
B = "UC" + "b" * 22
C = "UC" + "c" * 22


def serp(channel_ids: list) -> dict:
    items = [{"type": "youtube_video", "rank_absolute": i + 1, "video_id": f"v{i}", "channel_id": cid,
              "views_count": 100, "title": "t"} for i, cid in enumerate(channel_ids)]
    return {"status_code": 20000, "tasks": [{"id": "t", "status_code": 20000, "data": {"keyword": "k"},
                                              "result": [{"keyword": "k", "items": items}]}]}


def tab(subs: int | None, views: list[int]) -> str:
    return json.dumps({"channel": "Some channel", "channel_follower_count": subs,
                       "entries": [{"id": f"x{i}", "view_count": v} for i, v in enumerate(views)]})


class Baselines(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.out = str(Path(self.dir.name) / "baselines.json")
        self.answers: dict[str, tuple[int, str, str]] = {}
        self.asked: list[str] = []

        def fake(argv: list[str]) -> tuple[int, str, str]:
            cid = argv[-1].split("/channel/")[1].split("/")[0]
            self.asked.append(cid)
            return self.answers.get(cid, (0, tab(1000, [10, 20, 30, 40, 50]), ""))
        patcher = mock.patch.object(cb, "run_ytdlp", side_effect=fake)
        patcher.start()
        self.addCleanup(patcher.stop)

    def file(self, doc: dict) -> str:
        path = Path(self.dir.name) / f"serp{len(list(Path(self.dir.name).iterdir()))}.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        return str(path)

    def call(self, *argv: str) -> tuple[int, dict]:
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = cb.run(cb.main, [*argv, "--out", self.out, "--sleep", "0"])
        return code, json.loads(out.getvalue())

    def saved(self) -> dict:
        return json.loads(Path(self.out).read_text())

    def test_each_channel_of_the_top_is_read_once_and_collaborations_are_skipped(self):
        code, doc = self.call("--serp", self.file(serp([A, B, A, None, "not-an-id"])))
        self.assertEqual(code, 0)
        self.assertEqual(self.asked, [A, B])
        self.assertEqual(doc["read"], 2)

    def test_the_median_and_the_subscribers_are_recorded(self):
        self.answers[A] = (0, tab(1850, [75, 81, 78, 240, 287, 531, 89000]), "")
        self.call("--channel-id", A)
        row = self.saved()["channels"][A]
        self.assertEqual((row["subscribers"], row["videos_read"], row["median_views"]), (1850, 7, 240))
        self.assertNotIn("note", row)

    def test_a_channel_with_few_uploads_carries_a_note(self):
        self.answers[A] = (0, tab(10, [5, 6]), "")
        self.call("--channel-id", A)
        self.assertIn("fewer than 5", self.saved()["channels"][A]["note"])

    def test_a_second_run_reads_only_what_the_first_did_not(self):
        self.call("--channel-id", A)
        self.asked.clear()
        code, doc = self.call("--channel-id", A, "--channel-id", B)
        self.assertEqual(self.asked, [B])
        self.assertEqual(doc["skipped"], 1)
        self.assertEqual(set(self.saved()["channels"]), {A, B})

    def test_a_rate_limit_stops_the_run_and_keeps_what_was_read(self):
        self.answers[B] = (1, "", "ERROR: HTTP Error 429: Too Many Requests")
        code, doc = self.call("--channel-id", A, "--channel-id", B, "--channel-id", C)
        self.assertEqual(code, 0)
        self.assertIn("429", doc["stopped"])
        self.assertEqual(self.asked, [A, B])
        self.assertEqual(set(self.saved()["channels"]), {A})

    def test_another_failure_is_recorded_and_the_run_goes_on(self):
        self.answers[A] = (1, "", "ERROR: This channel does not exist")
        code, doc = self.call("--channel-id", A, "--channel-id", B)
        self.assertEqual(doc["failed"], 1)
        self.assertIn(A, self.saved()["failed"])
        self.assertIn(B, self.saved()["channels"])

    def test_a_bad_channel_id_is_refused(self):
        code, doc = self.call("--channel-id", "@handle")
        self.assertEqual(code, 2)

    def test_an_out_file_of_another_kind_is_not_overwritten(self):
        Path(self.out).write_text('{"rows": []}')
        code, doc = self.call("--channel-id", A)
        self.assertEqual(code, 2)
        self.assertEqual(Path(self.out).read_text(), '{"rows": []}')


class MissingTool(unittest.TestCase):
    def test_missing_ytdlp_names_the_attachment(self):
        with mock.patch.object(cb.shutil, "which", return_value=None):
            with self.assertRaises(cb.Refusal) as e:
                cb.run_ytdlp(["--version"])
        self.assertIn("yt-dlp CLI from the shelf", str(e.exception))


if __name__ == "__main__":
    unittest.main()
