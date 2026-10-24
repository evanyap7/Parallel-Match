# Deployment runbook (Jiawei track)

Goal: find every Azure problem in the first hour, then keep the agents API
and the MCP history server live for the front end and the judges.

Everything runs on `PM_AGENT_BACKEND=template` until Foundry is wired, so
the demo never depends on credits or a model being up.

## 0. Prerequisites (once)

```bash
az login
az account set --subscription <AZURE_SUBSCRIPTION_ID>
az provider register -n Microsoft.App          # Container Apps
```

Create the shared resources (or use the hackathon-provided ones):

```bash
az group create -n rg-the-home-dugout -l southeastasia
az acr create -n <registry-name, globally unique> -g rg-the-home-dugout --sku Basic
az containerapp env create -n pm-env -g rg-the-home-dugout -l southeastasia
```

Put the four values in `.env` (copy `.env.example`; `.env` is git-ignored).

**Credits check**: `az account show` then Cost Management + Billing in the
portal - confirm the hackathon sponsorship is attached and see the remaining
balance. Container Apps with `minReplicas=0` and Basic ACR cost cents/hour;
Foundry model calls are the only real spend, and template mode uses none.

## 1. First hour: hello-world on Container Apps

The whole point is to flush out registry/ingress/identity problems while
nothing else depends on them:

```bash
./deploy/deploy.sh hello
# prints: hello: https://pm-hello.<env-domain>
curl https://pm-hello.<env-domain>/health   # {"status":"ok"}
```

If that works, deployment risk is retired. Delete it later with
`az containerapp delete -n pm-hello -g rg-the-home-dugout`.

## 2. Agents API + MCP server

One image, two apps (deploy.sh builds, pushes and creates both):

```bash
./deploy/deploy.sh all
# agents: https://pm-agents.<env-domain>
# mcp:    https://pm-history-mcp.<env-domain>/mcp
curl https://pm-agents.<env-domain>/health
```

- `pm-agents` runs uvicorn (`agents/server.py`) on port 8000.
- `pm-history-mcp` runs `python -m mcp_history.server` with
  `PM_MCP_HTTP=1` on port 8080 - an MCP streamable-http endpoint.

Re-deploys are the same command; `IMAGE_TAG` defaults to a timestamp so
revisions roll forward. The declarative equivalent for the agents app is
`deploy/containerapps.agents.yaml`.

## 3. Azure AI Foundry (the model behind the agents)

1. Portal -> Azure AI Foundry -> Create project (or use the hackathon's).
2. Deploy a model (e.g. `gpt-4o-mini`) in the project; note the **project
   endpoint** (`https://<res>.services.ai.azure.com/api/projects/<id>`)
   and the **model deployment name**.
3. Auth: easiest is managed identity -

   ```bash
   az containerapp identity assign -n pm-agents -g rg-the-home-dugout --system-assigned
   # grant the returned principal access to the Foundry project (IAM: Reader
   # + inference permissions) in the portal
   ```

   `agents/provider.py` uses `DefaultAzureCredential`, so the managed
   identity just works in the container. Locally, `az login` covers it.
4. Switch the app to the model backend:

   ```bash
   ./deploy/deploy.sh agents   # with PM_AGENT_BACKEND=foundry,
                               # AZURE_AI_FOUNDRY_PROJECT_ENDPOINT and
                               # AZURE_AI_FOUNDRY_MODEL in the environment
   ```

   `/health` reports the active provider; every utterance still passes the
   guardrails and falls back to template phrasing on any failure.

Local smoke test of the same path (no Container Apps needed):

```bash
pip install -e ".[foundry]"
PM_AGENT_BACKEND=foundry AZURE_AI_FOUNDRY_PROJECT_ENDPOINT=<ep> \
  AZURE_AI_FOUNDRY_MODEL=<model> uvicorn agents.server:app --port 8001
```

## 4. Microsoft Fabric (season history)

The plan calls for loading the season into Fabric and querying it from the
Historian. Until the curated 90-match season exists this is premature; the
integration point is deliberately narrow - `mcp_history/store.py` reads
match JSON. Options when the season lands, cheapest first:

1. Keep baked-in JSON (zero config, works today, fine for a 90-match season).
2. Export the season from Fabric to a storage account / OneLake endpoint and
   point `PM_HISTORY_DIR` at a mounted download at container start.
3. Query Fabric/Synapse directly in a `HistoryStore` subclass.

The MCP tool contract (`history_query`) does not change in any option, so
the agents and the front end are unaffected.

## 5. Rules of engagement

- Never commit secrets: `.env` is git-ignored; production secrets go in
  Container App secrets (`--secret-ref`) or Key Vault.
- Synthetic data only - the guardrails enforce the no-real-names rule on
  agent output; keep it true in every prompt and screen.
