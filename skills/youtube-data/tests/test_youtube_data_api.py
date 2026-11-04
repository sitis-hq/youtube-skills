"""data_api.py, analytics.py and reporting.py against a fake transport: no test touches the network."""

import contextlib
import csv
import io
import json
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1] / "scripts"))
sys.path.insert(0, str(HERE.parents[3] / "lib"))
sys.path.insert(0, str(HERE.parents[2] / "youtube-records" / "scripts"))

import _yt  # noqa: E402
import analytics  # noqa: E402
import data_api  # noqa: E402
import records  # noqa: E402
import reporting  # noqa: E402
from ytskills.common import Refusal, run  # noqa: E402

TOKEN = "ya29.SECRET-TOKEN-VALUE"


def vid(n: int) -> str:
    return f"vid{n:08d}"


class Fake:
    """Answers requests by path; records every call, and the Authorization it carried."""

    def __init__(self, handler, statuses=None):
        self.handler = handler
        self.calls = []
        self.statuses = list(statuses or [])
        self.token_calls = 0

    def http(self, method, url, headers, body=None):
        parts = urllib.parse.urlsplit(url)
        params = dict(urllib.parse.parse_qsl(parts.query))
        self.calls.append((method, parts.path, params, headers.get("Authorization")))
        if self.statuses:
            status = self.statuses.pop(0)
            if status != 200:
                return status, json.dumps({"error": {"errors": [{"reason": "x"}], "message": "m"}}).encode()
        out = self.handler(method, parts.path, params, body)
        if isinstance(out, tuple):
            return out
        return 200, out if isinstance(out, bytes) else json.dumps(out).encode()

    def token(self, argv):
        self.token_calls += 1
        return 0, json.dumps({"success": True, "command": "oauth-token",
                              "data": {"accessToken": f"{TOKEN}-{self.token_calls}",
                                       "expiresAt": "2026-11-04T12:00:00Z"}}) + "\n", ""


