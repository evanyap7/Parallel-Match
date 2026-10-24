# Frontend handoff and verification

Verified on 24 October 2026 against base commit `09c9a5d`.

## Story verified

A fan loads the synthetic match, selects a contestable event, requests the matching fixture fork and sees the comparison with explicit placeholder labels. The original pitch, event evidence and statistics follow the replay clock. The missing alternate event array produces a pending state.

## Automated checks

- Existing simulator: all 17 unittest tests pass using the bundled Python runtime.
- Frontend: 13 Vitest tests pass across shared-contract, replay/statistics and HTTP-adapter tests.
- TypeScript check and Vite production build pass.
- Package audit after updating the test runner reports zero vulnerabilities.

The tests cover incorrect event IDs and intervention types, invalid probabilities and intervals, unsorted or duplicate events, future-score leakage, same-time event ordering, shot/pass aggregation, empty alternate handling, full versus continuation timelines, exact API paths and JSON request bodies, and API failures without fixture fallback.

## Browser checks

- Fixture loads and the 10-minute foul renders its recorded call and Law reference.
- Explore displays both supplied win-probability curves, the verdict, interval and precedent cards.
- Selecting another moment removes the old comparison and disables unsupported fixture requests.
- Load example moment returns to the one supported canned request.
- Analyst view exposes `m012-0148` and its simulator step/margin.
- Play advances the clock; pause stops it; restart resets it to 00:00.
- Changing the followed club updates the win-probability impact perspective.
- Responsive checks at 390 px and 1440 px report no horizontal document overflow.
- Browser console reports no errors or warnings during the verified fixture flow.

## Integration boundary

No live backend existed at verification time. The HTTP adapter is tested with mocked responses, not a deployed service. Live fork execution, real alternate events, actual historical comparisons, AI narration and Azure deployment remain dependent on Evan and Jiawei's work. Do not describe those boundaries as verified end-to-end.

When the API arrives, use the configuration in `frontend/README.md`, then verify that `alternate.timeline` is nonempty, original and alternate clocks stay aligned, a second decision cannot receive a stale first response, and source labels accurately reflect measured versus placeholder values.

## Uwais task status

| Task | Status |
|---|---|
| React scaffold and original SVG replay | Implemented and browser checked |
| Contestable moment timeline | Implemented and browser checked |
| Split-screen shell, divergence, probability curves and verdict | Implemented; actual alternate replay needs engine events |
| Live API adapter | Implemented and unit tested; live-service verification pending |
| Demand check with five fans | Not conducted; questionnaire and fictional examples clearly labeled |
| Rival demo review | One demo inspected; other access limitations documented |
| Demo video under two minutes | 72-second frontend preview recorded; final integrated take pending |

## Ownership

Only `frontend/` and `docs/uwais/` are added. The shared fixtures, simulator, root README, existing plan and backend schema are not changed. The branch is intended for a PR into `main` under the existing team workflow.
