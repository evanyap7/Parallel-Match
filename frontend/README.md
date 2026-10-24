# Parallel Match viewer

React + TypeScript + Vite frontend integrated with Evan's completed simulator API. All clubs, players, events and comparisons are synthetic.

## Run the full application

From the repository root, use Python 3.11+:

```sh
python -m venv .venv
# Windows:
.venv\Scripts\python -m pip install -r requirements-api.txt
.venv\Scripts\python -m uvicorn parallel_match.api:app --host 127.0.0.1 --port 8000
# macOS/Linux: use .venv/bin/python instead.
```

In a second terminal (Node 22.12+ or 24):

```sh
cd frontend
npm ci
```

Create `frontend/.env.local` with this public configuration, then start Vite:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

```sh
npm run dev
```

Open `http://127.0.0.1:5173`. The badge reads **Live engine**. The default is the WES–COP penalty story (`m052`); all 90 season matches are available, with the five story matches first.

Remove/empty `VITE_API_BASE_URL` and restart for **Offline simulation**. That mode uses the actual precomputed `m052` penalty and `m012` offside fixtures, one alternative each. `predev`/`prebuild` copy shared fixtures unchanged to ignored `public/fixtures/`.

For Azure deployment, set `VITE_API_BASE_URL` before building to the API's HTTPS origin (or `/api` behind a reverse proxy). Serve `dist/` as the static frontend. This is public build-time configuration; never place a secret in a `VITE_` variable. Evan's existing Dockerfile runs the API only; it does not serve the frontend.

## Contract

The source of truth is `../docs/api.md`:

- `GET /matches`, `/clubs`, `/match/{id}` and `/moments/{id}` supply fixtures, names, squads, events and supported interventions.
- `POST /fork` uses `{match_id, event_id, change}`. The UI exposes officiating flips, red-card reversals, shot outcomes, foul cards, substitutions and pressing intensity. The API validates legal substitutions and remaining substitutions; rejection reasons appear inline.
- Fork responses use top-level `match_id`, `event_id`, `change`; probability points have numeric `minute` and display `min`; confidence intervals are `uncertainty.shift_ci95` in probability-point changes.
- `history` is nullable, and empty comparison groups have null rates. Missing precedent is explicitly unavailable. The viewer never invents a history result or treats it as causal evidence.
- The fork replaces the entire simulator step. Prefix events have `step < divergence.step`, preventing a retained original goal/card at the split.
- Default fresh runs use the engine's rollout count (currently 200); cached featured runs can return 500. The UI displays the returned count.

API errors never silently switch to fixture results. Requests time out after 60 seconds. Changing the match, selected moment or intervention clears the old result and aborts its client request. Cancellation stops waiting; it does not cancel a running server-side computation.

## Experience and boundaries

Two ball-event pitch replays share playback controls; there is no fabricated player tracking. The chart shows complete scenario probability paths. Club selection changes both the outcome shift and its interval, plus the data summary. Fan/analyst detail exposes additional event evidence.

The frontend creates a deterministic summary from returned values and labels it **Data summary from paired rollouts**. If an agent later supplies `verdict`, it is displayed as **Agent narrative**. The agent service panels are now connected as described below; Foundry deployment, multilingual narration and Fabric retrieval remain outside this frontend change. The backend's current season precedent is used directly. Kick-off player-unavailability is supported by the backend but has no frontend control yet.

## Checks

```sh
npm test
npm run build
```

Tests include all 60 backend cached fork responses, replay step boundaries, absent precedent, stale/wrong request rejection, substitution eligibility and HTTP errors. See `../docs/uwais/verification.md` for browser integration evidence.

## Agent integration

Run `uvicorn agents.server:app --port 8001` in a third terminal. The Vite development server proxies `/agents` to that local service. Optional `VITE_AGENTS_PROXY_TARGET` changes the development target; `VITE_AGENTS_BASE_URL` changes the browser-facing agents base (default `/agents`). Restart Vite after changing configuration.

The viewer calls `/explain` on moment selection, `/narrate` after a fork and `/precedents` for an officiating comparison. Free text calls `/parse` before `/fork`. Outputs are validated against the request, requests abort on changed selections, and errors have retry states. The header reports the service's template or Foundry provider mode.

For production, supply a same-origin `/agents` proxy or an HTTPS service URL with appropriate CORS support. See `.env.example` and `../docs/uwais/remaining-status.md` for the compatibility table, service handoffs and deployment checks. The earlier paragraph describing these panels as unimplemented is superseded by this integration section.

## Look and feel

Light "matchday editorial" style (achromatic ledger). The one rule to keep when editing:
**ink means the real match, the single blue (`--hue`) means the alternate world where the
decision changed.** Nothing else is coloured, so colour always says "this is the changed
timeline". Details:

- Tokens live at the top of `src/styles.css` (`--ground`, `--surface`, `--ink`, `--hue`).
  Pitch and chart SVG colours come from the same variables.
- Flat surfaces: a 1px edge and one tone step, no shadows or gradients.
- Geist for all text, tabular figures, nothing under 12px.
- Primary actions are near-black. The real timeline is solid ink; the alternate line in the
  chart is dashed blue, so the two stay distinguishable without colour.
- Check a change with the design-taste inspector (`node <skill>/scripts/inspect.mjs --app
  <url>`) and `npm test && npm run build`.