class Patched(unittest.TestCase):
    def use(self, fake):
        self._saved = (_yt.http_request, _yt.run_command)
        _yt.http_request, _yt.run_command = fake.http, fake.token
        self.addCleanup(self._restore)
        return fake

    def _restore(self):
        _yt.http_request, _yt.run_command = self._saved

    def run_main(self, main, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = run(main, argv)
        return code, buf.getvalue()


def video_item(i, views=100):
    return {"id": i, "snippet": {"channelId": "UC" + "a" * 22, "channelTitle": "Ch", "title": f"T {i}",
                                 "publishedAt": "2026-10-01T00:00:00Z", "liveBroadcastContent": "none"},
            "statistics": {"viewCount": str(views), "commentCount": "3"},
            "contentDetails": {"duration": "PT4M13S"}}


class Token(Patched):
    def test_token_comes_from_ai_integration_and_is_never_printed(self):
        fake = self.use(Fake(lambda m, p, q, b: {"items": [video_item(vid(1))]}))
        code, out = self.run_main(data_api.main, ["videos", "--id", vid(1)])
        self.assertEqual(code, 0)
        self.assertNotIn(TOKEN, out)
        self.assertEqual(fake.calls[0][3], f"Bearer {TOKEN}-1")

    def test_refused_token_names_the_cause(self):
        def refuse(argv):
            return 1, json.dumps({"success": False, "command": "oauth-token",
                                  "error": {"type": "X", "message": "connection YOUTUBE not given"}}), ""
        _saved = _yt.run_command
        _yt.run_command = refuse
        self.addCleanup(setattr, _yt, "run_command", _saved)
        with self.assertRaises(Refusal) as e:
            _yt.access_token()
        self.assertIn("not given", str(e.exception))
        self.assertIn("YOUTUBE_REFRESH_TOKEN", str(e.exception))

    def test_401_renews_the_token_once(self):
        fake = self.use(Fake(lambda m, p, q, b: {"items": []}, statuses=[401, 200]))
        c = _yt.Client()
        c.data_api("videos", {"id": vid(1)})
        self.assertEqual(fake.token_calls, 2)
        self.assertEqual(fake.calls[1][3], f"Bearer {TOKEN}-2")

    def test_quota_exhaustion_is_a_refusal(self):
        def handler(m, p, q, b):
            return 403, json.dumps({"error": {"errors": [{"reason": "quotaExceeded"}], "message": "q"}}).encode()
        self.use(Fake(handler))
        code, out = self.run_main(data_api.main, ["videos", "--id", vid(1)])
        self.assertEqual(code, 2)
        self.assertIn("quota", json.loads(out)["error"])


class Videos(Patched):
    def test_batches_of_fifty_and_units(self):
        fake = self.use(Fake(lambda m, p, q, b: {"items": [video_item(i) for i in q["id"].split(",")
                                                           if i != vid(7)]}))
        ids = [vid(i) for i in range(120)]
        out = data_api.main(["videos", "--id", ",".join(ids)])
        self.assertEqual([len(c[2]["id"].split(",")) for c in fake.calls], [50, 50, 20])
        self.assertEqual(out["quota"]["data_api_units"], 3)
        self.assertEqual(out["missing"], [vid(7)])
        row = out["videos"][0]
        self.assertEqual((row["duration_s"], row["views"], row["likes"]), (253, 100, None))
        self.assertRegex(out["as_of"], r"^\d{4}-\d{2}-\d{2}$")

    def test_ids_file_reads_records_and_drops_repeats(self):
        doc = {"data": [{"key": f"watch:{vid(1)}", "data": {"video_id": vid(1)}},
                        {"key": f"watch:{vid(2)}"}]}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(doc, fh)
        self.addCleanup(Path(fh.name).unlink)
        self.assertEqual(data_api.collect_ids([vid(3)], fh.name), [vid(3), vid(1), vid(2)])

    def test_bad_id_refused(self):
        with self.assertRaises(Refusal):
            data_api.collect_ids(["short"], None)


class Uploads(Patched):
    def test_uploads_playlist_is_derived_and_since_stops_paging(self):
        def handler(m, path, q, b):
            self.assertEqual(q["playlistId"], "UU" + "b" * 22)
            return {"items": [{"contentDetails": {"videoId": vid(1), "videoPublishedAt": "2026-10-20T00:00:00Z"}},
                              {"contentDetails": {"videoId": vid(2), "videoPublishedAt": "2026-09-01T00:00:00Z"}}],
                    "nextPageToken": "more"}
        fake = self.use(Fake(handler))
        out = data_api.main(["uploads", "--channel-id", "UC" + "b" * 22, "--since", "2026-10-01"])
        self.assertEqual([i["video_id"] for i in out["items"]], [vid(1)])
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(out["quota"]["data_api_units"], 1)


class Search(Patched):
    def test_budget_refuses_before_any_call(self):
        fake = self.use(Fake(lambda *a: {}))
        code, out = self.run_main(data_api.main, ["search", "--q", "lofi", "--pages", "3"])
        self.assertEqual(code, 2)
        self.assertIn("100 units", json.loads(out)["error"])
        self.assertEqual(fake.calls, [])

    def test_one_page_costs_100(self):
        self.use(Fake(lambda m, p, q, b: {"items": [{"id": {"videoId": vid(1)}, "snippet": {"title": "x"}}]}))
        out = data_api.main(["search", "--q", "lofi", "--published-after", "2026-10-01"])
        self.assertEqual(out["quota"]["data_api_units"], 100)
        self.assertEqual(out["results"][0]["video_id"], vid(1))


def retention_rows(q):
    rows = [[round(i / 100, 2), 1.0 - i / 200, 0.5] for i in range(1, 101)]
    return {"columnHeaders": [{"name": "elapsedVideoTimeRatio"}, {"name": "audienceWatchRatio"},
                              {"name": "relativeRetentionPerformance"}], "rows": rows}


class Analytics(Patched):
    def test_metrics_that_do_not_exist_are_refused(self):
        fake = self.use(Fake(lambda *a: {}))
        for m in ("impressions", "impressionClickThroughRate"):
            code, out = self.run_main(analytics.main, ["query", "--metrics", f"views,{m}", "--days", "7"])
            self.assertEqual(code, 2)
            self.assertIn(m, json.loads(out)["error"])
        self.assertEqual(fake.calls, [])

    def test_retention_csv_is_in_percent_for_retention_py(self):
        fake = self.use(Fake(lambda m, p, q, b: retention_rows(q)))
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "r.csv")
            out = analytics.main(["retention", "--id", vid(1), "--start", "2026-10-01", "--end",
                                  "2026-11-01", "--duration", "PT10M", "--csv", path])
            with open(path) as fh:
                rows = list(csv.reader(fh))
        self.assertEqual(rows[0], ["position_percent", "watching_percent"])
        self.assertEqual(rows[1], ["1.0", "99.5"])
        self.assertEqual(rows[50], ["50.0", "75.0"])
        self.assertEqual(out["duration_s"], 600)
        self.assertIn("--axis percent --duration 600", out["next"])
        q = fake.calls[0][2]
        self.assertEqual((q["dimensions"], q["filters"], q["ids"]),
                         ("elapsedVideoTimeRatio", f"video=={vid(1)}", "channel==MINE"))

    def test_the_csv_reads_back_in_retention_py(self):
        sys.path.insert(0, str(HERE.parents[2] / "youtube-metrics" / "scripts"))
        import retention
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "r.csv")
            # The API's shape, with a 10-point cliff at the middle of a 600 s video.
            api_rows = [{"elapsedVideoTimeRatio": x, "audienceWatchRatio": y - (0.1 if x > 0.5 else 0)}
                        for x, y, _ in retention_rows({})["rows"]]
            analytics.retention_csv(api_rows, path)
            out = retention.main([path, "--axis", "percent", "--duration", "600"])
        self.assertEqual(out["cliffs"][0]["at_seconds"], 300.0)

    def test_retention_without_data_is_not_an_error(self):
        self.use(Fake(lambda *a: {"columnHeaders": [], "rows": []}))
        out = analytics.main(["retention", "--id", vid(1), "--days", "7", "--duration", "60",
                              "--csv", "/nonexistent/x.csv"])
        self.assertFalse(out["available"])

    def test_video_metrics_rows_and_absent_videos(self):
        def handler(m, p, q, b):
            return {"columnHeaders": [{"name": "video"}, {"name": "views"}], "rows": [[vid(1), 10]]}
        fake = self.use(Fake(handler))
        out = analytics.main(["video-metrics", "--id", f"{vid(1)},{vid(2)}", "--days", "28"])
        self.assertEqual(out["videos"], [{"video": vid(1), "views": 10}])
        self.assertEqual(out["no_rows"], [vid(2)])
        self.assertEqual(fake.calls[0][2]["sort"], "-views")
        self.assertEqual(out["quota"]["data_api_units"], 0)


