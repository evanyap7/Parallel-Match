# Loading the season into Microsoft Fabric

Goal: the season's contestable decisions as a Fabric Lakehouse table, and the
Historian's precedent query run in Fabric with the **same answer the app
gives**. About 20 minutes once you have Fabric access.

## 0. Access (check this first, 2 minutes)

Open https://app.fabric.microsoft.com and sign in with your school account.

- If you see a workspace list or a "Start free trial" prompt (account menu,
  top right): start the Fabric trial (60 days, free). That's all you need.
- If it says your organisation doesn't allow Fabric or trials: tell the team.
  We drop Fabric from the pitch rather than claim it.

## 1. Export the tables (on your laptop)

```bash
python3 -m parallel_match export --out out/season
```

Writes `out/season/matches.csv`, `events.jsonl` and `moments.csv`. All
synthetic. `out/` is git-ignored.

## 2. Create a Lakehouse and load `moments`

1. In Fabric: **Workspaces** > your trial workspace (or **New workspace**,
   name it `the-home-dugout`, licence mode **Trial**).
2. **New item** > **Lakehouse**, name it `parallel_match`.
3. In the Lakehouse: **Get data** > **Upload files**, and upload
   `moments.csv` and `matches.csv`.
4. Under **Files**, for each file: **...** > **Load to Tables** > **New
   table**, keeping the names `moments` and `matches`, first row as headers.

## 3. Run the precedent query

Switch the Lakehouse view (top right) to **SQL analytics endpoint**, then
**New SQL query**, and paste this. It is the query from
`docs/history-query.md` with the m052 penalty at 56' filled in: foul,
attacking third, minute band 30 to 59, attacking side a goal down.

```sql
-- Precedent for m052-0715 (the featured penalty), same rule as history_for()
SELECT
  called,
  COUNT(*)                                             AS n,
  AVG(CASE WHEN att_result = 'W' THEN 1.0 ELSE 0 END)  AS att_win,
  AVG(CAST(att_goal_10 AS FLOAT))                      AS att_goal_10
FROM moments
WHERE family = 'foul'
  AND zone = 'att_third'
  AND CASE WHEN minute < 30 THEN 0 WHEN minute < 60 THEN 1 ELSE 2 END = 1
  AND score_diff = -1
  AND ABS(margin) < 0.15
  AND NOT (match_id = 'm052' AND event_id = 'm052-0715')
GROUP BY called
ORDER BY called DESC;
```

**Expected result** (identical to the app's Historian card and `/fork`'s
`history` block):

| called | n | att_win | att_goal_10 |
|---|---|---|---|
| 1 | 8 | 0.125 | 0.25 |
| 0 | 13 | 0.077 | 0.077 |

If the counts match, take a screenshot showing the query and the result grid
and save it as `docs/img/fabric-precedent-m052.png`.

## 4. Optional: the whole season at a glance

```sql
SELECT family, called, COUNT(*) AS decisions,
       AVG(CAST(att_goal_10 AS FLOAT)) AS att_goal_10
FROM moments
GROUP BY family, called
ORDER BY family, called DESC;
```

## What to claim

Only if step 3 matched: "The season's contestable decisions are loaded into a
Microsoft Fabric Lakehouse, and the Historian's precedent query runs there
over the SQL analytics endpoint with the same result as the app (screenshot)."
The live app computes precedent in code and serves it over MCP; Fabric is the
analytics copy, not on the request path.
