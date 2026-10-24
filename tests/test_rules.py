"""Officiating rules checked against hand-made positions (attacking frame:
ax = metres from the attacking team's own goal line)."""

import unittest

from parallel_match import rules


GK = 103.0  # opposing goalkeeper on their line


class OffsideTest(unittest.TestCase):
    def test_beyond_second_last_defender_is_offside(self):
        m = rules.offside_margin(attacker_ax=86.2, ball_ax=60.0, opp_ax=[GK, 85.0, 80.0, 78.0])
        self.assertAlmostEqual(m, 1.2)
        self.assertTrue(rules.assistant_flags_offside(m, noise=0.0))

    def test_level_is_onside(self):
        m = rules.offside_margin(85.0, 60.0, [GK, 85.0, 80.0])
        self.assertEqual(m, 0.0)
        self.assertFalse(rules.assistant_flags_offside(m, noise=0.0))

    def test_behind_line_is_onside(self):
        m = rules.offside_margin(84.7, 60.0, [GK, 85.0, 80.0])
        self.assertLess(m, 0.0)
        self.assertFalse(rules.assistant_flags_offside(m, noise=0.0))

    def test_own_half_is_never_offside(self):
        # Defenders pushed up to 40m: attacker beyond them but in own half.
        m = rules.offside_margin(50.0, 30.0, [GK, 40.0, 38.0])
        self.assertLessEqual(m, 0.0)

    def test_behind_the_ball_is_onside(self):
        # Attacker beyond the defenders but behind the ball.
        m = rules.offside_margin(88.0, 90.0, [GK, 85.0])
        self.assertLess(m, 0.0)

    def test_keeper_off_line_uses_second_last(self):
        # Keeper has come out to 80m, so the deepest outfield defender at 95m
        # is the last opponent and the keeper is second-last.
        m = rules.offside_margin(82.0, 60.0, [95.0, 80.0, 70.0])
        self.assertAlmostEqual(m, 2.0)

    def test_noise_can_flip_borderline_call(self):
        self.assertTrue(rules.assistant_flags_offside(-0.1, noise=0.2))
        self.assertFalse(rules.assistant_flags_offside(0.1, noise=-0.2))


class FoulTest(unittest.TestCase):
    def test_clear_foul_and_clear_non_foul(self):
        self.assertTrue(rules.referee_calls_foul(0.9, noise=0.0, threshold=0.53))
        self.assertFalse(rules.referee_calls_foul(0.1, noise=0.0, threshold=0.53))

    def test_borderline_contact_flips_with_noise(self):
        self.assertTrue(rules.referee_calls_foul(0.50, noise=0.05, threshold=0.53))
        self.assertFalse(rules.referee_calls_foul(0.56, noise=-0.05, threshold=0.53))

    def test_penalty_area(self):
        self.assertTrue(rules.in_penalty_area(95.0, 34.0))
        self.assertTrue(rules.in_penalty_area(88.5, 13.84))
        self.assertFalse(rules.in_penalty_area(88.4, 34.0))
        self.assertFalse(rules.in_penalty_area(95.0, 13.0))

    def test_cards(self):
        self.assertIsNone(rules.card_for(0.80, 0.93, 1.17))
        self.assertEqual(rules.card_for(0.95, 0.93, 1.17), "yellow")
        self.assertEqual(rules.card_for(1.20, 0.93, 1.17), "red")


if __name__ == "__main__":
    unittest.main()
