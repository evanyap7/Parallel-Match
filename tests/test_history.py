import unittest

from parallel_match import history, season


class HistoryForTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = history.season_rows()
        cls.called_foul = next(r for r in cls.rows if r["family"] == "foul" and r["called"])
        cls.onside = next(r for r in cls.rows if r["family"] == "offside" and not r["called"])

    def test_cached_rows_match_the_season(self):
        # Guards against a stale data/history_rows.json after the season changes.
        self.assertEqual(self.rows, history.build_season_rows())

    def test_unknown_or_non_call_moment_is_none(self):
        self.assertIsNone(history.history_for("m001", "m001-9999"))
        self.assertIsNone(history.history_for("nope", "nope-0001"))

    def test_groups_partition_the_comparables(self):
        for target in (self.called_foul, self.onside):
            with self.subTest(event=target["event_id"]):
                h = history.history_for(target["match_id"], target["event_id"])
                self.assertEqual(h["n"], h["when_given"]["n"] + h["when_not_given"]["n"])
                self.assertEqual(h["called"], bool(target["called"]))
                self.assertEqual(h["attacking_team"], target["att_team"])

    def test_shift_direction_follows_the_flip(self):
        h = history.history_for(self.called_foul["match_id"], self.called_foul["event_id"])
        if not h["enough_precedent"]:
            self.skipTest("not enough precedent for this moment")
        # Flipping a given call: shift = win(not given) - win(given).
        expected = round(h["when_not_given"]["win"] - h["when_given"]["win"], 3)
        self.assertAlmostEqual(h["history_shift_att_win"], expected, places=3)

    def test_compare_with_simulation_uses_the_attacking_side(self):
        h = history.history_for(self.called_foul["match_id"], self.called_foul["event_id"])
        shift = {"home": 0.10, "draw": -0.04, "away": -0.06}
        c = history.compare_with_simulation(h, shift)
        self.assertEqual(c["sim_shift_att_win"], 0.10 if h["attacking_is_home"] else -0.06)
        for key in h:
            self.assertEqual(c[key], h[key])

    def test_history_check_only_for_flipped_calls(self):
        base = {"match_id": self.called_foul["match_id"], "event_id": self.called_foul["event_id"],
                "outcome_shift": {"home": 0.0, "draw": 0.0, "away": 0.0}}
        self.assertIsNone(history.history_check({**base, "change": {"type": "tactics"}}))
        self.assertIsNotNone(history.history_check({**base, "change": {"type": "flip_call"}}))


class SeasonLoaderTest(unittest.TestCase):
    def test_match_dicts_cover_the_season(self):
        ms = season.match_dicts()
        self.assertEqual(len(ms), 90)
        self.assertEqual(sum(1 for m in ms if m["story"]), 5)
        self.assertTrue(all(len(m["events"]) > 1000 for m in ms))

    def test_match_dicts_load_into_the_mcp_store(self):
        try:
            from mcp_history.store import HistoryStore
        except ImportError:
            self.skipTest("mcp_history not importable")
        store = HistoryStore(season.match_dicts())
        self.assertEqual(store.season_summary()["matches"], 90)


if __name__ == "__main__":
    unittest.main()
