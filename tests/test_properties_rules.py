"""Property tests for the pure officiating rules."""

import unittest

from hypothesis import given, strategies as st

from parallel_match import rules
from tests import pbt_settings  # noqa: F401

ax = st.floats(0.0, rules.PITCH_L)
ys = st.floats(0.0, rules.PITCH_W)
opp = st.lists(ax, min_size=0, max_size=11)
noise = st.floats(-50.0, 50.0)


class PenaltyAreaTest(unittest.TestCase):
    @given(ax, ys)
    def test_matches_geometry(self, x, y):
        inside = (x >= rules.PITCH_L - rules.PEN_AREA_DEPTH
                  and abs(y - rules.GOAL_Y) <= rules.PEN_AREA_HALF_WIDTH)
        self.assertEqual(rules.in_penalty_area(x, y), inside)

    @given(st.floats(0.0, rules.PITCH_L - rules.PEN_AREA_DEPTH, exclude_max=True), ys)
    def test_outside_if_not_deep_enough(self, x, y):
        self.assertFalse(rules.in_penalty_area(x, y))

    @given(ax, st.floats(0.0, rules.PITCH_W / 2))
    def test_symmetric_across_the_pitch_width(self, x, d):
        self.assertEqual(rules.in_penalty_area(x, rules.GOAL_Y + d),
                         rules.in_penalty_area(x, rules.GOAL_Y - d))


class SecondLastTest(unittest.TestCase):
    @given(st.lists(ax, max_size=1))
    def test_fewer_than_two_opponents_defaults_to_goal_line(self, xs):
        self.assertEqual(rules.second_last_opponent(xs), rules.PITCH_L)

    @given(st.lists(ax, min_size=2, max_size=11))
    def test_is_second_largest(self, xs):
        v = rules.second_last_opponent(xs)
        self.assertIn(v, xs)
        self.assertEqual(v, sorted(xs)[-2])
        self.assertLessEqual(v, max(xs))

    @given(st.lists(ax, min_size=2, max_size=11), st.randoms(use_true_random=False))
    def test_order_independent(self, xs, rnd):
        shuffled = list(xs)
        rnd.shuffle(shuffled)
        self.assertEqual(rules.second_last_opponent(xs), rules.second_last_opponent(shuffled))


class OffsideMarginTest(unittest.TestCase):
    @given(ax, ax, opp)
    def test_never_offside_in_own_half(self, a, ball, opps):
        if a <= rules.HALFWAY:
            self.assertLessEqual(rules.offside_margin(a, ball, opps), 0.0)

    @given(ax, ax, opp)
    def test_level_with_ball_or_behind_is_onside(self, a, ball, opps):
        if a <= ball:
            self.assertLessEqual(rules.offside_margin(a, ball, opps), 0.0)

    @given(ax, ax, opp)
    def test_level_with_second_last_is_onside(self, a, ball, opps):
        if a <= rules.second_last_opponent(opps):
            self.assertLessEqual(rules.offside_margin(a, ball, opps), 0.0)

    @given(ax, ax, opp, st.floats(0.0, 20.0))
    def test_moving_attacker_forward_never_reduces_margin(self, a, ball, opps, d):
        self.assertGreaterEqual(rules.offside_margin(a + d, ball, opps),
                                rules.offside_margin(a, ball, opps))

    @given(ax, ax, opp)
    def test_margin_is_attacker_minus_line(self, a, ball, opps):
        line = max(rules.second_last_opponent(opps), ball, rules.HALFWAY)
        self.assertEqual(rules.offside_margin(a, ball, opps), a - line)

    @given(ax, ax, st.lists(ax, min_size=2, max_size=11), st.randoms(use_true_random=False))
    def test_opponent_order_independent(self, a, ball, opps, rnd):
        shuffled = list(opps)
        rnd.shuffle(shuffled)
        self.assertEqual(rules.offside_margin(a, ball, opps), rules.offside_margin(a, ball, shuffled))


class DecisionTest(unittest.TestCase):
    @given(st.floats(-100, 100), noise)
    def test_flag_iff_perceived_margin_positive(self, margin, n):
        self.assertEqual(rules.assistant_flags_offside(margin, n), margin + n > 0.0)

    @given(st.floats(-100, 100), noise, noise)
    def test_flag_monotone_in_noise(self, margin, n1, n2):
        lo, hi = sorted((n1, n2))
        if rules.assistant_flags_offside(margin, lo):
            self.assertTrue(rules.assistant_flags_offside(margin, hi))

    @given(st.floats(0.0, 1.0), noise, st.floats(0.0, 2.0))
    def test_foul_monotone_in_contact(self, contact, n, thr):
        if rules.referee_calls_foul(contact, n, thr):
            self.assertTrue(rules.referee_calls_foul(contact + 0.5, n, thr))

    @given(st.floats(0.0, 1.0), noise, st.floats(0.0, 2.0), st.floats(0.0, 2.0))
    def test_foul_monotone_in_threshold(self, contact, n, t1, t2):
        lo, hi = sorted((t1, t2))
        if rules.referee_calls_foul(contact, n, hi):
            self.assertTrue(rules.referee_calls_foul(contact, n, lo))

    @given(st.floats(-5, 5), st.floats(-5, 5), st.floats(-5, 5))
    def test_card_matches_thresholds(self, score, yellow, red):
        got = rules.card_for(score, yellow, red)
        if score >= red:
            self.assertEqual(got, "red")
        elif score >= yellow:
            self.assertEqual(got, "yellow")
        else:
            self.assertIsNone(got)

    @given(st.floats(-5, 5), st.floats(-5, 5), st.floats(-5, 5), st.floats(0, 5))
    def test_card_severity_never_decreases_with_score(self, score, yellow, red, d):
        order = {None: 0, "yellow": 1, "red": 2}
        self.assertGreaterEqual(order[rules.card_for(score + d, yellow, red)],
                                order[rules.card_for(score, yellow, red)])


if __name__ == "__main__":
    unittest.main()
