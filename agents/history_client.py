"""Precedent for the Historian, fetched through the MCP history server.

When PM_HISTORY_MCP_URL is set (deployment: the pm-history-mcp app's /mcp
endpoint), the Historian calls the `history_query` MCP tool over streamable
HTTP, so the agent really uses MCP for its facts. If the server is slow,
cold or down, it falls back to the same function in process
(parallel_match.history.history_for), so the numbers are identical either way
and the card never breaks. Every response says which path answered.
"""

from __future__ import annotations

import asyncio
import json
import os

from mcp_history.precedent import history_for

MCP_URL = os.environ.get("PM_HISTORY_MCP_URL", "").strip()
MCP_TIMEOUT_S = float(os.environ.get("PM_HISTORY_MCP_TIMEOUT_S", "8"))

_last_error: str | None = None


def _client():
    """Streamable-HTTP client context manager across mcp 1.x and 2.x."""
    try:  # mcp 2.x
        from mcp.client.streamable_http import streamable_http_client as c
    except ImportError:  # mcp 1.x
        from mcp.client.streamable_http import streamablehttp_client as c
    return c


def _decode(result) -> dict | None:
    """The tool's dict, from structured content or the JSON text block."""
    structured = getattr(result, "structuredContent", None) or getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        # FastMCP wraps non-object returns as {"result": ...}; ours is a dict.
        return structured.get("result", structured) if set(structured) == {"result"} else structured
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text:
            return json.loads(text)
    return None


async def _call(url: str, match_id: str, event_id: str) -> dict | None:
    from mcp import ClientSession

    async with _client()(url) as streams:
        read, write = streams[0], streams[1]
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "history_query", {"match_id": match_id, "event_id": event_id})
    if getattr(result, "isError", False):
        raise RuntimeError(f"history_query failed: {_decode(result)}")
    data = _decode(result)
    if data is None:
        raise RuntimeError("history_query returned no content")
    if "error" in data:   # not a contestable call: same meaning as None
        return None
    return data


def precedent(match_id: str, event_id: str) -> tuple[dict | None, str]:
    """(history block or None, source). Source is "mcp" or "in-process"."""
    global _last_error
    if MCP_URL:
        try:
            block = asyncio.run(asyncio.wait_for(_call(MCP_URL, match_id, event_id), MCP_TIMEOUT_S))
            _last_error = None
            return block, "mcp"
        except Exception as exc:  # cold start, network, server down: stay up
            while isinstance(exc, BaseExceptionGroup) and exc.exceptions:  # anyio task groups
                exc = exc.exceptions[0]
            _last_error = f"{type(exc).__name__}: {str(exc)[:200]}"
    return history_for(match_id, event_id), "in-process"


def status() -> dict:
    """For /health."""
    return {"mcp_url": MCP_URL or None, "mcp_last_error": _last_error}
