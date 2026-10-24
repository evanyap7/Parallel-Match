"""MCP history server package. See mcp_history/server.py."""

from .precedent import history_for
from .store import HistoryStore, default_store

__all__ = ["HistoryStore", "default_store", "history_for"]
