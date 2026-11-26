"""The pitch plan — one computation for what Create Music Release promises and what Pitch does.

Why these cases. The owner is shown a window and a date; Pitch acts on the same computation days or
months later. The rules are ours (21 days between pitches, 21 days before release, Spotify's one pitch
at a time, one reservation); the platforms' and the owner's timing are never assumed. Each timeline
below is one that broke an earlier design on paper, and the property test runs thousands of random
ones against the invariants the owner fixed.
"""

import random
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import records  # noqa: E402

A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
CITY_ALIVE = {"album_id": "6UkqasjKwgTtnyekAWQSXU", "title": "City Alive", "status": "pitched",
              "pitch_day": "2026-11-23", "release_day": "2026-11-28", "source": "Pitch a Song on Spotify"}


def release(spec, day, status="held", consent=False):
    r = {"spec": spec, "date": day, "status": status, "pitch_ok": consent}
    if consent:
        r["pitch_ok_at"] = "2026-11-27T10:00:00Z"
    return r


def plan(today, releases, pitched=(), claims=(), reservation=None, candidate=None, lead=7):
    return records.pitch_plan(today=today, lead_days=lead, pitched=list(pitched), open_claims=list(claims),
                              reservation=reservation, releases=list(releases), candidate=candidate)


class Timelines(unittest.TestCase):
    def test_the_first_promise_at_rollout(self):
        # City Alive was pitched 11-23 for 11-28: the slot opens 12-14. A Yes gives the first Friday
        # whose window is at least 7 days: 2027-01-15, window 12-14 – 12-25.
        p = plan("2026-11-27", [release(A, "2026-12-04")], [CITY_ALIVE], candidate=A)
        self.assertEqual(p["slot_opens"], "2026-12-14")
        offer = p["offer"]
        self.assertTrue(offer["can_offer"])
        self.assertEqual(offer["yes_date"], "2027-01-15")
        self.assertEqual((offer["window"]["from"], offer["window"]["to"], offer["window"]["days"]),
                         ("2026-12-14", "2026-12-25", 12))
        self.assertEqual(offer["no_date"], "2026-12-04")

    def test_a_live_reservation_is_not_offered_to_another_release(self):
        rels = [release(A, "2027-01-15", consent=True), release(B, "2027-01-22")]
        p = plan("2026-11-27", rels, [CITY_ALIVE], reservation={"spec": A}, candidate=B)
        self.assertEqual(p["reservation"]["state"], "live")
        self.assertFalse(p["offer"]["can_offer"])
        self.assertEqual(p["offer"]["taken_by"], A)

    def test_a_missed_window_frees_the_reservation(self):
        rels = [release(A, "2027-01-15", consent=True)]
        self.assertEqual(plan("2026-12-25", rels, [CITY_ALIVE], reservation={"spec": A})["reservation"]["state"],
                         "live")
        missed = plan("2026-12-26", rels, [CITY_ALIVE], reservation={"spec": A})["reservation"]
        self.assertEqual(missed["state"], "free")
        self.assertIn("missed", missed["why"])

    def test_a_claim_in_flight_keeps_the_reservation_live_past_its_window(self):
        rels = [release(A, "2027-01-15", consent=True)]
        p = plan("2026-12-27", rels, [CITY_ALIVE], claims=[{"claim_day": "2026-12-24"}], reservation={"spec": A})
        self.assertEqual(p["reservation"]["state"], "live")

    def test_a_withdrawn_consent_frees_the_reservation(self):
        rels = [release(A, "2027-01-15", consent=False)]
        self.assertEqual(plan("2026-12-01", rels, [CITY_ALIVE], reservation={"spec": A})["reservation"]["state"],
                         "free")

    def test_a_pitched_song_far_ahead_holds_the_next_slot_until_it_is_out(self):
        far = {**CITY_ALIVE, "pitch_day": "2026-12-01", "release_day": "2027-02-26"}
        p = plan("2026-12-02", [release(A, "2027-01-15")], [far], candidate=A)
        self.assertEqual(p["slot_opens"], "2027-02-26")
        self.assertEqual(p["offer"]["yes_date"], "2027-03-26")

    def test_our_pitched_release_counts_with_its_current_date(self):
        # A move after the pitch changes when the song is out, so when the next pitch may go.
        ours = {**CITY_ALIVE, "spec": A}
        del ours["release_day"]
        rels = [release(A, "2026-12-18", status="committed")]
        self.assertEqual(plan("2026-11-27", rels, [ours])["slot_opens"], "2026-12-18")

    def test_a_committed_release_keeps_its_date(self):
        rels = [release(A, "2026-12-25", status="committed")]
        offer = plan("2026-11-27", rels, [CITY_ALIVE], candidate=A)["offer"]
        self.assertEqual(offer["yes_date"], "2026-12-25")
        self.assertFalse(offer["can_offer"])  # 12-25 − 21 = 12-04, before the slot opens
        short = plan("2026-11-27", [release(A, "2027-01-08", status="committed")], [CITY_ALIVE], candidate=A)
        self.assertTrue(short["offer"]["can_offer"])
        self.assertTrue(short["offer"]["short"])  # 12-14 – 12-18: 5 days, Pitch still acts

    def test_a_taken_friday_is_skipped(self):
        rels = [release(A, "2026-12-04"), release(B, "2027-01-15", status="committed")]
        offer = plan("2026-11-27", rels, [CITY_ALIVE], candidate=A)["offer"]
        self.assertEqual(offer["yes_date"], "2027-01-22")

    def test_the_lead_setting_is_respected_above_the_pitch_rule(self):
        offer = plan("2026-11-27", [release(A, "2026-12-04")], [], candidate=A, lead=60)["offer"]
        self.assertGreaterEqual(offer["yes_date"], "2027-01-26")
        self.assertEqual(date.fromisoformat(offer["yes_date"]).weekday(), 4)

    def test_no_history_opens_the_slot_today(self):
        p = plan("2026-11-27", [release(A, "2026-12-04")], [], candidate=A)
        self.assertEqual(p["slot_opens"], "2026-11-27")
        self.assertEqual(p["offer"]["yes_date"], "2026-12-25")


