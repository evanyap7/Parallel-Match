"""Fork engine: copy the state at a moment, apply one change, play on.

fork() answers "what if?" for one event of a simulated match:

1. Replay the match deterministically to just before the event's step.
2. Turn the requested change into a force (step, key, value) that the
   simulator applies at exactly that step.
3. Run paired rollouts from that state. For each rollout seed, the original
   branch and the altered branch play with the same random numbers, so the
   difference between them is the effect of the change, not luck. Rollout 0
   keeps the match seed, so its original branch is the real match.
4. Keep one typical alternate timeline for the parallel broadcast.

All numbers here come from code. Agents only phrase them.
"""

import math
import os
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

from . import winprob
from .rng import hash_unit
from .sim import Context, MatchRecord, new_match, play, simulate, step
from .state import MatchState
from .teams import Club

DEFAULT_ROLLOUTS = 200
TACTIC_KEYS = ("attack", "defence", "press", "tempo", "directness")
SHOT_OUTCOMES = ("goal", "saved", "off_target", "blocked")


class ForkError(ValueError):
    """The requested change does not apply to the chosen moment."""


# ---- replay -----------------------------------------------------------------

def state_before(home: Club, away: Club, seed: int, match_id: str, target_step: int):
    """(ctx, state after step target_step - 1, events produced so far)."""
    ctx, st = new_match(home, away, seed, match_id)
    events = []
    while st.step < target_step - 1 and not st.finished:
        events.extend(step(ctx, st))
    return ctx, st, events


def find_event(rec: MatchRecord, event_id: str):
    for e in rec.events:
        if e.id == event_id:
            return e
    raise ForkError(f"no event {event_id!r} in match {rec.match_id}")


# ---- changes ----------------------------------------------------------------

def _team(ctx: Context, code: str) -> int:
    for i, c in enumerate(ctx.clubs):
        if c.code == code:
            return i
    raise ForkError(f"team {code!r} is not in this match")


def _idx(ctx: Context, t: int, pid: str) -> int:
    for i, p in enumerate(ctx.clubs[t].squad):
        if p.id == pid:
            return i
    raise ForkError(f"player {pid!r} is not in {ctx.clubs[t].code}'s squad")


def fork_step(ev, change: dict) -> int:
    """The simulator step at which the change is applied."""
    if change.get("type") == "unavailable":
        return 1
    return ev.step


def resolve_change(ctx: Context, st: MatchState, rec: MatchRecord, ev, change: dict):
    """Validate the change and turn it into (force, description)."""
    ct = change.get("type")
    S = fork_step(ev, change)
    x = ev.extra if ev is not None else {}

    if ct == "none":
        return None, "no change (control run)"

    if ct == "flip_call":
        if ev.type == "foul":
            return (S, "foul", False), f"no foul given instead of a {x['call'].replace('_', ' ')}"
        if ev.type in ("tackle", "dribble") and x.get("call") == "no_foul":
            return (S, "foul", True), "foul given instead of play on"
        if ev.type == "offside":
            return (S, "offside", False), "onside instead of offside, play continues"
        if ev.type == "pass" and x.get("call") == "onside":
            return (S, "offside", True), "offside given instead of onside"
        if ev.type == "card":
            return (S, "card", None), "no card shown"
        raise ForkError(f"no officiating call to flip on a {ev.type} event")

    if ct == "not_sent_off":
        if ev.type != "card" or x.get("color") != "red":
            raise ForkError("not_sent_off needs a red card event")
        if x.get("reason") == "second_yellow":
            return (S, "card", None), "second yellow not shown, player stays on"
        return (S, "card", "yellow"), "yellow card instead of a red, player stays on"

    if ct == "card":
        if ev.type != "foul":
            raise ForkError("card changes need a foul event")
        card = change.get("card")
        if card not in (None, "yellow", "red"):
            raise ForkError("card must be null, 'yellow' or 'red'")
        return (S, "card", card), f"{card or 'no'} card for this foul"

    if ct == "shot_outcome":
        outcome = change.get("outcome")
        if outcome not in SHOT_OUTCOMES:
            raise ForkError(f"outcome must be one of {SHOT_OUTCOMES}")
        shot = ev
        if ev.type == "goal":
            shots = [e for e in rec.events if e.step == ev.step and e.type == "shot"]
            if not shots:
                raise ForkError("no shot found for this goal")
            shot = shots[-1]
        if shot.type != "shot":
            raise ForkError("shot_outcome needs a shot or goal event")
        if shot.extra["outcome"] == outcome:
            raise ForkError(f"the shot was already {outcome}")
        return (S, "shot", outcome), f"shot {shot.extra['outcome'].replace('_', ' ')} becomes {outcome.replace('_', ' ')}"

    if ct == "substitution":
        t = _team(ctx, change.get("team", ""))
        off, on = _idx(ctx, t, change.get("off", "")), _idx(ctx, t, change.get("on", ""))
        if ev.type == "substitution" and ev.team == ctx.clubs[t].code:
            # Replace the original substitution: the player it brought on is still on the bench here.
            if off not in st.on[t] or on < 11 and st.played[t][on]:
                raise ForkError("that substitution is not possible at this moment")
            return ((S, "sub_override", {"team": t, "off": off, "on": on}),
                    f"{change['off']} off for {change['on']} instead of the original change")
        if off not in st.on[t]:
            raise ForkError(f"{change['off']} is not on the pitch at this moment")
        if st.played[t][on]:
            raise ForkError(f"{change['on']} has already played")
        if st.subs[t] >= 5:
            raise ForkError("no substitutions left")
        return ((S, "pre", {"kind": "sub", "team": t, "off": off, "on": on}),
                f"{change['off']} off, {change['on']} on")

    if ct == "tactics":
        t = _team(ctx, change.get("team", ""))
        new = change.get("set") or {}
        if not new or any(k not in TACTIC_KEYS or not 0.0 <= float(v) <= 1.0 for k, v in new.items()):
            raise ForkError(f"tactics.set needs keys from {TACTIC_KEYS} with values 0..1")
        new = {k: float(v) for k, v in new.items()}
        desc = ", ".join(f"{k} {st.tactics[t][k]:.2f} to {v:.2f}" for k, v in new.items())
        return (S, "pre", {"kind": "tactics", "team": t, "set": new}), f"tactical change: {desc}"

    if ct == "unavailable":
        t = _team(ctx, change.get("team", ""))
        off = _idx(ctx, t, change.get("player", ""))
        squad = ctx.clubs[t].squad
        if off >= 11:
            raise ForkError(f"{change['player']} is not in the starting XI")
        bench = [i for i in range(11, len(squad)) if squad[i].pos == squad[off].pos]
        if not bench:
            raise ForkError("no like-for-like replacement on the bench")
        return ((1, "pre", {"kind": "unavailable", "team": t, "off": off, "on": bench[0]}),
                f"{change['player']} unavailable, {squad[bench[0]].id} starts")

    raise ForkError(f"unknown change type {ct!r}")


