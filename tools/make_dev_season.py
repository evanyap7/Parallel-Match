"""Generate the dev-season history for the Historian agent and MCP server.

Writes data/dev_season/mNNN.json for seeds 1..N (compact JSON, same schema
as fixtures/m012.json). Stand-in for Evan's curated 90-match season; the
HistoryStore swaps it out without code changes because it only reads match
JSON files.

Usage: python3 tools/make_dev_season.py [n_matches] [out_dir]
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parallel_match.sim import simulate  # noqa: E402
from parallel_match.teams import build_league, club_by_code  # noqa: E402


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "data/dev_season"
    os.makedirs(out_dir, exist_ok=True)
    clubs = build_league()
    home, away = club_by_code(clubs, "HAR"), club_by_code(clubs, "NOR")
    for seed in range(1, n + 1):
        rec = simulate(home, away, seed, f"m{seed:03d}")
        path = os.path.join(out_dir, f"m{seed:03d}.json")
        with open(path, "w") as fh:
            json.dump(rec.to_dict(), fh, separators=(",", ":"))
        print(f"seed {seed}: {rec.score[0]}-{rec.score[1]} -> {path}")


if __name__ == "__main__":
    main()
