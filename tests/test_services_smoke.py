"""Smoke tests for the FastAPI agents service and the MCP history server.

Skipped when the optional dependencies (fastapi / mcp) are not installed,
so the core suite runs dependency-free.
"""

import json
import os
import unittest

from tests.fixture_ids import FOUL

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from fastapi.testclient import TestClient
    HAS_FASTAPI = True
except ImportError:  # pragma: no cover
    HAS_FASTAPI = False

try:
    import mcp_history.server as mcp_server  # noqa: F401
    HAS_MCP = True
except ImportError:  # pragma: no cover
    HAS_MCP = False


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class AgentsServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from agents.server import app
        cls.client = TestClient(app)

    def test_health(self):
        body = self.client.get("/health").json()
        self.assertEqual(body["status"], "ok")
        self.assertIn("season", body)
        self.assertIn("matches", body["season"])

    def test_explain(self):
        body = self.client.post("/explain",
                                json={"match_id": "m012", "event_id": FOUL}).json()
        self.assertIn("Law 12", body["text"])
        self.assertEqual(body["event_id"], FOUL)

    def test_explain_404_for_unknown_event(self):
        status = self.client.post("/explain",
                                  json={"match_id": "m012", "event_id": "nope"}).status_code
        self.assertEqual(status, 404)

    def test_precedents(self):
        body = self.client.post("/precedents",
                                json={"match_id": "m012", "event_id": FOUL}).json()
        self.assertIn("n", body["history"])
        self.assertTrue(body["text"])

    def test_precedents_with_fork_matches_fork_history(self):
        fork = json.load(open(os.path.join(REPO, "fixtures", "fork_m052.json")))
        body = self.client.post("/precedents", json={
            "match_id": fork["match_id"], "event_id": fork["event_id"],
            "fork_response": fork}).json()
        self.assertEqual(body["history"]["n"], fork["history"]["n"])
        self.assertEqual(body["agrees_with_simulation"],
                         fork["history"]["agrees_with_simulation"])

    def test_precedents_rejects_fork_for_other_moment(self):
        fork = json.load(open(os.path.join(REPO, "fixtures", "fork_m052.json")))
        status = self.client.post("/precedents", json={
            "match_id": "m012", "event_id": FOUL, "fork_response": fork}).status_code
        self.assertEqual(status, 422)

    def test_cors_allows_hosted_front_end(self):
        r = self.client.options("/narrate", headers={
            "Origin": "https://pm-web.example.azurecontainerapps.io",
            "Access-Control-Request-Method": "POST"})
        self.assertEqual(r.status_code, 200)
        self.assertIn(r.headers.get("access-control-allow-origin"), ("*",
                      "https://pm-web.example.azurecontainerapps.io"))

    def test_narrate(self):
        fork = json.load(open(os.path.join(REPO, "fixtures", "fork_m012.json")))
        body = self.client.post("/narrate", json={"fork_response": fork}).json()
        self.assertEqual(len(body["script"]), 4)

    def test_parse(self):
        body = self.client.post("/parse", json={
            "text": "what if it wasn't a foul",
            "match_id": "m012", "event_id": FOUL}).json()
        self.assertTrue(body["ok"], body)
        self.assertEqual(body["request"]["change"]["call"], "no_foul")


@unittest.skipUnless(HAS_MCP, "mcp not installed")
class McpServerTests(unittest.TestCase):
    def test_history_query_tool(self):
        result = mcp_server.history_query("m012", FOUL)
        self.assertIn("when_given", result)
        self.assertGreater(result["n"], 0)

    def test_history_query_matches_fork_history(self):
        fork = json.load(open(os.path.join(REPO, "fixtures", "fork_m052.json")))
        result = mcp_server.history_query(fork["match_id"], fork["event_id"])
        self.assertEqual(result["n"], fork["history"]["n"])
        self.assertEqual(result["history_shift_att_win"],
                         fork["history"]["history_shift_att_win"])

    def test_history_query_unknown_event_tool(self):
        result = mcp_server.history_query("m012", "m012-9999")
        self.assertIn("error", result)

    def test_season_summary_tool(self):
        summary = mcp_server.season_summary()
        self.assertEqual(summary["matches"], 90)
        self.assertIn("contestable_moments", summary)


if __name__ == "__main__":
    unittest.main()
