"""Neutral statements of the Laws of the Game used by the simulator.

Keys are the exact `law` strings emitted by parallel_match/rules.py, so the
explainer always finds its text. Statements describe what the Law requires
and how match officials apply it. They never evaluate a decision as right or
wrong, and never imply the official erred.

Paraphrased for this project's synthetic league; the Laws themselves are
referenced by number and title only.
"""

from __future__ import annotations

# call value -> neutral phrase describing the call that was made
CALL_PHRASES = {
    "free_kick": "a direct free kick was awarded",
    "penalty": "a penalty kick was awarded",
    "no_foul": "play was allowed to continue, with no foul called",
    "foul": "a foul was called",
    "offside": "the offside offence was given",
    "onside": "the player was judged onside",
    "yellow": "a yellow card was shown",
    "red": "a red card was shown",
    "goal": "the goal was awarded",
    "no_goal": "the goal was not awarded",
}

LAWS: dict[str, dict[str, object]] = {
    "Law 11: Offside": {
        "title": "Law 11: Offside",
        "statement": (
            "A player is in an offside position if any part of the head, body "
            "or feet is nearer to the opponents' goal line than both the ball "
            "and the second-last opponent, in the opponents' half. Being in "
            "that position is not itself an offence; an offence occurs only "
            "if the player becomes involved in active play, interferes with "
            "an opponent, or gains an advantage from that position. "
            "Offside is judged at the moment the ball is played by a "
            "teammate, not when it is received."
        ),
        "judgement": (
            "The assistant referee perceives the margin with human eyesight; "
            "a decision within a few tenths of a metre of the line can "
            "reasonably be seen either way on a single viewing."
        ),
        "flips": ("offside", "onside"),
    },
    "Law 12: Fouls and Misconduct (direct free kick offences)": {
        "title": "Law 12: Fouls and Misconduct (direct free kick offences)",
        "statement": (
            "A direct free kick is awarded if a player commits any of a list "
            "of offences against an opponent in a manner considered careless, "
            "reckless or using excessive force - including trips, kicks, "
            "jumps at, charges, strikes, pushes and holds. Inside the "
            "penalty area, such an offence by the defending team is punished "
            "with a penalty kick instead."
        ),
        "judgement": (
            "Carelessness is a judgement of degree: the referee weighs how "
            "much contact occurred and its consequence for the opponent. "
            "Contact near the threshold of a careless challenge can "
            "reasonably be judged either way at full speed."
        ),
        "flips": ("free_kick", "penalty", "no_foul"),
    },
    "Law 12: Fouls and Misconduct (cautionable offences)": {
        "title": "Law 12: Fouls and Misconduct (cautionable offences)",
        "statement": (
            "A player is cautioned and shown the yellow card for offences "
            "including unsporting behaviour, dissent by word or action, "
            "persistent offences, delaying the restart, and failing to "
            "respect the required distance at restarts. A reckless challenge "
            "is cautionable."
        ),
        "judgement": (
            "Whether a challenge reaches the reckless threshold is a "
            "judgement of degree made at match speed."
        ),
        "flips": ("yellow", "none"),
    },
    "Law 12: Fouls and Misconduct (sending-off offences)": {
        "title": "Law 12: Fouls and Misconduct (sending-off offences)",
        "statement": (
            "A player is sent off and shown the red card for serious foul "
            "play, violent conduct, spitting, denying the opposing team a "
            "goal or an obvious goal-scoring opportunity by an offence, "
            "offensive language, or receiving a second caution in the same "
            "match. Excessive force is sending-off."
        ),
        "judgement": (
            "The boundary between reckless and excessive force is a "
            "judgement of degree made at match speed."
        ),
        "flips": ("red", "yellow", "none"),
    },
    "Law 13: Free Kicks": {
        "title": "Law 13: Free Kicks",
        "statement": (
            "Free kicks are either direct or indirect. The ball is in play "
            "once it is kicked and clearly moves; opponents must remain at "
            "least 9.15 m (10 yards) from the ball until it is in play."
        ),
        "judgement": "Restart placement and distance are managed by the referee.",
        "flips": (),
    },
    "Law 14: The Penalty Kick": {
        "title": "Law 14: The Penalty Kick",
        "statement": (
            "A penalty kick is awarded when a player commits a direct-free-"
            "kick offence inside their own penalty area. The ball is placed "
            "on the penalty mark, the kicker must be identified, the "
            "defending goalkeeper must stay on the goal line until the kick "
            "is taken, and the kick is in play once it is kicked."
        ),
        "judgement": (
            "Whether the initiating contact occurred inside the penalty area "
            "can be marginal when the contact begins near the boundary line."
        ),
        "flips": ("penalty", "free_kick"),
    },
    "Law 15: The Throw-in": {
        "title": "Law 15: The Throw-in",
        "statement": (
            "A throw-in is awarded when the whole of the ball passes over "
            "the touchline, on the ground or in the air, last touched by a "
            "player of the team that did not touch it last. The thrower "
            "faces the field, has part of each foot on the touchline or "
            "ground behind it, uses both hands, and delivers the ball from "
            "behind and over the head."
        ),
        "judgement": "Which team touched the ball last determines the award.",
        "flips": (),
    },
    "Law 16: The Goal Kick": {
        "title": "Law 16: The Goal Kick",
        "statement": (
            "A goal kick is awarded when the whole of the ball passes over "
            "the goal line, on the ground or in the air, last touched by a "
            "player of the attacking team, and no goal was scored. The ball "
            "is placed anywhere inside the goal area and is in play once it "
            "is kicked and clearly moves."
        ),
        "judgement": "Which team touched the ball last determines the award.",
        "flips": (),
    },
    "Law 17: The Corner Kick": {
        "title": "Law 17: The Corner Kick",
        "statement": (
            "A corner kick is awarded when the whole of the ball passes over "
            "the goal line, last touched by a player of the defending team, "
            "and no goal was scored. The ball is placed in the corner "
            "nearest to where it crossed the line and is in play once it is "
            "kicked and clearly moves."
        ),
        "judgement": "Which team touched the ball last determines the award.",
        "flips": (),
    },
    "Law 3: The Players (substitution procedure)": {
        "title": "Law 3: The Players (substitution procedure)",
        "statement": (
            "A team may use substitutes up to the number permitted by the "
            "competition. The substitution procedure requires the referee's "
            "permission, and the substitute only enters after the outgoing "
            "player has left, at the halfway line, with both players staying "
            "off the field of play thereafter unless returning as a "
            "permitted substitute."
        ),
        "judgement": "The referee controls the substitution window.",
        "flips": (),
    },
    "Law 10: Determining the Outcome of a Match": {
        "title": "Law 10: Determining the Outcome of a Match",
        "statement": (
            "A goal is scored when the whole of the ball passes over the "
            "goal line, between the goalposts and under the crossbar, "
            "provided no offence by the scoring team immediately preceded "
            "it. The team scoring the greater number of goals wins; equal "
            "goals mean a draw."
        ),
        "judgement": "Goals stand unless an attacking offence immediately precedes them.",
        "flips": (),
    },
}

DEFAULT_LAW_TEXT = (
    "This moment is governed by the Laws of the Game; the relevant Law text "
    "is not indexed for this event type."
)


def law_text(law_field: str) -> dict[str, object]:
    """Law entry for a simulator `law` string, with a neutral fallback."""
    return LAWS.get(law_field, {
        "title": law_field or "The Laws of the Game",
        "statement": DEFAULT_LAW_TEXT,
        "judgement": "",
        "flips": (),
    })


def call_phrase(call: str | None) -> str:
    return CALL_PHRASES.get(call or "", f"the decision on the field was '{call}'")
