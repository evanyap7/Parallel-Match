# Event schema

A match is a JSON object with `match_id`, `seed`, `home`, `away`, `score` and an
ordered `events` list. Each event is one flat object. See `fixtures/m012.json`.

All data is synthetic: fictional clubs, fictional players, simulated matches.

## Common fields

| Field | Type | Meaning |
|---|---|---|
| `id` | string | `<match_id>-<seq>`, e.g. `m012-0341` |
| `step` | int | Simulator step that produced the event. Forks anchor on this. |
| `t` | int | Elapsed playing seconds since kickoff (continuous across halves) |
| `min` | string | Broadcast clock label: `"52"`, `"45+2"`, `"90+4"` |
| `period` | int | 1 or 2 |
| `type` | string | See below |
| `team` | string | Club code of the acting team (`HAR`) |
| `player` | string | Acting player id: club initial plus shirt number (`H7`) |
| `xy` | [x, y] | Ball position in metres. Pitch is 105 x 68. Home attacks towards x = 105 |
| `score` | [home, away] | Score after this event |

## Event types and extra fields

| Type | Extra fields |
|---|---|
| `kickoff` | |
| `pass` | `kind` (back, lateral, forward, long, through, cross), `to`, `success`; optional `offside_margin` (m), `contestable`, `call: "onside"`, `law` |
| `dribble` | `success`, `beat` (defender id or null); optional `contact`, `margin`, `call: "no_foul"`, `contestable`, `law` |
| `tackle` | `victim`, `success`, `contact`; optional `margin`, `call: "no_foul"`, `contestable`, `law` |
| `interception` | optional `via: "clearance"` |
| `foul` | `victim`, `contact` (0..1), `margin` (contact minus referee threshold), `call` (free_kick or penalty), `card`, `contestable`, `law` |
| `card` | `color` (yellow or red), `reason` (yellow, second_yellow, red), `score_margin`, `law` |
| `offside` | `margin` (metres beyond the line, positive = offside position), `call`, `contestable`, `law` |
| `shot` | `kind` (open_play, header, free_kick, penalty), `xg`, `dist`, `outcome` (goal, saved, blocked, off_target), `on_target` |
| `goal` | `assist`, `law` |
| `throw_in`, `goal_kick`, `corner`, `free_kick` | `law` |
| `substitution` | `player` is the player coming on, `off` the player going off, `law` |
| `half_time`, `full_time` | |

## Contestable moments

`contestable: true` marks a decision close enough to go either way. It covers:

- Fouls and non-fouls where `|contact - threshold| < 0.12`, plus every foul in the box.
- Offsides and onside passes where `|margin| < 0.6` m.
- Fouls where the card decision was close to the yellow threshold.

The referee perceives contact with noise, and the assistant perceives the
offside margin with noise (about 0.2 m). So the recorded ground truth
(`contact`, `margin`) and the call can disagree. That disagreement is what
the "what if" fork flips. `law` cites the Law of the Game neutrally.
