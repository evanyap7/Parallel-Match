"""The single precedent source for the Historian and the MCP tool.

Agreed contract (docs/REMAINING.md):

    parallel_match.history.history_for(match_id, event_id) -> dict | None

returns the same shape as the `history` block of POST /fork. When that
function exists we call it and nothing else. Until it lands on `main`, the
fallback below computes the block from the *same* functions the simulator API
uses for `/fork` (`moment_rows`, `comparable`, `_rates`) over the real
season, so the numbers already match `/fork` exactly. Delete the fallback
once Evan's wrapper is merged.
"""

from __future__ import annotations

from parallel_match import history

from .season_source import season_data


def source() -> str:
    """Which implementation answers precedent queries (shown in /health)."""
    return "parallel_match.history.history_for" if hasattr(history, "history_for") \
        else "mcp_history.precedent (fallback over parallel_match.history)"


def _fallback(match_id: str, event_id: str) -> dict | None:
    rows = season_data().rows
    target = next((r for r in rows
                   if r["match_id"] == match_id and r["event_id"] == event_id), None)
    if target is None:
        return None
    comp = history.comparable(target, rows)
    given = history._rates([r for r in comp if r["called"]])
    not_given = history._rates([r for r in comp if not r["called"]])
    # Same estimate as history.history_check: effect of flipping this call on
    # the attacking team's win share, only when both sides have >= 5 cases.
    hist = None
    if given["n"] >= 5 and not_given["n"] >= 5:
        d = given["win"] - not_given["win"]
        hist = round(-d if target["called"] else d, 3)
    what = "fouls" if target["family"] == "foul" else "offside decisions"
    return {
        "n": len(comp),
        "description": (f"{len(comp)} comparable borderline {what} this season: "
                        f"{target['zone'].replace('_', ' ')}, same score state, similar minute"),
        "when_given": given,
        "when_not_given": not_given,
        "attacking_team": target["att_team"],
        "called": bool(target["called"]),
        "family": target["family"],
        "history_shift_att_win": hist,
        "note": "Precedent compares different matches, so it carries confounding; "
                "the paired simulation isolates the call. Disagreement is shown, not hidden.",
    }


def history_for(match_id: str, event_id: str) -> dict | None:
    """Precedent for one contestable moment, or None if it is not a call."""
    real = getattr(history, "history_for", None)
    if real is not None:
        return real(match_id, event_id)
    return _fallback(match_id, event_id)


def compare_with_simulation(block: dict, fork_response: dict | None) -> dict:
    """Add the simulation side to a precedent block, using the same rule as
    /fork (history.history_check), so the Historian card can say whether the
    two estimates disagree. Prefers the fork's own `history` block when the
    fork already carries one."""
    out = dict(block)
    if not fork_response:
        return out
    fork_hist = fork_response.get("history") or {}
    if "sim_shift_att_win" in fork_hist:
        out["sim_shift_att_win"] = fork_hist["sim_shift_att_win"]
        out["agrees_with_simulation"] = fork_hist.get("agrees_with_simulation")
        return out
    shift = fork_response.get("outcome_shift") or {}
    att = block.get("attacking_team")
    home = (fork_response.get("match") or {}).get("home")
    if not shift or att is None or home is None:
        return out
    sim = shift["home"] if att == home else shift["away"]
    hist = block.get("history_shift_att_win")
    out["sim_shift_att_win"] = round(sim, 3)
    out["agrees_with_simulation"] = None if hist is None else (
        abs(sim - hist) < 0.08 or (sim > 0) == (hist > 0))
    return out
