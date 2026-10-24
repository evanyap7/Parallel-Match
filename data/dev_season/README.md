Dev-season history for the Historian agent and the MCP server.

Generated: `python3 tools/make_dev_season.py 10` (seeds 1-10, HAR vs NOR,
compact JSON, same schema as `fixtures/m012.json`). Deterministic: the same
seeds regenerate the same matches.

Stand-in for Evan's curated 90-match season. The HistoryStore reads whatever
match JSON lands here (`PM_HISTORY_DIR`); replacing these files replaces the
season, no code changes.
