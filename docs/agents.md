# Agents and the MCP history server

Status: working against the contract fixtures and a generated dev season.
No cloud credentials needed to run any of it locally.

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

The Intervention Parser is plain code on purpose (and first on the cut list):
the fork engine accepts a bounded set of changes, and a deterministic parser
guarantees a parse lands inside that set or is refused - never a free-form
model guess. Negated fan phrasings ("that wasn't a foul", "he was onside")
are handled explicitly.

## Microsoft stack

- **Microsoft Agent Framework** (`agent-framework` on PyPI): when
  `PM_AGENT_BACKEND=foundry`, `agents/provider.py` builds an `Agent` on a
  `FoundryChatClient` against the Azure AI Foundry project. Default
  everywhere else is the deterministic `TemplateProvider`, so dev, CI and a
  credits-outage demo all behave identically.
- **MCP**: the season history query is exposed as MCP tools
  (`history_query`, `season_summary`) by `mcp_history/server.py`. The
  Historian uses the same `HistoryStore` in process; any MCP client can use
  the server. In the Foundry deployment an Agent Framework agent can attach
  the tool with `MCPStreamableHTTPTool` against the deployed `pm-history-mcp`
  app (both are wired in `deploy/deploy.sh`).
- **Azure Container Apps**: one image, two apps (`pm-agents`, `pm-history-mcp`)
  - see `docs/deployment.md`.

## Run locally

```bash
pip install -e ".[agents,mcp]"          # or nothing: core agents run dep-free
python -m unittest discover -s tests -t .   # 69 tests, no deps required

# agents REST API
uvicorn agents.server:app --port 8001
curl -s localhost:8001/health

# MCP server (stdio for local clients)
python -m mcp_history.server
# MCP over streamable-http (deployment mode)
PM_MCP_HTTP=1 PM_MCP_HOST=0.0.0.0 PM_MCP_PORT=8080 python -m mcp_history.server
```

API endpoints: `GET /health`, `POST /narrate`, `POST /explain`,
`POST /precedents`, `POST /parse` (bodies in `agents/server.py` docstring).

## Season data

`mcp_history` reads match JSON from `PM_FIXTURES_DIR` (default `fixtures/`)
and `PM_HISTORY_DIR` (default `data/dev_season/`). The dev season is ten
generated matches (`tools/make_dev_season.py`, seeds 1-10, ~1,500 contestable
moments across 11 matches with m012). When Evan's 90-match season lands it
replaces `data/dev_season/` file-for-file and nothing else changes. In
deployment, both directories are baked into the image; swap to a volume or
Fabric export by pointing the env vars elsewhere.

## Comparable-moment query (the Historian's tool)

A moment is comparable when it is in the same decision family with a similar
measured quantity:

- **contact family** (foul / tackle / dribble, Law 12): `|contact difference| <= 0.2`
- **offside family** (offside / borderline onside pass, Law 11): `|margin difference| <= 0.4 m`

Pitch zone (same attacking frame, away-team x mirrored) and clock proximity
(15 min) add tie-break bonuses. The queried match is excluded by default so
precedent comes from other matches. For every comparable the store also
computes whether the benefiting team scored within 15 minutes - that is the
"in N comparable moments this season..." number, in plain code.
