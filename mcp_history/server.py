"""MCP server exposing the season history query as a tool.

The Historian agent calls the same HistoryStore in process; any other MCP
client (including an agent-framework Agent via MCPStreamableHTTPTool) can
reach it here. The tool returns computed facts only - no phrasing, no
invented numbers.

Run stdio (default):            python -m mcp_history.server
Run streamable-http (deploy):   PM_MCP_HTTP=1 python -m mcp_history.server
  then the endpoint is http://0.0.0.0:8080/mcp
"""

from __future__ import annotations

import os

try:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP
except ImportError:  # mcp 2.x renamed FastMCP to MCPServer
    from mcp.server.mcpserver import MCPServer as FastMCP

from .store import default_store

mcp = FastMCP("parallel-match-history")


def _store():
    return default_store(
        os.environ.get("PM_FIXTURES_DIR", "fixtures"),
        os.environ.get("PM_HISTORY_DIR", "data/dev_season"),
    )


@mcp.tool()
def history_query(match_id: str, event_id: str, limit: int = 8) -> dict:
    """Comparable contestable moments from the recorded season.

    Given a contestable moment (contact decisions under Law 12, or offside
    margin decisions under Law 11), returns the closest comparable moments,
    each with its closeness, the call made, and whether the benefiting team
    scored within 15 minutes - plus aggregate stats. All numbers are
    computed by plain code; no estimation.
    """
    result = _store().query(match_id, event_id, limit=limit)
    if result is None:
        return {"error": f"no contestable family moment '{event_id}' in match '{match_id}'"}
    return result.to_dict()


@mcp.tool()
def season_summary() -> dict:
    """What the recorded season holds: matches, events, contestable moments."""
    return _store().season_summary()


def main() -> None:
    if os.environ.get("PM_MCP_HTTP"):
        host = os.environ.get("PM_MCP_HOST", "127.0.0.1")
        port = int(os.environ.get("PM_MCP_PORT", "8080"))
        try:  # mcp 2.x: run() forwards transport kwargs
            mcp.run(transport="streamable-http", host=host, port=port)
        except TypeError:  # mcp 1.x: host/port live on settings
            mcp.settings.host = host
            mcp.settings.port = port
            mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