REACH_CSV = ("date,channel_id,video_id,video_thumbnail_impressions,video_thumbnail_impressions_ctr\n"
             f"20261101,UC{'a' * 22},{vid(1)},1000,4.5\n"
             f"20261101,UC{'a' * 22},{vid(1)},3000,1.5\n"
             f"20261102,UC{'a' * 22},{vid(1)},500,2.0\n")


class Reporting(Patched):
    def handler(self, m, path, q, b):
        if path.endswith("/jobs"):
            return {"jobs": [{"id": "J1", "reportTypeId": reporting.REACH}]}
        if path.endswith("/reports"):
            return {"reports": [
                {"id": "r1", "startTime": "2026-11-01T07:00:00Z", "createTime": "2026-11-03T00:00:00Z",
                 "downloadUrl": "https://youtubereporting.googleapis.com/v1/media/old"},
                {"id": "r2", "startTime": "2026-11-01T07:00:00Z", "createTime": "2026-11-05T00:00:00Z",
                 "downloadUrl": "https://youtubereporting.googleapis.com/v1/media/new"}]}
        if path.endswith("/media/new"):
            return REACH_CSV.encode()
        raise AssertionError(f"the superseded report was downloaded: {path}")

    def test_reach_gives_studio_records_with_fraction_ctr(self):
        self.use(Fake(self.handler))
        out = reporting.main(["reach", "--ctr-scale", "percent", "--id", f"{vid(1)},{vid(2)}", "--all-days"])
        recs = out["records"]
        first = recs[0]
        # 1000 at 4.5 % and 3000 at 1.5 %: 90 clicks of 4000, not the mean of the two rates.
        self.assertEqual((first["as_of"], first["impressions"], first["ctr"]), ("2026-11-01", 4000, 0.0225))
        absent = [r for r in recs if r["video_id"] == vid(2)][0]
        self.assertFalse(absent["available"])
        for r in recs:
            records.build("studio", r)  # every element is a valid studio record as it comes

    def test_newest_day_only_by_default(self):
        self.use(Fake(self.handler))
        out = reporting.main(["reach", "--ctr-scale", "percent"])
        self.assertEqual([(r["as_of"], r["ctr"]) for r in out["records"]], [("2026-11-02", 0.02)])

    def test_a_scale_the_file_contradicts_is_refused(self):
        with self.assertRaises(Refusal):
            reporting.parse_reach_csv(REACH_CSV, "fraction")


if __name__ == "__main__":
    unittest.main()
