"""Event-level match simulator.

One call to step() advances the match by one action (a pass, a dribble, a
shot, a restart...) and returns the events it produced. All randomness for a
step comes from Rng(seed, step), drawn up front in a fixed order per handler,
so a copied state replays identically and forks share random numbers until
they diverge.
"""

import math
from dataclasses import dataclass

from . import rules
from .rng import Rng, hash_unit, pick_index
from .rules import LAWS, PITCH_L, PITCH_W, GOAL_Y
from .schema import Event
from .state import MatchState
from .teams import FORMATIONS, Club

# Tuning constants. Calibrated by the realism report, not by hand-waving.
PASS_BASE = 0.975
PASS_DIST_PEN = 0.0042
KIND_PEN = {"back": -0.04, "lateral": -0.01, "forward": 0.07, "long": 0.30,
            "through": 0.30, "cross": 0.40}
INTERCEPT_SHARE = 0.72
SHOT_RANGE = 30.0
SHOT_K = 2.1
BLOCK_P = 0.24
ON_TARGET_UNBLOCKED = 0.46
CHALLENGE_BASE = 0.25
CONTACT_EXP = 1.5
BOOKED_CAUTION = 0.80
FWD_LINE_BIAS = 0.98   # share of forward positions held onside
FWD_LINE_SPREAD = 7.0  # metres
HOME_XG = 1.18        # home advantage on chance quality
LATE_GAME = 3900.0     # seconds after which trailing teams push
CONTEST_FOUL = 0.12    # |contact - threshold| treated as a borderline call
CONTEST_OFFSIDE = 0.6  # metres

DT_BASE = {"pass": 3.4, "dribble": 4.5, "shot": 6.0, "tackle": 3.5,
           "interception": 2.5, "foul": 18.0, "card": 25.0, "offside": 22.0,
           "goal": 50.0, "throw_in": 9.0, "goal_kick": 14.0, "corner": 20.0,
           "free_kick": 12.0, "kickoff": 4.0, "substitution": 30.0}


@dataclass(frozen=True, slots=True)
class Referee:
    foul_thr: float    # contact severity above which a foul is given
    noise: float       # perception noise on contact
    ar_noise: float    # assistant referee perception noise, metres
    yellow_thr: float
    red_thr: float

    @staticmethod
    def for_seed(seed: int) -> "Referee":
        u = hash_unit(seed, 77)
        return Referee(foul_thr=0.53 + 0.08 * (u - 0.5), noise=0.07, ar_noise=0.20,
                       yellow_thr=0.93, red_thr=1.17)


@dataclass(frozen=True, slots=True)
class Context:
    """Static match context, never copied or mutated."""
    match_id: str
    clubs: tuple[Club, Club]
    formations: tuple[list, list]
    referee: Referee


@dataclass(slots=True)
class MatchRecord:
    match_id: str
    seed: int
    home: str
    away: str
    score: list[int]
    events: list[Event]

    def to_dict(self) -> dict:
        return {"match_id": self.match_id, "seed": self.seed, "home": self.home,
                "away": self.away, "score": list(self.score),
                "events": [e.to_dict() for e in self.events]}


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def ax_of(team: int, x: float) -> float:
    """Absolute x to the team's attacking frame."""
    return x if team == 0 else PITCH_L - x


abs_x = ax_of  # the mapping is its own inverse


def new_match(home: Club, away: Club, seed: int, match_id: str = "m000") -> tuple[Context, MatchState]:
    ctx = Context(match_id=match_id, clubs=(home, away),
                  formations=(FORMATIONS[home.formation], FORMATIONS[away.formation]),
                  referee=Referee.for_seed(seed))
    first_end = 2700.0 + 60.0 + 150.0 * hash_unit(seed, 1)
    second_end = first_end + 2700.0 + 150.0 + 240.0 * hash_unit(seed, 2)
    n = [len(home.squad), len(away.squad)]
    st = MatchState(
        seed=seed, step=0, seq=0, t=0.0, period=1, half_end=[first_end, second_end],
        score=[0, 0], ball_x=PITCH_L / 2, ball_y=GOAL_Y, poss=0, carrier=9, prev_carrier=-1,
        on=[list(range(11)), list(range(11))],
        fatigue=[[0.0] * n[0], [0.0] * n[1]],
        yellows=[[0] * n[0], [0] * n[1]],
        sent_off=[[False] * n[0], [False] * n[1]],
        played=[[i < 11 for i in range(n[0])], [i < 11 for i in range(n[1])]],
        subs=[0, 0], tactics=[home.style(), away.style()],
        restart=("kickoff", 0, PITCH_L / 2, GOAL_Y),
    )
    return ctx, st


