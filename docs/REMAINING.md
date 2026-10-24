# What's left: plan to submission

Team: Evan (backend, data), Jiawei (Microsoft stack, deployment), Uwais (front end, video).
**Deadline: Wed Oct 28, 2:59 PM Singapore time.** Target: submit Monday night or
Tuesday. Wednesday is buffer only.

This replaces the timeline in `PLAN.md`. The hard rules there still apply.

## Where we are

Merged into `main` and passing (83 Python tests, 77 front-end tests, front end builds):

- Simulator, fork engine, 90-match season with 5 story matches, 60 precomputed forks,
  precedent check, simulator API (`parallel_match/`, `docs/api.md`)
- Four agents, agents API, MCP history server, Container Apps scripts
  (`agents/`, `mcp_history/`, `deploy/`, `docs/agents.md`, `docs/deployment.md`)
- React match viewer with live-engine mode, demand check, demo script, rival review
  (`frontend/`, `docs/uwais/`)

## The gaps judges would notice

1. Nothing is deployed, so there is no working link yet.
2. The UI never calls the agents, so the agentic part is invisible in the demo
   (agentic design is 20% of the score).
3. The Historian reads `data/dev_season` (10 matches from the older simulator), not the
   real 90-match season. There are also two history implementations, which could show
   two different precedent numbers.
4. `deploy/deploy.sh` would build the wrong image (see Jiawei, task 1).

## We all work at once

Three handoffs could block someone. Each has a way to work without waiting:

| Handoff | Who waits | Work without waiting |
|---|---|---|
| Live URLs (Jiawei to Uwais) | Uwais | Run all three services locally (commands below). Swapping to live URLs is one env change. |
| History wrapper (Evan to Jiawei) | Jiawei | Signature agreed now (below). Wire MCP to it while Evan implements it. |
| Agent response shapes (Jiawei to Uwais) | Uwais | Endpoints exist and are tested. Save one sample response from each as a fixture and build against it. |

Run everything locally:

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[api,agents,mcp]"
.venv/bin/uvicorn parallel_match.api:app --port 8000     # simulator API
.venv/bin/uvicorn agents.server:app --port 8001          # agents API
.venv/bin/python -m mcp_history.server                   # MCP history
cd frontend && npm install && VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

### Agreed contract: the history wrapper

```python
# parallel_match/history.py (Evan implements, Jiawei calls from mcp_history)
def history_for(match_id: str, event_id: str) -> dict | None:
    """Precedent for one contestable moment in the real season.
    Same shape as the `history` block in POST /fork:
    {n, description, when_given: {n, win, goal_10}, when_not_given: {...},
     attacking_team, history_shift_att_win, ...}
    None if the moment is not a contestable call."""
```

Until it lands, `mcp_history` keeps returning its current dev-season result.

## Tasks

### Evan: backend and data (owns the numbers)

1. [ ] `history_for()` as above, on the real season. Make it the single precedent
   source, so the `/fork` `history` block and the MCP tool give the same number.
2. [ ] Make the season easy to load for the agents and MCP services (no dependency on
   `data/dev_season`). Rerun precompute if any simulator output changes.
3. [ ] Backend bug bash: every change type on all 5 story matches through the API;
   every featured moment returns `cached: true`.
4. [ ] Final README and judge notes: what is synthetic, realism report, measured fork
   speed, the "model world" caveat.

### Jiawei: Microsoft stack and deployment

1. [ ] **Fix `deploy/deploy.sh` first.** `build()` has no `--file`, so every image is
   built from the root `Dockerfile` (the simulator API). Pass
   `--file deploy/Dockerfile` for agents and MCP, `--file deploy/hello/Dockerfile` for
   hello.
2. [ ] Add a target for the simulator API (root `Dockerfile`, port 8000). Deploy all
   three services and post the HTTPS URLs in chat.
3. [ ] Foundry on: `PM_AGENT_BACKEND=foundry` with a managed identity, template
   fallback kept for when the model is down.
4. [ ] Narrator: use `original.outcome` and `alternate.outcome` (rollout shares), not
   the final win-probability point, which gives "0% instead of 0%".
5. [ ] Switch the Historian and MCP to `history_for()` and retire `data/dev_season`.
6. [ ] Host the front end (`dist/` as a Static Web App or a Container App) with
   `VITE_API_BASE_URL` set. This is the link the judges open.

### Uwais: what the judges see

1. [ ] Agents in the UI (biggest scoring gap):
   - Narrator commentary for both timelines in the split screen
   - Law Explainer card on the tapped moment
   - Historian card next to the simulation number, showing "these disagree" when they do
   - Free-text "what if..." box: `/parse` then `/fork`
2. [ ] Point the build at the live URLs and check the "Live engine" badge on the
   deployed site.
3. [ ] Optional: remove em dashes from `frontend/` and `docs/uwais/` for consistency.
4. [ ] Rival check, then the demo video (under 2 minutes, starting from the m052
   penalty), then submit.

## Checkpoints

| When | Done means |
|---|---|
| Sat evening | Deploy script fixed, three services live, URLs shared (Jiawei). `history_for()` merged (Evan). |
| Sun midday | Agent panels working in the UI against live URLs (Uwais). Historian on the real season (Jiawei). |
| Sun evening | Front end hosted. The full demo works from one public link. Everyone bug-bashes. |
| Mon | Video recorded, README final. Submit Monday night or Tuesday. |
| Wed | Buffer only. |

The only hard ordering is the final end-to-end check at the Sunday-evening checkpoint,
since it needs everything deployed. Everything before it runs in parallel.

## If we fall behind, cut in this order

1. The free-text "what if" box
2. Foundry (keep template phrasing, still on Agent Framework)
3. The hosted MCP server (call `history_for()` directly)

## Working rules

- One branch each (`evan/...`, `jiawei/...`, `uwais/...`). Small PRs into `main`, merged
  at least at every checkpoint, not one big merge at the end.
- Stay in your folders: Evan `parallel_match/` and `tests/`, Jiawei `agents/`,
  `mcp_history/` and `deploy/`, Uwais `frontend/` and `docs/uwais/`. Evan edits
  `README.md` and `pyproject.toml`; keep anyone else's edits there tiny.
- No silent contract changes. If the `/fork` response, an agent endpoint or anything in
  `fixtures/` changes, say so in chat first.
- Pull `main` before starting each task.
- No secrets in the repo: `.env` is git-ignored, production secrets go in Container
  App secrets or Key Vault. Synthetic data only, no real names.
