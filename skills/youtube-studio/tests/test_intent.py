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
import intent  # noqa: E402

TEMPLATE = "11111111-1111-4111-8111-111111111111"
PROJECT = "33333333-3333-4333-8333-333333333333"
IDS = ["--spec-template-id", TEMPLATE, "--project-id", PROJECT]

# A stand-in for ai-integration with the semantics of migration 068: a fresh claim inserts, a
# failed claim is re-claimed, anything else answers "exists"; commit/fail without a claim answer
# not_found. Every call is appended to a log the tests read.
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
entry = {"verb": verb, "argv": a}
if opt("--result-file"):
    entry["result"] = json.load(open(opt("--result-file")))
with open(log_path, "a") as fh:
    fh.write(json.dumps(entry) + "\n")
if state.get("broken"):
    print(json.dumps({"success": False, "command": verb, "error": {"type": "ServiceError", "message": "db down"}}))
    sys.exit(1)
key = opt("--intent-key")
rec = state.get(key)
if verb == "claim-intent":
    if rec is None or rec["status"] == "failed":
        state[key] = {"status": "claimed", "result": None, "reason": None}
        data = {"outcome": "fresh", "status": "claimed"}
    else:
        data = {"outcome": "exists", "status": rec["status"], "result": rec["result"], "reason": rec["reason"]}
elif rec is None:
    data = {"outcome": "not_found"}
elif verb == "commit-intent":
    rec.update(status="committed", result=entry.get("result"))
    data = {"outcome": "committed", "status": "committed"}
else:
    rec.update(status="failed", reason=opt("--reason"))
    data = {"outcome": "failed", "status": "failed"}
