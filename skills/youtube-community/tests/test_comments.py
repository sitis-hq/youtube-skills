import io
import json
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "youtube-records" / "scripts"))
import comments  # noqa: E402
import records  # noqa: E402

CHANNEL = "UC" + "c" * 22
VIEWER = "UC" + "v" * 22
VIDEO = "dQw4w9WgXcQ"
IDS = ["--spec-template-id", "11111111-1111-4111-8111-111111111111",
       "--project-id", "33333333-3333-4333-8333-333333333333"]
TOKEN = "ya29.secret-token-never-printed"

# The intent half of ai-integration (migration 068 semantics), as in youtube-studio's tests.
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


def comment(cid, author, at, text="hi", video=VIDEO):
    return {"id": cid, "snippet": {"authorDisplayName": "x", "authorChannelId": {"value": author},
                                   "textOriginal": text, "publishedAt": at, "likeCount": 0, "videoId": video}}


def thread(cid, author, at, replies=(), total=None, video=VIDEO):
    return {"id": cid, "snippet": {"videoId": video, "topLevelComment": comment(cid, author, at, video=video),
                                   "totalReplyCount": len(replies) if total is None else total},
            "replies": {"comments": list(replies)}}


class FakeApi:
    """Stands in for the Data API: answers by endpoint and records what was asked."""

    def __init__(self, pages=None, insert=None, error=None):
        self.pages = list(pages or [])
        self.insert = insert or {"id": "Ugx1111111111.9z2222222222"}
        self.error = error
        self.calls = []

    def __call__(self, method, endpoint, params, body, token):
        self.calls.append({"method": method, "endpoint": endpoint, "params": params, "body": body, "token": token})
        if self.error:
            raise self.error
        if endpoint == "commentThreads":
            return self.pages.pop(0) if self.pages else {"items": []}
        if endpoint == "comments" and method == "POST":
            return self.insert
        return {}


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        stub = Path(self.dir.name) / "ai-integration"
        stub.write_text(STUB)
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        self.stub = stub
        os.environ["AI_INTEGRATION_BIN"] = str(stub)
        self.saved = (comments.http, comments.access_token)
        comments.access_token = lambda connection: TOKEN

    def tearDown(self):
        comments.http, comments.access_token = self.saved
        os.environ.pop("AI_INTEGRATION_BIN", None)
        self.dir.cleanup()

    def run_cli(self, api, *argv):
        comments.http = api
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = comments.main(list(argv))
        text = buf.getvalue()
        self.assertNotIn(TOKEN, text)
        return code, json.loads(text)

    def intent_calls(self):
        log = Path(str(self.stub) + ".log")
        return [json.loads(x)["verb"] for x in log.read_text().splitlines()] if log.exists() else []


class Fetch(Base):
    def test_handled_own_and_already_answered_threads_are_dropped(self):
        page = {"items": [
            thread("UgxNEWNEWNEW01", VIEWER, "2026-11-04T09:00:00Z"),
            thread("UgxHANDLED0001", VIEWER, "2026-11-04T08:00:00Z"),
            thread("UgxOWNOWNOWN01", CHANNEL, "2026-11-04T07:00:00Z"),
            thread("UgxBYHAND00001", VIEWER, "2026-11-04T06:00:00Z",
                   replies=[comment("UgxBYHAND00001.9zREPLY00001", CHANNEL, "2026-11-04T06:30:00Z")]),
        ]}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(["replied:UgxHANDLED0001:hide"], fh)
        code, out = self.run_cli(FakeApi([page]), "fetch", "--channel-id", CHANNEL, "--since", "2026-11-04",
                                 "--handled-file", fh.name)
        os.unlink(fh.name)
        self.assertEqual(code, 0, out)
        self.assertEqual([i["comment_id"] for i in out["items"]], ["UgxNEWNEWNEW01"])
        self.assertEqual(out["dropped"], {"handled": 1, "own": 1, "answered_by_channel": 1})

    def test_a_follow_up_after_the_channels_reply_is_surfaced(self):
        page = {"items": [thread("UgxTHREAD00001", VIEWER, "2026-11-04T06:00:00Z", replies=[
            comment("UgxTHREAD00001.9zOLDVIEW0001", VIEWER, "2026-11-04T06:10:00Z"),
            comment("UgxTHREAD00001.9zCHANNEL0001", CHANNEL, "2026-11-04T06:20:00Z"),
            comment("UgxTHREAD00001.9zFOLLOWUP001", VIEWER, "2026-11-04T06:30:00Z"),
        ])]}
        _, out = self.run_cli(FakeApi([page]), "fetch", "--channel-id", CHANNEL, "--since", "2026-11-04")
        (item,) = out["items"]
        self.assertEqual(item["comment_id"], "UgxTHREAD00001.9zFOLLOWUP001")
        self.assertEqual(item["parent_id"], "UgxTHREAD00001")
        self.assertTrue(item["is_reply"])

    def test_reading_stops_at_the_since_day(self):
        api = FakeApi([{"items": [thread("UgxNEWNEWNEW01", VIEWER, "2026-11-04T09:00:00Z"),
                                  thread("UgxOLDOLDOLD01", VIEWER, "2026-11-02T09:00:00Z")],
                        "nextPageToken": "p2"},
                       {"items": [thread("UgxOLDEROLDER1", VIEWER, "2026-11-01T09:00:00Z")]}])
        _, out = self.run_cli(api, "fetch", "--channel-id", CHANNEL, "--since", "2026-11-03")
        self.assertEqual([i["comment_id"] for i in out["items"]], ["UgxNEWNEWNEW01"])
        self.assertEqual(len(api.calls), 1)
        self.assertEqual(out["units_used"], 1)
        self.assertEqual(api.calls[0]["params"]["allThreadsRelatedToChannelId"], CHANNEL)
        self.assertEqual(api.calls[0]["params"]["order"], "time")

    def test_the_page_budget_is_kept_and_said(self):
        pages = [{"items": [thread(f"UgxPAGE{n}0000001", VIEWER, "2026-11-04T09:00:00Z")], "nextPageToken": "n"}
                 for n in range(5)]
        api = FakeApi(pages)
        _, out = self.run_cli(api, "fetch", "--channel-id", CHANNEL, "--since", "2026-11-01", "--max-pages", "2")
        self.assertTrue(out["truncated"])
        self.assertEqual(len(api.calls), 2)

    def test_held_comments_are_read_only_on_request(self):
        api = FakeApi([{"items": []}, {"items": []}, {"items": []}])
        self.run_cli(api, "fetch", "--channel-id", CHANNEL, "--since", "2026-11-01", "--include-held")
        self.assertEqual([c["params"]["moderationStatus"] for c in api.calls],
                         ["published", "heldForReview", "likelySpam"])

    def test_handled_keys_come_in_several_shapes(self):
        self.assertEqual(comments.handled_ids(["replied:UgxA0000000001", {"key": "replied:UgxB0000000001"},
                                               "UgxC0000000001"]),
                         {"UgxA0000000001", "UgxB0000000001", "UgxC0000000001"})


