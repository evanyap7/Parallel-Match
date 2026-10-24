# Uwais: remaining work status, 24 October 2026

## Completed on uwais/frontend-match-viewer

- Narrator commentary for both timelines, labelled as full-match stories.
- Law Explainer for the selected moment, with service errors and retry.
- Historian panel beside the simulation evidence. Disagreement is visible; the current development-query results are labelled separately from the canonical simulator precedent.
- Free text through `/parse` then `/fork`, preserving refusals and displaying the engine's `description` of the submitted intervention.
- Actual samples from all four agent endpoints saved under `frontend/fixtures/agents/` for tests. These samples are test inputs, never silent production fallbacks.
- Configurable agents URL and local Vite proxy. Simulator requests remain on `VITE_API_BASE_URL`.
- Refreshed rival review and an 80-second captioned local demo: `agent-demo.mp4`. Starts with the m052 penalty; includes real replay frames. Template mode and current handoffs are labelled throughout.
- 92 frontend tests pass. Production build checked. Browser confirmed commentary, law, history, successful free-text fork and verbatim parser refusal; no browser console errors.

## Parser compatibility table

The only translation lives in `frontend/src/parser-adapter.ts`, with tests in `agents.test.ts`. No code in `agents/` or `parallel_match/` was changed by this frontend task.

| Parser output | Required selected event | Engine change |
|---|---|---|
| `flip_call`, `call: no_foul` | Foul currently given as free kick or penalty | `flip_call` |
| `flip_call`, `call: onside` | Recorded call is offside | `flip_call` |
| `flip_call`, `call: offside` | Recorded call is onside | `flip_call` |
| `shot_outcome`, `outcome: goal` | Shot recorded as saved, off target or blocked | Identical typed change |

Everything else is refused by the frontend without sending `/fork`. In particular, `missed` is not silently turned into `saved`, and card changes on card events are not reinterpreted as changes on foul events. Parser refusal text is shown verbatim. A valid but unsupported parse shows the returned change and a clear unsupported-case reason. Typed manager controls remain available.

## Handoffs for Jiawei / Uwais

1. **Actual deployed URLs:** latest fetched `main` (`fb6432e`), `jiawei/agents-stack`, deployment notes and PR descriptions contain placeholders, not a simulator/agents/frontend HTTPS URL. Hosted build verification and actual submission remain pending.
2. **CORS or hosting proxy:** agents service has no CORS middleware. Locally Vite forwards `/agents` to port 8001. Production must proxy that path or the service must permit the frontend origin. A static host alone does not supply this proxy.
3. **Narrator contract:** current service reads the old `request` envelope. The frontend adds an explicitly documented alias containing the same match/event/change while preserving the engine fields and numbers. Remove it when Jiawei updates the reader.
4. **Narrator probability bug:** the service verdict uses the final curve point rather than rollout outcome shares. The UI displays its original/alternate story lines and keeps the verified simulator summary as the impact verdict. Jiawei should fix the numeric verdict before it is exposed.
5. **Historian source:** Evan's `history_for()` and `season.match_dicts()` are merged, but Jiawei's service still uses `data/dev_season`. Its 15-minute goal query cannot be equated with a final-result probability shift. The UI labels this difference; disagreement assessment currently uses the engine's canonical history. Switch the agent to the unified source to remove the duplicate counts.
6. **Season coverage:** existing agents can serve the two exported contract fixtures and dev season. Other simulator matches can return a clear 404 until the service loads the full season.

Foundry mode was not tested and no cloud credentials were requested. The demo is a working local template-mode walkthrough, not a claim of deployed Foundry or a completed submission. Demand interviews remain unperformed; fictional examples remain labelled.
