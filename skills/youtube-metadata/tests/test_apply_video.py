import io
import json
import os
import stat
import struct
import sys
import tempfile
import unittest
import zlib
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import apply_video  # noqa: E402

ac = apply_video.ac
VIDEO = "dQw4w9WgXcQ"
IDS = ["--spec-template-id", "11111111-1111-4111-8111-111111111111",
       "--project-id", "33333333-3333-4333-8333-333333333333"]
TOKEN = "ya29.secret-token-never-printed"

# The intent half of ai-integration, as in youtube-channel-setup's tests.
STUB = r'''#!/usr/bin/env python3
import json, sys
state_path, log_path = sys.argv[0] + ".state", sys.argv[0] + ".log"
a = sys.argv[1:]
verb = a[0]
opt = lambda name: a[a.index(name) + 1] if name in a else None
try:
    state = json.load(open(state_path))
except OSError:
    state = {}
open(log_path, "a").write(json.dumps({"verb": verb, "argv": a}) + "\n")
key = opt("--intent-key")
rec = state.get(key)
if verb == "claim-intent":
    if rec is None or rec["status"] == "failed":
        state[key] = {"status": "claimed", "result": None}
        data = {"outcome": "fresh", "status": "claimed"}
    else:
        data = {"outcome": "exists", "status": rec["status"], "result": rec["result"]}
elif verb == "commit-intent":
    rec.update(status="committed", result=json.load(open(opt("--result-file"))) if opt("--result-file") else None)
    data = {"outcome": "committed", "status": "committed"}
else:
    rec.update(status="failed")
    data = {"outcome": "failed", "status": "failed"}
json.dump(state, open(state_path, "w"))
print(json.dumps({"success": True, "command": verb, "data": data}))
'''


def png(w, h, pad=0):
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    chunk = struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr))
    return b"\x89PNG\r\n\x1a\n" + chunk + b"\x00" * pad


class FakeApi:
    """A video's snippet as the Data API keeps it; videos.update replaces the whole snippet."""

    def __init__(self, apply_update=True, errors=None, lag=0):
        self.snippet = {"title": "Old title", "description": "old", "tags": ["a", "b"], "categoryId": "10",
                        "defaultLanguage": "en", "publishedAt": "2026-11-01T00:00:00Z", "channelId": "UCx",
                        "thumbnails": {}, "localized": {"title": "Old title"}}
        self.apply_update = apply_update
        self.errors = dict(errors or {})
        self.lag = lag
        self.stale = None
        self.calls = []

    def __call__(self, method, url, headers, body):
        name = url.split("?")[0].rsplit("/v3/", 1)[1]
        self.calls.append({"method": method, "name": name, "url": url, "headers": headers, "body": body})
        if name in self.errors:
            status, reason = self.errors[name]
            return status, json.dumps({"error": {"errors": [{"reason": reason}], "message": reason}}).encode()
        if name == "videos" and method == "GET":
            shown = self.snippet
            if self.lag and self.stale is not None:
                self.lag -= 1
                shown = self.stale
            return 200, json.dumps({"items": [{"id": VIDEO, "snippet": shown}]}).encode()
        if name == "videos" and method == "PUT":
            sent = json.loads(body)
            if self.apply_update:
                self.stale, self.snippet = self.snippet, sent["snippet"]
            return 200, json.dumps(sent).encode()
        if name == "thumbnails/set":
            return 200, json.dumps({"items": [{"default": {"url": "u"}}]}).encode()
        raise AssertionError(f"unexpected call {method} {url}")

    def names(self):
        return [(c["method"], c["name"]) for c in self.calls]


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.dir.name)
        stub = self.tmp / "ai-integration"
        stub.write_text(STUB)
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        self.stub = stub
        os.environ["AI_INTEGRATION_BIN"] = str(stub)
        self.saved = (ac.http, ac.access_token, ac.SLEEP)
        ac.access_token = lambda connection: TOKEN
        self.slept = []
        ac.SLEEP = self.slept.append

    def tearDown(self):
        ac.http, ac.access_token, ac.SLEEP = self.saved
        os.environ.pop("AI_INTEGRATION_BIN", None)
        self.dir.cleanup()

    def run_cli(self, api, *argv):
        ac.http = api
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = apply_video.main(list(argv))
        text = buf.getvalue()
        self.assertNotIn(TOKEN, text)
        return code, json.loads(text)

    def desired(self, value):
        p = self.tmp / "meta.json"
        p.write_text(json.dumps(value))
        return str(p)

    def intent_calls(self):
        log = Path(str(self.stub) + ".log")
        return [json.loads(x)["verb"] for x in log.read_text().splitlines()] if log.exists() else []


