# Deployment runbook

Goal: one public link for the judges (the front end), backed by the simulator
API, the agents API and the MCP history server, all on Azure Container Apps.

| App | Image (Dockerfile) | Port | What |
|---|---|---|---|
| `pm-web` | `deploy/frontend/Dockerfile` | 80 | React match viewer (nginx). **The link the judges open.** |
| `pm-api` | `Dockerfile` (root) | 8000 | Simulator API: matches, `/fork`, precomputed story forks |
| `pm-agents` | `deploy/Dockerfile`, `PM_SERVICE=api` | 8000 | Narrator, Law Explainer, Historian, parser |
| `pm-history-mcp` | `deploy/Dockerfile`, `PM_SERVICE=mcp` | 8080 | MCP over streamable HTTP at `/mcp` |
| `pm-hello` | `deploy/hello/Dockerfile` | 8000 | First-hour smoke test only |

Images are built locally with Docker (`docker buildx`, `linux/amd64`, also on
Apple Silicon) and pushed to the registry: Azure for Students blocks ACR Tasks
(`az acr build` fails with `TasksOperationsNotAllowed`). On a subscription
that allows it, `PM_BUILDER=acr` builds in Azure instead. Docker Desktop must
be running, or Colima on a Mac:

```bash
brew install colima docker docker-buildx
mkdir -p ~/.docker/cli-plugins
ln -sfn "$(brew --prefix)/opt/docker-buildx/bin/docker-buildx" ~/.docker/cli-plugins/docker-buildx
colima start --cpu 4 --memory 6 --vm-type vz --vz-rosetta
```
Everything runs on `PM_AGENT_BACKEND=template` until Foundry is wired, so the
demo never depends on credits or a model being up.

## 0. Prerequisites (once)

Copy `.env.example` to `.env` (git-ignored) and fill in the subscription,
resource group, location and a globally unique registry **name**. Then:

```bash
az login
./deploy/deploy.sh setup     # providers, resource group, Basic registry, environment
```

**Region.** Azure for Students subscriptions only allow a few regions (ours:
indonesiacentral, japaneast, koreacentral, eastasia, uaenorth). We use
`japaneast`: Container Apps and Foundry OpenAI models are both available there,
and everything sits in one region.

All apps share one user-assigned managed identity (`pm-identity`, created by
`setup` and granted AcrPull). It pulls images and, for the agents, signs in to
Foundry (`AZURE_CLIENT_ID`). User-assigned because Container Apps *express*
environments, which a student subscription can get, do not support
system-assigned identities. No registry password exists anywhere.

## Cost (Azure for Students, $100 credit)

The site must stay up and free to use until judging ends (**10 Nov 2026,
11:59 pm PT**), about 17 days from deploy. Container Apps bills a warm but idle
replica at about $0.000003 per vCPU-second and per GiB-second, and gives each
subscription a monthly free grant (180,000 vCPU-s, 360,000 GiB-s, 2M requests).

| Item | Size | Warm? | ~per day |
|---|---|---|---|
| pm-api | 2 vCPU, 4 GiB | min 1 | $1.56 |
| pm-agents | 0.5 vCPU, 1 GiB | min 1 | $0.39 |
| pm-web | 0.25 vCPU, 0.5 GiB | min 1 | $0.20 |
| pm-history-mcp | 0.25 vCPU, 0.5 GiB | min 1 | $0.20 |
| Registry (Basic) | | | $0.17 |
| Foundry (gpt-4.1-mini) | per call | | cents |

About **$2.5/day, ~$45 to 10 Nov**, before the free grant; active request
time and image builds add a little. No Log Analytics workspace is created
(`--logs-destination none`); stream logs with
`az containerapp logs show -n pm-agents -g <rg> --follow`.

Check the remaining credit at https://www.microsoftazuresponsorships.com/balance.
After judging: `./deploy/deploy.sh pause` (scale to zero, keeps URLs), and
after winners are announced (20 Nov) `./deploy/deploy.sh teardown`.

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

