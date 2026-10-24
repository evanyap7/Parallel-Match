"""Smoke tests for the FastAPI agents service and the MCP history server.

Skipped when the optional dependencies (fastapi / mcp) are not installed,
so the core suite runs dependency-free.
"""

import json
import os
import unittest

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
                                json={"match_id": "m012", "event_id": "m012-0148"}).json()
        self.assertIn("Law 12", body["text"])
        self.assertEqual(body["event_id"], "m012-0148")

    def test_explain_404_for_unknown_event(self):
        status = self.client.post("/explain",
                                  json={"match_id": "m012", "event_id": "nope"}).status_code
        self.assertEqual(status, 404)

    def test_precedents(self):
        body = self.client.post("/precedents",
                                json={"match_id": "m012", "event_id": "m012-0148"}).json()
        self.assertIn("n", body["stats"])
        self.assertTrue(body["text"])

    def test_narrate(self):
        fork = json.load(open(os.path.join(REPO, "fixtures", "fork_m012.json")))
        body = self.client.post("/narrate", json={"fork_response": fork}).json()
        self.assertEqual(len(body["script"]), 4)

    def test_parse(self):
        body = self.client.post("/parse", json={
            "text": "what if it wasn't a foul",
            "match_id": "m012", "event_id": "m012-0148"}).json()
        self.assertTrue(body["ok"], body)
        self.assertEqual(body["request"]["change"]["call"], "no_foul")


@unittest.skipUnless(HAS_MCP, "mcp not installed")
class McpServerTests(unittest.TestCase):
    def test_history_query_tool(self):
        result = mcp_server.history_query("m012", "m012-0148")
        self.assertIn("stats", result)
        self.assertGreater(result["stats"]["n"], 0)

    def test_history_query_unknown_event_tool(self):
        result = mcp_server.history_query("m012", "m012-9999")
        self.assertIn("error", result)

    def test_season_summary_tool(self):
        summary = mcp_server.season_summary()
        self.assertGreaterEqual(summary["matches"], 1)
        self.assertIn("contestable_moments", summary)


if __name__ == "__main__":
    unittest.main()
