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
import apply_channel  # noqa: E402

CHANNEL = "UC" + "c" * 22
IDS = ["--spec-template-id", "11111111-1111-4111-8111-111111111111",
       "--project-id", "33333333-3333-4333-8333-333333333333"]
TOKEN = "ya29.secret-token-never-printed"
BANNER_URL = "https://yt3.googleusercontent.com/banner-new"

# The intent half of ai-integration (migration 068 semantics), as in youtube-community's tests.
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
    """A PNG whose header says w x h; the parser reads only the header."""
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    chunk = struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr))
    return b"\x89PNG\r\n\x1a\n" + chunk + b"\x00" * pad


def jpeg(w, h):
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x00" * 9
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, h, w, 1) + b"\x01\x11\x00"
    return b"\xff\xd8" + app0 + sof + b"\xff\xd9"


class FakeApi:
    """Stands in for the Data API: keeps a channel's brandingSettings and answers by URL."""

    def __init__(self, branding=None, errors=None, apply_update=True, banner=None):
        self.branding = branding if branding is not None else {
            "channel": {"title": "Artist", "description": "old", "keywords": "music \"lo fi\"",
                        "trackingAnalyticsAccountId": "UA-1"},
            "image": {"bannerExternalUrl": "https://yt3.googleusercontent.com/banner-old"}}
        self.errors = dict(errors or {})  # endpoint name -> (status, reason)
        self.apply_update = apply_update
        self.banner = {"url": BANNER_URL} if banner is None else banner
        self.calls = []

    def __call__(self, method, url, headers, body):
        name = url.split("?")[0].rsplit("/v3/", 1)[1]
        self.calls.append({"method": method, "url": url, "name": name, "headers": headers, "body": body})
        if name in self.errors:
            status, reason = self.errors[name]
            if status is None:
                raise apply_channel.ApiError(None, "network", "connection reset")
            return status, json.dumps({"error": {"errors": [{"reason": reason}], "message": reason}}).encode()
        if name == "channels" and method == "GET":
            item = {"id": CHANNEL}
            if "brandingSettings" in url:
                item["brandingSettings"] = json.loads(json.dumps(self.branding))
            return 200, json.dumps({"items": [item]}).encode()
        if name == "channels" and method == "PUT":
            sent = json.loads(body)
            if self.apply_update:
                self.branding = sent["brandingSettings"]
            return 200, json.dumps(sent).encode()
        if name == "channelBanners/insert":
            return 200, json.dumps(self.banner).encode()
        if name == "watermarks/set":
            return 204, b""
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
        self.saved = (apply_channel.http, apply_channel.access_token)
        apply_channel.access_token = lambda connection: TOKEN

    def tearDown(self):
        apply_channel.http, apply_channel.access_token = self.saved
        os.environ.pop("AI_INTEGRATION_BIN", None)
        self.dir.cleanup()

    def run_cli(self, api, *argv):
        apply_channel.http = api
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = apply_channel.main(list(argv))
        text = buf.getvalue()
        self.assertNotIn(TOKEN, text)
        return code, json.loads(text)

    def desired(self, value):
        p = self.tmp / "desired.json"
        p.write_text(json.dumps(value))
        return str(p)

    def file(self, name, data):
        p = self.tmp / name
        p.write_bytes(data)
        return str(p)

    def intent_calls(self):
        log = Path(str(self.stub) + ".log")
        return [json.loads(x)["verb"] for x in log.read_text().splitlines()] if log.exists() else []