class Reply(Base):
    def setUp(self):
        super().setUp()
        self.text = Path(self.dir.name) / "reply.txt"
        self.text.write_text("Thanks — the full version is out Friday.\n", encoding="utf-8")

    def reply(self, api, cid="UgxTHREAD00001.9zFOLLOWUP001"):
        return self.run_cli(api, "reply", "--comment-id", cid, "--video-id", VIDEO,
                            "--text-file", str(self.text), *IDS)

    def test_a_reply_is_claimed_posted_committed_and_recordable(self):
        api = FakeApi()
        code, out = self.reply(api)
        self.assertEqual(code, 0, out)
        post = [c for c in api.calls if c["method"] == "POST"][0]
        # A reply to a reply lands in the top-level thread: YouTube nests one level only.
        self.assertEqual(post["body"]["snippet"]["parentId"], "UgxTHREAD00001")
        self.assertEqual(self.intent_calls(), ["claim-intent", "commit-intent"])
        self.assertEqual(out["units_used"], 50)
        key, _ = records.build("replied", out["record"])
        self.assertEqual(key, "replied:UgxTHREAD00001.9zFOLLOWUP001:reply")

    def test_a_second_run_does_not_reply_again(self):
        self.reply(FakeApi())
        api = FakeApi()
        code, out = self.reply(api)
        self.assertEqual(code, 0)
        self.assertFalse(out["acted"])
        self.assertEqual(api.calls, [])
        self.assertEqual(out["claim"]["result"]["reply_id"], "Ugx1111111111.9z2222222222")

    def test_a_missing_scope_fails_the_claim_and_points_to_studio(self):
        api = FakeApi(error=comments.ApiError(403, "insufficientPermissions", "Request had insufficient scopes"))
        code, out = self.reply(api)
        self.assertEqual(code, 2)
        self.assertEqual(out["fallback"], "studio")
        self.assertEqual(self.intent_calls(), ["claim-intent", "fail-intent"])

    def test_an_unknown_outcome_leaves_the_claim_in_flight(self):
        api = FakeApi(error=comments.ApiError(None, "network", "timed out"))
        code, out = self.reply(api)
        self.assertEqual(code, 2)
        self.assertTrue(out["uncertain"])
        self.assertEqual(self.intent_calls(), ["claim-intent"])
        _, again = self.reply(FakeApi())
        self.assertFalse(again["acted"])

    def test_a_server_error_is_not_taken_for_a_refusal(self):
        api = FakeApi(error=comments.ApiError(503, "backendError", "try later"))
        _, out = self.reply(api)
        self.assertTrue(out["uncertain"])
        self.assertNotIn("fail-intent", self.intent_calls())

    def test_an_empty_reply_is_refused_before_claiming(self):
        self.text.write_text("  \n")
        code, out = self.reply(FakeApi())
        self.assertEqual(code, 2)
        self.assertEqual(self.intent_calls(), [])


class Hide(Base):
    def test_a_hide_is_a_rejection_under_its_own_key(self):
        api = FakeApi()
        code, out = self.run_cli(api, "hide", "--comment-id", "UgxSPAMSPAM001", "--video-id", VIDEO, *IDS)
        self.assertEqual(code, 0, out)
        self.assertEqual(api.calls[0]["params"], {"id": "UgxSPAMSPAM001", "moderationStatus": "rejected"})
        self.assertNotIn("banAuthor", api.calls[0]["params"])
        self.assertEqual(out["key"], "hide:comment:UgxSPAMSPAM001")
        records.build("replied", out["record"])


if __name__ == "__main__":
    unittest.main()
