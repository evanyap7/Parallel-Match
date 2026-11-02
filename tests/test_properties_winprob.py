"""Property tests for the win-probability model."""

import unittest

from hypothesis import event, given, strategies as st

from parallel_match import winprob
from tests import pbt_settings  # noqa: F401

minutes = st.floats(0.0, 200.0)
gds = st.integers(-20, 20)
mds = st.integers(-5, 5)
TEAMS = ("AAA", "BBB")


@st.composite
def timelines(draw):
    n = draw(st.integers(0, 40))
    ts = sorted(draw(st.lists(st.integers(0, 7000), min_size=n, max_size=n)))
    evs = []
    for t in ts:
        kind = draw(st.sampled_from(["goal", "card", "pass"]))
        e = {"t": t, "min": str(t // 60), "type": kind, "team": draw(st.sampled_from(TEAMS))}
        if kind == "card":
            e["color"] = draw(st.sampled_from(["red", "yellow"]))
        evs.append(e)
    return evs


class KeyTest(unittest.TestCase):
    @given(minutes, gds, mds)
    def test_key_fields_are_clamped(self, m, gd, md):
        b, g, d = (int(x) for x in winprob._key(m, gd, md).split(","))
        self.assertTrue(0 <= b < winprob.N_BUCKETS)
        self.assertTrue(-winprob.GD_CAP <= g <= winprob.GD_CAP)
        self.assertTrue(-1 <= d <= 1)

    @given(minutes, gds, mds, st.integers(0, 10))
    def test_goal_difference_beyond_cap_shares_a_cell(self, m, gd, md, extra):
        hi = winprob.GD_CAP + extra
        self.assertEqual(winprob._key(m, hi, md), winprob._key(m, winprob.GD_CAP, md))
        self.assertEqual(winprob._key(m, -hi, md), winprob._key(m, -winprob.GD_CAP, md))

    @given(minutes, minutes, gds, mds)
    def test_bucket_is_monotone_in_minute(self, m1, m2, gd, md):
        lo, hi = sorted((m1, m2))
        self.assertLessEqual(int(winprob._key(lo, gd, md).split(",")[0]),
                             int(winprob._key(hi, gd, md).split(",")[0]))


class ProbTest(unittest.TestCase):
    @given(minutes, gds, mds)
    def test_is_a_distribution(self, m, gd, md):
        p = winprob.prob(m, gd, md)
        self.assertEqual(len(p), 3)
        for x in p:
            self.assertTrue(0.0 <= x <= 1.0)
        self.assertAlmostEqual(sum(p), 1.0, places=9)

    @given(st.integers(0, 19), st.floats(0.0, 0.999), st.floats(0.0, 0.999), gds, mds)
    def test_minutes_in_one_bucket_share_an_answer(self, bucket, f1, f2, gd, md):
        m1 = bucket * winprob.BUCKET_MIN + f1 * winprob.BUCKET_MIN
        m2 = bucket * winprob.BUCKET_MIN + f2 * winprob.BUCKET_MIN
        self.assertEqual(winprob.prob(m1, gd, md), winprob.prob(m2, gd, md))

    @given(minutes, st.integers(1, 3))
    def test_leading_is_better_than_trailing_for_home(self, m, gd):
        ahead = winprob.prob(m, gd, 0)
        behind = winprob.prob(m, -gd, 0)
        self.assertGreater(ahead[0], behind[0])
        self.assertLess(ahead[2], behind[2])


class ResultTest(unittest.TestCase):
    @given(st.integers(-30, 30))
    def test_result_of_partitions_goal_difference(self, gd):
        self.assertEqual(winprob.result_of(gd), 0 if gd > 0 else 1 if gd == 0 else 2)


class MinuteStatesTest(unittest.TestCase):
    @given(timelines())
    def test_minutes_strictly_increase_by_one(self, evs):
        ms = [s[0] for s in winprob.minute_states(evs, "AAA")]
        self.assertEqual(ms, list(range(len(ms))))

    @given(timelines())
    def test_covers_every_event_time(self, evs):
        ms = [s[0] for s in winprob.minute_states(evs, "AAA")]
        if evs:
            self.assertGreaterEqual(ms[-1] * 60, evs[-1]["t"] - 59)

    @given(timelines())
    def test_final_goal_difference_counts_goals(self, evs):
        *_, last = winprob.minute_states(evs, "AAA")
        home = sum(1 for e in evs if e["type"] == "goal" and e["team"] == "AAA")
        away = sum(1 for e in evs if e["type"] == "goal" and e["team"] != "AAA")
        self.assertEqual(last[2], home - away)

    @given(timelines())
    def test_final_man_advantage_counts_reds(self, evs):
        *_, last = winprob.minute_states(evs, "AAA")
        reds = [e for e in evs if e["type"] == "card" and e.get("color") == "red"]
        home = sum(1 for e in reds if e["team"] == "AAA")
        away = len(reds) - home
        self.assertEqual(last[3], away - home)

    @given(timelines())
    def test_swapping_perspective_negates_state(self, evs):
        a = list(winprob.minute_states(evs, "AAA"))
        b = list(winprob.minute_states(evs, "BBB"))
        self.assertEqual([(s[0], s[2], s[3]) for s in a], [(s[0], -s[2], -s[3]) for s in b])


class CurveTest(unittest.TestCase):
    @given(timelines())
    def test_every_point_is_a_distribution(self, evs):
        for pt in winprob.curve(evs, "AAA"):
            self.assertAlmostEqual(pt["home"] + pt["draw"] + pt["away"], 1.0, delta=0.0031)

    @given(timelines())
    def test_full_time_point_is_certain(self, evs):
        evs = evs + [{"t": (evs[-1]["t"] if evs else 0) + 1, "min": "90", "type": "full_time",
                      "team": "AAA"}]
        last = winprob.curve(evs, "AAA")[-1]
        self.assertEqual(sorted((last["home"], last["draw"], last["away"])), [0.0, 0.0, 1.0])
        *_, final = winprob.minute_states(evs, "AAA")
        r = winprob.result_of(final[2])
        self.assertEqual((last["home"], last["draw"], last["away"])[r], 1.0)
        event(f"result={r}")


if __name__ == "__main__":
    unittest.main()
