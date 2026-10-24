"""Historian agent: precedent from the league's own recorded season.

Every number comes from `mcp_history.precedent.history_for` - the same
precedent block POST /fork returns - so the Historian card and the simulation
card can never cite two different counts. The same query is exposed as an MCP
tool (`history_query` in mcp_history/server.py).

Given a fork response as well, the Historian also states the simulation's
estimate next to precedent's, and says plainly when the two disagree.
"""

from __future__ import annotations

from . import prompts
from .facts import canonical, club_name
from .provider import ChatProvider, TemplateProvider, phrase


def _pct(x) -> int | None:
    """Share as a whole percentage, rounding halves up (0.125 -> 13)."""
    if not isinstance(x, (int, float)):
        return None
    v = x * 100
    return int(v + 0.5) if v >= 0 else -int(-v + 0.5)


def _points(x) -> int | None:
    """Share difference as signed percentage points."""
    return _pct(x)


def build_facts(match: dict | None, event: dict | None, block: dict) -> dict:
    given, not_given = block.get("when_given") or {}, block.get("when_not_given") or {}
    facts = {
        "match_id": (match or {}).get("match_id"),
        "event_id": (event or {}).get("id"),
        "n": block.get("n", 0),
        "description": block.get("description", ""),
        "attacking_team": club_name(block.get("attacking_team", "")),
        "given_n": given.get("n", 0),
        "given_win_pct": _pct(given.get("win")),
        "given_goal10_pct": _pct(given.get("goal_10")),
        "not_given_n": not_given.get("n", 0),
        "not_given_win_pct": _pct(not_given.get("win")),
        "not_given_goal10_pct": _pct(not_given.get("goal_10")),
        "history_shift_pts": _points(block.get("history_shift_att_win")),
        "sim_shift_pts": _points(block.get("sim_shift_att_win")),
        "agrees_with_simulation": block.get("agrees_with_simulation"),
        "goal_window_min": 10,      # parallel_match.history.WINDOW_S // 60
        "min_cases": 5,             # both groups need this many for an estimate
    }
    for key in ("history_shift_pts", "sim_shift_pts"):
        if facts[key] is not None:
            facts[key + "_abs"] = abs(facts[key])
    # keep the raw block for grounding checks
    facts["_truth"] = canonical(block)
    return facts


def _signed(points: int) -> str:
    if points == 0:
        return "no change in"
    return f"{abs(points)} points {'up' if points > 0 else 'down'} on"


def template(facts: dict) -> str:
    n = facts["n"]
    if n == 0:
        return (
            "No comparable moment exists in the recorded season for this "
            "decision (same family, zone, score state and minute band), so "
            "there is no precedent to cite either way."
        )
    team = facts["attacking_team"]
    desc = facts["description"]
    parts = [f"Precedent: {desc}."
             if desc else f"Precedent: {n} comparable moments in the recorded season."]
    for label, k in (("given", "given"), ("not given", "not_given")):
        cnt = facts[f"{k}_n"]
        if cnt:
            parts.append(
                f"When the call was {label} ({cnt} case{'s' if cnt != 1 else ''}), "
                f"the attacking side won {facts[f'{k}_win_pct']}% of those matches and "
                f"scored within 10 minutes {facts[f'{k}_goal10_pct']}% of the time."
            )
        else:
            parts.append(f"No comparable case has the call {label}.")
    hist = facts["history_shift_pts"]
    if hist is None:
        parts.append(
            "One side has fewer than 5 cases, so precedent gives no estimate "
            "of what flipping this call does."
        )
    else:
        parts.append(
            f"Precedent puts flipping this call at {_signed(hist)} the win share for {team}."
        )
    sim = facts["sim_shift_pts"]
    if sim is not None:
        parts.append(f"The paired simulation puts it at {_signed(sim)} the win share.")
        agrees = facts["agrees_with_simulation"]
        if agrees is False:
            parts.append(
                "These disagree: precedent compares different matches, while "
                "the simulation replays this one with only the call changed."
            )
        elif agrees is True:
            parts.append("The two estimates point the same way.")
    return " ".join(parts)


def run(match: dict | None, event: dict | None, block: dict,
        provider: ChatProvider | None = None) -> dict:
    facts = build_facts(match, event, block)
    text, fell_back = phrase(
        provider or TemplateProvider(),
        prompts.HISTORIAN,
        facts,
        template(facts),
    )
    return {
        "match_id": facts["match_id"],
        "event_id": facts["event_id"],
        "history": block,
        "agrees_with_simulation": block.get("agrees_with_simulation"),
        "text": text,
        "facts": facts,
        "fell_back": fell_back,
    }
