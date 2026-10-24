# API

FastAPI service in `parallel_match/api.py`. Interactive docs at `/docs` once running.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-api.txt
.venv/bin/uvicorn parallel_match.api:app --reload      # http://localhost:8000/docs
```

Docker (what Azure Container Apps runs):

```bash
docker build -t parallel-match-api .
docker run -p 8000:8000 parallel-match-api
```

## Endpoints

| Method | Path | Returns |
|---|---|---|
| GET | `/health` | `{"ok": true, "model_world": true}` |
| GET | `/clubs` | 10 fictional clubs with style and squad |
| GET | `/matches` | 90 season fixtures: `match_id, round, home, away, seed, score, story, summary` |
| GET | `/standings` | League table |
| GET | `/match/{match_id}` | Full match: `{match_id, seed, home, away, score, story, events: [...]}` |
| GET | `/moments/{match_id}` | Tappable moments, each an event plus `changes: [...]` it supports |
| GET | `/history/{match_id}/{event_id}` | Precedent for one contestable call (same numbers as the fork's `history` block); 404 if not a contestable call |
| POST | `/fork` | The what-if result (below) |

Story matches (good for the demo) have a non-null `story`: `comeback`, `early_red`,
`late_winner`, `penalty_drama`, `tight_offside`.

## POST /fork

```json
{"match_id": "m039", "event_id": "m039-0412", "change": {"type": "flip_call"}, "rollouts": 200}
```

`rollouts` is 10 to 1000, default 200. Featured moments in the story matches are
precomputed at 500 rollouts and come back instantly with `"cached": true`.

### Changes

| `change` | Use on | Meaning |
|---|---|---|
| `{"type": "flip_call"}` | any moment with `contestable: true` | Foul becomes no foul (or the reverse), offside becomes onside (or the reverse) |
| `{"type": "not_sent_off"}` | red card | Second yellow not shown, or direct red becomes yellow |
| `{"type": "card", "card": null}` | foul | Change the card for a foul: `null`, `"yellow"`, `"red"` |
| `{"type": "shot_outcome", "outcome": "goal"}` | shot | A missed shot goes in |
| `{"type": "shot_outcome", "outcome": "saved"}` | goal | The goal does not stand |
| `{"type": "substitution", "team": "HAR", "off": "H9", "on": "H20"}` | any event | Make this change at this moment (or replace the original change on a substitution event) |
| `{"type": "tactics", "team": "HAR", "set": {"press": 0.9}}` | any event | Keys: `attack, defence, press, tempo, directness`, values 0..1 |
| `{"type": "unavailable", "team": "HAR", "player": "H9"}` | no `event_id` | Starter misses the match, like-for-like bench player starts |

Invalid changes return HTTP 422 with a reason.

### Response

Same shape as `fixtures/fork_m012.json`, with real numbers:

| Field | Meaning |
|---|---|
| `description` | Plain statement of the change, e.g. "no foul given instead of a penalty" |
| `diverged` | false if the change made no difference at that step |
| `divergence` | `{event_id, step, t, min}` where the timelines split |
| `moment` / `alternate_moment` | The original event, and what happened instead at that step |
| `original.final_score`, `original.win_prob`, `original.outcome` | Real match, its win-probability curve, and the original-branch outcome shares from the rollouts |
| `alternate.final_score`, `alternate.win_prob`, `alternate.outcome`, `alternate.timeline` | The typical alternate timeline (most common alternate score) and its events from the split onward |
| `outcome_shift` | Alternate minus original outcome shares, paired rollouts |
| `uncertainty.shift_ci95` | 95% interval on each shift |
| `score_spread` | Top 5 alternate final scores and their shares |
| `history` | Precedent check (flip_call only): comparable moments, rates when given vs not, `agrees_with_simulation` |
| `timing` | Seconds taken and workers used |
| `model_world` | Always true: this is a simulation, label it as such |

`win_prob` points: `{"minute": 52, "min": "52", "home": 0.61, "draw": 0.24, "away": 0.15}`,
one per elapsed minute. The last point is the final result.
