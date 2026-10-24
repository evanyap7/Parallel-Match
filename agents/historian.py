"""Historian agent: precedent from the league's own recorded season.

The moment-finding and every number live in mcp_history/store.py. This agent
receives the query result and phrases it. The same history query is exposed
as an MCP tool (mcp_history/server.py); in the Microsoft Agent Framework
deployment the agent holds it as an MCP tool (see docs/agents.md).
"""

from __future__ import annotations

from . import prompts
from .facts import canonical
from .laws import call_phrase
from .provider import ChatProvider, TemplateProvider, phrase


def build_facts(match: dict, event: dict, result) -> dict:
    """Facts from a store.QueryResult (all numbers precomputed)."""
    d = result.to_dict()
    q, stats = d["query"], d["stats"]
    change_beneficiary = q["team"] if q["call"] in ("no_foul", "onside") else q["opponent"]
    facts = {
        "query": {**q, "team_name": q["team"], "opponent_name": q["opponent"]},
        "stats": stats,
        "criteria": d["criteria"],
        "top": [c for c in d["comparables"][:3]],
        "query_call_phrase": call_phrase(q.get("call")),
        "beneficiary": change_beneficiary,
        "n": stats.get("n", 0),
        "n_other": stats.get("n_other_call", 0),
        "n_same": stats.get("n_same_call", 0),
        "share_other_pct": round(stats.get("share_other_call", 0) * 100),
        "n_other_scored": stats.get("n_other_call_scored_within_15m", 0),
        "avg_other": stats.get("avg_goals_by_team_next_15m_when_other_call"),
        # keep the raw truth for grounding checks
        "_truth": canonical(d),
    }
    return facts


def template(facts: dict) -> str:
    n = facts["n"]
    if n == 0:
        return (
            "No comparable moment exists in the recorded season for this "
            "decision family within the query tolerances, so there is no "
            "precedent to cite either way."
        )
    criteria = facts["criteria"]
    if criteria["family"] == "contact":
        tol = f"measured contact within {criteria['contact_tolerance']}"
    else:
        tol = f"an offside margin within {criteria['margin_tolerance_m']} m"
    parts = [
        f"Across the recorded season, {n} moment{'s' if n != 1 else ''} match this one: "
        f"same decision family, {tol}, with pitch zone and clock as tie-breakers."
    ]
    parts.append(
        f"In {facts['n_other']} of them the call went the other way "
        f"({facts['share_other_pct']}%), and in {facts['n_other_scored']} of those "
        f"{facts['n_other']} cases the team that benefited scored inside the next "
        f"15 minutes."
    )
    top = facts["top"]
    if top:
        c = top[0]
        goals = c["goals_by_team_next_15m"]
        goals_text = (f"{goals} goal{'s' if goals != 1 else ''} by that team inside 15 minutes"
                      if goals else "no goal by that team inside 15 minutes")
        parts.append(
            f"Closest precedent: {c['match_id']} at {c['min']}', {c['type']} for "
            f"{c['team']} against {c['opponent']} - {call_phrase(c.get('call'))} "
            f"({goals_text})."
        )
    return " ".join(parts)


def run(match: dict, event: dict, result, provider: ChatProvider | None = None) -> dict:
    facts = build_facts(match, event, result)
    text, fell_back = phrase(
        provider or TemplateProvider(),
        prompts.HISTORIAN,
        facts,
        template(facts),
    )
    return {
        "event_id": event.get("id"),
        "stats": facts["stats"],
        "comparables": facts["top"],
        "text": text,
        "facts": facts,
        "fell_back": fell_back,
    }
