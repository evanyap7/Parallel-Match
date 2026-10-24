"""Event ids in the committed fixtures, looked up by kind rather than hardcoded,
so agent tests keep working when the fixtures are regenerated from the season."""

import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(REPO, "fixtures", "m012.json")) as _fh:
    M012 = json.load(_fh)
with open(os.path.join(REPO, "fixtures", "fork_m012.json")) as _fh:
    FORK_M012 = json.load(_fh)

_BY_ID = {e["id"]: e for e in M012["events"]}


def _first(pred) -> str:
    return next(e["id"] for e in M012["events"] if pred(e))


def event(event_id: str) -> dict:
    return _BY_ID[event_id]


# A borderline foul given as a free kick (contact near the referee threshold).
FOUL = _first(lambda e: e["type"] == "foul" and e.get("call") == "free_kick"
              and e.get("contestable") and abs(e["margin"]) < 0.05)
# A flagged offside with the attacker beyond the line.
OFFSIDE = _first(lambda e: e["type"] == "offside" and e["margin"] > 0)
# A borderline challenge where play went on.
NO_FOUL = _first(lambda e: e["type"] == "tackle" and e.get("call") == "no_foul")


def score_text(score) -> str:
    return f"{score[0]}-{score[1]}"
