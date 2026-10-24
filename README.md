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
python3 -m parallel_match match --seed 12 --out fixtures/m012.json
python3 -m parallel_match realism --matches 360                   # writes reports/realism_v1.md
python3 -m unittest discover -s tests -t .                        # all tests
```

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
  (fictional league), `state.py`, `rng.py`, `realism.py`, `cli.py`
- `tests/` determinism, state copy (fork with no change), rules, realism
- `docs/event-schema.md` event format for the UI and agents
- `fixtures/m012.json` sample match for front-end work
- `reports/realism_v1.md` latest realism report
