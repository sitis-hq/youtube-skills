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
import records  # noqa: E402

VIDEO = "dQw4w9WgXcQ"
CHANNEL = "UC" + "a" * 22


def run(*argv: str) -> tuple[int, dict]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = records.main(list(argv))
    return code, json.loads(buf.getvalue())


class Keys(unittest.TestCase):
    def test_a_reader_builds_the_key_from_the_key_fields_alone(self):
        self.assertEqual(run("key", "seed", "--term", "Sad Phonk 2026!")[1], {"key": "seed:sad-phonk-2026"})
        self.assertEqual(run("key", "plan", "--date", "2026-11-10", "--slot", "short-1")[1],
                         {"key": "plan:2026-11-10:short-1"})

    def test_a_key_without_its_field_names_the_flag(self):
        code, out = run("key", "plan", "--date", "2026-11-10")
        self.assertEqual(code, 2)
        self.assertIn("--slot", out["error"])

    def test_two_slots_of_one_day_are_two_records(self):
        a = records.build("plan", dict(date="2026-11-10", slot="main", title="A", format="long",
                                       status="planned", source="planning"))[0]
        b = records.build("plan", dict(date="2026-11-10", slot="short-1", title="B", format="short",
                                       status="planned", source="planning"))[0]
        self.assertNotEqual(a, b)


class Refusals(unittest.TestCase):
    def check(self, kind, **fields):
        with self.assertRaises(records.Refusal) as ctx:
            records.build(kind, fields)
        return str(ctx.exception)

    def test_a_percentage_is_not_taken_for_a_fraction(self):
        msg = self.check("studio", video_id=VIDEO, as_of="2026-11-04", available="true",
                         impressions="1000", ctr="4.5", source="reporting-api")
        self.assertIn("ctr", msg)

    def test_no_data_is_recorded_without_numbers(self):
        _, data = records.build("studio", dict(video_id=VIDEO, as_of="2026-11-04", available="false",
                                               source="studio-export"))
        self.assertFalse(data["available"])
        self.assertIn("must not carry", self.check("studio", video_id=VIDEO, as_of="2026-11-04",
                                                   available="false", ctr="0.04", source="studio-export"))

    def test_available_data_carries_both_numbers(self):
        self.assertIn("needs both", self.check("studio", video_id=VIDEO, as_of="2026-11-04",
                                               available="true", ctr="0.04", source="reporting-api"))

    def test_an_unknown_field_is_refused_rather_than_stored(self):
        self.assertIn("no field", self.check("velocity", video_id=VIDEO, as_of="2026-11-04",
                                             views_per_day="10", anomaly="none", source="data-api",
                                             trend="up"))

    def test_an_anomaly_is_a_closed_set(self):
        self.assertIn("one of", self.check("velocity", video_id=VIDEO, as_of="2026-11-04",
                                           views_per_day="10", anomaly="big jump", source="data-api"))

    def test_keyword_difficulty_stays_on_its_own_scale(self):
        _, data = records.build("seed", dict(term="lofi", source="dataforseo", as_of="2026-11-04", kd_web="37"))
        self.assertEqual(data["kd_web"], 37)
        # The old contract stored 0..1; such a value is refused, not read as 0 % difficulty.
        self.assertIn("whole number", self.check("seed", term="lofi", source="dataforseo", as_of="2026-11-04",
                                                 kd_web="0.37"))
        self.assertIn("0..100", self.check("seed", term="lofi", source="dataforseo", as_of="2026-11-04",
                                           kd_web="150"))

    def test_an_idea_carries_keyword_hook_and_thumbnail(self):
        self.assertIn("hook", self.check("idea", title="X", keyword="k", thumbnail="t", format="long",
                                         status="new", source="owner"))

    def test_a_reply_names_its_own_id(self):
        self.assertIn("reply_id", self.check("replied", comment_id="UgxAAAAAAAAAAAA", video_id=VIDEO,
                                             action="reply", at="2026-11-04T10:00:00Z", source="community"))

    def test_a_reply_comment_id_has_a_parent(self):
        _, data = records.build("replied", dict(comment_id="UgxAAAAAAAAAAAA.9zBBBBBBBBBBB", video_id=VIDEO,
                                                action="pin", at="2026-11-04T10:00:00Z", source="community"))
        self.assertEqual(data["comment_id"], "UgxAAAAAAAAAAAA.9zBBBBBBBBBBB")

    def test_a_time_without_a_zone_is_refused(self):
        self.assertIn("time zone", self.check("publish", video_id=VIDEO, published_at="2026-11-04T10:00:00",
                                              format="long", title="T", source="release"))


