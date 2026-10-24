"""The single precedent source for the Historian and the MCP tool.

Both call `parallel_match.history.history_for` - the same function behind the
`history` block of POST /fork - so the Historian card, the MCP tool and the
simulation card can never show two different counts.
"""

from __future__ import annotations

from parallel_match import history


def source() -> str:
    """Which implementation answers precedent queries (shown in /health)."""
    return "parallel_match.history.history_for"


def history_for(match_id: str, event_id: str) -> dict | None:
    """Precedent for one contestable moment, or None if it is not a call."""
    return history.history_for(match_id, event_id)


def compare_with_simulation(block: dict, fork_response: dict | None) -> dict:
    """Add the simulation's estimate and whether the two agree, using the same
    rule as /fork. Prefers the fork's own `history` block when present."""
    if not fork_response:
        return dict(block)
    fork_hist = fork_response.get("history") or {}
    if "sim_shift_att_win" in fork_hist:
        return {**block,
                "sim_shift_att_win": fork_hist["sim_shift_att_win"],
                "agrees_with_simulation": fork_hist.get("agrees_with_simulation")}
    shift = fork_response.get("outcome_shift")
    if not shift or "attacking_is_home" not in block:
        return dict(block)
    return history.compare_with_simulation(block, shift)
