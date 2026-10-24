import unittest

try:
    from fastapi.testclient import TestClient

    from parallel_match.api import app
except ImportError:  # API extras not installed: pip install -r requirements-api.txt httpx
    TestClient = None


@unittest.skipIf(TestClient is None, "fastapi/httpx not installed")
class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_season_endpoints(self):
        c = self.client
        self.assertEqual(c.get("/health").json()["ok"], True)
        self.assertEqual(len(c.get("/clubs").json()), 10)
        ms = c.get("/matches").json()
        self.assertEqual(len(ms), 90)
        self.assertEqual(len(c.get("/standings").json()), 10)
        m = c.get(f"/match/{ms[0]['match_id']}").json()
        self.assertGreater(len(m["events"]), 1000)
        self.assertEqual(c.get("/match/nope").status_code, 404)

    def test_fork_round_trip(self):
        c = self.client
        mid = c.get("/matches").json()[0]["match_id"]
        moment = next(m for m in c.get(f"/moments/{mid}").json() if m["type"] == "foul")
        r = c.post("/fork", json={"match_id": mid, "event_id": moment["id"],
                                  "change": {"type": "flip_call"}, "rollouts": 10})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        for key in ("divergence", "original", "alternate", "outcome_shift", "uncertainty", "history"):
            self.assertIn(key, body)
        self.assertTrue(body["model_world"])
        bad = c.post("/fork", json={"match_id": mid, "event_id": moment["id"],
                                    "change": {"type": "teleport"}, "rollouts": 10})
        self.assertEqual(bad.status_code, 422)

    def test_one_precedent_source(self):
        """The fork's history block, GET /history and history_for() agree,
        live and cached."""
        from parallel_match.history import history_for

        c = self.client
        story = next(m for m in c.get("/matches").json() if m["story"] == "penalty_drama")
        mid = story["match_id"]
        pen = next(e for e in c.get(f"/match/{mid}").json()["events"]
                   if e["type"] == "foul" and e["call"] == "penalty")
        direct = history_for(mid, pen["id"])
        via_get = c.get(f"/history/{mid}/{pen['id']}").json()
        self.assertEqual(via_get, direct)
        for rollouts in (10, 500):  # 10 runs live; 500 may come from the precomputed cache
            body = c.post("/fork", json={"match_id": mid, "event_id": pen["id"],
                                         "change": {"type": "flip_call"}, "rollouts": rollouts}).json()
            for key, value in direct.items():
                self.assertEqual(body["history"][key], value, key)
        self.assertEqual(c.get(f"/history/{mid}/{mid}-9999").status_code, 404)


if __name__ == "__main__":
    unittest.main()
