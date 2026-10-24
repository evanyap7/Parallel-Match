# Parallel Match viewer

React + TypeScript + Vite. This directory is the frontend track. It consumes the shared fixtures without changing them or the simulator. The visual replay shows recorded ball-event positions, not invented full-team tracking.

## Run

Node 22.12+ or 24 recommended.

```sh
cd frontend
npm ci
npm run dev
```

Open the printed localhost URL (default `http://127.0.0.1:5173`). The `predev` and `prebuild` steps copy the repository fixtures into ignored `public/fixtures/`. Do not edit those generated copies.

```sh
npm test
npm run build
npm run preview
```

`dist/` is a static artifact suitable for the deployment track's container/static web server. No server-side secrets are needed by the viewer. No external fonts or image services are used.

## Connect the API

Set `VITE_API_BASE_URL` to the API origin (or `/api` for a same-origin reverse proxy), then restart Vite or rebuild. An example is in `.env.example`; real `.env` files remain ignored. This is public build-time configuration: never place a secret in a `VITE_` variable.

The adapter uses:

- `GET /matches`: an array of `{match_id, home?, away?}`, or `{matches: [...]}`.
- `GET /match/{id}`: the exact `docs/event-schema.md` match shape.
- `POST /fork`: `{match_id, event_id, change: {type: "flip_call", call: "no_foul"}}`, using the complete shape of `fixtures/fork_m012.json`.

Contestable moments are derived from `event.contestable` in the already-loaded match. No second `/moments` request is necessary; that endpoint's response shape is not yet documented. Cross-origin APIs must allow the viewer's origin and JSON POST requests through CORS.

API errors are shown with retry/cancel controls and never silently switch to fixture output. Requests time out after 60 seconds. Selecting another moment aborts the request and clears the previous verdict. Responses must match the selected request, time and simulator step.

## Current boundary

`fixtures/fork_m012.json` is explicitly a placeholder and only covers `m012-0148`. It includes no alternate timeline. The viewer displays both probability curves and the supplied verdict with placeholder labels, but leaves the alternate pitch pending. It never reuses original events as an alternate or invents a fork.

When the engine supplies `alternate.timeline`, the viewer plays it on the shared clock. Both full-match alternate timelines and continuation-only arrays anchored at the decision are accepted. Leave pre-decision events unchanged; keep events chronologically ordered. Set `placeholder: false` only for measured results.

Only typed officiating flips supported by the existing fixture are exposed. Broader substitutions, tactics and free-text parsing need an agreed backend request schema; none is guessed here. Agent narration, multilingual output and real precedent retrieval belong to the other track and have no API contract in this revision.

## UI

- Two SVG pitch panels; pause, restart, scrubbing and 1/6/12/30× playback.
- Contestable timeline markers and filtered decision list.
- Matching fork request, divergence marker and stale-result protection.
- Original/alternate home-win curves; outcome shifts, interval, precedent and disagreement state.
- Fan/analyst detail and favourite-club impact perspective.
- Current-time score, shots, simulator xG and pass-completion counts.
- Responsive layout, keyboard controls, reduced-motion support, modal Escape/focus containment.

The win-probability chart compares the full supplied scenario; it is not labeled a live forecast. Interpolated lines join supplied points. Historical precedent is observational, not an independent causal proof. An API payload missing required evidence is rejected rather than completed with invented values.

See `../docs/uwais/` for demand-check status, demo guidance, rival-review notes and verification.
