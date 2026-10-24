"""Fact bundles: the only data agents are allowed to phrase.

Every agent function takes facts built here by plain code and turns them into
prose. Facts carry every number the output may contain, so a grounded agent
output can be validated mechanically (see guardrails.py).
"""

from __future__ import annotations

import json

try:  # club display names live in the simulator package (plain data)
    from parallel_match.teams import build_league

    _CLUB_NAMES = {c.code: c.name for c in build_league()}
except Exception:  # pragma: no cover - simulator package not importable
    _CLUB_NAMES = {}


def club_name(code: str) -> str:
    return _CLUB_NAMES.get(code, code)


def moment_facts(match: dict, event: dict) -> dict:
    """Compact, phrasing-ready summary of one event with match context."""
    team = event.get("team", match["home"])
    opponent = match["away"] if team == match["home"] else match["home"]
    facts = {
        "match_id": match["match_id"],
        "home": club_name(match["home"]),
        "away": club_name(match["away"]),
        "min": event.get("min", ""),
        "type": event.get("type", ""),
        "team": club_name(team),
        "opponent": club_name(opponent),
        "player": event.get("player", ""),
        "call": event.get("call"),
        "contact": event.get("contact"),
        "margin": event.get("margin"),
        "offside_margin": event.get("offside_margin"),
        "law": event.get("law", ""),
        "score_at": list(event.get("score", [0, 0])),
        "card_color": event.get("color"),
        "contestable": bool(event.get("contestable")),
    }
    return {k: v for k, v in facts.items() if v is not None}


def fork_facts(fork_response: dict) -> dict:
    """Facts from a POST /fork response (see fixtures/fork_m012.json)."""
    req = fork_response.get("request", {})
    div = fork_response.get("divergence", {})
    moment = fork_response.get("moment", {})
    original = fork_response.get("original", {})
    alternate = fork_response.get("alternate", {})

    def _last_winprob(side: dict) -> dict | None:
        series = side.get("win_prob") or []
        return series[-1] if series else None

    return {
        "match_id": req.get("match_id", ""),
        "event_id": req.get("event_id", ""),
        "change": req.get("change", {}),
        "divergence_min": div.get("min", ""),
        "moment_type": moment.get("type", ""),
        "moment_call": moment.get("call"),
        "moment_contact": moment.get("contact"),
        "moment_margin": moment.get("margin"),
        "original_final_score": list(original.get("final_score", [0, 0])),
        "alternate_final_score": list(alternate.get("final_score", [0, 0])),
        "original_last_winprob": _last_winprob(original),
        "alternate_last_winprob": _last_winprob(alternate),
        "placeholder": bool(fork_response.get("placeholder")),
    }


def canonical(facts: dict) -> str:
    """Single string containing every fact value, for grounding checks."""
    return json.dumps(facts, sort_keys=True, default=str)
