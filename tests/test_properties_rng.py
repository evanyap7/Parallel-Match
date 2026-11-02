"""Property tests for the counter-based RNG."""

import unittest

from hypothesis import given, strategies as st

from parallel_match import rng
from tests import pbt_settings  # noqa: F401  (loads the Hypothesis profile)

ints = st.integers(min_value=-(1 << 70), max_value=1 << 70)
weights = st.lists(st.floats(min_value=0.0, max_value=1e9, allow_nan=False), min_size=1, max_size=30)
unit = st.floats(min_value=0.0, max_value=1.0, exclude_max=True)


class HashUnitTest(unittest.TestCase):
    @given(st.lists(ints, max_size=8))
    def test_in_unit_interval(self, keys):
        self.assertTrue(0.0 <= rng.hash_unit(*keys) < 1.0)

    @given(st.lists(ints, max_size=8))
    def test_stateless(self, keys):
        self.assertEqual(rng.hash_unit(*keys), rng.hash_unit(*keys))

    @given(ints, ints)
    def test_keyed_unit_in_unit_interval(self, key, n):
        k = rng.key_of(key)
        self.assertTrue(0.0 <= rng.keyed_unit(k, n) < 1.0)

    @given(st.lists(ints, min_size=1, max_size=6))
    def test_key_of_is_deterministic_and_64_bit(self, keys):
        k = rng.key_of(*keys)
        self.assertEqual(k, rng.key_of(*keys))
        self.assertTrue(0 <= k < (1 << 64))


class StreamTest(unittest.TestCase):
    @given(ints, ints, st.integers(1, 50))
    def test_same_seed_and_stream_replays(self, seed, stream, n):
        a, b = rng.Rng(seed, stream), rng.Rng(seed, stream)
        self.assertEqual([a.u() for _ in range(n)], [b.u() for _ in range(n)])

    @given(ints, ints, st.integers(1, 50))
    def test_draws_in_unit_interval(self, seed, stream, n):
        r = rng.Rng(seed, stream)
        for _ in range(n):
            self.assertTrue(0.0 <= r.u() < 1.0)

    @given(ints, ints, st.integers(1, 40))
    def test_stream_matches_keyed_unit(self, seed, stream, n):
        r = rng.Rng(seed, stream)
        key = r._key
        for i in range(1, n + 1):
            self.assertEqual(r.u(), rng.keyed_unit(key, i))

    @given(ints, ints, st.integers(0, 30))
    def test_normal_consumes_exactly_two_draws(self, seed, stream, warmup):
        a, b = rng.Rng(seed, stream), rng.Rng(seed, stream)
        for _ in range(warmup):
            a.u(), b.u()
        a.normal()
        b.u(), b.u()
        self.assertEqual(a.u(), b.u())

    @given(ints, ints, st.floats(-1e6, 1e6), st.floats(0.0, 1e6))
    def test_normal_is_finite(self, seed, stream, mu, sd):
        v = rng.Rng(seed, stream).normal(mu, sd)
        self.assertEqual(v, v)
        self.assertNotIn(v, (float("inf"), float("-inf")))

    @given(ints, ints, st.floats(-1e6, 1e6), st.floats(-1e6, 1e6))
    def test_uniform_stays_between_bounds(self, seed, stream, a, b):
        lo, hi = min(a, b), max(a, b)
        v = rng.Rng(seed, stream).uniform(lo, hi)
        self.assertTrue(lo <= v <= hi)

    @given(ints, ints)
    def test_chance_extremes_are_exact(self, seed, stream):
        self.assertFalse(rng.Rng(seed, stream).chance(0.0))
        self.assertTrue(rng.Rng(seed, stream).chance(1.0))


class PickIndexTest(unittest.TestCase):
    @given(weights, unit)
    def test_index_is_valid(self, w, r):
        self.assertTrue(0 <= rng.pick_index(w, r) < len(w))

    @given(weights, unit)
    def test_never_picks_zero_weight_unless_all_zero(self, w, r):
        i = rng.pick_index(w, r)
        if sum(w) > 0 and i != len(w) - 1:
            self.assertGreater(w[i], 0.0)

    @given(st.integers(1, 30), unit)
    def test_all_zero_weights_pick_first(self, n, r):
        self.assertEqual(rng.pick_index([0.0] * n, r), 0)

    @given(weights, unit, unit)
    def test_monotone_in_r(self, w, r1, r2):
        lo, hi = sorted((r1, r2))
        self.assertLessEqual(rng.pick_index(w, lo), rng.pick_index(w, hi))


if __name__ == "__main__":
    unittest.main()
