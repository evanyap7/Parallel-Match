"""MCP server exposing season precedent as tools.

The Historian agent calls the same `history_for` in process; any other MCP
client (including an Agent Framework agent via MCPStreamableHTTPTool) can
reach it here. Tools return computed facts only - no phrasing, no invented
numbers - and the precedent numbers are the same ones POST /fork returns.

Run stdio (default):            python -m mcp_history.server
Run streamable-http (deploy):   PM_MCP_HTTP=1 python -m mcp_history.server
  then the endpoint is http://<host>:8080/mcp
"""

from __future__ import annotations

import os

try:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP
except ImportError:  # mcp 2.x renamed FastMCP to MCPServer
    from mcp.server.mcpserver import MCPServer as FastMCP

from .precedent import history_for, source
from .store import default_store

mcp = FastMCP("parallel-match-history")


@mcp.tool()
def history_query(match_id: str, event_id: str) -> dict:
    """Precedent for one contestable call in the league's recorded season.

    Finds comparable borderline decisions (same family - foul or offside -
    same pitch zone, score state and minute band) and splits them by whether
    the call was given, with the attacking team's win share and its chance
    of scoring within 10 minutes in each group. `history_shift_att_win` is
    precedent's estimate of what flipping this call does to the attacking
    team's win share (null when either group has fewer than 5 cases). Same
    numbers as the `history` block of POST /fork. Plain code; no estimation.
    """
    block = history_for(match_id, event_id)
    if block is None:
        return {"error": f"'{event_id}' in match '{match_id}' is not a contestable call"}
    return block


@mcp.tool()
def season_summary() -> dict:
    """What the recorded season holds: matches, events, contestable moments."""
    return {**default_store().season_summary(), "precedent_source": source()}


def main() -> None:
    if os.environ.get("PM_MCP_HTTP"):
        host = os.environ.get("PM_MCP_HOST", "127.0.0.1")
        port = int(os.environ.get("PM_MCP_PORT", "8080"))
        default_store()  # replay the season before taking traffic
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
