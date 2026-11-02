"""Property tests for fixture scheduling and the league table."""

import unittest

from hypothesis import given, strategies as st

from parallel_match import season
from tests import pbt_settings  # noqa: F401

# The circle method needs an even number of teams (the league has 10).
even_clubs = st.integers(1, 12).map(lambda k: [f"C{i:02d}" for i in range(2 * k)])
score = st.integers(0, 12)


class ScheduleTest(unittest.TestCase):
    @given(even_clubs)
    def test_double_round_robin_size(self, codes):
        n = len(codes)
        sched = season.schedule(codes)
        self.assertEqual(len(sched), n * (n - 1))
        self.assertEqual(max(r for r, _, _ in sched), 2 * (n - 1))

    @given(even_clubs)
    def test_every_ordered_pair_exactly_once(self, codes):
        pairs = [(h, a) for _, h, a in season.schedule(codes)]
        self.assertEqual(len(pairs), len(set(pairs)))
        self.assertEqual(set(pairs), {(h, a) for h in codes for a in codes if h != a})

    @given(even_clubs)
    def test_each_club_plays_once_per_round(self, codes):
        by_round = {}
        for r, h, a in season.schedule(codes):
            by_round.setdefault(r, []).extend((h, a))
        for r, teams in by_round.items():
            self.assertEqual(sorted(teams), sorted(codes), f"round {r}")

    @given(even_clubs)
    def test_second_half_mirrors_first(self, codes):
        n = len(codes)
        sched = season.schedule(codes)
        first = {(r, h, a) for r, h, a in sched if r <= n - 1}
        second = {(r - (n - 1), a, h) for r, h, a in sched if r > n - 1}
        self.assertEqual(first, second)

    @given(even_clubs)
    def test_no_club_plays_itself(self, codes):
        self.assertTrue(all(h != a for _, h, a in season.schedule(codes)))


class MatchSeedTest(unittest.TestCase):
    @given(st.integers(0, 1 << 40), st.integers(0, 500), st.integers(0, 500))
    def test_seed_in_range_and_deterministic(self, world, n, k):
        s = season.match_seed(world, n, k)
        self.assertTrue(0 <= s < (1 << 62))
        self.assertEqual(s, season.match_seed(world, n, k))


@st.composite
def seasons(draw):
    codes = [f"C{i}" for i in range(draw(st.integers(2, 8)))]
    n = draw(st.integers(0, 40))
    ms = []
    for _ in range(n):
        h, a = draw(st.sampled_from(codes)), draw(st.sampled_from(codes))
        if h == a:
            a = codes[(codes.index(h) + 1) % len(codes)]
        ms.append({"home": h, "away": a, "score": [draw(score), draw(score)]})
    return {"matches": ms}


class StandingsTest(unittest.TestCase):
    @given(seasons())
    def test_games_split_into_results(self, s):
        for r in season.standings(s):
            self.assertEqual(r["p"], r["w"] + r["d"] + r["l"])

    @given(seasons())
    def test_points_are_three_per_win_one_per_draw(self, s):
        for r in season.standings(s):
            self.assertEqual(r["pts"], 3 * r["w"] + r["d"])

    @given(seasons())
    def test_goals_for_equal_goals_against_league_wide(self, s):
        rows = season.standings(s)
        self.assertEqual(sum(r["gf"] for r in rows), sum(r["ga"] for r in rows))
        self.assertEqual(sum(r["gf"] for r in rows), sum(sum(m["score"]) for m in s["matches"]))

    @given(seasons())
    def test_wins_equal_losses_and_each_match_counted_twice(self, s):
        rows = season.standings(s)
        self.assertEqual(sum(r["w"] for r in rows), sum(r["l"] for r in rows))
        self.assertEqual(sum(r["p"] for r in rows), 2 * len(s["matches"]))

    @given(seasons())
    def test_sorted_by_points_then_goal_difference_then_goals_then_name(self, s):
        rows = season.standings(s)
        keys = [(-r["pts"], -(r["gf"] - r["ga"]), -r["gf"], r["club"]) for r in rows]
        self.assertEqual(keys, sorted(keys))

    @given(seasons(), st.randoms(use_true_random=False))
    def test_match_order_does_not_matter(self, s, rnd):
        shuffled = list(s["matches"])
        rnd.shuffle(shuffled)
        self.assertEqual(season.standings(s), season.standings({"matches": shuffled}))

    @given(seasons())
    def test_only_clubs_that_played_appear(self, s):
        played = {m["home"] for m in s["matches"]} | {m["away"] for m in s["matches"]}
        self.assertEqual({r["club"] for r in season.standings(s)}, played)


if __name__ == "__main__":
    unittest.main()
