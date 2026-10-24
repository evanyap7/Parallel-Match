# History query (for Fabric and the Historian agent)

The "precedent" estimate is the league's own history: comparable borderline
decisions this season, split by whether the call was given. It is computed in
plain code by `parallel_match/history.py`, and the same query can run in
Microsoft Fabric over the exported tables. The Historian agent calls it as a
tool (ideally over MCP) and only phrases the result.

## Export the tables

```bash
python3 -m parallel_match export --out out/season
```

This writes three files (synthetic data, safe to upload):

| File | One row per | Key columns |
|---|---|---|
| `matches.csv` | match | `match_id, round, home, away, seed, home_goals, away_goals, story` |
| `events.jsonl` | event | the event schema in `docs/event-schema.md`, plus `match_id` |
| `moments.csv` | contestable decision | see below |

`moments.csv` columns:

| Column | Meaning |
|---|---|
| `match_id`, `event_id` | Where the decision happened |
| `minute` | Elapsed minute |
| `family` | `foul` or `offside` |
| `called` | 1 if the foul or offside was given, 0 if play went on |
| `att_team`, `att_home` | The attacking side the decision affects, and whether it is the home team |
| `zone` | `att_third`, `mid_third`, `def_third` from the attacking side's view |
| `in_box` | 1 if inside the penalty area |
| `margin` | Contact minus referee threshold (fouls) or metres beyond the line (offside) |
| `score_diff` | Attacking side's goal difference before the decision, clamped to -1..1 |
| `att_goal_10`, `att_conceded_10` | Did the attacking side score / concede within 10 minutes |
| `att_result` | Attacking side's final result: W, D or L |

## The query

Comparable = same family, same zone, same minute band (0-29, 30-59, 60+),
same score state, and a borderline margin (`ABS(margin) < 0.15`). Then
compare results when the call was given against when it was not.

```sql
-- Parameters from the tapped moment: @family, @zone, @band, @score_diff, @match_id, @event_id
SELECT
  called,
  COUNT(*)                                             AS n,
  AVG(CASE WHEN att_result = 'W' THEN 1.0 ELSE 0 END)  AS att_win,
  AVG(CAST(att_goal_10 AS FLOAT))                      AS att_goal_10
FROM moments
WHERE family = @family
  AND zone = @zone
  AND CASE WHEN minute < 30 THEN 0 WHEN minute < 60 THEN 1 ELSE 2 END = @band
  AND score_diff = @score_diff
  AND ABS(margin) < 0.15
  AND NOT (match_id = @match_id AND event_id = @event_id)
GROUP BY called;
```

History shift for a flipped call = `att_win(not given) - att_win(given)` if the
original call was given, otherwise the reverse. The API compares it with the
simulated shift and sets `history.agrees_with_simulation`. Need at least 5
rows in each group, otherwise report "not enough precedent".

Precedent compares different matches, so it carries confounding (better teams
attack more). The paired simulation isolates the call. When the two disagree,
the screen says so instead of hiding it.
