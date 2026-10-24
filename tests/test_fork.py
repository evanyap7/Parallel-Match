import unittest

from parallel_match import build_league, simulate
from parallel_match.fork import ForkError, _play_branch, fork, moments, state_before

N = 4  # rollouts per test fork: correctness here, not statistics


class ForkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clubs = build_league()
        cls.home, cls.away = cls.clubs[0], cls.clubs[1]
        cls.seed, cls.mid = 12, "m012"
        cls.rec = simulate(cls.home, cls.away, cls.seed, cls.mid)

    def _fork(self, event_id, change, rec=None, seed=None, mid=None):
        return fork(self.home, self.away, seed or self.seed, mid or self.mid,
                    event_id, change, rollouts=N, workers=1, record=rec or self.rec)

    def _first(self, pred, rec=None):
        for e in (rec or self.rec).events:
            if pred(e):
                return e
        self.skipTest("no suitable event in this match")

    def test_no_change_reproduces_original_exactly(self):
        ev = self.rec.events[600]
        ctx, st0, before = state_before(self.home, self.away, self.seed, self.mid, ev.step)
        _, first, rest = _play_branch(ctx, st0, None, None)
        full = [e.to_dict() for e in before + first + rest]
        self.assertEqual(full, [e.to_dict() for e in self.rec.events])

    def test_no_change_fork_has_zero_shift(self):
        ev = self.rec.events[400]
        r = self._fork(ev.id, {"type": "none"})
        self.assertFalse(r["diverged"])
        self.assertEqual(r["original"]["outcome"], r["alternate"]["outcome"])
        self.assertEqual(r["outcome_shift"], {"home": 0.0, "draw": 0.0, "away": 0.0})

    def test_flip_foul_removes_the_foul(self):
        ev = self._first(lambda e: e.type == "foul" and e.extra["contestable"])
        r = self._fork(ev.id, {"type": "flip_call"})
        self.assertTrue(r["diverged"])
        types = [e["type"] for e in r["alternate_moment"]]
        self.assertNotIn("foul", types)
        self.assertEqual(r["alternate_moment"][0]["contact"], ev.extra["contact"])

    def test_flip_no_foul_gives_a_foul(self):
        ev = self._first(lambda e: e.type in ("tackle", "dribble") and e.extra.get("call") == "no_foul")
        r = self._fork(ev.id, {"type": "flip_call"})
        self.assertIn("foul", [e["type"] for e in r["alternate_moment"]])

    def test_flip_offside_plays_on(self):
        ev = self._first(lambda e: e.type == "offside")
        r = self._fork(ev.id, {"type": "flip_call"})
        types = [e["type"] for e in r["alternate_moment"]]
        self.assertNotIn("offside", types)
        self.assertTrue(r["alternate_moment"][0]["success"])

    def test_missed_shot_goes_in(self):
        ev = self._first(lambda e: e.type == "shot" and e.extra["outcome"] != "goal")
        r = self._fork(ev.id, {"type": "shot_outcome", "outcome": "goal"})
        self.assertIn("goal", [e["type"] for e in r["alternate_moment"]])

    def test_goal_does_not_stand(self):
        ev = self._first(lambda e: e.type == "goal")
        r = self._fork(ev.id, {"type": "shot_outcome", "outcome": "saved"})
        self.assertNotIn("goal", [e["type"] for e in r["alternate_moment"]])

    def test_substitution_and_tactics(self):
        ev = self.rec.events[300]
        r = self._fork(ev.id, {"type": "substitution", "team": "HAR", "off": "H9", "on": "H20"})
        self.assertEqual(r["alternate_moment"][0]["type"], "substitution")
        self.assertEqual(r["alternate_moment"][0]["off"], "H9")
        r = self._fork(ev.id, {"type": "tactics", "team": "NOR", "set": {"press": 0.2}})
        self.assertEqual(r["alternate_moment"][0]["type"], "tactical_change")

    def test_unavailable_player_never_appears(self):
        r = self._fork(None, {"type": "unavailable", "team": "HAR", "player": "H9"})
        self.assertEqual(r["alternate"]["timeline"][0]["type"], "lineup_change")
        appears = [e for e in r["alternate"]["timeline"][1:] if e.get("player") == "H9" or e.get("to") == "H9"]
        self.assertEqual(appears, [])

    def test_not_sent_off(self):
        for seed in range(200, 400):
            rec = simulate(self.home, self.away, seed, "mred")
            reds = [e for e in rec.events if e.type == "card" and e.extra["color"] == "red"]
            if reds:
                break
        else:
            self.skipTest("no red card found")
        r = self._fork(reds[0].id, {"type": "not_sent_off"}, rec=rec, seed=seed, mid="mred")
        colors = [e.get("color") for e in r["alternate_moment"] if e["type"] == "card"]
        self.assertNotIn("red", colors)

    def test_invalid_changes_are_rejected(self):
        ev = self._first(lambda e: e.type == "pass" and "call" not in e.extra)
        with self.assertRaises(ForkError):
            self._fork(ev.id, {"type": "flip_call"})
        with self.assertRaises(ForkError):
            self._fork(ev.id, {"type": "tactics", "team": "HAR", "set": {"press": 2.0}})
        with self.assertRaises(ForkError):
            self._fork(ev.id, {"type": "substitution", "team": "HAR", "off": "H19", "on": "H20"})
        with self.assertRaises(ForkError):
            self._fork("m012-9999", {"type": "flip_call"})

    def test_moments_list_supported_changes(self):
        ms = moments(self.rec)
        self.assertTrue(ms)
        for m in ms:
            self.assertTrue(m["changes"])


if __name__ == "__main__":
    unittest.main()
