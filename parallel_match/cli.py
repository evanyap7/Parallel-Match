import argparse
import json
from collections import Counter

from . import realism
from .sim import simulate
from .teams import build_league, club_by_code


def _cmd_clubs(_):
    for c in build_league():
        print(f"{c.code}  {c.name:<20} {c.formation:<8} q={c.quality:.2f}  {c.archetype}")


def _cmd_match(args):
    clubs = build_league()
    home, away = club_by_code(clubs, args.home), club_by_code(clubs, args.away)
    rec = simulate(home, away, args.seed, args.id)
    counts = Counter(e.type for e in rec.events)
    print(f"{home.name} {rec.score[0]} - {rec.score[1]} {away.name}  (seed {args.seed})")
    print(f"{len(rec.events)} events: " + ", ".join(f"{k} {v}" for k, v in counts.most_common()))
    for e in rec.events:
        if e.type in ("goal", "card", "offside") or (e.type == "foul" and e.extra.get("call") == "penalty"):
            d = e.to_dict()
            print(f"  {d['min']:>5}'  {d['type']:<8} {d.get('team', ''):<4} {d.get('player', '')}"
                  f"  {json.dumps({k: d[k] for k in ('contact', 'margin', 'call', 'color', 'assist') if k in d})}")
    contestable = [e for e in rec.events if e.extra.get("contestable")]
    print(f"{len(contestable)} contestable moments")
    if args.out:
        with open(args.out, "w") as f:
            json.dump(rec.to_dict(), f, indent=1)
        print(f"wrote {args.out}")


def _cmd_realism(args):
    rep = realism.run(args.matches, args.seed)
    path = realism.write(rep, args.out_dir)
    print(realism.to_markdown(rep))
    print(f"wrote {path}")


def _cmd_season(args):
    from . import season, winprob
    if args.winprob:
        winprob.save_table(winprob.build_table(1600, workers=args.workers))
        print(f"wrote {winprob.TABLE_PATH}")
    s = season.build_season(workers=args.workers)
    print(f"wrote {season.save(s)}")
    for m in s["matches"]:
        if m["story"]:
            print(f"  {m['match_id']}  {m['home']} {m['score'][0]}-{m['score'][1]} {m['away']}  {m['summary']}")


def _cmd_export(args):
    from . import season
    print(f"wrote {season.export(season.load(), args.out)}")


def _cmd_fork(args):
    from .api import run_fork
    change = json.loads(args.change)
    r = run_fork(args.match, args.event, change, args.rollouts, use_cache=False)
    print(f"{r['description']}  ({r['rollouts']} rollouts, {r['timing']['total_s']}s)")
    print(f"original {r['original']['final_score']} {r['original']['outcome']}")
    print(f"alternate {r['alternate']['final_score']} {r['alternate']['outcome']}")
    print(f"shift {r['outcome_shift']}  ci95 {r['uncertainty']['shift_ci95']}")
    if r["history"]:
        print(f"history: {r['history']['description']}; agrees={r['history']['agrees_with_simulation']}")
    if args.out:
        with open(args.out, "w") as f:
            json.dump(r, f, indent=1)
        print(f"wrote {args.out}")


def _cmd_precompute(args):
    """Precompute forks for every flip-able moment in the story matches."""
    import time
    from .api import _record, _season, cache_path, run_fork
    from .fork import ForkError, featured_moments
    ids = args.matches.split(",") if args.matches else [m["match_id"] for m in _season()["matches"] if m["story"]]
    for mid in ids:
        t0, n = time.perf_counter(), 0
        for m in featured_moments(_record(mid), args.limit):
            for change in m["changes"]:
                if change["type"] == "substitution":
                    continue  # needs a chosen player; computed live
                try:
                    r = run_fork(mid, m["id"], change, args.rollouts, use_cache=False)
                except ForkError:
                    continue
                p = cache_path(mid, m["id"], change)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(r, separators=(",", ":")))
                n += 1
        print(f"{mid}: {n} forks in {time.perf_counter() - t0:.0f}s")


def main(argv=None):
    p = argparse.ArgumentParser(prog="parallel_match")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("clubs").set_defaults(fn=_cmd_clubs)
    m = sub.add_parser("match")
    m.add_argument("--home", default="HAR")
    m.add_argument("--away", default="NOR")
    m.add_argument("--seed", type=int, default=12)
    m.add_argument("--id", default="m012")
    m.add_argument("--out")
    m.set_defaults(fn=_cmd_match)
    r = sub.add_parser("realism")
    r.add_argument("--matches", type=int, default=200)
    r.add_argument("--seed", type=int, default=1000)
    r.add_argument("--out-dir", default="reports")
    r.set_defaults(fn=_cmd_realism)
    s = sub.add_parser("season", help="build data/season.json (fixtures, seeds, planted stories)")
    s.add_argument("--workers", type=int, default=8)
    s.add_argument("--winprob", action="store_true", help="also rebuild the win probability table")
    s.set_defaults(fn=_cmd_season)
    x = sub.add_parser("export", help="flat season tables for Microsoft Fabric")
    x.add_argument("--out", default="out/season")
    x.set_defaults(fn=_cmd_export)
    f = sub.add_parser("fork", help="what if? on one moment of a season match")
    f.add_argument("--match", required=True)
    f.add_argument("--event")
    f.add_argument("--change", default='{"type": "flip_call"}')
    f.add_argument("--rollouts", type=int, default=200)
    f.add_argument("--out")
    f.set_defaults(fn=_cmd_fork)
    pc = sub.add_parser("precompute", help="cache forks for the story matches")
    pc.add_argument("--matches", help="comma-separated match ids (default: story matches)")
    pc.add_argument("--rollouts", type=int, default=500)
    pc.add_argument("--limit", type=int, default=12, help="featured moments per match")
    pc.set_defaults(fn=_cmd_precompute)
    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
