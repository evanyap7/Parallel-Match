# Parallel Match

Microsoft x Premier League "Inside the Game" developer hackathon entry.

A fan taps a contestable moment (foul, offside, card, penalty, substitution) and asks
"what if that wasn't a foul?". The screen splits into the real match and an alternate
match played as a full broadcast, backed by Monte Carlo re-simulation and precedent from
the league's own history.

**All data is synthetic.** Fictional clubs and players only. No real match data, logos,
names or music. The simulator is tuned so its per-match averages fall inside
football-like ranges (see the realism report).

## Quick start

Python 3.11+, no dependencies.

```bash
python3 -m parallel_match clubs                                   # the fictional league
python3 -m parallel_match match --home HAR --away NOR --seed 12   # one match summary
python3 -m parallel_match realism --matches 360                   # writes reports/realism_v1.md
python3 -m parallel_match fork --match m052 --event m052-0715     # what if that penalty was not given?
python3 -m parallel_match export --out out/season                 # flat tables for Microsoft Fabric
python3 -m unittest discover -s tests -t .                        # all tests
```

API (for the front end and agents), see `docs/api.md`:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-api.txt
.venv/bin/uvicorn parallel_match.api:app --reload                 # http://localhost:8000/docs
```

## Fork engine

`parallel_match/fork.py` answers "what if?" for one moment:

1. Replay the match to just before the moment (deterministic, so exact).
2. Turn the change into a force the simulator applies at exactly that step: flip a
   call, change a card, a shot goes in or a goal does not, a substitution, a tactical
   change, or a player unavailable.
3. Paired rollouts: each rollout plays the original and the altered branch with the
   same random numbers, so the difference is the change, not luck. Rollout 0 keeps the
   match seed, so its original branch is the real match.
4. One typical alternate timeline (the most common alternate score) is kept for the
   parallel broadcast, with a win-probability curve for both timelines.

Speed, measured on a 10-core laptop: one rollout from mid-match is about 30 ms of CPU;
200 rollouts take 2 to 4 s on 8 workers. Featured moments in the story matches are
precomputed at 500 rollouts and served instantly.

The precedent check (`parallel_match/history.py`) is independent of the rollouts:
comparable borderline decisions in the season, split by whether the call was given.
If the two estimates disagree, the response says so.

## Season

`parallel_match/data/season.json` holds 90 fixtures (double round robin) and their
seeds; every match regenerates exactly from its seed. Five story matches were planted
by searching seeds for a two-goal comeback, an early red card, a stoppage-time winner,
a borderline penalty and a tight late offside. Still generated, just selected.

## Generator design

- **Event level, not physics.** About 1,200 events per match: passes, dribbles, tackles,
  fouls, offsides, shots, set pieces, cards, substitutions.
- **Small copyable state** (`parallel_match/state.py`): clock, score, ball, possession,
  fatigue, cards, tactics, and the RNG position. `MatchState.copy()` is the fork.
- **Derived positions.** Players are not stored. Each step they are placed from formation
  slots, pulled toward the ball by team style (press, attack). Forwards play on the
  shoulder of the defensive line, so offside is measured against real derived positions.
- **Officiating with margins.** Fouls carry contact severity 0..1 against the referee's
  threshold. Offsides carry a margin in metres. Officials perceive both with noise, so
  borderline calls can flip. Rules live in `parallel_match/rules.py` as pure functions.
- **Seeded and deterministic.** Randomness is keyed by (seed, step), so the same seed
  replays the identical match, and a fork shares random numbers with the original
  until the two diverge.

## Layout

- `parallel_match/` simulator: `sim.py` (match engine), `rules.py` (Laws), `teams.py`
  (fictional league), `state.py`, `rng.py`, `fork.py` (what-if engine), `winprob.py`,
  `season.py`, `history.py` (precedent), `api.py` (FastAPI), `realism.py`, `cli.py`
- `parallel_match/data/` season fixtures, win-probability table, precomputed forks
- `tests/` determinism, state copy, rules, fork engine, API, realism
- `docs/` event schema, API, history query for Fabric, build plan
- `fixtures/` sample match and fork responses for front-end work
- `reports/realism_v1.md` latest realism report
- `Dockerfile` the API image for Azure Container Apps
