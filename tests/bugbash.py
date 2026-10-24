"""Backend bug bash: every change type on every story match, through the API.

Run before a demo or submission:  .venv/bin/python -W ignore -m tests.bugbash
"""
import re, sys, time
from fastapi.testclient import TestClient
from parallel_match.api import app
from parallel_match.fork import featured_moments
from parallel_match.api import _record

c = TestClient(app)
JUDGING = re.compile(r"\b(wrong|mistake|error|blunder|robbed|cheat|should have)\b", re.I)
problems, ran = [], 0

def check(mid, label, change, event_id, expect=200):
    global ran
    ran += 1
    r = c.post("/fork", json={"match_id": mid, "event_id": event_id, "change": change, "rollouts": 20})
    if r.status_code != expect:
        problems.append(f"{mid} {label}: HTTP {r.status_code} (expected {expect}) {r.text[:160]}")
        return None
    if expect != 200:
        return None
    b = r.json()
    for side in ("original", "alternate"):
        tot = sum(b[side]["outcome"].values())
        if abs(tot - 1) > 0.002:
            problems.append(f"{mid} {label}: {side} outcome sums to {tot}")
        wp = b[side]["win_prob"]
        last = wp[-1]
        if sorted((last["home"], last["draw"], last["away"])) != [0.0, 0.0, 1.0]:
            problems.append(f"{mid} {label}: {side} final win_prob not certain {last}")
        if any(p["minute"] != i for i, p in enumerate(wp)):
            problems.append(f"{mid} {label}: {side} win_prob minutes not contiguous")
    for k, (lo, hi) in b["uncertainty"]["shift_ci95"].items():
        if not lo - 1e-9 <= b["outcome_shift"][k] <= hi + 1e-9:
            problems.append(f"{mid} {label}: shift {k} outside its CI")
    if not b["diverged"]:
        problems.append(f"{mid} {label}: did not diverge")
    if not b["alternate_moment"]:
        problems.append(f"{mid} {label}: empty alternate_moment")
    tl = b["alternate"]["timeline"]
    if not tl or tl[0]["step"] != b["divergence"]["step"] or tl[-1]["type"] != "full_time":
        problems.append(f"{mid} {label}: timeline does not run from divergence to full time")
    if not all(e["id"].startswith(f"{mid}x-") for e in tl):
        problems.append(f"{mid} {label}: alternate ids not prefixed {mid}x-")
    if b["alternate"]["final_score"] != list(tl[-1]["score"]):
        problems.append(f"{mid} {label}: typical final score != timeline final score")
    text = b["description"] + " " + " ".join(str(e.get("law", "")) for e in b["alternate_moment"])
    if JUDGING.search(text) or "\u2014" in text:
        problems.append(f"{mid} {label}: wording issue: {text[:120]}")
    if change["type"] == "flip_call" and b["history"] is None and b["moment"].get("contestable"):
        problems.append(f"{mid} {label}: contestable flip has no history")
    return b

def main():
    global ran
    stories = [m for m in c.get("/matches").json() if m["story"]]
    t0 = time.perf_counter()
    for m in stories:
        mid = m["match_id"]
        ev = c.get(f"/match/{mid}").json()["events"]
        first = lambda pred: next((e for e in ev if pred(e)), None)
        home, away = m["home"], m["away"]
        cases = [
            ("flip foul", {"type": "flip_call"}, first(lambda e: e["type"] == "foul" and e.get("contestable"))),
            ("flip no_foul", {"type": "flip_call"}, first(lambda e: e.get("call") == "no_foul")),
            ("flip offside", {"type": "flip_call"}, first(lambda e: e["type"] == "offside" and e.get("contestable"))),
            ("flip onside", {"type": "flip_call"}, first(lambda e: e["type"] == "pass" and e.get("call") == "onside")),
            ("card none", {"type": "card", "card": None}, first(lambda e: e["type"] == "foul" and e.get("card"))),
            ("card yellow", {"type": "card", "card": "yellow"}, first(lambda e: e["type"] == "foul" and not e.get("card"))),
            ("not sent off", {"type": "not_sent_off"}, first(lambda e: e["type"] == "card" and e["color"] == "red")),
            ("miss goes in", {"type": "shot_outcome", "outcome": "goal"}, first(lambda e: e["type"] == "shot" and e["outcome"] != "goal")),
            ("goal saved", {"type": "shot_outcome", "outcome": "saved"}, first(lambda e: e["type"] == "goal")),
            ("tactics", {"type": "tactics", "team": home, "set": {"press": 0.95, "attack": 0.9}}, ev[300]),
            ("sub", {"type": "substitution", "team": home, "off": f"{home[0]}9", "on": f"{home[0]}20"}, ev[400]),
        ]
        sub_ev = first(lambda e: e["type"] == "substitution" and e["team"] == home)
        if sub_ev:
            on_pitch_off = f"{home[0]}10" if sub_ev["off"] != f"{home[0]}10" else f"{home[0]}8"
            cases.append(("sub override", {"type": "substitution", "team": home, "off": on_pitch_off, "on": sub_ev["player"]}, sub_ev))
        for label, change, e in cases:
            if e is None:
                continue
            check(mid, label, change, e["id"])
        check(mid, "unavailable", {"type": "unavailable", "team": away, "player": f"{away[0]}9"}, None)
        # Invalid changes must be refused cleanly.
        check(mid, "bad type", {"type": "teleport"}, ev[10]["id"], expect=422)
        check(mid, "flip on goal kick", {"type": "flip_call"},
              first(lambda e: e["type"] == "goal_kick")["id"], expect=422)
        check(mid, "bad tactic", {"type": "tactics", "team": home, "set": {"press": 3}}, ev[10]["id"], expect=422)
        check(mid, "unknown event", {"type": "flip_call"}, f"{mid}-9999", expect=422)
    live_s = time.perf_counter() - t0

    # Every featured moment is served from the precomputed cache.
    uncached, n_cached = [], 0
    for m in stories:
        for fm in featured_moments(_record(m["match_id"])):
            for change in fm["changes"]:
                if change["type"] == "substitution":
                    continue
                r = c.post("/fork", json={"match_id": m["match_id"], "event_id": fm["id"], "change": change, "rollouts": 500}).json()
                n_cached += 1
                if not r.get("cached"):
                    uncached.append(f"{m['match_id']} {fm['id']} {change}")

    print(f"{ran} API fork calls across {len(stories)} story matches in {live_s:.0f}s")
    print(f"{n_cached - len(uncached)}/{n_cached} featured-moment forks served from cache")
    print(f"{len(problems)} problems")
    for p in problems + uncached:
        print("  -", p)
    sys.exit(1 if problems or uncached else 0)


if __name__ == '__main__':
    main()
