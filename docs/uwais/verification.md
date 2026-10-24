# Integration verification — 24 October 2026

Evan's main commit `fd05be0` was merged into `uwais/frontend-match-viewer` without Git conflicts. User approved adapting the frontend to the completed backend contract. Integration edits stay in `frontend/` and `docs/uwais/`; backend code and shared fixtures are preserved.

## Story

A fan chooses a synthetic match and moment, submits an intervention to the live Python API, and sees a synchronized alternate replay with outcome shifts, uncertainty and available season precedent.

## Evidence

| Boundary | Result |
|---|---|
| Python backend | 31 tests passed, including actual API fork round-trip, determinism, interventions and rules |
| Frontend contract | All 60 engine-owned cached forks accepted, including nullable history and goal/red-card interventions |
| Live browser → API | `/matches`, `/clubs`, `/match/m052`, `/moments/m052` and `/fork` returned HTTP 200 |
| Penalty flip | Browser showed 500 paired runs, WES shift −14.4 pp, 21 comparable moments, real alternate events |
| Fresh tactical fork | WES press 0.30 → 0.80 returned 200 runs and +14.0 pp (95% interval +5.4 to +22.6 pp) |
| Fresh substitution | W10 → W20 returned 200 runs and +1.0 pp; interval included zero and summary stated uncertainty |
| Goal saved | Browser showed 500 runs, WES −21.2 pp; full-time alternate replay ended 1–1 versus original 2–1 |
| Club personalization | Switching to COP changed the goal comparison to +33.2 pp, interval +28.7 to +37.7 pp |
| Missing precedent | Goal, tactics and substitution comparisons displayed unavailable history rather than fabricated rates |
| Offline mode | Both m052 penalty and m012 offside loaded real alternate events without API configuration |
| Browser console | No errors during live integration checks |

Values above are simulator results, not real-football forecasts. Browser verification used the local API, not an Azure deployment. The initial sandboxed Python test run stalled at process-worker startup; it was stopped, and the full suite passed with local process execution enabled in 36 seconds. The installed Starlette version printed a non-failing httpx deprecation warning.

## Handoff

- API contract: `docs/api.md`; frontend setup: `frontend/README.md`.
- Jiawei can integrate agent output through a documented API addition. The current summary is calculated prose, not an LLM-generated explanation.
- Fabric/MCP historian, agent orchestration, multilingual output and Azure deployment are not verified by this integration.
- Five-fan demand validation remains unperformed. `demand-check.md` contains clearly fictional examples and a real interview template.
- `demo-preview.mp4` is the older placeholder UI preview; it is not evidence of this integrated version. Use the updated demo script for a final recording after the agent track is connected.

Final frontend checks: 77 tests passed; TypeScript and Vite production build passed; git diff whitespace check passed.
