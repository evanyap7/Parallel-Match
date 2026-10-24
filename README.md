# Parallel Match

Microsoft x Premier League "Inside the Game" developer hackathon entry.

A fan taps a contestable moment (foul, offside, card, penalty, substitution) and asks
"what if that wasn't a foul?". The screen splits into the real match and an alternate
match played as a full broadcast, backed by Monte Carlo re-simulation and precedent from
the league's own history.

**All data is synthetic.** Fictional clubs and players only. No real match data, logos,
names or music.

## Layout (planned)

- `parallel_match/` seeded event-level match simulator, fork engine
- `tests/` determinism, fork and rules tests
- `agents/` Foundry / Agent Framework agents
- `web/` React + SVG front end

Work in progress.
