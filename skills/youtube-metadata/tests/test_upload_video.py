"""upload_video.py against a fake resumable session and the intent stub of test_apply_video."""

import io
import json
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import upload_video as uv  # noqa: E402
from test_apply_video import IDS, STUB, TOKEN  # noqa: E402

ac = uv.ac
SESSION = "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=abc"
VIDEO = "Zx9Yw8Vu7Ts"


class FakeSession:
    """One resumable session as YouTube keeps it: the bytes it holds, and failures to inject."""

    def __init__(self, held=0, start_status=200, lose_piece=None, gone=False, piece_status=None):
        self.received = bytearray()
        self.held = held
        self.start_status = start_status
        self.lose_piece = lose_piece
        self.gone = gone
        self.piece_status = piece_status
        self.pieces = []
        self.size = None
        self.start_body = None

    def __call__(self, method, url, headers, body):
        if method == "POST":
            self.start_body = json.loads(body)
            self.size = int(headers["X-Upload-Content-Length"])
            if self.start_status != 200:
                return self.start_status, {}, json.dumps({"error": {"errors": [{"reason": "forbidden"}],
                                                                    "message": "no"}}).encode()
            return 200, {"location": SESSION}, b""
        self.size = int(headers["Content-Range"].split("/")[-1])
        if self.gone:
            return 404, {}, b""
        if headers["Content-Range"].startswith("bytes */"):
            return self.state()
        start = int(headers["Content-Range"].split(" ")[1].split("-")[0])
        assert start == self.held, f"piece starts at {start}, the session holds {self.held}"
        self.pieces.append(start)
        if self.piece_status and len(self.pieces) == 1:
            return self.piece_status, {}, b""
        self.held += len(body)
        if self.lose_piece is not None and len(self.pieces) == self.lose_piece:
            raise ac.ApiError(None, "network", "answer lost")
        return self.state()

    def state(self):
        if self.held >= self.size:
            return 200, {}, json.dumps({"id": VIDEO, "status": {"privacyStatus": "private",
                                                                "publishAt": "2030-01-01T15:00:00Z"}}).encode()
        return 308, ({"range": f"bytes=0-{self.held - 1}"} if self.held else {}), b""


class Upload(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.dir.name)
        stub = self.tmp / "ai-integration"
        stub.write_text(STUB)
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        self.stub = stub
        os.environ["AI_INTEGRATION_BIN"] = str(stub)
        self.saved = (uv.http, uv._token, uv.SLEEP, uv.PIECE)
        uv._token = lambda connection: TOKEN
        uv.SLEEP = lambda s: None
        uv.PIECE = 10
        self.file = self.tmp / "mix.mp4"
        self.file.write_bytes(b"\x00\x00\x00\x18ftypmp42" + bytes(range(33)))  # 45 bytes: 5 pieces
        self.meta = self.tmp / "meta.json"
        self.write_meta()

    def tearDown(self):
        uv.http, uv._token, uv.SLEEP, uv.PIECE = self.saved
        os.environ.pop("AI_INTEGRATION_BIN", None)
        self.dir.cleanup()

    def write_meta(self, **change):
        meta = {"title": "Late Night Mix", "description": "d", "tags": ["mix"], "publishAt": "2030-01-01T15:00:00Z",
                "selfDeclaredMadeForKids": False}
        meta.update(change)
        meta = {k: v for k, v in meta.items() if v is not None}
        self.meta.write_text(json.dumps(meta))

    def cli(self, api, *argv):
        uv.http = api
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = uv.main([*IDS, *argv])
        text = buf.getvalue()
        self.assertNotIn(TOKEN, text)
        return code, json.loads(text)

    def intent_state(self):
        return json.loads((self.tmp / "ai-integration.state").read_text())

    def start(self, api):
        return self.cli(api, "start", "--file", str(self.file), "--meta", str(self.meta))

    def send(self, api):
        return self.cli(api, "send", "--file", str(self.file), "--session", SESSION)

    def test_start_opens_a_session_and_sends_nothing(self):
        api = FakeSession()
        code, out = self.start(api)
        self.assertEqual(code, 0)
        self.assertEqual(out["session_uri"], SESSION)
        self.assertEqual(api.pieces, [])
        self.assertEqual(api.start_body["status"], {"privacyStatus": "private", "selfDeclaredMadeForKids": False,
                                                    "publishAt": "2030-01-01T15:00:00Z"})
        self.assertEqual(list(self.intent_state().values())[0]["status"], "claimed")
        code, again = self.start(FakeSession())
        self.assertEqual(code, 2)
        self.assertFalse(again["acted"])
        self.assertIn("session uri was stored", again["say"])

    def test_send_uploads_every_piece_once_and_commits(self):
        self.start(FakeSession())
        api = FakeSession()
        code, out = self.send(api)
        self.assertEqual(code, 0)
        self.assertEqual(out["video_id"], VIDEO)
        self.assertEqual(api.pieces, [0, 10, 20, 30, 40])
        rec = list(self.intent_state().values())[0]
        self.assertEqual((rec["status"], rec["result"]), ("committed", {"video_id": VIDEO}))

    def test_a_later_run_resumes_where_the_session_stopped(self):
        self.start(FakeSession())
        api = FakeSession(held=20)
        code, out = self.send(api)
        self.assertEqual(code, 0)
        self.assertEqual(out["resumed_at"], 20)
        self.assertEqual(api.pieces, [20, 30, 40])

    def test_a_lost_answer_is_checked_not_resent(self):
        self.start(FakeSession())
        api = FakeSession(lose_piece=2)
        code, out = self.send(api)
        self.assertEqual(code, 0)
        # The piece whose answer was lost had arrived; the session said so and it was not sent again.
        self.assertEqual(api.pieces, [0, 10, 20, 30, 40])

    def test_a_finished_session_gives_the_video_without_sending(self):
        self.start(FakeSession())
        api = FakeSession(held=45)
        code, out = self.send(api)
        self.assertEqual((code, out["video_id"], api.pieces), (0, VIDEO, []))

    def test_a_gone_session_is_uncertain_and_keeps_the_claim(self):
        self.start(FakeSession())
        code, out = self.send(FakeSession(gone=True))
        self.assertEqual(code, 2)
        self.assertTrue(out["uncertain"])
        self.assertEqual(list(self.intent_state().values())[0]["status"], "claimed")

    def test_a_refused_piece_is_uncertain(self):
        self.start(FakeSession())
        code, out = self.send(FakeSession(piece_status=400))
        self.assertEqual(code, 2)
        self.assertTrue(out["uncertain"])

    def test_a_refused_start_fails_the_intent_so_a_later_run_may_start(self):
        code, out = self.start(FakeSession(start_status=403))
        self.assertEqual((code, out["intent"]), (2, "failed"))
        code, out = self.start(FakeSession())
        self.assertEqual(code, 0)

    def test_metadata_is_checked_before_any_claim(self):
        for change in ({"selfDeclaredMadeForKids": None}, {"privacy": "public"}, {"title": "x" * 101},
                       {"publishAt": "2020-01-01T00:00:00Z"}, {"description": "a <b>"}):
            self.write_meta(**change)
            code, out = self.start(FakeSession())
            self.assertEqual(code, 2, change)
            self.assertFalse(out["ok"])
        self.assertFalse((self.tmp / "ai-integration.state").exists())

    def test_not_a_video_is_refused(self):
        self.file.write_bytes(b"not a video at all")
        code, out = self.start(FakeSession())
        self.assertEqual(code, 2)
        self.assertIn("ftyp", out["error"])


if __name__ == "__main__":
    unittest.main()
