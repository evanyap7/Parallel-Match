# Parallel Match

Microsoft x Premier League "Inside the Game" developer hackathon entry.

A fan taps a contestable moment (foul, offside, card, penalty, substitution) and asks
"what if that wasn't a foul?". The screen splits into the real match and an alternate
match played as a full broadcast, backed by Monte Carlo re-simulation and precedent from
the league's own history.

**All data is synthetic.** Fictional clubs and players only. No real match data, logos,
names or music. The simulator is tuned so its per-match averages fall inside
football-like ranges (see the realism report).

## For judges

**Live demo:** _link to be added once deployed_. Start with match **m052** (WES 2-1 COP),
the borderline penalty at 56', and ask "what if that was not a penalty?".

**What you are looking at is a model world.** Every match, club and player is generated.
The alternate timeline is a simulation, not a prediction of real football, and every
number on screen comes with its uncertainty.

| Question | Answer, and where to check it |
|---|---|
| Is the data synthetic? | Yes. 10 invented clubs with tactical archetypes and generated players (`parallel_match/teams.py`); 90 simulated matches (`parallel_match/data/season.json`). No real data was used to build or tune anything beyond public, approximate per-match averages. |
| Is it football-like? | Measured over 360 matches: 2.78 goals, 27.4 shots, 82% pass accuracy, 24.4 fouls, 3.2 yellows, 10.3 corners, 42% home wins, 24% draws per match. All 16 metrics fall inside approximate top-flight ranges (`reports/realism_v1.md`). The ranges are a sanity band, not measured truth. |
| How is "what if" computed? | Replay the seeded match to the moment, apply one change, then play hundreds of paired rollouts: original and altered branches share random numbers, so the difference is the change, not luck. The result carries a 95% interval (`parallel_match/fork.py`). |
| Is there a second opinion? | Yes. Precedent from the season itself: comparable borderline calls, split by whether the call was given (`parallel_match/history.py`). When it disagrees with the simulation, the response says so. One function, `history_for()`, feeds both the API and the MCP tool. |
| How fast? | Measured on a 10-core laptop: a full match simulates in about 60 ms; 200 rollouts take 2 to 4 s on 8 workers; featured moments of the 5 story matches are precomputed at 500 rollouts and return in about 60 ms. |
| Do the agents invent numbers? | No. All numbers and moment-finding stay in plain code; agents only phrase them, and guardrails reject output with numbers not in the facts or wording that judges officials (`agents/guardrails.py`). |
| Is it neutral about officials? | Decisions are explained against the Law of the Game they fall under, with the measured margin. Nothing says a referee or player "got it wrong". |

**Microsoft stack**

| Service | Used for | Where | Status |
|---|---|---|---|
| Microsoft Agent Framework + Azure AI Foundry | Narrator, Law Explainer, Historian, Intervention Parser | `agents/`, `docs/agents.md` | Built; template phrasing by default, Foundry with `PM_AGENT_BACKEND=foundry` |
| MCP | Season history query as tools (`history_query`, `season_summary`) | `mcp_history/` | Built |
| Azure Container Apps | Simulator API, agents API, MCP server, front end | `Dockerfile`, `deploy/`, `docs/deployment.md` | Pending deployment |
| Microsoft Fabric | Season tables and the precedent query in SQL | `python3 -m parallel_match export`, `docs/history-query.md` | Tables and SQL ready; load pending |

**Known limits.** Positions are derived from formations, not tracked, so this is an
event-level model, not physics. Team strength is not yet a feature of the live
win-probability curve. Precedent compares different matches, so it carries confounding;
the paired simulation is the cleaner estimate of a single call's effect.

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

## Agents (Narrator, Law Explainer, Historian, Intervention Parser)

Phrasing agents on the Microsoft stack (Agent Framework + Azure AI Foundry,
MCP, Azure Container Apps), built against the contract fixtures:

```bash
pip install -e ".[agents,mcp]"
uvicorn agents.server:app --port 8001        # REST: /narrate /explain /precedents /parse
python -m mcp_history.server                 # MCP tools: history_query, season_summary
```

They run dependency-free on deterministic template phrasing by default and
switch to a Foundry model with `PM_AGENT_BACKEND=foundry`. All numbers and
all moment-finding stay in plain code; guardrails enforce neutrality (never
"the referee got it wrong") and factual grounding on every output. See
`docs/agents.md` and `docs/deployment.md`.

## Front end (React match viewer)

Uwais's viewer lives in `frontend/` (React + Vite + SVG pitch). It runs on the
repository fixtures by default and against the live API when `VITE_API_BASE_URL`
is set. See `frontend/README.md`.

```bash
cd frontend && npm install && npm run dev
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
  (fictional league), `state.py`, `rng.py`, `fork.py` (what-if engine), `winprob.py`,
  `season.py`, `history.py` (precedent), `api.py` (FastAPI), `realism.py`, `cli.py`
- `parallel_match/data/` season fixtures, win-probability table, precomputed forks
- `agents/` phrasing agents + FastAPI service; `mcp_history/` season history
  query + MCP server; `tools/make_dev_season.py` dev-season generator
- `frontend/` React match viewer (Uwais)
- `tests/` determinism, state copy, rules, fork engine, API, realism,
  agents, guardrails, history store
- `docs/` event schema, API, history query for Fabric, build plan, `agents.md`,
  `deployment.md` (Azure runbook), `uwais/` demand check, demo script, rival review
- `fixtures/` sample match and fork responses for front-end work;
  `data/dev_season/` ten generated matches for the Historian (dev stand-in for the real season)
- `deploy/` Container Apps deploy script, agents Dockerfile, hello-world smoke app
- `reports/realism_v1.md` latest realism report
- `Dockerfile` the simulator API image for Azure Container Apps
