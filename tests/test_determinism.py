import unittest

from parallel_match import build_league, new_match, play, simulate, step


def _dicts(events):
    return [e.to_dict() for e in events]


class DeterminismTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        clubs = build_league()
        cls.home, cls.away = clubs[0], clubs[1]

    def test_same_seed_identical_match(self):
        a = simulate(self.home, self.away, seed=12, match_id="m012")
        b = simulate(self.home, self.away, seed=12, match_id="m012")
        self.assertEqual(_dicts(a.events), _dicts(b.events))
        self.assertGreater(len(a.events), 1000)

    def test_different_seed_different_match(self):
        a = simulate(self.home, self.away, seed=12)
        b = simulate(self.home, self.away, seed=13)
        self.assertNotEqual(_dicts(a.events), _dicts(b.events))

    def test_league_is_deterministic(self):
        self.assertEqual(build_league(), build_league())


class StateCopyTest(unittest.TestCase):
    """A copy of the state taken mid-match must replay the remainder exactly.
    This is the 'fork with no change reproduces the original' guarantee."""

    @classmethod
    def setUpClass(cls):
        clubs = build_league()
        cls.home, cls.away = clubs[2], clubs[5]

    def _midmatch(self, n_steps):
        ctx, st = new_match(self.home, self.away, seed=99, match_id="m099")
        before = []
        for _ in range(n_steps):
            before.extend(step(ctx, st))
        return ctx, st, before

    def test_copy_replays_identically(self):
        for n in (1, 250, 600, 1100):
            with self.subTest(fork_step=n):
                ctx, st, before = self._midmatch(n)
                fork = st.copy()
                rest_a = play(ctx, st)
                rest_b = play(ctx, fork)
                self.assertEqual(_dicts(rest_a), _dicts(rest_b))
                full = simulate(self.home, self.away, seed=99, match_id="m099")
                self.assertEqual(_dicts(before + rest_a), _dicts(full.events))

    def test_copy_is_independent(self):
        ctx, st, _ = self._midmatch(400)
        snapshot = st.copy()
        fork = st.copy()
        fork.score[0] += 3
        fork.on[0][5] = -1
        fork.fatigue[1][3] = 1.0
        fork.tactics[0]["press"] = 0.0
        play(ctx, fork)
        self.assertEqual(st, snapshot)


if __name__ == "__main__":
    unittest.main()