class StoredRecords(unittest.TestCase):
    def test_a_record_read_back_is_checked_against_its_key(self):
        key, data = records.build("watch", dict(video_id=VIDEO, channel_id=CHANNEL, source="search"))
        self.assertEqual(records.validate_stored(key, data), "watch")
        with self.assertRaises(records.Refusal):
            records.validate_stored("watch:aaaaaaaaaaa", data)

    def test_another_schema_version_is_named(self):
        key, data = records.build("watch", dict(video_id=VIDEO, channel_id=CHANNEL, source="search"))
        data["v"] = 0
        with self.assertRaises(records.Refusal) as ctx:
            records.validate_stored(key, data)
        self.assertIn("schema version", str(ctx.exception))

    def test_the_schema_lists_every_kind_with_its_writer(self):
        out = records.schema()
        self.assertEqual(set(out["kinds"]), set(records.KINDS))
        for k in out["kinds"].values():
            self.assertTrue(k["writer"])


class Writing(unittest.TestCase):
    """`write` hands the record to ai-integration; a stand-in binary records what it was given."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        d = Path(self.dir.name)
        self.log = d / "call.json"
        stub = d / "ai-integration"
        stub.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "a = sys.argv[1:]\n"
            "data = json.load(open(a[a.index('--data-file') + 1]))\n"
            f"json.dump({{'argv': a, 'data': data}}, open({str(self.log)!r}, 'w'))\n"
            "print(json.dumps({'success': True}))\n"
        )
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        os.environ["AI_INTEGRATION_BIN"] = str(stub)
        self.cwd = os.getcwd()
        os.chdir(d)

    def tearDown(self):
        os.chdir(self.cwd)
        os.environ.pop("AI_INTEGRATION_BIN", None)
        self.dir.cleanup()

    def test_the_ids_come_from_current_task_when_not_given(self):
        Path("current-task.md").write_text(
            "# Step\n\nProcess id (for durable memory records): `11111111-1111-4111-8111-111111111111`\n"
            "Spec id (this run's instance, pass as `--spec-id` to memory write verbs): "
            "`22222222-2222-4222-8222-222222222222`\n"
        )
        code, out = run("write", "velocity", "--video-id", VIDEO, "--as-of", "2026-11-04",
                        "--views-per-day", "12.5", "--anomaly", "spike", "--source", "data-api")
        self.assertEqual(code, 0, out)
        call = json.loads(self.log.read_text())
        argv = call["argv"]
        self.assertEqual(argv[argv.index("--key") + 1], f"velocity:{VIDEO}")
        self.assertEqual(argv[argv.index("--spec-id") + 1], "22222222-2222-4222-8222-222222222222")
        self.assertEqual(call["data"]["anomaly"], "spike")
        self.assertEqual(call["data"]["v"], 1)

    def test_without_ids_nothing_is_written(self):
        code, out = run("write", "velocity", "--video-id", VIDEO, "--as-of", "2026-11-04",
                        "--views-per-day", "1", "--anomaly", "none", "--source", "data-api")
        self.assertEqual(code, 2)
        self.assertIn("--spec-template-id", out["error"])
        self.assertFalse(self.log.exists())

    def test_an_invalid_record_never_reaches_the_platform(self):
        code, _ = run("write", "velocity", "--video-id", "short", "--as-of", "2026-11-04",
                      "--views-per-day", "1", "--anomaly", "none", "--source", "data-api",
                      "--spec-template-id", "11111111-1111-4111-8111-111111111111",
                      "--spec-id", "22222222-2222-4222-8222-222222222222")
        self.assertEqual(code, 2)
        self.assertFalse(self.log.exists())

    def test_identity_tokens_repeat(self):
        code, out = run("check", "profile", "--channel-id", CHANNEL, "--title", "Dustin Vane",
                        "--language", "en", "--niche", "dark pop", "--channel-type", "music-artist",
                        "--identity-token", "Dustin Vane", "--identity-token", "Neon Hearts")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["data"]["identity_token"], ["Dustin Vane", "Neon Hearts"])


if __name__ == "__main__":
    unittest.main()