def step(ctx: Context, st: MatchState) -> list[Event]:
    if st.finished:
        return []
    st.step += 1
    return _Step(ctx, st).run()


def play(ctx: Context, st: MatchState, max_steps: int = 20_000) -> list[Event]:
    """Play from the current state to full time."""
    out: list[Event] = []
    for _ in range(max_steps):
        if st.finished:
            break
        out.extend(step(ctx, st))
    return out


def simulate(home: Club, away: Club, seed: int, match_id: str = "m000") -> MatchRecord:
    ctx, st = new_match(home, away, seed, match_id)
    events = play(ctx, st)
    return MatchRecord(match_id, seed, home.code, away.code, list(st.score), events)


class _Step:
    __slots__ = ("ctx", "st", "rng", "events", "dt", "_pos", "_line")

    def __init__(self, ctx: Context, st: MatchState):
        self.ctx, self.st = ctx, st
        self.rng = Rng(st.seed, st.step)
        self.events: list[Event] = []
        self.dt = 0.0
        self._pos = [None, None]
        self._line = [None, None]

    # ---- helpers ---------------------------------------------------------

    def player(self, t, i):
        return self.ctx.clubs[t].squad[i]

    def attr(self, t, i, name):
        v = getattr(self.ctx.clubs[t].squad[i], name)
        if name == "discipline":
            return v
        return v * (1.0 - 0.25 * self.st.fatigue[t][i])

    def tact(self, t, key):
        st = self.st
        v = st.tactics[t][key]
        if key == "attack" and st.period == 2 and st.t > LATE_GAME and st.score[t] < st.score[1 - t]:
            v += 0.15
        return _clamp(v, 0.0, 1.0)

    def n_on(self, t):
        return sum(1 for i in self.st.on[t] if i >= 0)

    def minute(self) -> str:
        st = self.st
        if st.period == 1:
            m = int(st.t // 60) + 1
            return str(m) if m <= 45 else f"45+{m - 45}"
        m = 45 + int((st.t - st.half_end[0]) // 60) + 1
        return str(m) if m <= 90 else f"90+{m - 90}"

    def emit(self, etype, team=None, player=None, xy=None, dt_key=None, **extra):
        st, ctx = self.st, self.ctx
        st.seq += 1
        self.events.append(Event(
            id=f"{ctx.match_id}-{st.seq:04d}", step=st.step, t=int(round(st.t)),
            min=self.minute(), period=st.period, type=etype,
            team=ctx.clubs[team].code if team is not None else None,
            player=self.player(team, player).id if player is not None else None,
            xy=(round(xy[0], 1), round(xy[1], 1)) if xy is not None else None,
            score=(st.score[0], st.score[1]), extra=extra,
        ))
        base = DT_BASE.get(dt_key or etype, 0.0)
        if base:
            self.dt += base * (0.6 + 0.8 * hash_unit(st.seed, st.step, st.seq))

    def pid(self, t, i):
        return self.player(t, i).id

    # ---- derived positions ----------------------------------------------

    def positions(self, t):
        """[(squad_idx, ax, y, role)] for team t's on-pitch players, in t's frame."""
        if self._pos[t] is None:
            self._pos[t] = self._compute_positions(t)
        return self._pos[t]

    def offside_line(self, t):
        """ax (team t's frame) of the second-last opponent of team t."""
        if self._line[t] is None:
            opp = [PITCH_L - a for (_, a, _, _) in self.positions(1 - t)]
            self._line[t] = rules.second_last_opponent(opp)
        return self._line[t]

    def _compute_positions(self, t):
        st = self.st
        form = self.ctx.formations[t]
        bax = ax_of(t, st.ball_x)
        by = st.ball_y
        has_ball = st.poss == t
        press = self.tact(t, "press")
        k = 0.30 if has_ball else 0.28 + 0.25 * press
        push = 5.0 * self.tact(t, "attack") if has_ball else -6.0 * (1.0 - press)
        out = []
        for slot, idx in enumerate(st.on[t]):
            if idx < 0:
                continue
            role, sx, sy = form[slot]
            j1 = hash_unit(st.seed, st.step, t, slot, 1) - 0.5
            j2 = hash_unit(st.seed, st.step, t, slot, 2) - 0.5
            if role == "GK":
                a = sx + 0.06 * (bax - sx)
                y = GOAL_Y + 0.15 * (by - GOAL_Y)
            elif has_ball and role == "FWD":
                # Forwards play on the shoulder of the defensive line.
                u = hash_unit(st.seed, st.step, t, slot, 3)
                a = self.offside_line(t) + (u - FWD_LINE_BIAS) * FWD_LINE_SPREAD
                y = sy + 0.22 * (by - sy) + 6.0 * j2
            else:
                a = sx + k * (bax - sx) + push + 4.0 * j1
                y = sy + 0.22 * (by - sy) + 4.0 * j2
            out.append((idx, _clamp(a, 1.0, PITCH_L - 1.0), _clamp(y, 1.0, PITCH_W - 1.0), role))
        return out

    def pick_near(self, t, ax, y, r, exclude=(), roles=None, scale=6.0):
        """Pick a team-t player near (ax, y) given in t's frame."""
        cands = [p for p in self.positions(t)
                 if p[0] not in exclude and (roles is None or p[3] in roles)
                 and (roles is not None or p[3] != "GK")]
        if not cands:
            cands = [p for p in self.positions(t) if p[0] not in exclude]
        w = [math.exp(-math.hypot(p[1] - ax, p[2] - y) / scale) + 1e-9 for p in cands]
        return cands[pick_index(w, r)]

    def gk(self, t):
        for p in self.positions(t):
            if p[3] == "GK":
                return p[0]
        return self.positions(t)[0][0]

    def set_ball(self, t, ax, y):
        self.st.ball_x = abs_x(t, _clamp(ax, 0.5, PITCH_L - 0.5))
        self.st.ball_y = _clamp(y, 0.0, PITCH_W)

    def give(self, t, idx, ax=None, y=None):
        st = self.st
        if st.poss != t:
            st.prev_carrier = -1
        st.poss, st.carrier = t, idx
        if ax is not None:
            self.set_ball(t, ax, y)

    def xy(self):
        return (self.st.ball_x, self.st.ball_y)

    # ---- main dispatch ---------------------------------------------------

    def run(self) -> list[Event]:
        st = self.st
        if st.t >= st.half_end[st.period - 1]:
            self.end_period()
        elif st.restart is not None:
            self.restart()
        else:
            self.open_play()
        self.advance_clock()
        return self.events

    def advance_clock(self):
        st = self.st
        dt = self.dt
        st.t += dt
        if dt <= 0:
            return
        for t in (0, 1):
            load = 0.75 + 0.35 * self.tact(t, "press") + 0.30 * self.tact(t, "tempo")
            fat = st.fatigue[t]
            squad = self.ctx.clubs[t].squad
            for idx in st.on[t]:
                if idx >= 0 and squad[idx].pos != "GK":
                    fat[idx] = min(1.0, fat[idx] + dt / 5400.0 * (1.15 - squad[idx].stamina) * load)

    def end_period(self):
        st = self.st
        if st.period == 1:
            self.emit("half_time")
            st.period = 2
            for t in (0, 1):
                st.fatigue[t] = [f * 0.8 for f in st.fatigue[t]]
            st.restart = ("kickoff", 1, PITCH_L / 2, GOAL_Y)
            for t in (0, 1):
                self.maybe_sub(t, at_half_time=True)
        else:
            self.emit("full_time")
            st.finished = True

    # ---- substitutions ---------------------------------------------------

    def maybe_sub(self, t, at_half_time=False):
        st = self.st
        r = self.rng.u()
        if st.subs[t] >= 5:
            return
        if at_half_time:
            p = 0.18
        else:
            if st.period == 1:
                return
            mins = (st.t - st.half_end[0]) / 60.0 + 45.0
            p = 0.0 if mins < 56 else 0.10
        if r >= p:
            return
        squad = self.ctx.clubs[t].squad
        outfield = [(st.fatigue[t][i] + 0.15 * st.yellows[t][i], slot, i)
                    for slot, i in enumerate(st.on[t]) if i >= 0 and squad[i].pos != "GK"]
        if not outfield:
            return
        _, slot, off = max(outfield)
        bench = [i for i in range(11, len(squad)) if not st.played[t][i] and squad[i].pos != "GK"]
        if not bench:
            return
        same = [i for i in bench if squad[i].pos == squad[off].pos]
        on = (same or bench)[0]
        st.on[t][slot] = on
        st.played[t][on] = True
        st.subs[t] += 1
        if st.poss == t and st.carrier == off:
            st.carrier = on
        self.emit("substitution", t, on, off=self.pid(t, off), law=LAWS["substitution"])

    # ---- restarts --------------------------------------------------------

    def restart(self):
        st, rng = self.st, self.rng
        kind, t, x, y = st.restart
        st.restart = None
        o = 1 - t
        r1, r2, r3 = rng.u(), rng.u(), rng.u()
        self.maybe_sub(0)
        self.maybe_sub(1)
        st.ball_x, st.ball_y = x, y
        st.poss, st.prev_carrier = t, -1
        bax = ax_of(t, x)

        if kind == "kickoff":
            p = self.pick_near(t, 50.0, GOAL_Y, r1, roles=("FWD", "MID"))
            st.carrier = p[0]
            self.emit("kickoff", t, p[0], self.xy())
        elif kind == "throw_in":
            p = self.pick_near(t, bax, y, r1)
            st.carrier = p[0]
            self.emit("throw_in", t, p[0], self.xy(), law=LAWS["throw_in"])
        elif kind == "goal_kick":
            st.carrier = self.gk(t)
            self.emit("goal_kick", t, st.carrier, self.xy(), law=LAWS["goal_kick"])
        elif kind == "corner":
            taker = self.pick_near(t, bax, y, r1, roles=("MID", "FWD"), scale=40.0)
            self.emit("corner", t, taker[0], self.xy(), law=LAWS["corner"])
            if r2 < 0.32:
                header = self.pick_near(t, 96.0, GOAL_Y, r3, exclude=(taker[0],),
                                        roles=("FWD", "DEF", "MID"), scale=12.0)
                self.give(t, header[0], 96.0 + 3.0 * (r3 - 0.5), GOAL_Y + 10.0 * (r2 - 0.16))
                st.prev_carrier = taker[0]
                self.shot(t, o, header[0], kind="header", xg_scale=0.55)
            elif r2 < 0.45:
                st.carrier = taker[0]
            else:
                clr = self.pick_near(o, 14.0, GOAL_Y, r3)
                self.give(o, clr[0], 25.0 + 15.0 * r3, GOAL_Y + 30.0 * (r1 - 0.5))
                self.emit("interception", o, clr[0], self.xy(), via="clearance")
        elif kind == "free_kick":
            dist = math.hypot(PITCH_L - bax, y - GOAL_Y)
            taker = self.pick_near(t, bax, y, r1, scale=20.0)
            st.carrier = taker[0]
            self.emit("free_kick", t, taker[0], self.xy(), law=LAWS["free_kick"])
            if dist < 30.0 and bax > 75.0 and r2 < 0.35:
                self.shot(t, o, taker[0], kind="free_kick", xg_scale=0.55)
        elif kind == "penalty":
            self.penalty(t, o)

    # ---- open play -------------------------------------------------------

    def open_play(self):
        st, rng = self.st, self.rng
        t, o, c = st.poss, 1 - st.poss, st.carrier
        r_act = rng.u()
        bax = ax_of(t, st.ball_x)
        dist = math.hypot(PITCH_L - bax, st.ball_y - GOAL_Y)
        role = self.player(t, c).pos
        w_pass = 1.0
        w_drib = 0.0 if role == "GK" else 0.10 + 0.22 * self.attr(t, c, "dribbling")
        w_shot = 0.0
        if role != "GK" and dist < SHOT_RANGE and bax > 75.0:
            closeness = (SHOT_RANGE - dist) / SHOT_RANGE
            w_shot = (SHOT_K * closeness ** 1.5 * (0.6 + 0.8 * self.tact(t, "attack"))
                      * (0.6 + 0.8 * self.attr(t, c, "finishing")))
        act = pick_index((w_pass, w_drib, w_shot), r_act)
        if act == 0:
            self.pass_(t, o, c, bax)
        elif act == 1:
            self.dribble(t, o, c, bax)
        else:
            self.shot(t, o, c, kind="open_play")

    def pass_(self, t, o, c, bax):
        st, rng, ref = self.st, self.rng, self.ctx.referee
        r_kind, r_recv, r_succ, r_fail = rng.u(), rng.u(), rng.u(), rng.u()
        n_dx, n_dy = rng.normal(), rng.normal()
        n_ar = rng.normal(0.0, ref.ar_noise)
        by = st.ball_y
        direct = self.tact(t, "directness")
        is_gk = self.player(t, c).pos == "GK"
        wide = abs(by - GOAL_Y) > 20.0 and bax > 75.0
        kinds = ("back", "lateral", "forward", "long", "through", "cross")
        weights = (
            0.0 if is_gk else 0.17 * (1.3 - direct),
            0.36 * (1.3 - direct),
            0.30,
            (0.30 if is_gk else 0.035) + 0.07 * direct,
            0.0 if is_gk else 0.025 + 0.035 * self.tact(t, "attack"),
            0.40 if wide else 0.0,
        )
        kind = kinds[pick_index(weights, r_kind)]
        if kind == "cross":
            tx, ty = 95.0 + 4.0 * n_dx, GOAL_Y + 7.0 * n_dy
        else:
            mu, sd = {"back": (-9, 4), "lateral": (0, 5), "forward": (11, 5),
                      "long": (32, 8), "through": (18, 5)}[kind]
            tx = bax + mu + sd * n_dx
            ty = by + (14.0 if kind == "lateral" else 8.0) * n_dy
        tx, ty = _clamp(tx, 2.0, PITCH_L - 2.0), _clamp(ty, 1.0, PITCH_W - 1.0)

        roles = ("FWD", "MID") if kind in ("through", "long") else None
        recv = self.pick_near(t, tx, ty, r_recv, exclude=(c,), roles=roles)
        ridx, ra, ry, _ = recv
        d = math.hypot(ra - bax, ry - by)

        margin = None
        if kind in ("forward", "long", "through", "cross") and ra > bax:
            opp = [PITCH_L - a for (_, a, _, _) in self.positions(o)]
            margin = rules.offside_margin(ra, bax, opp)

        p = (PASS_BASE - PASS_DIST_PEN * d - KIND_PEN[kind]
             + 0.30 * (self.attr(t, c, "passing") - 0.55)
             - 0.07 * self.tact(o, "press")
             + 0.015 * (self.n_on(t) - self.n_on(o))
             + (0.01 if t == 0 else 0.0))
        success = r_succ < p

        extra = {"kind": kind, "to": self.pid(t, ridx)}
        if margin is not None and abs(margin) < 1.5:
            extra["offside_margin"] = round(margin, 2)

        if margin is not None and margin > -1.5 and rules.assistant_flags_offside(margin, n_ar):
            self.emit("pass", t, c, self.xy(), success=True, **extra)
            self.set_ball(t, ra, ry)
            self.emit("offside", t, ridx, self.xy(), margin=round(margin, 2), call="offside",
                      contestable=abs(margin) < CONTEST_OFFSIDE, law=LAWS["offside"])
            st.restart = ("free_kick", o, st.ball_x, st.ball_y)
            return

        if margin is not None and abs(margin) < CONTEST_OFFSIDE:
            extra["contestable"] = True
            extra["call"] = "onside"
            extra["law"] = LAWS["offside"]

        if success:
            self.emit("pass", t, c, self.xy(), success=True, **extra)
            st.prev_carrier = c
            st.carrier = ridx
            self.set_ball(t, ra, ry)
            return

        self.emit("pass", t, c, self.xy(), success=False, **extra)
        if r_fail < INTERCEPT_SHARE:
            r2 = r_fail / INTERCEPT_SHARE
            if (kind == "cross" and r2 < 0.45) or (tx > 88.0 and r2 < 0.15):
                # Cleared behind by a defender inside the box.
                side = 0.0 if by < GOAL_Y else PITCH_W
                st.restart = ("corner", t, abs_x(t, PITCH_L), side)
                return
            ia, iy = tx - 0.4 * (tx - bax), ty
            icpt = self.pick_near(o, PITCH_L - ia, iy, r2)
            self.give(o, icpt[0], PITCH_L - ia, iy)
            self.emit("interception", o, icpt[0], self.xy())
        elif kind in ("long", "cross", "through") and tx > PITCH_L - 12.0:
            # Over the goal line: off a defender gives a corner, otherwise a goal kick.
            if r_fail > 1.0 - (1.0 - INTERCEPT_SHARE) * 0.6:
                side = 0.0 if ty < GOAL_Y else PITCH_W
                st.restart = ("corner", t, abs_x(t, PITCH_L), side)
            else:
                st.restart = ("goal_kick", o, abs_x(o, 6.0), GOAL_Y)
            self.set_ball(t, PITCH_L, ty)
        else:
            side = 0.0 if ty < GOAL_Y else PITCH_W
            st.restart = ("throw_in", o, abs_x(t, tx), side)
            self.set_ball(t, tx, side)

    def dribble(self, t, o, c, bax):
        st, rng, ref = self.st, self.rng, self.ctx.referee
        r_chal, r_contact, r_win, r_adv, r_def = rng.u(), rng.u(), rng.u(), rng.u(), rng.u()
        n_ref, n_card = rng.normal(0.0, ref.noise), rng.normal(0.0, 0.08)
        by = st.ball_y
        adv = 3.0 + 6.0 * r_adv
        if r_chal >= CHALLENGE_BASE + 0.30 * self.tact(o, "press"):
            self.emit("dribble", t, c, self.xy(), success=True, beat=None)
            self.set_ball(t, bax + adv, by + 4.0 * (r_def - 0.5))
            return
        dfn = self.pick_near(o, PITCH_L - bax, by, r_def)[0]
        tack = self.attr(o, dfn, "tackling")
        disc = self.attr(o, dfn, "discipline")
        contact = _clamp(r_contact ** CONTACT_EXP * (1.15 - 0.3 * tack) * (1.12 - 0.2 * disc), 0.0, 1.0)
        if st.yellows[o][dfn]:
            contact *= BOOKED_CAUTION  # booked players pull out of challenges
        thr = ref.foul_thr
        margin = contact - thr
        if rules.referee_calls_foul(contact, n_ref, thr):
            self.foul(t, o, c, dfn, contact, margin, n_card, bax, by)
            return
        drib = self.attr(t, c, "dribbling")
        extra = {"contact": round(contact, 3)}
        if abs(margin) < CONTEST_FOUL:
            extra.update(margin=round(margin, 3), call="no_foul", contestable=True, law=LAWS["foul"])
        if r_win < 0.50 + 0.5 * (tack - drib):
            self.give(o, dfn)
            self.emit("tackle", o, dfn, self.xy(), victim=self.pid(t, c), success=True, **extra)
        else:
            self.emit("dribble", t, c, self.xy(), success=True, beat=self.pid(o, dfn), **extra)
            self.set_ball(t, bax + adv, by)

    def foul(self, t, o, victim, dfn, contact, margin, n_card, bax, by):
        st, ref = self.st, self.ctx.referee
        in_box = rules.in_penalty_area(bax, by)
        card_score = contact + n_card + 0.25 * (0.5 - self.attr(o, dfn, "discipline"))
        card = rules.card_for(card_score, ref.yellow_thr, ref.red_thr)
        call = "penalty" if in_box else "free_kick"
        contestable = abs(margin) < CONTEST_FOUL or in_box or (
            card is not None and abs(card_score - ref.yellow_thr) < 0.06)
        self.emit("foul", o, dfn, self.xy(), victim=self.pid(t, victim), contact=round(contact, 3),
                  margin=round(margin, 3), call=call, card=card, contestable=contestable,
                  law=LAWS["foul"])
        if card == "yellow" and st.yellows[o][dfn] >= 1:
            card = "second_yellow"
        if card is not None:
            if card == "yellow":
                st.yellows[o][dfn] += 1
            else:
                st.sent_off[o][dfn] = True
                st.on[o] = [-1 if i == dfn else i for i in st.on[o]]
            self.emit("card", o, dfn, self.xy(), color="yellow" if card == "yellow" else "red",
                      reason=card, score_margin=round(card_score - ref.yellow_thr, 3),
                      law=LAWS["caution"] if card == "yellow" else LAWS["sending_off"])
        if in_box:
            st.restart = ("penalty", t, abs_x(t, PITCH_L - 11.0), GOAL_Y)
        else:
            st.restart = ("free_kick", t, st.ball_x, st.ball_y)

    # ---- shots -----------------------------------------------------------

    def xg(self, t, o, c, dist, y):
        angle = max(0.25, 1.0 - abs(y - GOAL_Y) / 40.0)
        base = 0.46 * math.exp(-(max(dist, 6.0) - 6.0) / 8.0) * angle
        x = (base * (0.55 + 0.9 * self.attr(t, c, "finishing"))
             * (0.85 + 0.3 * self.tact(t, "attack"))
             * (1.15 - 0.3 * self.tact(o, "defence"))
             * (1.0 + 0.05 * (self.n_on(t) - self.n_on(o)))
             * (HOME_XG if t == 0 else 1.0))
        return _clamp(x, 0.005, 0.75)

    def shot(self, t, o, c, kind="open_play", xg_scale=1.0):
        st, rng = self.st, self.rng
        r_block, r_out, r_after, r_who = rng.u(), rng.u(), rng.u(), rng.u()
        bax = ax_of(t, st.ball_x)
        by = st.ball_y
        dist = math.hypot(PITCH_L - bax, by - GOAL_Y)
        xg = self.xg(t, o, c, dist, by) * xg_scale
        keeper = self.gk(o)
        p_block = BLOCK_P + (0.08 if dist > 20 else 0.0)
        if kind == "free_kick":
            p_block = 0.20
        pg = min(0.9, xg * (1.25 - 0.5 * self.attr(o, keeper, "saving")) / (1.0 - BLOCK_P))
        if r_block < p_block:
            outcome = "blocked"
        elif r_out < pg:
            outcome = "goal"
        elif r_out < max(pg + 0.08, ON_TARGET_UNBLOCKED):
            outcome = "saved"
        else:
            outcome = "off_target"
        self.emit("shot", t, c, self.xy(), kind=kind, xg=round(xg, 3), dist=round(dist, 1),
                  outcome=outcome, on_target=outcome in ("goal", "saved"))
        self.after_shot(t, o, c, outcome, r_after, r_who)

    def penalty(self, t, o):
        st, rng = self.st, self.rng
        r_goal, r_after, r_who = rng.u(), rng.u(), rng.u()
        on = [p[0] for p in self.positions(t) if p[3] != "GK"]
        taker = max(on, key=lambda i: self.attr(t, i, "finishing"))
        st.carrier = taker
        keeper = self.gk(o)
        p = 0.76 + 0.2 * (self.attr(t, taker, "finishing") - 0.6) - 0.15 * (self.attr(o, keeper, "saving") - 0.6)
        outcome = "goal" if r_goal < p else ("saved" if r_goal < p + (1 - p) * 0.7 else "off_target")
        self.emit("shot", t, taker, self.xy(), kind="penalty", xg=0.76, dist=11.0,
                  outcome=outcome, on_target=outcome in ("goal", "saved"), law=LAWS["penalty"])
        self.after_shot(t, o, taker, outcome, r_after, r_who)

    def after_shot(self, t, o, c, outcome, r_after, r_who):
        st = self.st
        if outcome == "goal":
            st.score[t] += 1
            assist = st.prev_carrier if st.prev_carrier >= 0 and st.prev_carrier != c else None
            self.emit("goal", t, c, (abs_x(t, PITCH_L), GOAL_Y),
                      assist=self.pid(t, assist) if assist is not None else None,
                      law=LAWS["goal"])
            st.restart = ("kickoff", o, PITCH_L / 2, GOAL_Y)
        elif outcome == "saved":
            if r_after < 0.38:
                self.give(o, self.gk(o), 6.0, GOAL_Y)
            elif r_after < 0.75:
                side = 0.0 if st.ball_y < GOAL_Y else PITCH_W
                st.restart = ("corner", t, abs_x(t, PITCH_L), side)
            else:
                p = self.pick_near(t, 92.0, GOAL_Y, r_who)
                self.give(t, p[0], 92.0, GOAL_Y + 16.0 * (r_who - 0.5))
        elif outcome == "blocked":
            if r_after < 0.42:
                side = 0.0 if st.ball_y < GOAL_Y else PITCH_W
                st.restart = ("corner", t, abs_x(t, PITCH_L), side)
            elif r_after < 0.70:
                p = self.pick_near(o, 18.0, GOAL_Y, r_who)
                self.give(o, p[0], 18.0, st.ball_y)
            else:
                p = self.pick_near(t, 82.0, st.ball_y, r_who)
                self.give(t, p[0], 82.0, st.ball_y)
        else:
            st.restart = ("goal_kick", o, abs_x(o, 6.0), GOAL_Y)
