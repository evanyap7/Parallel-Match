"""Tests for mcp_history.store: the comparable-moment query, in plain code."""

import os
import tempfile
import unittest

from mcp_history.store import (
    CONTACT_TOLERANCE, HistoryStore, _goals_in_window, _zone,
)


def _match(match_id="mA", home="HAR", away="NOR", events=None, score=None):
    return {
        "match_id": match_id, "seed": 1, "home": home, "away": away,
        "score": score or [0, 0], "events": events or [],
    }


def _event(seq, **kw):
    e = {"id": f"mA-{seq:04d}", "step": seq, "t": seq * 60, "min": str(seq),
         "period": 1, "type": "pass", "team": "HAR", "player": "H7",
         "xy": [52.5, 34.0], "score": [0, 0]}
    e.update(kw)
    return e


class ZoneTests(unittest.TestCase):
    def test_zone_labels(self):
        self.assertEqual(_zone(10), "defending third")
        self.assertEqual(_zone(52), "middle third")
        self.assertEqual(_zone(95), "attacking third")

    def test_attacking_frame_flips_for_away_team(self):
        store = HistoryStore([_match(events=[
            _event(1, type="foul", team="NOR", xy=[10, 34], contact=0.5,
                 margin=0.0, call="free_kick", law="Law 12: Fouls and Misconduct (direct free kick offences)"),
        ])])
        mom = store.moments[0][2]
        # away team at x=10 attacks towards x=0, so x_att = 105-10 = 95
        self.assertEqual(mom.zone, "attacking third")
        self.assertEqual(mom.side, "away")
        self.assertEqual(mom.opponent, "HAR")


class IndexingTests(unittest.TestCase):
    def test_only_family_events_are_moments(self):
        store = HistoryStore([_match(events=[
            _event(1, type="foul", contact=0.6, margin=0.1, call="free_kick", law="x"),
            _event(2, type="substitution", off="H8", law="y"),
            _event(3, type="offside", margin=0.2, call="offside", law="z"),
            _event(4, type="pass"),  # pass without offside_margin: not a moment
            _event(5, type="pass", offside_margin=0.1, call="onside", law="z"),
        ])])
        types = [m.type for _, _, m in store.moments]
        self.assertEqual(types, ["foul", "offside", "pass"])
        self.assertEqual([m.family for _, _, m in store.moments],
                         ["contact", "offside", "offside"])

    def test_load_skips_non_match_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            match_path = os.path.join(tmp, "mA.json")
            other_path = os.path.join(tmp, "not_a_match.json")
            with open(match_path, "w") as fh:
                fh.write('{"match_id": "mA", "home": "HAR", "away": "NOR", "score": [0,0], "events": [], "seed": 1}')
            with open(other_path, "w") as fh:
                fh.write('{"placeholder": true, "request": {}}')
            store = HistoryStore.load(tmp)
        self.assertEqual(list(store.matches), ["mA"])


def _two_match_store():
    a = _match("mA", events=[
        _event(5, type="foul", contact=0.50, margin=0.0, call="free_kick", law="L12"),
        _event(6, type="tackle", contact=0.53, call="no_foul", law="L12"),
        _event(9, type="foul", contact=0.90, margin=0.4, call="free_kick", law="L12"),
        _event(11, type="offside", margin=0.10, call="offside", law="L11"),
    ])
    b = _match("mB", events=[
        _event(4, type="foul", contact=0.55, margin=0.05, call="no_foul", law="L12"),
        _event(6, type="foul", contact=0.75, margin=0.2, call="free_kick", law="L12"),
        _event(8, type="offside", margin=0.30, call="offside", law="L11"),
        _event(12, type="tackle", contact=0.52, call="no_foul", law="L12"),
    ])
    return HistoryStore([a, b])


class QueryTests(unittest.TestCase):
    def test_contact_comparables_within_tolerance_only(self):
        store = _two_match_store()
        result = store.query("mA", "mA-0005")   # contact 0.50, other matches only
        contacts = [c.moment.contact for c in result.comparables]
        # mB: 0.55 and 0.52 within 0.2; 0.75 and 0.90 are not
        self.assertEqual(sorted(contacts), [0.52, 0.55])

    def test_families_never_mix(self):
        store = _two_match_store()
        result = store.query("mA", "mA-0011")   # offside
        families = {c.moment.family for c in result.comparables}
        self.assertEqual(families, {"offside"})

    def test_same_match_excluded_by_default(self):
        store = _two_match_store()
        result = store.query("mA", "mA-0005")
        self.assertTrue(all(c.moment.match_id == "mB" for c in result.comparables))
        # mA-0006 (0.53) joins when the same match is allowed
        included = store.query("mA", "mA-0005", include_same_match=True)
        self.assertEqual(len(included.comparables), len(result.comparables) + 1)

    def test_stats_counts(self):
        store = _two_match_store()
        result = store.query("mA", "mA-0005")   # call was free_kick
        stats = result.stats()
        # both mB comparables (0.55, 0.52) were called no_foul
        self.assertEqual(stats["n"], 2)
        self.assertEqual(stats["n_other_call"], 2)
        self.assertEqual(stats["n_same_call"], 0)
        self.assertEqual(stats["share_other_call"], 1.0)

    def test_closeness_orders_by_proximity(self):
        store = _two_match_store()
        result = store.query("mA", "mA-0005")
        self.assertEqual(result.comparables[0].moment.contact, 0.52)

    def test_query_unknown_event_returns_none(self):
        store = _two_match_store()
        self.assertIsNone(store.query("mA", "mA-9999"))
        self.assertIsNone(store.query("mZ", "whatever"))

    def test_tolerance_constant(self):
        self.assertLessEqual(CONTACT_TOLERANCE, 0.25)


class GoalWindowTests(unittest.TestCase):
    def test_goals_in_window_counts_team_and_window_only(self):
        events = [   # kept in match-clock order, as real event lists are
            _event(1, type="foul", contact=0.5, margin=0.0, call="free_kick", law="L"),
            _event(2, type="goal", team="HAR", t=600),
            _event(3, type="goal", team="NOR", t=700),       # other team
            _event(5, type="goal", team="HAR", t=660),
            _event(9, type="goal", team="HAR", t=600 + 900),  # outside window
        ]
        match = _match(events=events)
        self.assertEqual(_goals_in_window(match, 0, "HAR"), 2)
        self.assertEqual(_goals_in_window(match, 0, "NOR"), 1)


class SeasonSummaryTests(unittest.TestCase):
    def test_summary_shape(self):
        store = _two_match_store()
        s = store.season_summary()
        self.assertEqual(s["matches"], 2)
        self.assertEqual(s["contestable_moments"], len(store.moments))
        self.assertEqual(s["by_family"]["contact"], 6)


if __name__ == "__main__":
    unittest.main()
