"""The real season, loaded once per process for the agents and MCP services.

`parallel_match.season.match_dicts()` replays all 90 matches from their seeds
(a few seconds), giving the same match JSON as GET /match/{id}. Loaded once
and cached. This replaces `data/dev_season` (10 matches from the older
simulator), so every match the simulator serves is also known to the agents.
"""

from __future__ import annotations

import threading
from functools import lru_cache

from parallel_match import season

_lock = threading.Lock()


@lru_cache(maxsize=1)
def _load() -> list[dict]:
    return season.match_dicts()


def season_matches() -> list[dict]:
    """All 90 season matches as dicts (cached; thread-safe first load)."""
    with _lock:
        return _load()