# ---- rollouts ---------------------------------------------------------------

def rollout_seed(seed: int, fork_at: int, r: int) -> int | None:
    """Rollout 0 keeps the match seed; others get a derived seed."""
    if r == 0:
        return None
    return int(hash_unit(seed, fork_at, r, 0xF0) * (1 << 62))


def _play_branch(ctx, st0, force, seed):
    st = st0.copy()
    st.force = force
    first = step(ctx, st)
    if seed is not None:
        st.seed = seed
    rest = play(ctx, st)
    return st, first, rest


def _rollout_pairs(args):
    ctx, st0, force, seeds = args
    out = []
    for s in seeds:
        a, _, _ = _play_branch(ctx, st0, None, s)
        b, _, _ = _play_branch(ctx, st0, force, s)
        out.append(((a.score[0], a.score[1]), (b.score[0], b.score[1])))
    return out


_EXECUTOR = None


def _executor(workers: int):
    global _EXECUTOR
    if _EXECUTOR is None or _EXECUTOR._max_workers != workers:
        if _EXECUTOR is not None:
            _EXECUTOR.shutdown(cancel_futures=True)
        _EXECUTOR = ProcessPoolExecutor(max_workers=workers)
    return _EXECUTOR


def default_workers() -> int:
    # PM_FORK_WORKERS overrides the guess. In a container os.cpu_count() can
    # report the vCPUs it was given (pm-api: 2), and "minus one" then leaves
    # a single worker: a fresh early-match fork took ~32 s live instead of ~16.
    env = os.environ.get("PM_FORK_WORKERS", "").strip()
    if env.isdigit() and int(env) > 0:
        return min(8, int(env))
    return max(1, min(8, (os.cpu_count() or 2) - 1))


def run_pairs(ctx, st0, force, n: int, workers: int):
    seeds = [rollout_seed(st0.seed, st0.step + 1, r) for r in range(n)]
    if workers <= 1 or n < 8:
        return _rollout_pairs((ctx, st0, force, seeds)), seeds
    chunk = math.ceil(n / (workers * 2))
    jobs = [(ctx, st0, force, seeds[i:i + chunk]) for i in range(0, n, chunk)]
    out = []
    for part in _executor(workers).map(_rollout_pairs, jobs):
        out.extend(part)
    return out, seeds


# ---- summary ----------------------------------------------------------------

def _res(score) -> int:
    return 0 if score[0] > score[1] else (1 if score[0] == score[1] else 2)


def _dist(scores) -> dict:
    c = Counter(_res(s) for s in scores)
    n = len(scores)
    return {"home": round(c[0] / n, 3), "draw": round(c[1] / n, 3), "away": round(c[2] / n, 3)}


def _paired_shift(pairs) -> tuple[dict, dict]:
    n = len(pairs)
    shift, ci = {}, {}
    for k, name in enumerate(("home", "draw", "away")):
        d = [(_res(b) == k) - (_res(a) == k) for a, b in pairs]
        mean = sum(d) / n
        var = sum((x - mean) ** 2 for x in d) / max(1, n - 1)
        half = 1.96 * math.sqrt(var / n)
        shift[name] = round(mean, 3)
        ci[name] = [round(mean - half, 3), round(mean + half, 3)]
    return shift, ci


