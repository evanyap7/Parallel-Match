"""Realism report: per-match averages from simulated matches compared with
football-like target ranges.

The target ranges are approximate figures for a top-flight league season
(per match, both teams combined). They are a sanity band, not measured
truth, and should be checked against public aggregate statistics before
quoting them anywhere.
"""

import json
import time
from pathlib import Path

from .sim import simulate
from .teams import build_league

# metric: (lo, hi, description)
TARGETS = {
    "goals": (2.4, 3.2, "goals per match"),
    "shots": (20.0, 28.0, "shots per match"),
    "shots_on_target": (7.0, 11.0, "shots on target per match"),
    "conversion": (0.09, 0.13, "goals per shot"),
    "passes": (700.0, 1050.0, "passes attempted per match"),
    "pass_accuracy": (0.78, 0.87, "share of passes completed"),
    "fouls": (18.0, 26.0, "fouls given per match"),
    "yellows": (2.8, 4.8, "yellow cards per match"),
    "reds": (0.03, 0.25, "red cards per match"),
    "corners": (8.0, 12.0, "corners per match"),
    "offsides": (2.0, 5.0, "offsides given per match"),
    "penalties": (0.15, 0.45, "penalties awarded per match"),
    "home_win": (0.40, 0.50, "share of home wins"),
    "draw": (0.20, 0.30, "share of draws"),
    "events": (1000.0, 1500.0, "events per match (project spec)"),
    "subs": (6.0, 10.0, "substitutions per match"),
}


def match_stats(rec) -> dict:
    s = {k: 0 for k in ("goals", "shots", "shots_on_target", "passes", "passes_ok",
                        "fouls", "yellows", "reds", "corners", "offsides", "penalties", "subs")}
    home_passes = 0
    for e in rec.events:
        ty = e.type
        if ty == "goal":
            s["goals"] += 1
        elif ty == "shot":
            s["shots"] += 1
            s["shots_on_target"] += e.extra["on_target"]
            s["penalties"] += e.extra["kind"] == "penalty"
        elif ty == "pass":
            s["passes"] += 1
            s["passes_ok"] += e.extra["success"]
            home_passes += e.team == rec.home
        elif ty == "foul":
            s["fouls"] += 1
        elif ty == "card":
            s["yellows" if e.extra["color"] == "yellow" else "reds"] += 1
        elif ty == "corner":
            s["corners"] += 1
        elif ty == "offside":
            s["offsides"] += 1
        elif ty == "substitution":
            s["subs"] += 1
    s["events"] = len(rec.events)
    s["home_pass_share"] = home_passes / max(1, s["passes"])
    h, a = rec.score
    s["result"] = "H" if h > a else "A" if a > h else "D"
    return s


def fixtures(n_matches: int, base_seed: int):
    """Cycle through a double round robin of the 10 clubs until n matches."""
    clubs = build_league()
    pairs = [(h, a) for h in clubs for a in clubs if h is not a]
    for i in range(n_matches):
        h, a = pairs[i % len(pairs)]
        yield h, a, base_seed + i, f"r{i:04d}"


def run(n_matches: int = 200, base_seed: int = 1000) -> dict:
    t0 = time.perf_counter()
    rows = [match_stats(simulate(h, a, seed, mid)) for h, a, seed, mid in fixtures(n_matches, base_seed)]
    elapsed = time.perf_counter() - t0
    n = len(rows)

    def mean(k):
        return sum(r[k] for r in rows) / n

    values = {k: mean(k) for k in ("goals", "shots", "shots_on_target", "passes", "fouls",
                                   "yellows", "reds", "corners", "offsides", "penalties",
                                   "events", "subs")}
    values["pass_accuracy"] = sum(r["passes_ok"] for r in rows) / max(1, sum(r["passes"] for r in rows))
    values["conversion"] = sum(r["goals"] for r in rows) / max(1, sum(r["shots"] for r in rows))
    values["home_win"] = sum(r["result"] == "H" for r in rows) / n
    values["draw"] = sum(r["result"] == "D" for r in rows) / n
    metrics = []
    for k, (lo, hi, desc) in TARGETS.items():
        v = values[k]
        metrics.append({"name": k, "description": desc, "value": round(v, 3),
                        "lo": lo, "hi": hi, "ok": lo <= v <= hi})
    return {
        "matches": n, "base_seed": base_seed, "seconds": round(elapsed, 2),
        "matches_per_sec": round(n / elapsed, 2),
        "home_pass_share": round(mean("home_pass_share"), 3),
        "metrics": metrics,
        "all_ok": all(m["ok"] for m in metrics),
    }


def to_markdown(rep: dict) -> str:
    lines = [
        "# Realism report v1",
        "",
        f"{rep['matches']} simulated matches (seeds {rep['base_seed']}..{rep['base_seed'] + rep['matches'] - 1}), "
        f"{rep['seconds']}s total, {rep['matches_per_sec']} matches/sec on the machine that ran it.",
        "",
        "Target ranges are approximate top-flight figures per match (both teams). "
        "They are a sanity band to verify against public aggregate stats, not measured truth.",
        "",
        "| Metric | Simulated | Target range | In range |",
        "|---|---|---|---|",
    ]
    for m in rep["metrics"]:
        lines.append(f"| {m['description']} | {m['value']} | {m['lo']} to {m['hi']} | {'yes' if m['ok'] else 'NO'} |")
    lines += ["", f"Home share of passes (possession proxy): {rep['home_pass_share']}", ""]
    return "\n".join(lines)


def write(rep: dict, out_dir: str = "reports") -> Path:
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / "realism_v1.json").write_text(json.dumps(rep, indent=2))
    md = d / "realism_v1.md"
    md.write_text(to_markdown(rep))
    return md
