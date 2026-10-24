"""The fictional season: a 90-match double round robin with planted stories.

A season is fully defined by fixtures and seeds, because every match replays
deterministically from its seed. Memorable matches are still generated, just
selected: for a few fixtures we try many seeds and keep the best story.
"""

import csv
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from .rng import hash_unit
from .sim import MatchRecord, simulate
from .teams import build_league, club_by_code

SEASON_PATH = Path(__file__).parent / "data" / "season.json"
WORLD_SEED = 2026
SEEDS_PER_FIXTURE = 30

# Stories to plant. Each is searched across every fixture not already used,
# because some match-ups (two tight defences) almost never produce a given story.
STORIES = ("comeback", "early_red", "late_winner", "penalty_drama", "tight_offside")


def schedule(codes: list[str]) -> list[tuple[int, str, str]]:
    """Circle-method double round robin: [(round, home, away)]."""
    teams = list(codes)
    n = len(teams)
    rounds = []
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = teams[i], teams[n - 1 - i]
            pairs.append((a, b) if (r + i) % 2 == 0 else (b, a))
        rounds.append(pairs)
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    second = [[(b, a) for a, b in rnd] for rnd in rounds]
    out = []
    for r, rnd in enumerate(rounds + second, start=1):
        out.extend((r, h, a) for h, a in rnd)
    return out


def match_seed(world: int, n: int, k: int = 0) -> int:
    return int(hash_unit(world, n, k, 0x5EA5) * (1 << 62))


# ---- story detectors: return a score (higher is better) or None ------------

def _goals(rec):
    return [e for e in rec.events if e.type == "goal"]


def story_comeback(rec):
    deficit = {rec.home: 0, rec.away: 0}
    gd = 0
    for e in _goals(rec):
        gd += 1 if e.team == rec.home else -1
        deficit[rec.home] = max(deficit[rec.home], -gd)
        deficit[rec.away] = max(deficit[rec.away], gd)
    h, a = rec.score
    winner = rec.home if h > a else rec.away if a > h else None
    if winner is None or deficit[winner] < 2 or h + a > 9 or max(h, a) > 5:
        return None  # keep it believable: a 5-4, not a 9-3
    return 10 * deficit[winner] + h + a


def story_early_red(rec):
    reds = [e for e in rec.events if e.type == "card" and e.extra["color"] == "red"]
    if not reds or not 5 * 60 <= reds[0].t <= 20 * 60:
        return None
    return 100 - reds[0].t / 60 + (5 if rec.score[0] != rec.score[1] else 0)


def story_late_winner(rec):
    g = _goals(rec)
    h, a = rec.score
    if not g or h == a or abs(h - a) != 1:
        return None
    last = g[-1]
    winner = rec.home if h > a else rec.away
    if last.team != winner or not last.min.startswith("90+"):
        return None
    return 10 + h + a


def story_penalty_drama(rec):
    best = None
    for i, e in enumerate(rec.events):
        if e.type == "foul" and e.extra["call"] == "penalty" and abs(e.extra["margin"]) < 0.08:
            nxt = rec.events[i + 1:i + 6]
            scored = any(x.type == "goal" for x in nxt)
            h, a = rec.score
            score = (10 if scored else 0) + (5 if abs(h - a) <= 1 else 0) - abs(e.extra["margin"]) * 50
            best = score if best is None else max(best, score)
    return best


def story_tight_offside(rec):
    best = None
    for e in rec.events:
        if e.type == "offside" and abs(e.extra["margin"]) < 0.15 and e.t > 70 * 60:
            h, a = rec.score
            if abs(h - a) <= 1:
                score = 10 - abs(e.extra["margin"]) * 30 + e.t / 600
                best = score if best is None else max(best, score)
    return best


DETECTORS = {"comeback": story_comeback, "early_red": story_early_red,
             "late_winner": story_late_winner, "penalty_drama": story_penalty_drama,
             "tight_offside": story_tight_offside}


def _try_seed(args):
    home_code, away_code, seed, mid, story = args
    clubs = build_league()
    rec = simulate(club_by_code(clubs, home_code), club_by_code(clubs, away_code), seed, mid)
    return seed, DETECTORS[story](rec), list(rec.score)


