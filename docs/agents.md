# Agents and the MCP history server

Status: working against the real 90-match season (the same one the simulator
API serves). No cloud credentials needed to run any of it locally.

## The one rule

**All numbers and all moment-finding stay in plain code. Agents only phrase
results and never invent facts.** Everything is built to make that rule
mechanically checkable:

1. Every agent consumes a *fact bundle* built by plain code (`agents/facts.py`,
   `mcp_history/store.py`). The bundle carries every number the output may
   contain.
2. Every agent output - template or model - passes `agents/guardrails.py`:
   - **neutrality**: no phrase that judges an official or decision ("got it
     wrong", "should have", "robbed", ...), no real-world football proper
     nouns (VAR, league names).
   - **grounding**: every number in the output must appear in the fact bundle.
3. A failing output is replaced by the deterministic template phrasing, so
     the service degrades to template mode per utterance, never to
     rule-breaking text.

## The four agents

| Agent | File | Input | Output |
|---|---|---|---|
| Narrator | `agents/narrator.py` | a `POST /fork` response (`fixtures/fork_m012.json` shape) | 4-line script: real timeline, divergence, alternate timeline (labelled *model world*), verdict card |
| Law Explainer | `agents/law_explainer.py` | one event | what was decided + the neutral Law text + how close to the boundary |
| Historian | `agents/historian.py` | one contestable moment | "in N comparable moments..." with counts, shares and outcomes from the season |
| Intervention Parser | `agents/intervention.py` | fan free text + event | a typed, validated `POST /fork` change - or refusal with a reason |

The Law Explainer's texts live in `agents/laws.py`, keyed by the exact `law`
strings the simulator emits (`parallel_match/rules.py`). A test asserts the
two tables stay in sync, and that no Law text trips the neutrality guardrail.

The Intervention Parser is plain code on purpose:
the fork engine accepts a bounded set of changes, and a deterministic parser
guarantees a parse lands inside that set or is refused - never a free-form
model guess. Negated fan phrasings ("that wasn't a foul", "he was onside")
are handled explicitly.

## The Match Desk (agents working together)

`agents/desk.py`, served at `POST /desk` and shown in the Analyst view as the
Agent desk panel. One request runs every agent on one moment:

1. **Producer** plans the run: a Historian only for a flipped, contestable call.
2. **Narrator, Law Explainer, Historian** draft in parallel from their own fact bundles.
3. **Fact-Checker** reviews every draft against a shared case file through four
   tools: `get_fork_result`, `get_precedent` (the MCP precedent), `get_law` and
   `check_numbers`. Code checks are the hard gate (guardrails, the key numbers each
   piece must state, and cross-checks that the agents describe the same moment,
   call and precedent count). With Foundry the Fact-Checker is also a Microsoft
   Agent Framework agent that calls the same tools (`provider.run_agent`) and can
   reject a draft with a reason, which catches errors the number check cannot,
   such as two shares swapped.
4. **Editor** rewrites a rejected draft with the notes; the rewrite is checked
   again, and the deterministic reference text is restored if it still fails.
5. **Recap Writer** turns the approved pieces into one recap, in the fan's language.

The response carries the trace (role, status, timing, tool calls) that the panel
renders. If the reviewer agent errors, the code checks stay in charge and the
trace says so. `tests/test_desk.py` covers the template run, the swapped-share
catch and repair, a failed rewrite, and a reviewer failure.

## Microsoft stack

- **Microsoft Agent Framework** (`agent-framework` on PyPI): when
  `PM_AGENT_BACKEND=foundry`, `agents/provider.py` builds an `Agent` on a
  `FoundryChatClient` against the Azure AI Foundry project. Default
  everywhere else is the deterministic `TemplateProvider`, so dev, CI and a
  credits-outage demo all behave identically.
- **MCP**: precedent is exposed as MCP tools (`history_query`,
  `season_summary`) by `mcp_history/server.py`. The Historian fetches its
  facts by calling `history_query` on the deployed server over streamable HTTP
  (`agents/history_client.py`, `PM_HISTORY_MCP_URL`), and falls back to the
  same function in process if MCP is unreachable. `/precedents` reports
  `source: "mcp"` or `"in-process"`; `/health` shows the MCP URL and last error. In the Foundry deployment an Agent Framework agent can attach
  the tool with `MCPStreamableHTTPTool` against the deployed `pm-history-mcp`
  app (both are wired in `deploy/deploy.sh`).
- **Azure Container Apps**: one image, two apps (`pm-agents`, `pm-history-mcp`)
  - see `docs/deployment.md`.

## Run locally

```bash
pip install -e ".[agents,mcp]"          # or nothing: core agents run dep-free
python -m pytest -q                          # full suite

# agents REST API
uvicorn agents.server:app --port 8001
curl -s localhost:8001/health

# MCP server (stdio for local clients)
python -m mcp_history.server
# MCP over streamable-http (deployment mode)
PM_MCP_HTTP=1 PM_MCP_HOST=0.0.0.0 PM_MCP_PORT=8080 python -m mcp_history.server
```

API endpoints: `GET /health`, `POST /narrate`, `POST /explain`,
`POST /precedents`, `POST /parse`, `POST /desk` (bodies in `agents/server.py` docstring).

## Season data

The agents and the MCP server read the real 90-match season: fixtures and
seeds from `parallel_match/data/season.json`, replayed once per process at
startup via `parallel_match.season.match_dicts()`
(`mcp_history/season_source.py`, a few seconds). The match JSON is
identical to `GET /match/{id}` on the simulator API. `data/dev_season/` and
`tools/make_dev_season.py` are retired.

## Precedent: one source (the Historian's tool)

Every precedent number comes from `history_for(match_id, event_id)`
(`mcp_history/precedent.py`), which returns the same shape and the same
numbers as the `history` block of `POST /fork`:

```
{n, description, when_given: {n, win, goal_10}, when_not_given: {...},
 attacking_team, history_shift_att_win, note}
```

Comparable decisions: same family (foul or offside), same pitch zone, same
score state, same minute band, borderline margin (`|margin| < 0.15`). Within
them, `when_given` / `when_not_given` give the attacking team's win share and
its chance of scoring within 10 minutes. `history_shift_att_win` is
precedent's estimate of flipping the call (null when either group has fewer
than 5 cases).

