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
                                       time="15:00", status="planned", source="planning"))[0]
        b = records.build("plan", dict(date="2026-11-10", slot="short-1", title="B", format="short",
                                       time="19:00", status="planned", source="planning"))[0]
        self.assertNotEqual(a, b)


SPEC = "11111111-1111-4111-8111-111111111111"
SONG_A = {"release": "22222222-2222-4222-8222-222222222222", "title": "Up the Will", "duration": 284.633,
          "video_id": VIDEO}
SONG_B = {"release": "33333333-3333-4333-8333-333333333333", "title": "Green as the Pines", "duration": 184.383,
          "video_id": "Zx9Yw8Vu7Ts"}


class Mix(unittest.TestCase):
    def mix(self, **change):
        fields = dict(spec=SPEC, theme="late-night r&b", status="listed", songs=[SONG_A, SONG_B],
                      listed_at="2026-11-25T20:00:00Z", source="Create Music Release Mix")
        fields.update(change)
        return records.build("mix", {k: v for k, v in fields.items() if v is not None})

    def test_a_mix_keeps_its_songs_in_order(self):
        key, data = self.mix()
        self.assertEqual(key, f"mix:{SPEC}")
        self.assertEqual([s["title"] for s in data["songs"]], ["Up the Will", "Green as the Pines"])

    def test_the_whole_list_can_be_set_at_once(self):
        _, data = self.mix(songs=json.dumps([SONG_B, SONG_A]))
        self.assertEqual(data["songs"][0]["title"], "Green as the Pines")

    def test_the_command_line_takes_the_list_as_one_json_flag_or_one_flag_per_song(self):
        base = ["check", "mix", "--spec", SPEC, "--theme", "t", "--status", "listed",
                "--listed-at", "2026-11-25T20:00:00Z", "--source", "Create Music Release Mix"]
        code, out = run(*base, "--songs", json.dumps([SONG_A, SONG_B]))
        self.assertEqual(code, 0, out)
        code, out = run(*base, "--songs", json.dumps(SONG_A), "--songs", json.dumps(SONG_B))
        self.assertEqual(code, 0, out)

    def test_a_mix_needs_two_different_songs_and_a_published_one_its_video(self):
        for change, word in (({"songs": [SONG_A]}, "two songs"), ({"songs": [SONG_A, SONG_A]}, "twice"),
                             ({"status": "published"}, "video_id")):
            with self.assertRaises(records.Refusal) as ctx:
                self.mix(**change)
            self.assertIn(word, str(ctx.exception))

    def test_a_song_carries_exactly_its_four_fields(self):
        with self.assertRaises(records.Refusal):
            self.mix(songs=[{**SONG_A, "bpm": 90}, SONG_B])

    def test_the_assembled_file_is_named_by_its_upload_key(self):
        _, data = self.mix(status="assembled", upload_key="upload:video:3c7ec80d4876")
        self.assertEqual(data["upload_key"], "upload:video:3c7ec80d4876")
        with self.assertRaises(records.Refusal):
            self.mix(upload_key="upload:video:XYZ")

    def test_an_upload_session_is_an_https_uri(self):
        _, data = self.mix(status="assembled", upload_session="https://www.googleapis.com/upload/youtube/v3/videos?upload_id=x")
        self.assertTrue(data["upload_session"].startswith("https://"))
        with self.assertRaises(records.Refusal):
            self.mix(upload_session="ftp://x")

    def test_a_stored_mix_validates_and_a_lookalike_key_is_foreign(self):
        key, data = self.mix()
        self.assertEqual(records.validate_stored(key, data), "mix")
        with self.assertRaises(records.Foreign):
            records.validate_stored("mix:old-theme", data)

    def test_a_plan_slot_carries_its_hour(self):
        with self.assertRaises(records.Refusal) as ctx:
            records.build("plan", dict(date="2026-11-10", slot="main", title="A", format="long",
                                       status="planned", source="planning"))
        self.assertIn("time", str(ctx.exception))


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

    def test_available_data_carries_impressions_and_ctr_only_with_a_settled_scale(self):
        self.assertIn("needs impressions", self.check("studio", video_id=VIDEO, as_of="2026-11-04",
                                                      available="true", ctr="0.04", source="reporting-api"))
        # Impressions alone: the Reporting file's CTR scale is not settled yet.
        _, data = records.build("studio", dict(video_id=VIDEO, as_of="2026-11-04", available="true",
                                               impressions="120", source="reporting-api"))
        self.assertNotIn("ctr", data)

    def test_an_unknown_field_is_refused_rather_than_stored(self):
        self.assertIn("no field", self.check("velocity", video_id=VIDEO, as_of="2026-11-04",
                                             views_per_day="10", anomaly="none", source="data-api",
                                             trend="up"))

    def test_an_anomaly_is_a_closed_set(self):
        self.assertIn("one of", self.check("velocity", video_id=VIDEO, as_of="2026-11-04",
                                           views_per_day="10", anomaly="big jump", source="data-api"))

    def test_keyword_difficulty_stays_on_its_own_scale(self):
        _, data = records.build("seed", dict(term="lofi", source="dataforseo", as_of="2026-11-04", kd_web="37", niche="lofi"))
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

    def test_two_actions_on_one_comment_are_two_records(self):
        base = dict(comment_id="UgxAAAAAAAAAAAA", video_id=VIDEO, at="2026-11-04T10:00:00Z", source="community")
        reply = records.build("replied", dict(base, action="reply", reply_id="UgxAAAAAAAAAAAA.9zCCCCCCCCCCC"))[0]
        pin = records.build("replied", dict(base, action="pin"))[0]
        self.assertEqual((reply, pin), ("replied:UgxAAAAAAAAAAAA:reply", "replied:UgxAAAAAAAAAAAA:pin"))

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
                        "--timezone", "America/Chicago",
                        "--identity-token", "Dustin Vane", "--identity-token", "Neon Hearts")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["data"]["identity_token"], ["Dustin Vane", "Neon Hearts"])


