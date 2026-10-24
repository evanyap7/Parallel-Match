# Parallel Match: build plan

Team: Evan (simulator, forks, API), Jiawei (agents, Microsoft stack, deployment),
Uwais (front end, demand check, video).

**Deadline: Wed Oct 28, 2:59 PM Singapore time.** We are building everything in one
push today, so the tracks run in parallel and everyone builds against mocks until the real
pieces land. Aim to submit Tuesday night at the latest.

## Hard rules (from the official rules)

- Public GitHub repo, working link for judges, demo video under 2 minutes.
- Synthetic, football-realistic data only. Fictional clubs and players. No real match
  data, logos, names or music.
- Never say a referee or player "got it wrong". Explain the decision and cite the Law
  neutrally.
- Judging, 20% each: technical implementation, agentic design, real-world impact, UX and
  presentation, category fit.
- Visibly use the Microsoft stack: Foundry, Agent Framework, Fabric, Azure Container
  Apps. MCP integration scores under agentic design.

## What we are building

A fan taps a contestable moment (foul, offside, card, penalty, substitution) and asks
"what if that wasn't a foul?". The screen splits: the real match on one side, the
alternate match on the other, played as a full broadcast with a marker where the two
timelines diverge.

Two independent estimates back it: Monte Carlo re-simulation, and precedent from the
league's own history ("in N comparable moments this season..."). If they disagree, the
screen says so. Label the result "model world" and show the uncertainty.

## What already exists (pushed)

- `parallel_match/` seeded event-level simulator, about 1,200 events per match
- 10 fictional clubs with tactical archetypes, generated players
- Copyable `MatchState`: copying it is the fork. Same seed gives the identical match.
- Contestable moments carry their margin: foul `contact` 0..1, offside `margin` in metres
- `reports/realism_v1.md`: 16 metrics checked against approximate top-flight ranges
- `docs/event-schema.md`: the event format
- `fixtures/m012.json`: a full sample match
- `fixtures/fork_m012.json`: a canned `/fork` response (placeholder numbers, shape only)

Run it: `python3 -m parallel_match match --seed 12`. Tests:
`python3 -m unittest discover -s tests -t .`

## Shared contract

Everyone builds against two files, so nobody waits for anyone:

1. `fixtures/m012.json`, the match and its events (schema in `docs/event-schema.md`)
2. `fixtures/fork_m012.json`, the response shape of `POST /fork`

Planned API (Evan builds, Jiawei and Uwais mock first):

| Endpoint | Returns |
|---|---|
| `GET /matches` | List of matches in the season |
| `GET /match/{id}` | One match with all events |
| `GET /moments/{id}` | The contestable moments in a match |
| `POST /fork` | `{match_id, event_id, change}` gives the alternate timeline and the outcome shift |

Supported changes (keep it bounded): flip an officiating call, a different substitution or
tactic, a player unavailable or not sent off, a shot that missed goes in or a goal does
not. Free text parsed into one of these is the first thing we cut.

## Tracks

### Evan: simulator, forks, season, API

1. Contract fixture and push (so the others can start)
2. Fork engine: `fork(match, event_id, change)` copies the state at that moment, applies
   one change, plays on. A fork with no change must reproduce the original exactly.
3. Paired randomness: original and altered runs share random numbers until they diverge
4. About 500 rollouts for the win-probability shift, plus one typical timeline kept for
   the parallel broadcast
5. Fork speed: one rollout from mid-match is currently about 80 ms, so 500 rollouts take
   about 40 s on one core. We need seconds. Use multiple cores, fewer rollouts for the
   live view, and precompute forks for flagged moments. Measure, do not assume.
6. Season: 90 matches (double round robin), plus planted memorable matches found by
   running many seeds (a 5-4 comeback, a very early red card). Still generated, just
   selected.
7. FastAPI service with the endpoints above. Freeze the generator spec once it works.

### Jiawei: agents, Microsoft stack, deployment

1. **First hour:** create the Microsoft Foundry project and models, confirm what the
   hackathon credits cover, and deploy a hello-world container to Azure Container Apps.
   Deployment is the riskiest step, so find the problems now.
2. Agents with Microsoft Agent Framework, built against the fixtures:
   - **Narrator:** commentary for both timelines
   - **Law Explainer:** neutral statement of the relevant Law, using the event `law`
     field. Never say anyone got it wrong.
   - **Historian:** finds similar moments through a query tool
   - **Intervention Parser:** free text to a typed change, validated (cut first)
3. Load the season into Microsoft Fabric. Expose the history query as an MCP server for
   the Historian.
4. Deploy the API, agents and web app to Azure Container Apps.
5. Rule: all numbers and moment-finding stay in plain code. The agents only phrase
   results and never invent facts.

### Uwais: front end, demand check, video

1. **First hour:** run the 30-minute demand check with five fans. Ask: "What decision did
   you last argue about, and what did you do next?" Also scaffold the React app.
2. React + SVG pitch replaying `fixtures/m012.json`
3. Timeline with contestable moments flagged, tap a moment to ask "what if?"
4. Split screen against `fixtures/fork_m012.json`: real match on one side, alternate on
   the other, a divergence marker, both win-probability lines, and a verdict card
   ("turning point at 52'; no penalty, so no early goal")
5. Swap the canned response for the live API once it exists
6. Check rival entries' demos, then record the demo video (under 2 minutes, no real
   names, logos or music)

## Timeline (hours from now)

| Hours | Evan | Jiawei | Uwais |
|---|---|---|---|
| 0 to 1 | Push contract, start fork engine | Foundry, Fabric, hello-world on Container Apps | Scaffold app, demand check |
| 1 to 4 | Fork engine, fork speed, win probability, season | Narrator, Law Explainer, Historian on fixtures | Pitch, timeline, split-screen layout |
| 4 to 6 | FastAPI, planted matches, freeze spec | Fabric + MCP, agents behind the API, deploy | Live API, divergence marker, verdict card |
| 6 to 8 | Bug bash | Bug bash, README | Video, submit |

Wednesday is buffer only.

## Cut first, in this order

Free-text parsing, share cards, extra languages, Manager Duel (you vs AI vs real
manager), voice.

## Tests that keep us honest

1. Same seed gives an identical match (done)
2. A fork with no change reproduces the original exactly (done at state level)
3. Offside and foul calls pass hand-made test positions (done)
4. Realism report stays inside target ranges (done)

## Risks

- The alternate reality is only as real as the simulator. Label it "model world" and show
  the uncertainty and the realism report.
- About five similar public entries. Execution and the parallel-broadcast demo are the
  differentiator.
- Fork speed must be seconds, not minutes.

## Working agreements

- Branch per person (`evan/...`, `jiawei/...`, `uwais/...`), small PRs into `main`.
- Do not commit secrets. Azure and Foundry keys go in `.env` (git-ignored) or Azure
  Key Vault.
- Synthetic data only, and no real names anywhere in code, data or the video.
