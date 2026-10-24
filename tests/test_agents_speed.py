"""Agents speed: answer cache, concurrent Narrator lines, timing header."""

import json
import os
import threading
import time
import unittest

from agents import cache, narrator
from agents.provider import phrase

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from fastapi.testclient import TestClient
    HAS_FASTAPI = True
except ImportError:  # pragma: no cover
    HAS_FASTAPI = False


def _fork(name="fork_m052"):
    with open(os.path.join(REPO, "fixtures", f"{name}.json")) as fh:
        return json.load(fh)


class SlowProvider:
    """Stands in for a model: 0.3 s per call, records concurrency."""
    name = "slow"

    def __init__(self):
        self.active = 0
        self.peak = 0
        self.lock = threading.Lock()

    def complete(self, system, user):
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        time.sleep(0.3)
        with self.lock:
            self.active -= 1
        # echo the reference phrasing so guardrails pass
        return user.split("without changing any fact or number):\n", 1)[1]


class NarratorConcurrencyTests(unittest.TestCase):
    def test_lines_are_phrased_concurrently_in_order(self):
        p = SlowProvider()
        t0 = time.perf_counter()
        result = narrator.run(_fork(), None, p)
        elapsed = time.perf_counter() - t0
        self.assertEqual([s["timeline"] for s in result["script"]],
                         ["real", "divergence", "alternate", "verdict"])
        self.assertGreater(p.peak, 1)
        self.assertLess(elapsed, 1.0)       # four 0.3 s calls, not 1.2 s in a row
        self.assertFalse(result["fell_back"])


class CacheTests(unittest.TestCase):
    def setUp(self):
        cache.clear()

    def test_put_get_and_stats(self):
        k = cache.key("explain", "m052", "m052-0715")
        self.assertIsNone(cache.get(k))
        cache.put(k, {"text": "x"})
        self.assertEqual(cache.get(k), {"text": "x"})
        self.assertEqual(cache.stats(), {"entries": 1, "hits": 1, "misses": 1})


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class ServerCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from agents.server import app
        cls.client = TestClient(app)

    def setUp(self):
        cache.clear()

    def test_second_answer_is_cached_and_identical(self):
        body = {"match_id": "m052", "event_id": "m052-0715"}
        first = self.client.post("/explain", json=body)
        second = self.client.post("/explain", json=body)
        self.assertFalse(first.json()["cached"])
        self.assertTrue(second.json()["cached"])
        self.assertEqual(first.json()["text"], second.json()["text"])
        self.assertIn("app;dur=", second.headers["server-timing"])

    def test_narrate_cache_ignores_the_request_alias(self):
        fork = _fork()
        plain = self.client.post("/narrate", json={"fork_response": fork}).json()
        alias = {**fork, "request": {"match_id": fork["match_id"],
                                     "event_id": fork["event_id"], "change": fork["change"]}}
        aliased = self.client.post("/narrate", json={"match_id": fork["match_id"],
                                                     "fork_response": alias}).json()
        self.assertFalse(plain["cached"])
        self.assertTrue(aliased["cached"])

    def test_model_fallback_is_not_cached(self):
        from agents import server
        result = {"text": "t", "fell_back": True}
        orig = server._model_backend
        server._model_backend = lambda: True
        try:
            self.assertFalse(server._cacheable(result))
        finally:
            server._model_backend = orig
        self.assertTrue(server._cacheable(result))   # template backend: fine


if __name__ == "__main__":
    unittest.main()