class ForeignKeys(unittest.TestCase):
    def test_another_recipes_state_under_the_prefix_is_foreign(self):
        with self.assertRaises(records.Foreign):
            records.validate_stored("publish:distrokid:city-alive", {"status": "published"})

    def test_foreign_comes_before_the_version_and_exits_3(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = records.main(["validate", "--key", "publish:distrokid:x", "--data", "{}"])
        self.assertEqual(code, 3)
        self.assertTrue(json.loads(buf.getvalue())["foreign"])

    def test_a_contract_key_with_another_version_still_stops(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = records.main(["validate", "--key", "publish:abcdefghijk", "--data", '{"v": 2}'])
        self.assertEqual(code, 2)
        self.assertNotIn("foreign", json.loads(buf.getvalue()))


class SeedNiche(unittest.TestCase):
    def test_a_seed_carries_its_niche(self):
        _, data = records.build("seed", dict(term="rnb", source="dataforseo", as_of="2026-11-24", niche="alternative rnb"))
        self.assertEqual(data["niche"], "alternative rnb")
        records.validate_stored("seed:rnb", data)

    def test_a_seed_without_niche_is_refused(self):
        with self.assertRaises(records.Refusal):
            records.build("seed", dict(term="rnb", source="dataforseo", as_of="2026-11-24"))


class TakeAndProduction(unittest.TestCase):
    def test_an_idea_is_taken_once_by_its_slug(self):
        key, data = records.build("take", dict(idea="shadow-on-the-wire", status="in-work",
                                               taken_at="2026-11-24T22:00:00Z", source="Create Music Release"))
        self.assertEqual(key, "take:shadow-on-the-wire")
        records.validate_stored(key, data)

    def test_a_take_names_a_plan_only_by_its_full_key(self):
        with self.assertRaises(records.Refusal):
            records.build("take", dict(idea="x", status="in-work", taken_at="2026-11-24T22:00:00Z",
                                       source="cmr", plan="2026-12-05:main"))

    def test_production_is_one_of_six(self):
        base = dict(title="a b", keyword="k", hook="h", thumbnail="t", format="long", status="new", source="trend")
        self.assertEqual(records.build("idea", {**base, "production": "cover"})[1]["production"], "cover")
        with self.assertRaises(records.Refusal):
            records.build("idea", {**base, "production": "song"})


class ProfileTimezone(unittest.TestCase):
    BASE = dict(channel_id="UC" + "a" * 22, title="T", language="en", niche="n", channel_type="music-artist")

    def test_a_profile_needs_an_iana_zone(self):
        with self.assertRaises(records.Refusal):
            records.build("profile", dict(self.BASE))
        with self.assertRaises(records.Refusal):
            records.build("profile", {**self.BASE, "timezone": "ET"})
        with self.assertRaises(records.Refusal):
            records.build("profile", {**self.BASE, "timezone": "UTC"})
        self.assertEqual(records.build("profile", {**self.BASE, "timezone": "America/New_York"})[1]["timezone"],
                         "America/New_York")


STORE_STUB = r"""#!/usr/bin/env python3
import json, sys, os
a = sys.argv[1:]
store_path = os.environ["STUB_STORE"]
store = json.load(open(store_path)) if os.path.exists(store_path) else {}
def arg(n):
    return a[a.index(n) + 1] if n in a else None
if a[0] == "get-template-record":
    rec = store.get(arg("--key"))
    print(json.dumps({"success": True, "data": rec}))
    sys.exit(0)
key = arg("--key")
data = json.load(open(arg("--data-file")))
cur = store.get(key)
if "--if-absent" in a and cur is not None:
    print(json.dumps({"success": False, "error": {"type": "ConflictError", "message": "exists"}, "data": cur}))
    sys.exit(2)
if "--if-updated-at" in a and (cur is None or cur["updatedAt"] != arg("--if-updated-at")):
    print(json.dumps({"success": False, "error": {"type": "ConflictError", "message": "changed"}, "data": cur}))
    sys.exit(2)
n = int(cur["updatedAt"]) + 1 if cur else 1
store[key] = {"key": key, "data": data, "updatedAt": str(n)}
json.dump(store, open(store_path, "w"))
print(json.dumps({"success": True, "data": store[key]}))
"""

SPEC = "01a1827d-e3b1-7546-8c23-4a6252cdbe45"
TASK = ("Process id: `11111111-1111-4111-8111-111111111111`\n"
        "Spec id: `22222222-2222-4222-8222-222222222222`\n"
        "Project id: `33333333-3333-4333-8333-333333333333`\n")


class ConditionalWrites(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        d = Path(self.dir.name)
        stub = d / "ai-integration"
        stub.write_text(STORE_STUB)
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        os.environ["AI_INTEGRATION_BIN"] = str(stub)
        os.environ["STUB_STORE"] = str(d / "store.json")
        self.cwd = os.getcwd()
        os.chdir(d)
        Path("current-task.md").write_text(TASK)

    def tearDown(self):
        os.chdir(self.cwd)
        os.environ.pop("AI_INTEGRATION_BIN", None)
        os.environ.pop("STUB_STORE", None)
        self.dir.cleanup()

    def write_release(self, *extra):
        return run("write", "release", "--spec", SPEC, "--date", "2026-12-05", "--time", "10:00",
                   "--title", "Later Won't Wait", "--pitch-ok", "false", "--status", "held",
                   "--held-at", "2026-11-25T15:00:00Z", "--source", "Create Music Release", *extra)

    def test_if_absent_refuses_a_second_release_record_with_exit_4(self):
        self.assertEqual(self.write_release("--if-absent")[0], 0)
        code, out = self.write_release("--if-absent")
        self.assertEqual(code, 4)
        self.assertTrue(out["conflict"])
        self.assertEqual(out["current"]["data"]["date"], "2026-12-05")

    def test_update_moves_the_date_and_keeps_the_key(self):
        self.write_release("--if-absent")
        code, out = run("update", "--key", f"release:{SPEC}", "--set", "date=2026-12-12",
                        "--append", "moves=2026-12-05>2026-12-12")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["data"]["date"], "2026-12-12")
        self.assertEqual(out["data"]["moves"][0]["to"], "2026-12-12")

    def test_the_approved_pitch_is_set_on_a_release_the_owner_allowed(self):
        self.write_release("--if-absent")
        code, out = run("update", "--key", f"release:{SPEC}", "--set", "pitch_ok=true",
                        "--set", "pitch=A late-night drive through a city that forgot you.")
        self.assertEqual(code, 0, out)
        self.assertTrue(out["data"]["pitch_ok"])

    def test_a_pitch_on_a_release_the_owner_did_not_allow_is_refused(self):
        self.write_release("--if-absent")
        code, out = run("update", "--key", f"release:{SPEC}", "--set", "pitch=Some text.")
        self.assertEqual(code, 2, out)
        self.assertIn("pitch_ok", out["error"])

    def test_update_cannot_change_a_key_field(self):
        self.write_release("--if-absent")
        code, out = run("update", "--key", f"release:{SPEC}", "--set", "spec=22222222-2222-4222-8222-222222222222")
        self.assertEqual(code, 2)


class ReleaseState(unittest.TestCase):
    R = {"spec": SPEC, "date": "2026-12-05", "status": "committed"}

    def test_released_needs_its_date_and_a_publish_naming_it(self):
        self.assertEqual(records.release_state(self.R, [], "2026-12-06"), "active")
        self.assertEqual(records.release_state(self.R, [{"release": SPEC}], "2026-12-06"), "released")
        self.assertEqual(records.release_state(self.R, [{"release": SPEC}], "2026-12-04"), "active")

    def test_a_held_release_long_past_its_date_counts_as_dropped(self):
        held = {**self.R, "status": "held"}
        self.assertEqual(records.release_state(held, [], "2026-12-19"), "active")
        self.assertEqual(records.release_state(held, [], "2026-12-20"), "dropped")
        self.assertEqual(records.release_state({**self.R}, [], "2027-02-01"), "active")


class Pitch(unittest.TestCase):
    """The pitch fields and the 3-week slot (CONTRACT.md, rule 17).

    Why these cases. The slot is the one guarantee that two pitches are never closer than 21 days,
    and it is easy to get wrong in two quiet ways: comparing instants pushes the slot past the
    schedule's fire hour, and placing a UTC moment in the wrong day moves it by one.
    """

    RELEASE = {"spec": SPEC, "date": "2026-12-26", "time": "10:00", "title": "City Alive",
               "pitch_ok": "true", "status": "committed", "held_at": "2026-11-25T15:00:00Z",
               "source": "Create Music Release"}

    def test_a_pitch_over_500_characters_is_refused(self):
        with self.assertRaises(records.Refusal):
            records.build("release", {**self.RELEASE, "pitch": "x" * 501})
        records.build("release", {**self.RELEASE, "pitch": "x" * 500})

    def test_a_pitched_record_is_keyed_by_its_release(self):
        key, data = records.build("pitched", {
            "spec": SPEC, "title": "City Alive", "date": "2026-11-28",
            "album_id": "6UkqasjKwgTtnyekAWQSXU", "status": "pitched",
            "pitched_at": "2026-11-23T11:19:02Z", "source": "Pitch a Song on Spotify"})
        self.assertEqual(key, f"pitched:{SPEC}")

    def test_the_slot_opens_on_the_21st_day_by_the_channels_calendar(self):
        at = ["2026-11-23T11:19:02Z"]
        closed = records.pitch_slot(at, "America/New_York", "2026-12-13")
        self.assertEqual((closed["open"], closed["opens_on"]), (False, "2026-12-14"))
        # The fire at 09:00 UTC on the 21st day comes before the hour of the last pitch: still open.
        self.assertTrue(records.pitch_slot(at, "America/New_York", "2026-12-14")["open"])

    def test_a_moment_is_placed_in_the_channels_day_not_utcs(self):
        # 03:00 UTC on the 24th is the evening of the 23rd in New York.
        slot = records.pitch_slot(["2026-11-24T03:00:00Z"], "America/New_York", "2026-12-14")
        self.assertEqual(slot["last"], "2026-11-23")

    def test_the_latest_pitch_counts_and_none_means_open(self):
        slot = records.pitch_slot(["2026-10-26T12:44:12Z", "2026-11-23T11:19:02Z"], "America/New_York", "2026-11-26")
        self.assertEqual(slot["last"], "2026-11-23")
        self.assertEqual(records.pitch_slot([], "America/New_York", "2026-11-26"),
                         {"open": True, "last": None, "opens_on": None})

    def test_the_command_line_answers_the_same(self):
        code, out = run("pitch-slot", "--at", "2026-11-23T11:19:02Z", "--zone", "America/New_York",
                        "--today", "2026-12-14")
        self.assertEqual(code, 0, out)
        self.assertTrue(out["open"])
        code, out = run("pitch-slot", "--at", "2026-11-23T11:19:02", "--zone", "America/New_York")
        self.assertEqual(code, 2, out)


if __name__ == "__main__":
    unittest.main()
