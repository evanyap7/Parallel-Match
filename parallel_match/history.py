"""Precedent from the league's own history: an estimate independent of the
Monte Carlo rollouts.

Every contestable decision in the season becomes a row with its context
(family, zone, minute, score state, margin) and what happened next for the
attacking team. For a fork, we find comparable decisions, split them by
whether the call was given, and compare the attacking team's results. The
same query runs in Fabric over moments.csv (see docs/history-query.md).
"""

from .rules import PITCH_L, in_penalty_area

BORDERLINE = 0.15  # |margin| for a comparable decision (contact units or metres)
WINDOW_S = 600     # "next 10 minutes"


def _family_and_call(e: dict):
    """(family, called) for a contestable decision, else None."""
    ty = e["type"]
    if ty == "foul":
        return "foul", True
    if ty in ("tackle", "dribble") and e.get("call") == "no_foul":
        return "foul", False
    if ty == "offside":
        return "offside", True
    if ty == "pass" and e.get("call") == "onside":
        return "offside", False
    return None


def _attacking_team(e: dict, home: str, away: str) -> str:
    """The side the decision is for or against in attack: fouls and tackles are
    recorded on the defending team, everything else on the attacking team."""
    if e["type"] in ("foul", "tackle"):
        return away if e["team"] == home else home
    return e["team"]


def moment_rows(rec) -> list[dict]:
    events = [e.to_dict() for e in rec.events]
    home, away = rec.home, rec.away
    h, a = rec.score
    goals = [(e["t"], e["team"]) for e in events if e["type"] == "goal"]
    rows = []
    for e in events:
        if not e.get("contestable"):
            continue
        fc = _family_and_call(e)
        if fc is None:
            continue
        family, called = fc
        att = _attacking_team(e, home, away)
        att_home = att == home
        ax = e["xy"][0] if att_home else PITCH_L - e["xy"][0]
        sd = e["score"][0] - e["score"][1]
        if not att_home:
            sd = -sd
        gf, ga = (h, a) if att_home else (a, h)
        rows.append({
            "match_id": rec.match_id, "event_id": e["id"], "minute": e["t"] // 60,
            "family": family, "called": int(called), "att_team": att, "att_home": int(att_home),
            "zone": "att_third" if ax > 70 else ("mid_third" if ax > 35 else "def_third"),
            "in_box": int(in_penalty_area(ax, e["xy"][1])),
            "margin": e.get("margin", e.get("offside_margin")),
            "score_diff": max(-1, min(1, sd)),
            "att_goal_10": int(any(e["t"] < t <= e["t"] + WINDOW_S and team == att for t, team in goals)),
            "att_conceded_10": int(any(e["t"] < t <= e["t"] + WINDOW_S and team != att for t, team in goals)),
            "att_result": "W" if gf > ga else ("D" if gf == ga else "L"),
        })
    return rows


def _minute_band(m: int) -> int:
    return 0 if m < 30 else (1 if m < 60 else 2)


def comparable(target: dict, rows: list[dict]) -> list[dict]:
    return [r for r in rows
            if (r["match_id"], r["event_id"]) != (target["match_id"], target["event_id"])
            and r["family"] == target["family"] and r["zone"] == target["zone"]
            and _minute_band(r["minute"]) == _minute_band(target["minute"])
            and r["score_diff"] == target["score_diff"]
            and r["margin"] is not None and abs(r["margin"]) < BORDERLINE]


def _rates(rs: list[dict]) -> dict:
    n = len(rs)
    if n == 0:
        return {"n": 0, "win": None, "goal_10": None}
    return {"n": n, "win": round(sum(r["att_result"] == "W" for r in rs) / n, 3),
            "goal_10": round(sum(r["att_goal_10"] for r in rs) / n, 3)}


def history_check(fork_result: dict, rec, rows: list[dict]) -> dict | None:
    """Compare the fork's simulated shift with precedent. Returns None when the
    change is not a flipped call, since the precedent here is about calls."""
    if fork_result["change"].get("type") != "flip_call":
        return None
    mine = [r for r in moment_rows(rec) if r["event_id"] == fork_result["event_id"]]
    if not mine:
        return None
    target = mine[0]
    comp = comparable(target, rows)
    given = _rates([r for r in comp if r["called"]])
    not_given = _rates([r for r in comp if not r["called"]])

    # Effect of the flip on the attacking team's win share, from both sources.
    shift = fork_result["outcome_shift"]
    sim = shift["home"] if target["att_home"] else shift["away"]
    hist = None
    if given["n"] >= 5 and not_given["n"] >= 5:
        d = given["win"] - not_given["win"]
        hist = round(-d if target["called"] else d, 3)
    agrees = None if hist is None else (abs(sim - hist) < 0.08 or (sim > 0) == (hist > 0))
    what = "fouls" if target["family"] == "foul" else "offside decisions"
    return {
        "n": len(comp),
        "description": (f"{len(comp)} comparable borderline {what} this season: "
                        f"{target['zone'].replace('_', ' ')}, same score state, similar minute"),
        "when_given": given,
        "when_not_given": not_given,
        "attacking_team": target["att_team"],
        "sim_shift_att_win": round(sim, 3),
        "history_shift_att_win": hist,
        "agrees_with_simulation": agrees,
        "note": "Precedent compares different matches, so it carries confounding; "
                "the paired simulation isolates the call. Disagreement is shown, not hidden.",
    }
