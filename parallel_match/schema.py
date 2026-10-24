"""Event schema. One flat JSON object per event; see docs/event-schema.md."""

from dataclasses import dataclass, field

EVENT_TYPES = (
    "kickoff", "pass", "dribble", "tackle", "interception", "foul", "card",
    "offside", "shot", "goal", "throw_in", "goal_kick", "corner",
    "free_kick", "substitution", "half_time", "full_time",
)


@dataclass(slots=True)
class Event:
    id: str            # "<match_id>-<seq>", e.g. "m012-0341"
    step: int          # simulator step that produced it (fork anchor)
    t: int             # elapsed playing seconds since kickoff
    min: str           # broadcast clock label, e.g. "45+2"
    period: int        # 1 or 2
    type: str
    team: str | None   # club code of the acting team
    player: str | None
    xy: tuple[float, float] | None  # absolute pitch metres, home attacks +x
    score: tuple[int, int]          # score after this event (home, away)
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "id": self.id, "step": self.step, "t": self.t, "min": self.min,
            "period": self.period, "type": self.type,
        }
        if self.team is not None:
            d["team"] = self.team
        if self.player is not None:
            d["player"] = self.player
        d.update(self.extra)
        if self.xy is not None:
            d["xy"] = [self.xy[0], self.xy[1]]
        d["score"] = [self.score[0], self.score[1]]
        return d
