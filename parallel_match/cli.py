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
    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
