"""Season history store: comparable-moment queries in plain code.

All numbers and all moment-finding stay here. Agents and the MCP server only
phrase what this module computes; they never search or invent facts.

A "moment" is a contestable event (see docs/event-schema.md). Moments are
comparable when they belong to the same decision family:

- contact family: foul / tackle / dribble decided under Law 12, compared by
  measured contact (0..1) within CONTACT_TOLERANCE
- offside family: offside / borderline onside pass decided under Law 11,
  compared by margin (metres) within MARGIN_TOLERANCE

Zone and clock proximity add tie-break bonuses but never make two different
families comparable.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

CONTACT_FAMILY = ("foul", "tackle", "dribble")
OFFSIDE_FAMILY = ("offside", "pass")

CONTACT_TOLERANCE = 0.2       # max |contact difference| for comparability
MARGIN_TOLERANCE = 0.4        # max |margin difference| in metres
GOAL_WINDOW_S = 15 * 60       # "did the team profit soon after" window
MIN_CLOSENESS = 0.2           # base closeness floor

ZONES = ("defending third", "middle third", "attacking third")


def _zone(x_att: float) -> str:
    """Pitch zone in the acting team's attacking frame (x_att in 0..105)."""
    if x_att < 35:
        return ZONES[0]
    if x_att < 70:
        return ZONES[1]
    return ZONES[2]


@dataclass
class Moment:
    match_id: str
    event_id: str
    step: int
    t: int
    min: str
    period: int
    type: str
    family: str
    team: str
    side: str            # "home" or "away" in that match
    player: str
    call: str | None
    contact: float | None
    margin: float | None
    law: str
    zone: str
    score_at: tuple[int, int]
    opponent: str

    def summary(self) -> dict:
        return {
            "match_id": self.match_id,
            "event_id": self.event_id,
            "min": self.min,
            "type": self.type,
            "team": self.team,
            "opponent": self.opponent,
            "player": self.player,
            "call": self.call,
            "contact": self.contact,
            "margin": self.margin,
            "zone": self.zone,
            "score_at": list(self.score_at),
            "law": self.law,
        }


def _family(event: dict) -> str | None:
    if event.get("type") in CONTACT_FAMILY and event.get("contact") is not None:
        return "contact"
    if event.get("type") == "offside" and event.get("margin") is not None:
        return "offside"
    if event.get("type") == "pass" and event.get("offside_margin") is not None:
        return "offside"
    return None


def _margin_of(event: dict) -> float | None:
    if event.get("type") == "pass":
        return event.get("offside_margin")
    return event.get("margin")


def _moment(match: dict, event: dict, index: int) -> Moment | None:
    family = _family(event)
    if family is None:
        return None
    home, away = match["home"], match["away"]
    team = event.get("team", home)
    x, _y = event.get("xy", (52.5, 34.0))
    # Ball x is absolute; flip for the away team so x_att always means
    # "metres progressed towards the goal being attacked".
    x_att = x if team == home else 105.0 - x
    return Moment(
        match_id=match["match_id"],
        event_id=event["id"],
        step=event.get("step", index),
        t=event.get("t", 0),
        min=event.get("min", ""),
        period=event.get("period", 1),
        type=event["type"],
        family=family,
        team=team,
        side="home" if team == home else "away",
        player=event.get("player", ""),
        call=event.get("call"),
        contact=event.get("contact"),
        margin=_margin_of(event),
        law=event.get("law", ""),
        zone=_zone(x_att),
        score_at=tuple(event.get("score", [0, 0])),
        opponent=away if team == home else home,
    )


def _goals_in_window(match: dict, from_index: int, team: str) -> int:
    """Goals scored by `team` in the next GOAL_WINDOW_S playing seconds."""
    events = match["events"]
    t0 = events[from_index].get("t", 0)
    goals = 0
    for e in events[from_index:]:
        if e.get("t", 0) - t0 > GOAL_WINDOW_S:
            break
        if e.get("type") == "goal" and e.get("team") == team:
            goals += 1
    return goals


@dataclass
class Comparable:
    moment: Moment
    closeness: float
    same_call: bool
    goals_within_window: int
    final_score: tuple[int, int]

    def summary(self) -> dict:
        d = self.moment.summary()
        d["closeness"] = round(self.closeness, 3)
        d["same_call"] = self.same_call
        d["goals_by_team_next_15m"] = self.goals_within_window
        return d


@dataclass
class QueryResult:
    query: Moment
    comparables: list[Comparable] = field(default_factory=list)

    def stats(self) -> dict:
        n = len(self.comparables)
        if n == 0:
            return {"n": 0}
        other = [c for c in self.comparables if not c.same_call]
        same = [c for c in self.comparables if c.same_call]
        return {
            "n": n,
            "n_same_call": len(same),
            "n_other_call": len(other),
            "share_other_call": round(len(other) / n, 3),
            "n_other_call_scored_within_15m": sum(1 for c in other if c.goals_within_window > 0),
            "n_same_call_scored_within_15m": sum(1 for c in same if c.goals_within_window > 0),
            "avg_goals_by_team_next_15m_when_other_call": round(
                sum(c.goals_within_window for c in other) / len(other), 2
            ) if other else None,
            "avg_goals_by_team_next_15m_when_same_call": round(
                sum(c.goals_within_window for c in same) / len(same), 2
            ) if same else None,
        }

    def to_dict(self) -> dict:
        return {
            "query": self.query.summary(),
            "criteria": {
                "family": self.query.family,
                "contact_tolerance": CONTACT_TOLERANCE,
                "margin_tolerance_m": MARGIN_TOLERANCE,
                "goal_window_min": GOAL_WINDOW_S // 60,
            },
            "stats": self.stats(),
            "comparables": [c.summary() for c in self.comparables],
        }