class Metadata(Base):
    def test_the_whole_snippet_goes_back_with_only_the_desired_fields_changed(self):
        api = FakeApi()
        code, out = self.run_cli(api, "metadata", "--video-id", VIDEO, "--desired",
                                 self.desired({"title": "New title", "tags": ["x"]}), *IDS)
        self.assertEqual(code, 0, out)
        put = next(c for c in api.calls if c["method"] == "PUT")
        sent = json.loads(put["body"])
        self.assertEqual(sent["id"], VIDEO)
        sn = sent["snippet"]
        self.assertEqual((sn["title"], sn["tags"], sn["description"], sn["categoryId"]),
                         ("New title", ["x"], "old", "10"))
        self.assertNotIn("publishedAt", sn)
        self.assertIn("part=snippet", put["url"])
        self.assertEqual(out["key"].split(":")[:3], ["metadata", "video", VIDEO])
        self.assertEqual(self.intent_calls(), ["claim-intent", "commit-intent"])
        self.assertEqual(out["units_used"], 1 + 50 + 1)

    def test_nothing_differs_means_no_claim(self):
        api = FakeApi()
        code, out = self.run_cli(api, "metadata", "--video-id", VIDEO, "--desired",
                                 self.desired({"title": "Old title"}), *IDS)
        self.assertEqual((code, out["changed"]), (0, False))
        self.assertEqual(self.intent_calls(), [])

    def test_dry_run_prints_the_diff_and_claims_nothing(self):
        api = FakeApi()
        code, out = self.run_cli(api, "metadata", "--video-id", VIDEO, "--desired",
                                 self.desired({"description": "new"}), "--dry-run", *IDS)
        self.assertEqual(code, 0)
        self.assertEqual(out["diff"], [{"field": "description", "from": "old", "to": "new"}])
        self.assertEqual(api.names(), [("GET", "videos")])

    def test_a_lagging_re_read_is_waited_out(self):
        api = FakeApi(lag=1)
        code, out = self.run_cli(api, "metadata", "--video-id", VIDEO, "--desired",
                                 self.desired({"title": "New"}), *IDS)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.slept, [ac.REREAD_WAITS[0]])

    def test_a_re_read_that_never_shows_it_leaves_the_claim_open(self):
        api = FakeApi(apply_update=False)
        code, out = self.run_cli(api, "metadata", "--video-id", VIDEO, "--desired",
                                 self.desired({"title": "New"}), *IDS)
        self.assertEqual(code, 2)
        self.assertTrue(out["uncertain"])
        self.assertEqual(self.intent_calls(), ["claim-intent"])

    def test_a_4xx_fails_the_intent_and_a_missing_scope_points_at_studio(self):
        api = FakeApi()
        real = api.__call__

        def refuse_put(method, url, headers, body):
            if method == "PUT":
                api.calls.append({"method": method, "name": "videos"})
                return 403, json.dumps({"error": {"errors": [{"reason": "insufficientPermissions"}],
                                                  "message": "scope"}}).encode()
            return real(method, url, headers, body)
        code, out = self.run_cli(refuse_put, "metadata", "--video-id", VIDEO, "--desired",
                                 self.desired({"title": "New"}), *IDS)
        self.assertEqual(code, 2)
        self.assertEqual(out["intent"], "failed")
        self.assertEqual(out["fallback"], "studio")

    def test_a_second_run_after_commit_skips(self):
        api = FakeApi()
        path = self.desired({"title": "New"})
        self.run_cli(api, "metadata", "--video-id", VIDEO, "--desired", path, *IDS)
        api.snippet["title"] = "Changed by hand"
        code, out = self.run_cli(api, "metadata", "--video-id", VIDEO, "--desired", path, *IDS)
        self.assertFalse(out["acted"])
        self.assertEqual(self.intent_calls().count("commit-intent"), 1)

    def test_a_desired_state_is_checked_before_any_call(self):
        for bad in ({"categoryId": "22"}, {"title": " "}, {"tags": "a,b"}, {}, {"tags": ["ok", ""]}):
            api = FakeApi()
            code, out = self.run_cli(api, "metadata", "--video-id", VIDEO, "--desired", self.desired(bad), *IDS)
            self.assertEqual(code, 2, bad)
            self.assertEqual(api.calls, [], bad)

    def test_a_bad_video_id_is_refused(self):
        code, out = self.run_cli(FakeApi(), "metadata", "--video-id", "nope", "--desired",
                                 self.desired({"title": "x"}), *IDS)
        self.assertEqual(code, 2)


class Thumbnail(Base):
    def file(self, name, data):
        p = self.tmp / name
        p.write_bytes(data)
        return str(p)

    def test_a_thumbnail_is_uploaded_for_the_video_under_an_intent(self):
        api = FakeApi()
        image = self.file("t.png", png(1280, 720))
        code, out = self.run_cli(api, "thumbnail", "--video-id", VIDEO, "--image", image, *IDS)
        self.assertEqual(code, 0, out)
        up = api.calls[-1]
        self.assertTrue(up["url"].startswith("https://www.googleapis.com/upload/youtube/v3/thumbnails/set"))
        self.assertIn(f"videoId={VIDEO}", up["url"])
        self.assertEqual(up["headers"]["Content-Type"], "image/png")
        self.assertEqual(out["key"].split(":")[:3], ["thumbnail", "video", VIDEO])
        self.assertEqual(self.intent_calls(), ["claim-intent", "commit-intent"])

    def test_a_narrow_image_is_refused_before_any_claim(self):
        api = FakeApi()
        code, out = self.run_cli(api, "thumbnail", "--video-id", VIDEO, "--image",
                                 self.file("t.png", png(320, 180)), *IDS)
        self.assertEqual(code, 2)
        self.assertEqual((api.calls, self.intent_calls()), ([], []))

    def test_the_same_image_twice_is_one_action(self):
        api = FakeApi()
        image = self.file("t.png", png(1280, 720))
        self.run_cli(api, "thumbnail", "--video-id", VIDEO, "--image", image, *IDS)
        code, out = self.run_cli(api, "thumbnail", "--video-id", VIDEO, "--image", image, *IDS)
        self.assertFalse(out["acted"])
        self.assertEqual([c["name"] for c in api.calls].count("thumbnails/set"), 1)


if __name__ == "__main__":
    unittest.main()
