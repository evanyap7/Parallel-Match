"""Live win probability from match state, learned from simulated matches.

P(final result | elapsed minute, goal difference, man advantage), counted over
many simulated matches and smoothed toward coarser cells where data is thin.
Home perspective throughout, so home advantage is baked in. Team strength is
not a feature yet.
"""

import json
from functools import lru_cache
from pathlib import Path

BUCKET_MIN = 5
N_BUCKETS = 20
GD_CAP = 3
K_CELL = 8.0    # smoothing weight (in matches) toward the (gd, md) prior
K_PRIOR = 4.0   # smoothing weight (in matches) toward the global prior
TABLE_PATH = Path(__file__).parent / "data" / "winprob.json"


def _key(minute: float, gd: int, md: int) -> str:
    b = min(int(minute) // BUCKET_MIN, N_BUCKETS - 1)
    gd = max(-GD_CAP, min(GD_CAP, gd))
    md = max(-1, min(1, md))
    return f"{b},{gd},{md}"


def minute_states(events: list[dict], home: str):
    """Yield (minute, label, gd, md) at the start of each elapsed minute, then
    the final state. gd = home minus away goals, md = home minus away players."""
    gd = md = 0
    m = 0
    label = "1"
    for e in events:
        while m * 60 <= e["t"]:
            yield m, label, gd, md
            m += 1
        label = e["min"]
        if e["type"] == "goal":
            gd += 1 if e["team"] == home else -1
        elif e["type"] == "card" and e.get("color") == "red":
            md += -1 if e["team"] == home else 1
    yield m, label, gd, md


def result_of(gd: int) -> int:
    return 0 if gd > 0 else (1 if gd == 0 else 2)


def _match_cells(args):
    """Cells a match visits (each counted once) and its final result."""
    from .sim import simulate

    h, a, seed, mid = args
    rec = simulate(h, a, seed, mid)
    events = [e.to_dict() for e in rec.events]
    cells = {_key(m, gd, md) for m, _, gd, md in minute_states(events, rec.home)}
    return cells, result_of(rec.score[0] - rec.score[1])


def build_table(n_matches: int = 1200, base_seed: int = 777, workers: int = 1) -> dict:
    """Counts are per match, not per minute, so smoothing weights mean
    something: a cell seen in 3 matches has n = 3."""
    from concurrent.futures import ProcessPoolExecutor

    from .realism import fixtures

    jobs = list(fixtures(n_matches, base_seed))
    if workers > 1:
        with ProcessPoolExecutor(workers) as ex:
            results = list(ex.map(_match_cells, jobs, chunksize=20))
    else:
        results = [_match_cells(j) for j in jobs]
    counts: dict[str, list[int]] = {}
    for cells, final in results:
        for k in cells:
            counts.setdefault(k, [0, 0, 0])[final] += 1
    return {"matches": n_matches, "base_seed": base_seed, "bucket_min": BUCKET_MIN, "counts": counts}


def save_table(table: dict, path: Path = TABLE_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(table, separators=(",", ":"), sort_keys=True))
    return path


@lru_cache(maxsize=1)
def _model():
    if TABLE_PATH.exists():
        table = json.loads(TABLE_PATH.read_text())
    else:
        table = build_table(120)
    counts = table["counts"]
    total = [0, 0, 0]
    pooled: dict[str, list[int]] = {}
    for k, c in counts.items():
        _, gd, md = k.split(",")
        p = pooled.setdefault(f"{gd},{md}", [0, 0, 0])
        for i in range(3):
            p[i] += c[i]
            total[i] += c[i]
    n = sum(total)
    global_p = [x / n for x in total]
    return counts, pooled, global_p


def prob(minute: float, gd: int, md: int) -> tuple[float, float, float]:
    counts, pooled, gp = _model()
    k = _key(minute, gd, md)
    _, g, m = k.split(",")
    pc = pooled.get(f"{g},{m}", [0, 0, 0])
    pn = sum(pc)
    prior = [(pc[i] + K_PRIOR * gp[i]) / (pn + K_PRIOR) for i in range(3)]
    c = counts.get(k, [0, 0, 0])
    n = sum(c)
    p = [(c[i] + K_CELL * prior[i]) / (n + K_CELL) for i in range(3)]
    return p[0], p[1], p[2]


def curve(events: list[dict], home: str) -> list[dict]:
    """Win probability at each elapsed minute along a timeline. The last point
    is the final result (certain)."""
    states = list(minute_states(events, home))
    out = []
    for i, (minute, label, gd, md) in enumerate(states):
        if i == len(states) - 1 and events and events[-1]["type"] == "full_time":
            r = result_of(gd)
            ph, pd, pa = (1.0 if r == 0 else 0.0, 1.0 if r == 1 else 0.0, 1.0 if r == 2 else 0.0)
        else:
            ph, pd, pa = prob(minute, gd, md)
        out.append({"minute": minute, "min": label, "home": round(ph, 3),
                    "draw": round(pd, 3), "away": round(pa, 3)})
    return out
