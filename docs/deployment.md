# Deployment runbook (Jiawei track)

Goal: one public link for the judges (the front end), backed by the simulator
API, the agents API and the MCP history server, all on Azure Container Apps.

| App | Image (Dockerfile) | Port | What |
|---|---|---|---|
| `pm-web` | `deploy/frontend/Dockerfile` | 80 | React match viewer (nginx). **The link the judges open.** |
| `pm-api` | `Dockerfile` (root) | 8000 | Simulator API: matches, `/fork`, precomputed story forks |
| `pm-agents` | `deploy/Dockerfile`, `PM_SERVICE=api` | 8000 | Narrator, Law Explainer, Historian, parser |
| `pm-history-mcp` | `deploy/Dockerfile`, `PM_SERVICE=mcp` | 8080 | MCP over streamable HTTP at `/mcp` |
| `pm-hello` | `deploy/hello/Dockerfile` | 8000 | First-hour smoke test only |

Images are built in Azure (`az acr build`), so no local Docker is needed.
Everything runs on `PM_AGENT_BACKEND=template` until Foundry is wired, so the
demo never depends on credits or a model being up.

## 0. Prerequisites (once)

```bash
az login
az account set --subscription <AZURE_SUBSCRIPTION_ID>
az extension add --name containerapp --upgrade
az group create -n rg-the-home-dugout -l southeastasia
az acr create -n <registry-name, globally unique> -g rg-the-home-dugout --sku Basic
```

Copy `.env.example` to `.env` (git-ignored) and fill in the subscription,
resource group, location and registry **name**. `deploy.sh` reads `.env`
itself and creates the `pm-env` Container Apps environment if it is missing.

Apps pull from the registry with their own system-assigned managed identity
(`--registry-identity system`), so the registry needs no admin user and no
password ends up anywhere.

**Credits check**: Cost Management + Billing in the portal. Container Apps at
`MIN_REPLICAS=1` and Basic ACR cost cents per hour; Foundry calls are the only
real spend, and template mode uses none. Set `MIN_REPLICAS=0` after judging.

## 1. First hour: hello-world

```bash
./deploy/deploy.sh hello
curl https://pm-hello.<env-domain>/health   # {"status":"ok"}
```

Flushes out registry, ingress and identity problems while nothing depends on
them. Delete later: `az containerapp delete -n pm-hello -g rg-the-home-dugout`.

## 2. Everything

```bash
./deploy/deploy.sh          # api, agents, mcp, then web pointed at api + agents
./deploy/deploy.sh urls     # print every HTTPS URL (post these in chat)
./deploy/smoke.sh           # end-to-end check against the live URLs
```

Order matters only for the front end: Vite inlines `VITE_API_BASE_URL` and
`VITE_AGENTS_BASE_URL` at build time, so `deploy.sh web` reads the live
`pm-api` / `pm-agents` URLs and rebuilds. Redeploy one piece with
`./deploy/deploy.sh api|agents|mcp|web`; the first run creates each app, later
runs roll a new revision with a timestamped image tag.

`smoke.sh` checks: every `/health`; the featured m052 penalty fork returns
`cached: true`; the Historian's precedent count equals the fork's `history.n`;
the narrator's verdict uses rollout shares; MCP answers `initialize`; the web
app serves. Locally:

```bash
API=http://localhost:8000 AGENTS=http://localhost:8001 \
  MCP=http://localhost:8080 WEB= ./deploy/smoke.sh
```

(MCP locally: `PM_MCP_HTTP=1 PM_MCP_HOST=0.0.0.0 python -m mcp_history.server`.)

Sizing: `pm-api` gets 2 vCPU / 4 GiB because uncached forks run rollouts in a
process pool; the agents and MCP apps replay the 90-match season once at
startup (a few seconds), which is why `MIN_REPLICAS` defaults to 1.

The agents API allows any origin (`PM_CORS_ORIGINS=*`, no cookies are used);
set it to the `pm-web` URL to lock it down. The simulator API already allows
any origin.

## 3. Azure AI Foundry (the model behind the agents)

1. Portal: Azure AI Foundry, create a project (or use the hackathon's) and
   deploy a model (e.g. `gpt-4o-mini`). Note the **project endpoint**
   (`https://<res>.services.ai.azure.com/api/projects/<id>`), the **model
   deployment name**, and the Foundry resource's **resource ID**.
2. In `.env`:

   ```bash
   PM_AGENT_BACKEND=foundry
   AZURE_AI_FOUNDRY_PROJECT_ENDPOINT=https://<res>.services.ai.azure.com/api/projects/<id>
   AZURE_AI_FOUNDRY_MODEL=gpt-4o-mini
   AZURE_AI_FOUNDRY_RESOURCE_ID=/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<res>
   ```

3. `./deploy/deploy.sh agents`. With `foundry` selected it also grants
   `pm-agents`' managed identity the **Azure AI User** role on the Foundry
   resource (needs Owner or User Access Administrator there; otherwise it
   prints the portal steps). Role assignments can take a few minutes.
4. `curl https://pm-agents.<env-domain>/health` shows `provider`,
   `provider_error` and `model_last_error`.

Auth is keyless: in the container `agents/provider.py` uses
`ManagedIdentityCredential` (Container Apps sets `IDENTITY_ENDPOINT`);
locally it uses `DefaultAzureCredential`, so `az login` covers it.

**Fallback stays on.** If Foundry cannot be configured, `/health` reports why
and the service runs on templates. If a model call fails or exceeds
`PM_AGENT_TIMEOUT_S` (8 s), that utterance uses the template phrasing and the
model is skipped for `PM_AGENT_COOLDOWN_S` (60 s), so a down model costs one
timeout, not one per line. Every model output still passes the guardrails.

Local smoke test of the same path:

```bash
pip install -e ".[agents,foundry]"
az login
PM_AGENT_BACKEND=foundry AZURE_AI_FOUNDRY_PROJECT_ENDPOINT=<ep> \
  AZURE_AI_FOUNDRY_MODEL=<model> uvicorn agents.server:app --port 8001
```

## 4. Microsoft Fabric (season history)

All services read the real season from `parallel_match/data/season.json`
(replayed deterministically), and precedent comes from one function,
`history_for()`, shared with `/fork`. For Fabric, export flat tables with
`parallel_match.season.export(season, out_dir)` (`matches.csv`,
`events.jsonl`, `moments.csv`) and run the query in `docs/history-query.md`.
The MCP tool contract (`history_query`) does not change if the source moves
to Fabric later, so the agents and the front end are unaffected.

## 5. Rules of engagement

- Never commit secrets: `.env` is git-ignored; production secrets go in
  Container App secrets or Key Vault. Foundry and ACR use managed identity,
  so there are no keys to store.
- Synthetic data only: the guardrails enforce the no-real-names rule on agent
  output; keep it true in every prompt and screen.
