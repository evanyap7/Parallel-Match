"""Copyable match state. Copying it IS the fork.

Player positions are not stored: they are derived each step from formation
slots, the ball and team style. Randomness is not stored either: it is keyed
by (seed, step), so two integers capture the whole RNG state.
"""

from dataclasses import dataclass


@dataclass(slots=True)
class MatchState:
    seed: int
    step: int                     # RNG stream index; advances every step
    seq: int                      # last emitted event sequence number
    t: float                      # elapsed playing seconds
    period: int
    half_end: list[float]         # elapsed seconds at which each half ends
    score: list[int]              # [home, away]
    ball_x: float                 # absolute metres, home attacks +x
    ball_y: float
    poss: int                     # 0 home, 1 away
    carrier: int                  # squad index of the player on the ball
    prev_carrier: int             # last passer, for assists (-1 if none)
    on: list[list[int]]           # per team, squad index per formation slot (-1 = sent off)
    fatigue: list[list[float]]    # per team, per squad index, 0..1
    yellows: list[list[int]]
    sent_off: list[list[bool]]
    played: list[list[bool]]      # has appeared (cannot come back on)
    subs: list[int]
    tactics: list[dict]           # attack, defence, press, tempo, directness
    restart: tuple | None         # (kind, team, x, y) pending dead-ball restart
    finished: bool = False

    def copy(self) -> "MatchState":
        return MatchState(
            seed=self.seed, step=self.step, seq=self.seq, t=self.t,
            period=self.period, half_end=list(self.half_end),
            score=list(self.score), ball_x=self.ball_x, ball_y=self.ball_y,
            poss=self.poss, carrier=self.carrier, prev_carrier=self.prev_carrier,
            on=[list(x) for x in self.on],
            fatigue=[list(x) for x in self.fatigue],
            yellows=[list(x) for x in self.yellows],
            sent_off=[list(x) for x in self.sent_off],
            played=[list(x) for x in self.played],
            subs=list(self.subs),
            tactics=[dict(x) for x in self.tactics],
            restart=self.restart, finished=self.finished,
        )