def fork(home: Club, away: Club, seed: int, match_id: str, event_id: str | None, change: dict,
         rollouts: int = DEFAULT_ROLLOUTS, workers: int | None = None,
         record: MatchRecord | None = None) -> dict:
    t0 = time.perf_counter()
    workers = default_workers() if workers is None else workers
    rec = record or simulate(home, away, seed, match_id)
    if event_id is None:
        if change.get("type") != "unavailable":
            raise ForkError("event_id is required for this change")
        ev = rec.events[0]
    else:
        ev = find_event(rec, event_id)
    S = fork_step(ev, change)
    ctx, st0, before = state_before(home, away, seed, match_id, S)
    force, description = resolve_change(ctx, st0, rec, ev, change)

    pairs, seeds = run_pairs(ctx, st0, force, rollouts, workers)
    orig_scores = [p[0] for p in pairs]
    alt_scores = [p[1] for p in pairs]
    t_rollouts = time.perf_counter() - t0

    # Typical alternate: the most common alternate final score. Prefer rollout 0
    # (same luck as the real match) when it lands on that score.
    modal = Counter(alt_scores).most_common(1)[0][0]
    pick = 0 if alt_scores[0] == modal else alt_scores.index(modal)
    alt_ctx = replace(ctx, match_id=f"{match_id}x")
    _, first, rest = _play_branch(alt_ctx, st0, force, seeds[pick])
    alt_events = [e.to_dict() for e in first + rest]

    original_events = [e.to_dict() for e in rec.events]
    original_at = [e for e in original_events if e["step"] == S]
    prefix = [e.to_dict() for e in before]
    diverged = [{k: v for k, v in e.items() if k != "id"} for e in original_at] != \
               [{k: v for k, v in e.items() if k != "id"} for e in alt_events if e["step"] == S]

    shift, ci = _paired_shift(pairs)
    return {
        "match_id": match_id,
        "event_id": ev.id,
        "change": change,
        "description": description,
        "model_world": True,
        "diverged": diverged,
        "divergence": {"event_id": ev.id, "step": S, "t": ev.t if S == ev.step else 0,
                       "min": ev.min if S == ev.step else "0"},
        "moment": ev.to_dict(),
        "alternate_moment": [e for e in alt_events if e["step"] == S],
        "original": {
            "final_score": list(rec.score),
            "win_prob": winprob.curve(original_events, rec.home),
            "outcome": _dist(orig_scores),
        },
        "alternate": {
            "final_score": list(modal),
            "win_prob": winprob.curve(prefix + alt_events, rec.home),
            "outcome": _dist(alt_scores),
            "rollout_index": pick,
            "timeline": alt_events,
        },
        "rollouts": rollouts,
        "outcome_shift": shift,
        "uncertainty": {"shift_ci95": ci},
        "score_spread": [{"score": list(s), "share": round(c / rollouts, 3)}
                         for s, c in Counter(alt_scores).most_common(5)],
        "history": None,
        "timing": {"rollouts_s": round(t_rollouts, 2),
                   "total_s": round(time.perf_counter() - t0, 2), "workers": workers},
    }


# ---- moments ----------------------------------------------------------------

def moments(rec: MatchRecord) -> list[dict]:
    """Moments a fan can tap, each with the changes it supports."""
    out = []
    for e in rec.events:
        x = e.extra
        changes = []
        if x.get("contestable"):
            changes.append({"type": "flip_call"})
        if e.type == "card" and x.get("color") == "red":
            changes.append({"type": "not_sent_off"})
        if e.type == "goal":
            changes.append({"type": "shot_outcome", "outcome": "saved"})
        if e.type == "shot" and x["outcome"] in ("saved", "off_target") and x["xg"] >= 0.15:
            changes.append({"type": "shot_outcome", "outcome": "goal"})
        if e.type == "substitution":
            changes.append({"type": "substitution"})
        if not changes:
            continue
        d = e.to_dict()
        d["changes"] = changes
        out.append(d)
    return out


def _feature_score(m: dict) -> float:
    ty = m["type"]
    if ty == "goal":
        s = 10.0
    elif ty == "card" and m.get("color") == "red":
        s = 9.0
    elif ty == "foul" and m.get("call") == "penalty":
        s = 9.0
    elif ty in ("offside", "pass") and m.get("contestable"):
        s = 6.0 - 5.0 * abs(m.get("margin", m.get("offside_margin", 1.0)))
    elif m.get("contestable"):
        s = 4.0 - 10.0 * abs(m.get("margin", 0.3))
    else:
        s = 2.0
    return s + (1.5 if m["t"] > 70 * 60 else 0.0)


def featured_moments(rec: MatchRecord, limit: int = 12) -> list[dict]:
    """The moments a fan is most likely to argue about, in match order."""
    ranked = sorted(moments(rec), key=_feature_score, reverse=True)[:limit]
    return sorted(ranked, key=lambda m: m["t"])
