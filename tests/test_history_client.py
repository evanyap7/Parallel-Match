"""The Historian's MCP path: live over streamable HTTP, and the fallback."""

import importlib
import os
import socket
import subprocess
import sys
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    import mcp  # noqa: F401
    HAS_MCP = True
except ImportError:  # pragma: no cover
    HAS_MCP = False


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _client(url: str):
    os.environ["PM_HISTORY_MCP_URL"] = url
    from agents import history_client
    return importlib.reload(history_client)


@unittest.skipUnless(HAS_MCP, "mcp not installed")
class HistoryClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        env = {**os.environ, "PM_MCP_HTTP": "1", "PM_MCP_HOST": "127.0.0.1",
               "PM_MCP_PORT": str(cls.port)}
        cls.proc = subprocess.Popen([sys.executable, "-m", "mcp_history.server"], cwd=REPO,
                                    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 60
        while time.time() < deadline:
            with socket.socket() as s:
                if s.connect_ex(("127.0.0.1", cls.port)) == 0:
                    break
            time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(10)
        os.environ.pop("PM_HISTORY_MCP_URL", None)

    def test_fetches_through_mcp_with_same_numbers(self):
        hc = _client(f"http://127.0.0.1:{self.port}/mcp")
        block, via = hc.precedent("m052", "m052-0715")
        self.assertEqual(via, "mcp")
        from mcp_history.precedent import history_for
        self.assertEqual(block["n"], history_for("m052", "m052-0715")["n"])

    def test_non_call_is_none_over_mcp(self):
        hc = _client(f"http://127.0.0.1:{self.port}/mcp")
        self.assertEqual(hc.precedent("m052", "m052-0001"), (None, "mcp"))

    def test_unreachable_server_falls_back(self):
        hc = _client(f"http://127.0.0.1:{_free_port()}/mcp")
        block, via = hc.precedent("m052", "m052-0715")
        self.assertEqual(via, "in-process")
        self.assertEqual(block["n"], 21)
        self.assertTrue(hc.status()["mcp_last_error"])

    def test_no_url_uses_in_process(self):
        hc = _client("")
        self.assertEqual(hc.precedent("m052", "m052-0715")[1], "in-process")


if __name__ == "__main__":
    unittest.main()
