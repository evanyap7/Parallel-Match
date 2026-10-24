"""The real season, loaded once per process for the agents and MCP services.

The 90-match season is defined by `parallel_match/data/season.json`
(fixtures + seeds); every match replays deterministically from its seed.
Replaying all 90 takes a few seconds, so it happens once and is cached.

This replaces `data/dev_season` (10 matches from the older simulator): the
agents, the MCP server and the simulator API now read the same season.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from functools import lru_cache

from parallel_match import history, season


@dataclass(frozen=True)
class SeasonData:
    matches: list[dict]            # match JSON (same shape as GET /match/{id})
    rows: list[dict]               # parallel_match.history.moment_rows for every match
    records: dict                  # match_id -> MatchRecord


_lock = threading.Lock()


@lru_cache(maxsize=1)
def _load() -> SeasonData:
    data = season.load()
    matches, rows, records = [], [], {}
    for m in data["matches"]:
        rec = season.record(data, m["match_id"])
        records[m["match_id"]] = rec
        match = rec.to_dict()          # identical to GET /match/{id}
        match["story"] = m.get("story")
        matches.append(match)
        rows.extend(history.moment_rows(rec))
    return SeasonData(matches=matches, rows=rows, records=records)


def season_data() -> SeasonData:
    """The replayed season (cached; thread-safe first load)."""
    with _lock:
        return _load()
