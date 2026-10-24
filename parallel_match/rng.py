"""Counter-based deterministic RNG.

Every simulation step draws from its own stream keyed by (seed, step). The
match state therefore only needs to carry two integers to be fully
reproducible, and an original run and a forked run share the same random
numbers step for step until their states diverge (common random numbers).
"""

import math

_M = (1 << 64) - 1
_GOLDEN = 0x9E3779B97F4A7C15
_TWO53 = 9007199254740992.0


def _mix(z: int) -> int:
    """splitmix64 finalizer."""
    z = (z + _GOLDEN) & _M
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _M
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _M
    return z ^ (z >> 31)


def hash_unit(*keys: int) -> float:
    """Hash any number of ints to a float in [0, 1). Stateless."""
    h = 0x6A09E667F3BCC909
    for k in keys:
        h = _mix(h ^ (k & _M))
    return (h >> 11) / _TWO53


class Rng:
    __slots__ = ("_key", "_n")

    def __init__(self, seed: int, stream: int):
        self._key = _mix(_mix(seed & _M) ^ (stream & _M))
        self._n = 0

    def u(self) -> float:
        self._n += 1
        return (_mix((self._key + self._n * _GOLDEN) & _M) >> 11) / _TWO53

    def uniform(self, a: float, b: float) -> float:
        return a + (b - a) * self.u()

    def normal(self, mu: float = 0.0, sd: float = 1.0) -> float:
        # Always consumes exactly two draws so streams stay aligned.
        u1 = max(self.u(), 1e-12)
        u2 = self.u()
        return mu + sd * math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

    def chance(self, p: float) -> bool:
        return self.u() < p


def key_of(*keys: int) -> int:
    """Precompute a 64-bit key; pair with keyed_unit for one-mix lookups."""
    h = 0x6A09E667F3BCC909
    for k in keys:
        h = _mix(h ^ (k & _M))
    return h


def keyed_unit(key: int, n: int) -> float:
    """Fast stateless uniform for (key, n): a single mix."""
    return (_mix((key + n * _GOLDEN) & _M) >> 11) / _TWO53


def pick_index(weights, r: float) -> int:
    """Pick an index proportionally to weights using a pre-drawn uniform r."""
    total = sum(weights)
    if total <= 0:
        return 0
    target = r * total
    acc = 0.0
    for i, w in enumerate(weights):
        acc += w
        if target < acc:
            return i
    return len(weights) - 1