json.dump(state, open(state_path, "w"))
print(json.dumps({"success": True, "command": verb, "data": data}))
'''


def make_stub(directory: Path) -> Path:
    stub = directory / "ai-integration"
    stub.write_text(STUB)
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return stub


def run(*argv: str) -> tuple[int, dict]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = intent.main(list(argv))
    return code, json.loads(buf.getvalue())


class Keys(unittest.TestCase):
    def test_a_key_comes_from_the_intention(self):
        self.assertEqual(intent.build_key("pin", comment_id="UgxAAAAAAAAAAAA"), "pin:comment:UgxAAAAAAAAAAAA")
        self.assertEqual(intent.build_key("post", date="2026-11-04", title="New single: Neon Hearts!"),
                         "post:community:2026-11-04:new-single-neon-hearts")
        self.assertEqual(intent.build_key("ab", video_id="dQw4w9WgXcQ", date="2026-11-04"),
                         "ab:video:dQw4w9WgXcQ:2026-11-04")

    def test_a_reply_to_a_reply_has_its_own_key(self):
        self.assertEqual(intent.build_key("reply", comment_id="UgxAAAAAAAAAAAA.9zBBBBBBBBBBB"),
                         "reply:comment:UgxAAAAAAAAAAAA.9zBBBBBBBBBBB")

    def test_the_same_desired_state_is_the_same_intention(self):
        with tempfile.TemporaryDirectory() as d:
            a, b, c = Path(d, "a.json"), Path(d, "b.json"), Path(d, "c.json")
            a.write_text('{"country": "US", "keywords": "dark pop"}')
            b.write_text('{\n  "keywords": "dark pop",\n  "country": "US"\n}')
            c.write_text('{"country": "AR", "keywords": "dark pop"}')
            ka = intent.build_key("settings", area="channel", state_file=str(a))
            self.assertEqual(ka, intent.build_key("settings", area="channel", state_file=str(b)))
            self.assertNotEqual(ka, intent.build_key("settings", area="channel", state_file=str(c)))

    def test_an_image_is_keyed_by_content_not_name(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "banner.png").write_bytes(b"one")
            Path(d, "banner-copy.png").write_bytes(b"one")
            Path(d, "banner-v2.png").write_bytes(b"two")
            k = lambda f: intent.build_key("branding", part="banner", file=str(Path(d, f)))
            self.assertEqual(k("banner.png"), k("banner-copy.png"))
            self.assertNotEqual(k("banner.png"), k("banner-v2.png"))

    def test_a_watermark_is_keyed_by_its_image_and_its_timing(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "mark.png").write_bytes(b"mark")
            Path(d, "mark-copy.png").write_bytes(b"mark")
            k = lambda f, t: intent.build_key("watermark", file=str(Path(d, f)), timing=t)
            self.assertEqual(k("mark.png", "offsetFromEnd:15000"), k("mark-copy.png", "offsetFromEnd:15000"))
            # Retiming the same image is a new action; keyed by the image alone it was skipped as done.
            self.assertNotEqual(k("mark.png", "offsetFromEnd:15000"), k("mark.png", "offsetFromStart:0"))
            self.assertNotEqual(k("mark.png", "offsetFromEnd:15000"), k("mark.png", "offsetFromEnd:15000:5000"))
            self.assertRegex(k("mark.png", "offsetFromStart:0"), r"^branding:watermark:[0-9a-f]{12}$")

    def test_a_watermark_needs_a_timing_of_the_known_shape(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "mark.png").write_bytes(b"mark")
            with self.assertRaises(intent.Refusal):
                intent.build_key("watermark", file=str(Path(d, "mark.png")), timing="end")
            with self.assertRaises(intent.Refusal):
                intent.build_key("branding", part="watermark", file=str(Path(d, "mark.png")))

    def test_a_missing_part_names_its_flag(self):
        code, out = run("key", "ab", "--video-id", "dQw4w9WgXcQ", "--date", "2026-13-01")
        self.assertEqual(code, 2)
        self.assertIn("YYYY-MM-DD", out["error"])

    def test_every_built_key_passes_its_own_check(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d, "x.json")
            f.write_text("{}")
            for key in (intent.build_key("hide", comment_id="UgxAAAAAAAAAAAA"),
                        intent.build_key("thumbnail", video_id="dQw4w9WgXcQ", file=str(f)),
                        intent.build_key("metadata", video_id="dQw4w9WgXcQ", state_file=str(f)),
                        intent.build_key("settings", area="upload-defaults", state_file=str(f))):
                self.assertEqual(intent.check_key(key), key)


class Bracket(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.stub = make_stub(Path(self.dir.name))
        os.environ["AI_INTEGRATION_BIN"] = str(self.stub)
        self.cwd = os.getcwd()
        os.chdir(self.dir.name)

    def tearDown(self):
        os.chdir(self.cwd)
        os.environ.pop("AI_INTEGRATION_BIN", None)
        self.dir.cleanup()

    def calls(self) -> list[dict]:
        log = Path(str(self.stub) + ".log")
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def test_a_repeated_run_cannot_act_twice(self):
        key = "pin:comment:UgxAAAAAAAAAAAA"
        code, first = run("claim", "--key", key, *IDS)
        self.assertEqual(code, 0)
        self.assertTrue(first["act"])
        self.assertEqual(run("commit", "--key", key, "--result", '{"pinned": true}', *IDS)[0], 0)
        code, again = run("claim", "--key", key, *IDS)
        self.assertEqual(code, 0)
        self.assertFalse(again["act"])
        self.assertEqual(again["status"], "committed")
        self.assertEqual(again["result"], {"pinned": True})

    def test_an_unconfirmed_claim_is_not_retried(self):
        key = "post:community:2026-11-04:neon-hearts"
        run("claim", "--key", key, *IDS)
        code, again = run("claim", "--key", key, *IDS)
        self.assertFalse(again["act"])
        self.assertIn("may have happened", again["say"])

    def test_a_failed_action_may_be_tried_again(self):
        key = "ab:video:dQw4w9WgXcQ:2026-11-04"
        run("claim", "--key", key, *IDS)
        self.assertEqual(run("fail", "--key", key, "--reason", "A/B testing not offered", *IDS)[0], 0)
        self.assertTrue(run("claim", "--key", key, *IDS)[1]["act"])

    def test_the_result_travels_as_a_file(self):
        key = "reply:comment:UgxAAAAAAAAAAAA"
        run("claim", "--key", key, *IDS)
        run("commit", "--key", key, "--result", '{"reply_id": "UgxAAAAAAAAAAAA.9zBBBBBBBBBBB"}', *IDS)
        commit = [c for c in self.calls() if c["verb"] == "commit-intent"][0]
        self.assertIn("--result-file", commit["argv"])
        self.assertNotIn("--result", commit["argv"])
        self.assertEqual(commit["result"]["reply_id"], "UgxAAAAAAAAAAAA.9zBBBBBBBBBBB")

    def test_a_hand_made_key_never_reaches_the_platform(self):
        code, out = run("claim", "--key", "pin-UgxAAAAAAAAAAAA", *IDS)
        self.assertEqual(code, 2)
        self.assertIn("intent.py key", out["error"])
        self.assertEqual(self.calls(), [])

    def test_a_commit_without_a_claim_is_refused(self):
        code, out = run("commit", "--key", "hide:comment:UgxAAAAAAAAAAAA", *IDS)
        self.assertEqual(code, 2)
        self.assertIn("no claim", out["error"])

    def test_the_ids_come_from_current_task(self):
        Path("current-task.md").write_text(
            "# Step\n\nProject id (tenant, pass as `--project-id`): `33333333-3333-4333-8333-333333333333`\n"
            "Process id (for durable memory records): `11111111-1111-4111-8111-111111111111`\n")
        code, out = run("claim", "--key", "heart:comment:UgxAAAAAAAAAAAA")
        self.assertEqual(code, 0, out)
        argv = self.calls()[0]["argv"]
        self.assertEqual(argv[argv.index("--project-id") + 1], PROJECT)
        self.assertEqual(argv[argv.index("--spec-template-id") + 1], TEMPLATE)

    def test_without_ids_nothing_is_claimed(self):
        code, out = run("claim", "--key", "heart:comment:UgxAAAAAAAAAAAA")
        self.assertEqual(code, 2)
        self.assertIn("--project-id", out["error"])
        self.assertEqual(self.calls(), [])

    def test_a_platform_failure_is_a_refusal_not_a_go_ahead(self):
        Path(str(self.stub) + ".state").write_text('{"broken": true}')
        code, out = run("claim", "--key", "heart:comment:UgxAAAAAAAAAAAA", *IDS)
        self.assertEqual(code, 2)
        self.assertIn("db down", out["error"])


if __name__ == "__main__":
    unittest.main()