class Consent(unittest.TestCase):
    def test_three_states(self):
        self.assertEqual(records.consent({"pitch_ok": True}), "yes")
        self.assertEqual(records.consent({"pitch_ok": False, "pitch_declined_at": "2026-11-27T10:00:00Z"}),
                         "declined")
        self.assertEqual(records.consent({"pitch_ok": False}), "unanswered")


class Invariants(unittest.TestCase):
    """Random worlds: releases created at random, the owner answering at random, the box on or off at
    random, Spotify listing at random, hand pitches, and runs that crash after claiming. Whatever
    happens, the system never breaks the owner's rules, and a shown window moves only on an event."""

    def simulate(self, seed: int) -> None:
        rnd = random.Random(seed)
        start = date(2026, 11, 27)
        releases: dict[str, dict] = {}
        listed_on: dict[str, date] = {}
        pitched: list[dict] = [dict(CITY_ALIVE)]
        claims: list[dict] = []          # open slot claims: {claim_day, spec, resolve_on}
        reservation = None
        hand_pending: list[tuple[date, dict]] = []
        system_pitches: list[tuple[date, str]] = []
        shown: dict | None = None        # the reservation's window as last shown, and the event count
        events = 0
        n = 0
        for offset in range(240):
            today = start + timedelta(days=offset)
            iso = today.isoformat()

            def current_plan(candidate=None):
                return records.pitch_plan(today=iso, lead_days=7, pitched=pitched,
                                          open_claims=[{"claim_day": c["claim_day"]} for c in claims],
                                          reservation=reservation, releases=list(releases.values()),
                                          candidate=candidate)

            # The owner makes a release now and then, and answers the pitch question at random.
            if rnd.random() < 0.15:
                n += 1
                spec = f"{n:08x}-0000-4000-8000-000000000000"
                releases[spec] = {"spec": spec, "date": iso, "status": "held", "pitch_ok": False}
                offer = current_plan(spec)["offer"]
                if offer["can_offer"] and rnd.random() < 0.6:
                    releases[spec].update(date=offer["yes_date"], pitch_ok=True,
                                          pitch_ok_at=f"{iso}T10:00:00Z")
                    if current_plan()["reservation"]["state"] == "free":
                        reservation = {"spec": spec}
                        events += 1
                    else:  # lost the race: the consent is withdrawn, the release stays unanswered
                        releases[spec].update(pitch_ok=False)
                        releases[spec].pop("pitch_ok_at")
                else:
                    releases[spec]["date"] = offer["no_date"]
                listed_on[spec] = today + timedelta(days=rnd.randint(1, 40))  # never predicted

            # A hand pitch by the owner, seen by Pitch only when it next runs.
            if rnd.random() < 0.01:
                rd = today + timedelta(days=rnd.randint(8, 60))
                hand_pending.append((today, {"album_id": f"{rnd.randrange(10**21, 10**22)}", "title": "hand",
                                             "status": "pitched", "release_day": rd.isoformat(),
                                             "source": "owner"}))

            if rnd.random() < 0.3:  # the box is on and a Pitch run happens
                for made, rec in hand_pending:
                    pitched.append({**rec, "pitch_day": iso})  # first observed today: conservative
                    events += 1
                hand_pending.clear()
                for c in list(claims):  # reconcile stale claims by observation
                    if today >= c["resolve_on"]:
                        claims.remove(c)
                        if c["went"]:
                            pitched.append({"album_id": "x" * 22, "spec": c["spec"], "title": "ours",
                                            "status": "unknown", "pitch_day": c["claim_day"],
                                            "source": "Pitch a Song on Spotify"})
                        events += 1
                p = current_plan()
                res = p["reservation"]
                if res["state"] == "live" and not claims:
                    w = res["window"]
                    spec = res["spec"]
                    if w["open_today"] and listed_on[spec] <= today:
                        # Right before the submit the lead is re-checked (it is today's window).
                        rel_day = date.fromisoformat(releases[spec]["date"])
                        self.assertLessEqual(today, rel_day - timedelta(days=21))
                        if rnd.random() < 0.1:  # crash after the claim
                            claims.append({"claim_day": iso, "spec": spec, "went": rnd.random() < 0.5,
                                           "resolve_on": today + timedelta(days=rnd.randint(1, 10))})
                        else:
                            pitched.append({"album_id": "y" * 22, "spec": spec, "title": "ours",
                                            "status": "pitched", "pitch_day": iso,
                                            "source": "Pitch a Song on Spotify"})
                            system_pitches.append((today, spec))
                        events += 1

            # Invariant: the shown window of a live reservation moves only after an event.
            res = current_plan()["reservation"]
            if res["state"] == "live":
                key = (res["spec"], res["window"]["from"], res["window"]["to"])
                if shown and shown["spec"] == res["spec"] and shown["events"] == events:
                    self.assertEqual(shown["key"], key, f"seed {seed}: the window moved on {iso} with no event")
                shown = {"spec": res["spec"], "key": key, "events": events}
            else:
                shown = None

        # Invariants over every pitch the system made.
        all_pitches = [(date.fromisoformat(p["pitch_day"]), p) for p in pitched]
        for day, spec in system_pitches:
            rel_day = date.fromisoformat(releases[spec]["date"])
            self.assertLessEqual(day, rel_day - timedelta(days=21), f"seed {seed}: pitched late")
            for other_day, other in all_pitches:
                if other_day < day:
                    self.assertGreaterEqual((day - other_day).days, 21, f"seed {seed}: pitches too close")
                    other_release = (date.fromisoformat(releases[other["spec"]]["date"]) if other.get("spec")
                                     else date.fromisoformat(other["release_day"]))
                    self.assertGreaterEqual(day, other_release, f"seed {seed}: pitched while one was unreleased")

    def test_random_worlds_keep_the_rules(self):
        for seed in range(400):
            self.simulate(seed)


if __name__ == "__main__":
    unittest.main()