def _closeness(a: Moment, b: Moment) -> float | None:
    """Base closeness from the family's measured quantity, or None if the
    moments are not comparable."""
    if a.family != b.family:
        return None
    if a.family == "contact":
        if a.contact is None or b.contact is None:
            return None
        base = 1.0 - min(1.0, abs(a.contact - b.contact) / CONTACT_TOLERANCE * 0.8)
        # A contact difference beyond the tolerance is not comparable.
        if abs(a.contact - b.contact) > CONTACT_TOLERANCE:
            return None
    else:
        if a.margin is None or b.margin is None:
            return None
        if abs(a.margin - b.margin) > MARGIN_TOLERANCE:
            return None
        base = 1.0 - min(1.0, abs(a.margin - b.margin) / MARGIN_TOLERANCE * 0.8)
    if base < MIN_CLOSENESS:
        return None
    za, zb = ZONES.index(a.zone), ZONES.index(b.zone)
    if za == zb:
        base += 0.15
    elif abs(za - zb) == 1:
        base += 0.05
    if abs(a.t - b.t) <= GOAL_WINDOW_S:
        base += 0.1
    return base


class HistoryStore:
    """In-memory index over season matches. Loading is the only I/O."""

    def __init__(self, matches: list[dict]):
        self.matches: dict[str, dict] = {}
        self._events: dict[str, list[dict]] = {}
        self.moments: list[tuple[str, int, Moment]] = []   # (match_id, event_index, moment)
        for m in matches:
            mid = m["match_id"]
            self.matches[mid] = m
            self._events[mid] = m["events"]
            for i, e in enumerate(m["events"]):
                mom = _moment(m, e, i)
                if mom is not None:
                    self.moments.append((mid, i, mom))

    @classmethod
    def load(cls, *sources: str) -> "HistoryStore":
        """Load matches from files and/or directories of match JSON files."""
        files: list[str] = []
        for src in sources:
            if os.path.isdir(src):
                files.extend(
                    os.path.join(src, f)
                    for f in sorted(os.listdir(src))
                    if f.endswith(".json")
                )
            elif os.path.isfile(src):
                files.append(src)
        matches = []
        seen = set()
        for path in files:
            with open(path) as fh:
                data = json.load(fh)
            if isinstance(data, dict) and "match_id" in data and "events" in data:
                if data["match_id"] not in seen:
                    seen.add(data["match_id"])
                    matches.append(data)
        return cls(matches)

    # -- lookups ---------------------------------------------------------

    def match(self, match_id: str) -> dict | None:
        return self.matches.get(match_id)

    def event(self, match_id: str, event_id: str) -> tuple[dict, int] | None:
        events = self._events.get(match_id)
        if events is None:
            return None
        for i, e in enumerate(events):
            if e.get("id") == event_id:
                return e, i
        return None

    def moment(self, match_id: str, event_id: str) -> Moment | None:
        found = self.event(match_id, event_id)
        if found is None:
            return None
        event, index = found
        return _moment(self.matches[match_id], event, index)

    # -- the query -------------------------------------------------------

    def query(self, match_id: str, event_id: str, limit: int = 8,
              include_same_match: bool = False) -> QueryResult | None:
        target = self.moment(match_id, event_id)
        if target is None:
            return None
        scored: list[Comparable] = []
        for mid, idx, mom in self.moments:
            if mom.event_id == event_id and mid == match_id:
                continue
            if not include_same_match and mid == match_id:
                continue
            closeness = _closeness(target, mom)
            if closeness is None:
                continue
            scored.append(Comparable(
                moment=mom,
                closeness=closeness,
                same_call=(mom.call == target.call),
                goals_within_window=_goals_in_window(self.matches[mid], idx, mom.team),
                final_score=tuple(self.matches[mid].get("score", [0, 0])),
            ))
        scored.sort(key=lambda c: (-c.closeness, c.moment.t))
        return QueryResult(query=target, comparables=scored[:limit])

    def season_summary(self) -> dict:
        n_events = sum(len(v) for v in self._events.values())
        by_family: dict[str, int] = {}
        by_call: dict[str, int] = {}
        for _mid, _i, mom in self.moments:
            by_family[mom.family] = by_family.get(mom.family, 0) + 1
            key = f"{mom.type}:{mom.call}"
            by_call[key] = by_call.get(key, 0) + 1
        return {
            "matches": len(self.matches),
            "events": n_events,
            "contestable_moments": len(self.moments),
            "by_family": by_family,
            "by_call": by_call,
        }


def default_store(fixtures_dir: str = "fixtures",
                  history_dir: str = "data/dev_season") -> HistoryStore:
    """Store for local dev: the contract fixtures plus the generated dev
    season. In deployment both are replaced by the real season export."""
    sources = []
    if os.path.isdir(fixtures_dir):
        sources.append(fixtures_dir)
    if os.path.isdir(history_dir) and os.path.abspath(history_dir) != os.path.abspath(fixtures_dir):
        sources.append(history_dir)
    return HistoryStore.load(*sources)
