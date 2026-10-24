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


if __name__ == "__main__":
    unittest.main()