def _summary(rec: MatchRecord, story: str) -> str:
    h, a = rec.score
    if story == "comeback":
        return f"{rec.home} {h}-{a} {rec.away}: comeback from two goals down"
    if story == "early_red":
        red = next(e for e in rec.events if e.type == "card" and e.extra["color"] == "red")
        return f"Red card for {red.player} ({red.team}) in the {red.min}' minute"
    if story == "late_winner":
        g = _goals(rec)[-1]
        return f"Winner from {g.player} ({g.team}) in the {g.min}' minute"
    if story == "penalty_drama":
        return "Borderline penalty decision in a tight match"
    if story == "tight_offside":
        return "Offside by centimetres late in a one-goal game"
    return story


def build_season(world: int = WORLD_SEED, workers: int = 8, per_fixture: int = SEEDS_PER_FIXTURE) -> dict:
    clubs = build_league()
    fixtures = schedule([c.code for c in clubs])
    matches = []
    for n, (rnd, h, a) in enumerate(fixtures, start=1):
        matches.append({"match_id": f"m{n:03d}", "round": rnd, "home": h, "away": a,
                        "seed": match_seed(world, n), "story": None})

    with ProcessPoolExecutor(workers) as ex:
        for story in STORIES:
            jobs = [(m["home"], m["away"], match_seed(world, n, k), m["match_id"], story)
                    for n, m in enumerate(matches, start=1) if m["story"] is None
                    for k in range(1, per_fixture + 1)]
            best = None
            for job, (seed, score, _) in zip(jobs, ex.map(_try_seed, jobs, chunksize=30)):
                if score is not None and (best is None or score > best[0]):
                    best = (score, seed, job[3])
            if best is not None:
                m = next(x for x in matches if x["match_id"] == best[2])
                m["seed"] = best[1]
                m["story"] = story

    for m in matches:
        rec = simulate(club_by_code(clubs, m["home"]), club_by_code(clubs, m["away"]), m["seed"], m["match_id"])
        m["score"] = list(rec.score)
        if m["story"]:
            m["summary"] = _summary(rec, m["story"])
    return {"world_seed": world, "matches": matches}


def save(season: dict, path: Path = SEASON_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(season, indent=1))
    return path


def load(path: Path = SEASON_PATH) -> dict:
    return json.loads(path.read_text())


def record(season: dict, match_id: str) -> MatchRecord:
    clubs = build_league()
    for m in season["matches"]:
        if m["match_id"] == match_id:
            return simulate(club_by_code(clubs, m["home"]), club_by_code(clubs, m["away"]),
                            m["seed"], match_id)
    raise KeyError(match_id)


def standings(season: dict) -> list[dict]:
    table = {}
    for m in season["matches"]:
        h, a = m["score"]
        for code, gf, ga in ((m["home"], h, a), (m["away"], a, h)):
            row = table.setdefault(code, {"club": code, "p": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0, "pts": 0})
            row["p"] += 1
            row["gf"] += gf
            row["ga"] += ga
            if gf > ga:
                row["w"] += 1
                row["pts"] += 3
            elif gf == ga:
                row["d"] += 1
                row["pts"] += 1
            else:
                row["l"] += 1
    return sorted(table.values(), key=lambda r: (-r["pts"], -(r["gf"] - r["ga"]), -r["gf"], r["club"]))


def export(season: dict, out_dir: str) -> Path:
    """Flat tables for Microsoft Fabric: matches.csv, events.jsonl, moments.csv."""
    from .history import moment_rows

    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    rows = []
    with open(d / "matches.csv", "w", newline="") as mf, open(d / "events.jsonl", "w") as ef:
        w = csv.writer(mf)
        w.writerow(["match_id", "round", "home", "away", "seed", "home_goals", "away_goals", "story"])
        for m in season["matches"]:
            w.writerow([m["match_id"], m["round"], m["home"], m["away"], m["seed"],
                        m["score"][0], m["score"][1], m["story"] or ""])
            rec = record(season, m["match_id"])
            for e in rec.events:
                d_ = e.to_dict()
                d_["match_id"] = m["match_id"]
                ef.write(json.dumps(d_) + "\n")
            rows.extend(moment_rows(rec))
    with open(d / "moments.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return d
