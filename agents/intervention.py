"""Intervention Parser: fan free text to a typed, validated fork change.

Deliberately plain code, not a model: the fork engine accepts a bounded set
of changes, and a deterministic parser plus validator guarantees every parse
lands inside that set (or is refused). This is also the first feature on the
cut list, so it is small on purpose.

Supported changes (the bounded set the fork engine accepts):

- {"type": "flip_call", "call": ...} where call is one of
  no_foul / free_kick / penalty (contact family) or onside / offside
  (Law 11 family)
- {"type": "card", "color": "none" | "yellow" | "red"}
- {"type": "shot_outcome", "outcome": "goal" | "missed"}
"""

from __future__ import annotations

import re

CONTACT_EVENTS = ("foul", "tackle", "dribble")
OFFSIDE_EVENTS = ("offside", "pass")

# (regex, change) pairs scanned in order; first match wins per intent class.
# Negated phrasings ("wasn't a foul", "he was onside") come before the bare
# keywords so a fan asking to remove a call does not parse as adding one.
_RULES = [
    # negated Law 11 / contact flips
    (re.compile(r"\bw(?:as|ere)?n'?t off[\s-]?side\b|\bnot off[\s-]?side\b|\b(?:he|she|they) was (?:clearly )?onside\b", re.I),
     {"type": "flip_call", "call": "onside"}),
    (re.compile(r"\bw(?:as|ere)?n'?t (?:a foul|offending)\b|\bnot a foul\b|\bno foul\b|\bclean(?:ly)?\b|\bdived?\b|\bsimulation\b|\bnever touched\b", re.I),
     {"type": "flip_call", "call": "no_foul"}),
    # plain Law 11 flips
    (re.compile(r"\bonside\b", re.I), {"type": "flip_call", "call": "onside"}),
    (re.compile(r"\boff[\s-]?side\b", re.I), {"type": "flip_call", "call": "offside"}),
    # contact family flips
    (re.compile(r"\bpenalty\b|\bpen\b|\bspot kick\b", re.I), {"type": "flip_call", "call": "penalty"}),
    (re.compile(r"\bfoul\b|\bfree[\s-]?kick\b", re.I), {"type": "flip_call", "call": "free_kick"}),
    # cards
    (re.compile(r"\bno card\b|\bno yellow\b|\bno red\b|\bnothing\b", re.I),
     {"type": "card", "color": "none"}),
    (re.compile(r"\bred card\b|\bsent off\b|\bdismiss", re.I), {"type": "card", "color": "red"}),
    (re.compile(r"\byellow\b|\bbooked?\b|\bcaution", re.I), {"type": "card", "color": "yellow"}),
    # shots
    (re.compile(r"\bscored?\b|\bgoes? in\b|\bgoal\b|buried", re.I), {"type": "shot_outcome", "outcome": "goal"}),
    (re.compile(r"\bmiss(es|ed)?\b|\boff target\b|\bwide\b|\bsaved?\b", re.I),
     {"type": "shot_outcome", "outcome": "missed"}),
]


def parse(text: str) -> list[dict]:
    """All changes detected in `text`, in rule order."""
    changes: list[dict] = []
    seen: set[tuple] = set()
    for pattern, change in _RULES:
        if pattern.search(text) and tuple(sorted(change.items())) not in seen:
            seen.add(tuple(sorted(change.items())))
            changes.append(change)
    return changes


def _validate(change: dict, event: dict) -> str | None:
    """Reason the change cannot apply to this event, or None if it can."""
    etype, call = event.get("type"), event.get("call")
    ctype = change.get("type")

    if ctype == "flip_call":
        wanted = change["call"]
        if wanted in ("no_foul", "free_kick", "penalty"):
            if etype not in CONTACT_EVENTS:
                return f"a contact call can only flip on {CONTACT_EVENTS} events, not '{etype}'"
            if call == wanted:
                return f"the recorded call was already '{wanted}'"
            if wanted == "penalty" and etype == "foul" and call == "penalty":
                return "the recorded call was already 'penalty'"
        elif wanted in ("onside", "offside"):
            if etype not in OFFSIDE_EVENTS:
                return f"an offside call can only flip on {OFFSIDE_EVENTS} events, not '{etype}'"
            if call == wanted:
                return f"the recorded call was already '{wanted}'"
        else:
            return f"unknown flip_call target '{wanted}'"

    elif ctype == "card":
        if etype != "card":
            return f"a card change needs a card event, not '{etype}'"
        color = {"red": "red", "yellow": "yellow", "none": None}[change["color"]]
        if event.get("color") == color and color is not None:
            return "that card color was already recorded"

    elif ctype == "shot_outcome":
        if etype != "shot":
            return f"a shot outcome change needs a shot event, not '{etype}'"
        outcome = change["outcome"]
        if outcome == "goal" and event.get("outcome") == "goal":
            return "the shot was already recorded as a goal"
        if outcome == "missed" and event.get("outcome") in ("saved", "blocked", "off_target"):
            return "the shot was already recorded as not a goal"

    else:
        return f"unknown change type '{ctype}'"
    return None


def parse_and_validate(text: str, match: dict, event_id: str) -> dict:
    """Parse free text against one event of one match.

    Returns a POST /fork request body on success:
        {"ok": true, "request": {"match_id", "event_id", "change"}}
    or {"ok": false, "reason": "...", "candidates": [...]} on failure.
    """
    candidates = parse(text)
    if not candidates:
        return {
            "ok": False,
            "reason": "no recognised change in the text",
            "candidates": [],
        }
    event = None
    for e in match.get("events", []):
        if e.get("id") == event_id:
            event = e
            break
    if event is None:
        return {"ok": False, "reason": f"event '{event_id}' not found in match '{match.get('match_id')}'", "candidates": candidates}
    first_reason = None
    for change in candidates:
        reason = _validate(change, event)
        if reason is None:
            return {
                "ok": True,
                "request": {
                    "match_id": match["match_id"],
                    "event_id": event_id,
                    "change": change,
                },
                "other_candidates": [c for c in candidates if c != change],
            }
        if first_reason is None:
            first_reason = reason
    return {
        "ok": False,
        "reason": first_reason or "recognised changes do not apply to this event",
        "candidates": candidates,
        "event": {"id": event_id, "type": event.get("type"), "call": event.get("call")},
    }