class Branding(Base):
    def test_nothing_differs_means_no_claim_and_no_write(self):
        api = FakeApi()
        # Keywords re-spaced by YouTube are the same list of terms.
        code, out = self.run_cli(api, "branding", "--desired",
                                 self.desired({"description": "old", "keywords": "music  \"lo fi\""}), *IDS)
        self.assertEqual(code, 0, out)
        self.assertEqual((out["ok"], out["changed"]), (True, False))
        self.assertEqual(api.names(), [("GET", "channels")])
        self.assertEqual(self.intent_calls(), [])
        self.assertEqual(out["units_used"], 1)

    def test_the_whole_part_goes_back_and_unrelated_fields_survive(self):
        api = FakeApi()
        code, out = self.run_cli(api, "branding", "--desired",
                                 self.desired({"description": "new About", "country": "AR"}), *IDS)
        self.assertEqual(code, 0, out)
        put = next(c for c in api.calls if c["method"] == "PUT")
        sent = json.loads(put["body"])
        self.assertEqual(sent["id"], CHANNEL)
        ch = sent["brandingSettings"]["channel"]
        self.assertEqual((ch["description"], ch["country"]), ("new About", "AR"))
        self.assertEqual((ch["title"], ch["trackingAnalyticsAccountId"], ch["keywords"]),
                         ("Artist", "UA-1", "music \"lo fi\""))
        self.assertEqual(sent["brandingSettings"]["image"]["bannerExternalUrl"],
                         "https://yt3.googleusercontent.com/banner-old")
        self.assertIn("part=brandingSettings", put["url"])
        self.assertEqual(self.intent_calls(), ["claim-intent", "commit-intent"])
        self.assertEqual({d["field"] for d in out["diff"]},
                         {"brandingSettings.channel.description", "brandingSettings.channel.country"})
        self.assertEqual(out["units_used"], 1 + 50 + 1)
        for c in api.calls:
            self.assertEqual(c["headers"]["Authorization"], "Bearer " + TOKEN)

    def test_dry_run_prints_the_diff_and_claims_nothing(self):
        api = FakeApi()
        code, out = self.run_cli(api, "branding", "--desired", self.desired({"description": "x"}), "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["diff"], [{"field": "brandingSettings.channel.description", "from": "old", "to": "x"}])
        self.assertEqual(api.names(), [("GET", "channels")])
        self.assertEqual(self.intent_calls(), [])

    def test_a_re_read_that_does_not_show_the_change_leaves_the_claim_open(self):
        api = FakeApi(apply_update=False)
        code, out = self.run_cli(api, "branding", "--desired", self.desired({"description": "new"}), *IDS)
        self.assertEqual(code, 2)
        self.assertTrue(out["uncertain"])
        self.assertEqual(out["intent"], "claimed")
        self.assertEqual(self.intent_calls(), ["claim-intent"])

    def test_a_5xx_leaves_the_claim_open(self):
        original = FakeApi()

        def flaky(method, url, headers, body):
            if method == "PUT":
                return 503, b'{"error": {"errors": [{"reason": "backendError"}], "message": "x"}}'
            return original(method, url, headers, body)
        code, out = self.run_cli(flaky, "branding", "--desired", self.desired({"description": "new"}), *IDS)
        self.assertTrue(out["uncertain"])
        self.assertEqual(self.intent_calls(), ["claim-intent"])

    def test_a_4xx_fails_the_intent(self):
        def refuse(method, url, headers, body):
            if method == "PUT":
                return 400, b'{"error": {"errors": [{"reason": "invalidBrandingOption"}], "message": "bad"}}'
            return FakeApi()(method, url, headers, body)
        code, out = self.run_cli(refuse, "branding", "--desired", self.desired({"description": "new"}), *IDS)
        self.assertEqual(code, 2)
        self.assertEqual(out["intent"], "failed")
        self.assertNotIn("uncertain", out)
        self.assertNotIn("fallback", out)
        self.assertEqual(self.intent_calls(), ["claim-intent", "fail-intent"])

    def test_a_missing_scope_fails_and_points_at_studio(self):
        def refuse(method, url, headers, body):
            if method == "PUT":
                return 403, b'{"error": {"errors": [{"reason": "insufficientPermissions"}], "message": "scope"}}'
            return FakeApi()(method, url, headers, body)
        code, out = self.run_cli(refuse, "branding", "--desired", self.desired({"description": "new"}), *IDS)
        self.assertEqual((out["intent"], out["fallback"]), ("failed", "studio"))
        self.assertIn("channel-profile.md", out["playbook"])

    def test_a_second_run_after_commit_skips(self):
        desired = self.desired({"description": "new"})
        self.run_cli(FakeApi(), "branding", "--desired", desired, *IDS)
        # Someone set it back in Studio: the same desired state is still the same, done intention.
        api = FakeApi()
        code, out = self.run_cli(api, "branding", "--desired", desired, *IDS)
        self.assertEqual(code, 0, out)
        self.assertFalse(out["acted"])
        self.assertEqual(out["claim"]["status"], "committed")
        self.assertNotIn("PUT", [m for m, _ in api.names()])

    def test_fields_outside_the_list_and_long_values_are_refused(self):
        for value in ({"title": "New name"}, {"description": "x" * 1001}, {"keywords": "k" * 501},
                      {"country": "Argentina"}, {"unsubscribedTrailer": "short"}):
            api = FakeApi()
            code, out = self.run_cli(api, "branding", "--desired", self.desired(value), *IDS)
            self.assertEqual(code, 2, value)
            self.assertEqual(api.calls, [], value)
        self.assertEqual(self.intent_calls(), [])

    def test_the_token_is_not_printed_when_the_verb_fails(self):
        apply_channel.access_token = self.saved[1]
        self.stub.write_text("#!/bin/sh\necho '{\"success\": false, \"error\": {\"message\": \"not connected\"}}'\n")
        code, out = self.run_cli(FakeApi(), "branding", "--desired", self.desired({"description": "x"}))
        self.assertEqual(code, 2)
        self.assertIn("not connected", out["error"])


class Banner(Base):
    def test_the_banner_flow_sets_the_returned_url(self):
        api = FakeApi()
        image = self.file("banner.png", png(2560, 1440, pad=100))
        code, out = self.run_cli(api, "banner", "--image", image, *IDS)
        self.assertEqual(code, 0, out)
        self.assertEqual(api.names(), [("POST", "channelBanners/insert"), ("GET", "channels"),
                                       ("PUT", "channels"), ("GET", "channels")])
        upload = api.calls[0]
        self.assertTrue(upload["url"].startswith("https://www.googleapis.com/upload/youtube/v3/channelBanners/insert"))
        self.assertEqual(upload["headers"]["Content-Type"], "image/png")
        self.assertEqual(upload["body"], Path(image).read_bytes())
        sent = json.loads(api.calls[2]["body"])["brandingSettings"]
        self.assertEqual(sent["image"]["bannerExternalUrl"], BANNER_URL)
        self.assertEqual(sent["channel"]["description"], "old")
        self.assertEqual(out["banner_url"], BANNER_URL)
        self.assertEqual(out["units_used"], 50 + 1 + 50 + 1)
        self.assertEqual(self.intent_calls(), ["claim-intent", "commit-intent"])

    def test_a_jpeg_header_is_read_too(self):
        info = apply_channel.check_banner(self.file("b.jpg", jpeg(2048, 1152)))
        self.assertEqual((info["mime"], info["width"], info["height"]), ("image/jpeg", 2048, 1152))

    def test_an_insert_without_a_url_leaves_the_claim_open(self):
        api = FakeApi(banner={"kind": "youtube#channelBannerResource"})
        code, out = self.run_cli(api, "banner", "--image", self.file("b.png", png(2560, 1440)), *IDS)
        self.assertTrue(out["uncertain"])
        self.assertEqual(api.names(), [("POST", "channelBanners/insert")])
        self.assertEqual(self.intent_calls(), ["claim-intent"])

    def test_oversized_small_or_non_16_9_banners_are_refused_before_any_claim(self):
        for name, data in (("wide.png", png(2560, 1000)), ("small.png", png(1920, 1080)),
                           ("heavy.png", png(2560, 1440, pad=6 * 1024 * 1024)), ("x.gif", b"GIF89a....")):
            api = FakeApi()
            code, out = self.run_cli(api, "banner", "--image", self.file(name, data), *IDS)
            self.assertEqual(code, 2, name)
            self.assertEqual(api.calls, [], name)
        self.assertEqual(self.intent_calls(), [])


class Watermark(Base):
    def test_watermark_is_a_multipart_upload_for_the_own_channel(self):
        api = FakeApi()
        image = self.file("mark.png", png(300, 300))
        code, out = self.run_cli(api, "watermark", "--image", image, "--timing", "offsetFromEnd",
                                 "--offset-ms", "15000", *IDS)
        self.assertEqual(code, 0, out)
        self.assertEqual(api.names(), [("GET", "channels"), ("POST", "watermarks/set")])
        call = api.calls[1]
        self.assertIn(f"channelId={CHANNEL}", call["url"])
        self.assertIn("uploadType=multipart", call["url"])
        self.assertTrue(call["headers"]["Content-Type"].startswith("multipart/related; boundary="))
        self.assertIn(b'{"timing": {"type": "offsetFromEnd", "offsetMs": 15000}}', call["body"])
        self.assertIn(Path(image).read_bytes(), call["body"])
        self.assertEqual(out["units_used"], 51)
        self.assertEqual(self.intent_calls(), ["claim-intent", "commit-intent"])

    def test_the_same_watermark_retimed_is_applied_again(self):
        image = self.file("mark.png", png(300, 300))
        self.run_cli(FakeApi(), "watermark", "--image", image, "--timing", "offsetFromStart",
                     "--offset-ms", "0", *IDS)
        same = FakeApi()
        _, out = self.run_cli(same, "watermark", "--image", image, "--timing", "offsetFromStart",
                              "--offset-ms", "0", *IDS)
        self.assertFalse(out["acted"])
        self.assertNotIn(("POST", "watermarks/set"), same.names())
        retimed = FakeApi()
        code, out = self.run_cli(retimed, "watermark", "--image", image, "--timing", "offsetFromEnd",
                                 "--offset-ms", "15000", *IDS)
        self.assertEqual(code, 0, out)
        self.assertIn(("POST", "watermarks/set"), retimed.names())

    def test_timing_rules_and_image_limits_are_checked_before_any_call(self):
        cases = [(png(300, 300), ["--timing", "offsetFromEnd", "--offset-ms", "500"]),
                 (png(300, 300), ["--timing", "offsetFromEnd", "--offset-ms", "5000", "--duration-ms", "6000"]),
                 (png(300, 200), ["--timing", "offsetFromStart", "--offset-ms", "0"]),
                 (png(100, 100), ["--timing", "offsetFromStart", "--offset-ms", "0"])]
        for data, extra in cases:
            api = FakeApi()
            code, _ = self.run_cli(api, "watermark", "--image", self.file("m.png", data), *extra, *IDS)
            self.assertEqual(code, 2, extra)
            self.assertEqual(api.calls, [])
        self.assertEqual(self.intent_calls(), [])

    def test_a_network_failure_leaves_the_claim_open(self):
        api = FakeApi(errors={"watermarks/set": (None, "")})
        code, out = self.run_cli(api, "watermark", "--image", self.file("m.png", png(300, 300)),
                                 "--timing", "offsetFromStart", "--offset-ms", "0", *IDS)
        self.assertTrue(out["uncertain"])
        self.assertEqual(self.intent_calls(), ["claim-intent"])


if __name__ == "__main__":
    unittest.main()