Sizing: featured forks are precomputed (~1 s); an uncached fork took ~25 s
live on 1 vCPU, so the API runs on 2. The agents and MCP apps replay the 90-match season once at startup
(about 6 s, ~140 MB), which is why all four apps stay warm. The Historian
fetches precedent through `pm-history-mcp` (`PM_HISTORY_MCP_URL`, set by
`deploy.sh`), falling back to the same function in process if MCP is
unreachable; `/precedents` returns `source: "mcp"` or `"in-process"`.

The agents API allows any origin (`PM_CORS_ORIGINS=*`, no cookies are used);
set it to the `pm-web` URL to lock it down. The simulator API already allows
any origin.

## Hosting check (for the team and judges)

`./deploy/deploy.sh status` prints what is actually live: each app's CPU,
memory, minimum and maximum replicas and release, the warm cost per day, the
estimate to the end of judging (10 Nov, 11:59 pm PT), and the time for a
featured and a fresh fork. Paste its latest output here.

```
Hosting check, 2026-10-24 16:07 UTC
app                cpu  memory  min  max  release
pm-web            0.25   0.5Gi    1    2  20261025000506
pm-api             2.0     4Gi    1    2  20261024153124
pm-agents          0.5     1Gi    1    2  20261025000319
pm-history-mcp    0.25   0.5Gi    1    1  None
warm: 3 vCPU, 6 GiB -> about $2.50/day; 17.7 days to 10 Nov 11:59 pm PT -> about $44
credit balance: https://www.microsoftazuresponsorships.com/balance
fresh fork (m001-0012, not precomputed): 32.463714s
featured fork (m052-0715, precomputed): 1.056078s
```

Every app keeps at least one warm replica, pm-api has 2 vCPU, and the estimate
to the end of judging (about $44) is well inside the $100 student credit.
The 32 s fresh fork was one rollout worker on 2 vCPU (`os.cpu_count() - 1`);
`deploy.sh api` now sets `PM_FORK_WORKERS=2`, which halves it (measured 30.6 s
with one worker and 15.9 s with two on 2 CPUs, for that minute-1 moment; later
moments have less match left to play and are faster). Rerun `status` after the
next `deploy.sh api` and paste the new output here.

## 3. Azure AI Foundry (the model behind the agents)

1. `./deploy/deploy.sh foundry-create` creates the Foundry resource, a
   project and a model deployment (GlobalStandard, 20K tokens/min): the first
   of gpt-4.1-mini, gpt-4.1-nano, gpt-5-mini, gpt-5-nano that the region
   offers and that is not being retired (gpt-4o-mini 2024-07-18 now refuses
   new deployments),
   then prints the four `.env` lines below. If a step fails (older CLI, or no
   quota for the model in the region), do that step at ai.azure.com, or set
   `FOUNDRY_MODEL=gpt-4.1-mini` and rerun.
2. In `.env`:

   ```bash
   PM_AGENT_BACKEND=foundry
   AZURE_AI_FOUNDRY_PROJECT_ENDPOINT=https://<res>.services.ai.azure.com/api/projects/<id>
   AZURE_AI_FOUNDRY_MODEL=gpt-4.1-mini
   AZURE_AI_FOUNDRY_RESOURCE_ID=/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<res>
   ```

3. `./deploy/deploy.sh agents`. With `foundry` selected it also grants
   `pm-identity` **Azure AI User** (where the tenant has it), **Cognitive
   Services OpenAI User** and **Cognitive Services User** on the Foundry
   resource (the student tenant has no Azure AI User role, and returned 403
   through the project endpoint until Cognitive Services User was added) (needs
   Owner or User Access Administrator there; otherwise it prints the portal
   steps). Role assignments can take a few minutes to apply.
4. `curl https://pm-agents.<env-domain>/health` shows `provider`,
   `provider_error` and `model_last_error`.

Auth is keyless: in the container `agents/provider.py` uses
`ManagedIdentityCredential` with `AZURE_CLIENT_ID` (Container Apps sets
`IDENTITY_ENDPOINT`);
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