`mcp_history/precedent.py` calls `parallel_match.history.history_for` and,
for the simulation side, `parallel_match.history.compare_with_simulation`,
exactly as `/fork` does; tests assert the numbers match
`fixtures/fork_m052.json`.

`POST /precedents` takes an optional `fork_response`. With it, the response
adds `sim_shift_att_win` and `agrees_with_simulation`, and the Historian's
text says "These disagree" when they do. Response:

```
{match_id, event_id, history, agrees_with_simulation, text, facts, fell_back}
```

The old `HistoryStore.query` (contact/margin tolerance search) is no longer
used by any service; `HistoryStore` remains as the event index for `/explain`
and `/parse`.

## Narrator outcome line

The verdict states rollout shares from the fork point
(`original.outcome` / `alternate.outcome`), e.g. "Model world over 500
rollouts from this moment: Westfield Rangers win 15% of finishes instead of
29%". It no longer uses the final win-probability point, which is ~0 or ~1 at
full time.

## Languages

`/narrate`, `/explain`, `/precedents` and `/parse` accept `lang`, one of the 18
interface codes (`en es pt fr de it nl pl ru tr ar hi id th vi zh ja ko`);
anything else means English. Responses carry `lang` and `translated`.

- The deterministic English reference text is still built from the facts. With
  a model backend, the model writes it in the requested language
  (`agents/translate.py`, `provider.phrase_in`).
- The result is accepted only if every number is in the fact bundle (native
  digits and decimal commas are normalised first), it passes the English
  neutrality screen plus a per-language list of judging wording, and it is
  really in that language (script check, or differs from the reference).
  Otherwise the English text is returned with `translated: false` and the UI
  shows a note. The template provider always answers in English.
- Answers are cached per language; an untranslated answer is not cached, so it
  is retried.
- `/parse` translates the fan's free text to English with the model, then runs
  the same deterministic parser. If that fails the text is parsed as typed.
  Parser refusal reasons stay English.
- The per-language word lists are a screen, not a proof of neutrality: the
  source text is neutral and constrained, and a native speaker should review
  the lists before relying on them.
