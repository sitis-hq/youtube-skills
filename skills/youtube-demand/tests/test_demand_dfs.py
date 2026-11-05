import base64
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "scripts"))
import dfs  # noqa: E402

CREDS = {"DATAFORSEO_LOGIN": "api-login", "DATAFORSEO_PASSWORD": "api-pass"}
OK_BODY = {"status_code": 20000, "status_message": "Ok.", "cost": 0.002, "tasks": [
    {"id": "t1", "status_code": 20000, "status_message": "Ok.", "result": [{"items": []}]}]}


class FakeDataForSEO(BaseHTTPRequestHandler):
    answer: tuple[int, bytes] = (200, json.dumps(OK_BODY).encode())
    seen: list[dict] = []

    def _reply(self, body: bytes | None) -> None:
        type(self).seen.append({"method": self.command, "path": self.path,
                                "auth": self.headers.get("Authorization"),
                                "body": json.loads(body) if body else None})
        status, payload = type(self).answer
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):  # noqa: N802 (http.server's naming)
        self._reply(self.rfile.read(int(self.headers.get("Content-Length") or 0)))

    def do_GET(self):  # noqa: N802
        self._reply(None)

    def log_message(self, *args):
        pass


class Fake(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), FakeDataForSEO)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        FakeDataForSEO.seen = []
        FakeDataForSEO.answer = (200, json.dumps(OK_BODY).encode())
        patcher = mock.patch.object(dfs, "API_BASE", self.base)
        patcher.start()
        self.addCleanup(patcher.stop)

    def out(self, name: str = "resp.json") -> str:
        return str(Path(self.dir.name) / name)

    def call(self, *argv: str, env: dict | None = None) -> tuple[int, dict, str]:
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, env if env is not None else CREDS, clear=True), \
                redirect_stdout(out), redirect_stderr(err):
            code = dfs.main(list(argv))
        return code, json.loads(out.getvalue()), out.getvalue() + err.getvalue()


class Calls(Fake):
    def test_the_response_is_saved_exactly_as_it_came(self):
        raw = b'{"status_code": 20000, "cost": 0.002, "tasks": [], "extra": "kept as is"}'
        FakeDataForSEO.answer = (200, raw)
        code, doc, _ = self.call("post", "/v3/serp/youtube/organic/live/advanced", "--data", '{"keyword": "k"}',
                                 "--out", self.out())
        self.assertEqual(code, 0)
        self.assertEqual(Path(self.out()).read_bytes(), raw)
        self.assertEqual(doc["cost"], 0.002)

    def test_one_task_object_is_sent_as_a_list_of_one_with_basic_auth(self):
        self.call("post", "/v3/serp/youtube/organic/live/advanced", "--data", '{"keyword": "k"}', "--out", self.out())
        sent = FakeDataForSEO.seen[0]
        self.assertEqual(sent["body"], [{"keyword": "k"}])
        self.assertEqual(sent["path"], "/v3/serp/youtube/organic/live/advanced")
        self.assertEqual(sent["auth"], "Basic " + base64.b64encode(b"api-login:api-pass").decode())

    def test_the_username_alias_is_read_like_the_mcp_server_does(self):
        code, _, _ = self.call("get", "/v3/appendix/user_data", "--out", self.out(),
                               env={"DATAFORSEO_USERNAME": "api-login", "DATAFORSEO_PASSWORD": "api-pass"})
        self.assertEqual(code, 0)

    def test_task_results_are_summarised(self):
        code, doc, _ = self.call("get", "/v3/appendix/user_data", "--out", self.out())
        self.assertEqual(doc["tasks"], [{"id": "t1", "status_code": 20000, "status_message": "Ok.", "result_count": 1}])
        self.assertEqual(doc["failed_tasks"], 0)

    def test_an_account_error_fails_the_call_but_the_body_is_kept(self):
        FakeDataForSEO.answer = (402, json.dumps({"status_code": 40200, "status_message": "Payment Required."}).encode())
        code, doc, _ = self.call("get", "/v3/appendix/user_data", "--out", self.out())
        self.assertEqual(code, 2)
        self.assertIn("40200", doc["error"])
        self.assertEqual(json.loads(Path(self.out()).read_text())["status_code"], 40200)

    def test_the_credentials_are_never_printed(self):
        FakeDataForSEO.answer = (401, json.dumps({"status_code": 40100, "status_message": "auth"}).encode())
        _, _, printed = self.call("get", "/v3/appendix/user_data", "--out", self.out())
        self.assertNotIn("api-pass", printed)
        self.assertNotIn(base64.b64encode(b"api-login:api-pass").decode(), printed)


class Refusals(Fake):
    def test_missing_credentials_are_named(self):
        code, doc, _ = self.call("get", "/v3/appendix/user_data", "--out", self.out(), env={"DATAFORSEO_LOGIN": "x"})
        self.assertEqual(code, 2)
        self.assertIn("DATAFORSEO_PASSWORD", doc["error"])
        self.assertEqual(FakeDataForSEO.seen, [])

    def test_the_ai_shape_is_never_requested(self):
        code, doc, _ = self.call("post", "/v3/serp/youtube/organic/live/advanced.ai", "--data", "{}", "--out", self.out())
        self.assertEqual(code, 2)
        self.assertEqual(FakeDataForSEO.seen, [])

    def test_a_live_call_takes_one_task(self):
        code, doc, _ = self.call("post", "/v3/serp/youtube/organic/live/advanced", "--data", "[{}, {}]",
                                 "--out", self.out())
        self.assertEqual(code, 2)
        self.assertIn("one task per call", doc["error"])

    def test_a_standard_task_post_takes_many(self):
        code, _, _ = self.call("post", "/v3/serp/youtube/organic/task_post", "--data", '[{"keyword": "a"}, {"keyword": "b"}]',
                               "--out", self.out())
        self.assertEqual(code, 0)
        self.assertEqual(len(FakeDataForSEO.seen[0]["body"]), 2)

    def test_a_saved_response_is_not_replaced_by_accident(self):
        Path(self.out()).write_text("{}")
        code, doc, _ = self.call("get", "/v3/appendix/user_data", "--out", self.out())
        self.assertEqual(code, 2)
        self.assertEqual(Path(self.out()).read_text(), "{}")
        code, _, _ = self.call("get", "/v3/appendix/user_data", "--out", self.out(), "--overwrite")
        self.assertEqual(code, 0)

    def test_a_body_that_is_not_json_is_refused_before_any_call(self):
        code, doc, _ = self.call("post", "/v3/serp/youtube/organic/live/advanced", "--data", "{keyword", "--out", self.out())
        self.assertEqual(code, 2)
        self.assertEqual(FakeDataForSEO.seen, [])

    def test_a_path_outside_v3_is_refused(self):
        code, _, _ = self.call("get", "https://evil.example/v3/x", "--out", self.out())
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
