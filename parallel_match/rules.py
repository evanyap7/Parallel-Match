"""Pure geometry and officiating rules. No randomness lives here: noise is
passed in, so every decision can be tested with hand-made positions.

Coordinates are in the attacking team's frame: ax is metres from the
attacking team's own goal line (0..105), y is metres across (0..68).
"""

PITCH_L = 105.0
PITCH_W = 68.0
HALFWAY = PITCH_L / 2
GOAL_Y = PITCH_W / 2
PEN_AREA_DEPTH = 16.5
PEN_AREA_HALF_WIDTH = 20.16

# Neutral references to the Laws of the Game, used by the Law Explainer.
LAWS = {
    "offside": "Law 11: Offside",
    "foul": "Law 12: Fouls and Misconduct (direct free kick offences)",
    "caution": "Law 12: Fouls and Misconduct (cautionable offences)",
    "sending_off": "Law 12: Fouls and Misconduct (sending-off offences)",
    "free_kick": "Law 13: Free Kicks",
    "penalty": "Law 14: The Penalty Kick",
    "throw_in": "Law 15: The Throw-in",
    "goal_kick": "Law 16: The Goal Kick",
    "corner": "Law 17: The Corner Kick",
    "substitution": "Law 3: The Players (substitution procedure)",
    "goal": "Law 10: Determining the Outcome of a Match",
}


def in_penalty_area(ax: float, y: float) -> bool:
    """Is a point inside the penalty area the attacking team is attacking?"""
    return ax >= PITCH_L - PEN_AREA_DEPTH and abs(y - GOAL_Y) <= PEN_AREA_HALF_WIDTH


def second_last_opponent(opp_ax: list[float]) -> float:
    """ax of the second-last opponent (goalkeeper normally being the last)."""
    if len(opp_ax) < 2:
        return PITCH_L
    return sorted(opp_ax)[-2]


def offside_margin(attacker_ax: float, ball_ax: float, opp_ax: list[float]) -> float:
    """Metres by which an attacker is in an offside position at the moment of
    the pass. Positive = offside position, zero or negative = onside.

    Law 11: a player is in an offside position if any part of the body is in
    the opponents' half and nearer to the goal line than both the ball and
    the second-last opponent. Being level is onside.
    """
    line = max(second_last_opponent(opp_ax), ball_ax, HALFWAY)
    return attacker_ax - line


def assistant_flags_offside(margin: float, noise: float) -> bool:
    """The assistant referee perceives the margin with noise (metres)."""
    return margin + noise > 0.0


def referee_calls_foul(contact: float, noise: float, threshold: float) -> bool:
    """Contact severity 0..1 is perceived with noise against a threshold."""
    return contact + noise > threshold


def card_for(card_score: float, yellow_thr: float, red_thr: float) -> str | None:
    if card_score >= red_thr:
        return "red"
    if card_score >= yellow_thr:
        return "yellow"
    return None
