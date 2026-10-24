#!/usr/bin/env bash
# Deploy The Home Dugout to Azure Container Apps.
#
# Four apps, three images (each built from its own Dockerfile in ACR):
#   pm-api          root Dockerfile              simulator API      :8000
#   pm-agents       deploy/Dockerfile  PM_SERVICE=api  agents API    :8000
#   pm-history-mcp  deploy/Dockerfile  PM_SERVICE=mcp  MCP (/mcp)    :8080
#   pm-web          deploy/frontend/Dockerfile  React front end      :80
# plus pm-hello (deploy/hello/Dockerfile), the first-hour smoke test.
#
# Usage (first time: setup, then all):
#   ./deploy/deploy.sh setup      # resource group, registry, environment (once)
#   ./deploy/deploy.sh            # api, agents, mcp, then web (pointed at them)
#   ./deploy/deploy.sh api        # simulator API only
#   ./deploy/deploy.sh agents     # agents API only
#   ./deploy/deploy.sh mcp        # MCP history server only
#   ./deploy/deploy.sh web        # front end only (reads the live api/agents URLs)
#   ./deploy/deploy.sh hello      # smoke-test app
#   ./deploy/deploy.sh urls       # print the HTTPS URLs of everything deployed
#   ./deploy/deploy.sh foundry    # managed identity + Foundry role on pm-agents
#   ./deploy/deploy.sh foundry-create   # Foundry resource, project, model deployment
#   ./deploy/deploy.sh pause      # scale everything to zero (after judging)
#   ./deploy/deploy.sh resume     # back to the judging sizes
#   ./deploy/deploy.sh teardown   # delete the whole resource group (irreversible)
#
# Sized for an Azure for Students subscription ($100 credit): about $1.5 a day
# with web, api and agents kept warm; see docs/deployment.md "Cost".
#
# Required environment (see docs/deployment.md and .env.example):
#   AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP, AZURE_LOCATION,
#   AZURE_CONTAINER_REGISTRY (name, e.g. pmdugoutacr, or pmdugoutacr.azurecr.io)
# Optional:
#   PM_AGENT_BACKEND (template | foundry), AZURE_AI_FOUNDRY_PROJECT_ENDPOINT,
#   AZURE_AI_FOUNDRY_MODEL, AZURE_AI_FOUNDRY_RESOURCE_ID (to grant the agents'
#   managed identity access automatically), PM_ENV (default pm-env),
#   MIN_REPLICAS (default 1: no cold starts while judges are looking; the
#   MCP server always scales to zero), FOUNDRY_NAME, FOUNDRY_MODEL,
#   IMAGE_TAG (default: timestamp)

set -euo pipefail

cd "$(dirname "$0")/.."            # every build context is the repo root
if [[ -f .env ]]; then set -a; source .env; set +a; fi

WHAT="${1:-all}"
SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:?set AZURE_SUBSCRIPTION_ID}"
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:?set AZURE_RESOURCE_GROUP}"
LOCATION="${AZURE_LOCATION:?set AZURE_LOCATION}"
ACR_INPUT="${AZURE_CONTAINER_REGISTRY:?set AZURE_CONTAINER_REGISTRY}"
ACR_NAME="${ACR_INPUT%%.*}"                  # az acr build wants the name
ACR_SERVER="${ACR_NAME}.azurecr.io"          # image refs want the login server
ENV_NAME="${PM_ENV:-pm-env}"
MIN_REPLICAS="${MIN_REPLICAS:-1}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"
BACKEND="${PM_AGENT_BACKEND:-template}"
if [[ "$BACKEND" == "foundry" && -z "${AZURE_AI_FOUNDRY_PROJECT_ENDPOINT:-}" ]]; then
  echo "PM_AGENT_BACKEND=foundry needs AZURE_AI_FOUNDRY_PROJECT_ENDPOINT" >&2; exit 2
fi

API_IMAGE="${ACR_SERVER}/the-home-dugout-api:${IMAGE_TAG}"
AGENTS_IMAGE="${ACR_SERVER}/the-home-dugout:${IMAGE_TAG}"
WEB_IMAGE="${ACR_SERVER}/the-home-dugout-web:${IMAGE_TAG}"
HELLO_IMAGE="${ACR_SERVER}/the-home-dugout-hello:${IMAGE_TAG}"

log() { echo "==> $*" >&2; }

az account show --query name -o tsv > /dev/null 2>&1 || az login > /dev/null
az account set --subscription "$SUBSCRIPTION_ID"
az extension add --name containerapp --upgrade --only-show-errors > /dev/null 2>&1 || true

register() {
  az provider show -n "$1" --query registrationState -o tsv 2>/dev/null | grep -q Registered || {
    log "registering $1 (once, can take a few minutes)"
    az provider register -n "$1" --wait
  }
}

# One-time: resource group, Basic registry, Container Apps environment.
# Logs go to the console stream only (no Log Analytics workspace to pay for);
# read them with: az containerapp logs show -n <app> -g <rg> --follow
setup() {
  for ns in Microsoft.App Microsoft.ContainerRegistry Microsoft.CognitiveServices; do register "$ns"; done
  az group show -n "$RESOURCE_GROUP" > /dev/null 2>&1 || {
    log "creating resource group $RESOURCE_GROUP in $LOCATION"
    az group create -n "$RESOURCE_GROUP" -l "$LOCATION" > /dev/null
  }
  az acr show -n "$ACR_NAME" > /dev/null 2>&1 || {
    log "creating registry $ACR_NAME (Basic)"
    az acr create -n "$ACR_NAME" -g "$RESOURCE_GROUP" -l "$LOCATION" --sku Basic > /dev/null
  }
  ensure_env
}

ensure_env() {
  register Microsoft.App
  az containerapp env show -n "$ENV_NAME" -g "$RESOURCE_GROUP" > /dev/null 2>&1 || {
    log "creating Container Apps environment $ENV_NAME"
    az containerapp env create -n "$ENV_NAME" -g "$RESOURCE_GROUP" --location "$LOCATION" \
      --logs-destination none > /dev/null
  }
}

# build IMAGE DOCKERFILE [--build-arg K=V ...]
build() {
  local image="$1" dockerfile="$2"; shift 2
  log "building ${image##*/} from $dockerfile"
  az acr build --registry "$ACR_NAME" --image "${image#*/}" --file "$dockerfile" "$@" . > /dev/null
}

exists() { az containerapp show -n "$1" -g "$RESOURCE_GROUP" > /dev/null 2>&1; }

fqdn() {
  az containerapp show -n "$1" -g "$RESOURCE_GROUP" \
    --query properties.configuration.ingress.fqdn -o tsv 2>/dev/null || true
}

# upsert NAME IMAGE PORT CPU MEMORY MIN MAX [ENV=VAR ...]
# Creates the app the first time (system identity pulls from ACR); afterwards
# only rolls a new revision with the new image and env.
upsert() {
  local name="$1" image="$2" port="$3" cpu="$4" mem="$5" min="$6" max="$7"; shift 7
  local scale=(--cpu "$cpu" --memory "$mem" --min-replicas "$min" --max-replicas "$max")
  if exists "$name"; then
    log "updating $name"
    local env_args=()
    if (($#)); then env_args=(--set-env-vars "$@"); fi
    az containerapp update -n "$name" -g "$RESOURCE_GROUP" --image "$image" "${scale[@]}" \
      ${env_args[@]+"${env_args[@]}"} > /dev/null
  else
    log "creating $name"
    local env_args=()
    if (($#)); then env_args=(--env-vars "$@"); fi
    az containerapp create -n "$name" -g "$RESOURCE_GROUP" --environment "$ENV_NAME" \
      --image "$image" --target-port "$port" --ingress external \
      --registry-server "$ACR_SERVER" --registry-identity system "${scale[@]}" \
      ${env_args[@]+"${env_args[@]}"} > /dev/null
  fi
  echo "https://$(fqdn "$name")"
}

# Judging sizes. Featured forks are precomputed; an uncached fork takes about
# 9 s on 1 vCPU, and the agents service needs ~140 MB, so these are ample.
#        app             cpu   memory  min              max
SIZE_API=(1.0 2Gi "$MIN_REPLICAS" 2)
SIZE_AGENTS=(0.5 1Gi "$MIN_REPLICAS" 2)
SIZE_WEB=(0.25 0.5Gi "$MIN_REPLICAS" 2)
SIZE_MCP=(0.25 0.5Gi 0 1)        # judges rarely call MCP: scale to zero

deploy_api() {          # simulator API: forks run rollouts in a process pool
  build "$API_IMAGE" Dockerfile
  upsert pm-api "$API_IMAGE" 8000 "${SIZE_API[@]}"
}

deploy_agents() {
  build "$AGENTS_IMAGE" deploy/Dockerfile
  upsert pm-agents "$AGENTS_IMAGE" 8000 "${SIZE_AGENTS[@]}" \
    PM_SERVICE=api PM_AGENT_BACKEND="$BACKEND" \
    AZURE_AI_FOUNDRY_PROJECT_ENDPOINT="${AZURE_AI_FOUNDRY_PROJECT_ENDPOINT:-}" \
    AZURE_AI_FOUNDRY_MODEL="${AZURE_AI_FOUNDRY_MODEL:-gpt-4o-mini}"
  if [[ "$BACKEND" == "foundry" ]]; then setup_foundry > /dev/null; fi
}

deploy_mcp() {
  # Same image as the agents; build only if this run has not built it.
  az acr repository show --name "$ACR_NAME" --image "${AGENTS_IMAGE#*/}" > /dev/null 2>&1 || \
    build "$AGENTS_IMAGE" deploy/Dockerfile
  upsert pm-history-mcp "$AGENTS_IMAGE" 8080 "${SIZE_MCP[@]}" PM_SERVICE=mcp
}

deploy_web() {
  local api agents
  api="$(fqdn pm-api)"; agents="$(fqdn pm-agents)"
  [[ -n "$api" ]] || { echo "pm-api is not deployed yet: run ./deploy/deploy.sh api" >&2; exit 1; }
  [[ -n "$agents" ]] || log "pm-agents not deployed yet; /agents will fail until it is (then rerun web)"
  # The API URL is baked into the bundle; the agents are proxied at /agents
  # by nginx, so only AGENTS_UPSTREAM changes when the agents app moves.
  build "$WEB_IMAGE" deploy/frontend/Dockerfile \
    --build-arg "VITE_API_BASE_URL=https://$api"
  if [[ -n "$agents" ]]; then
    upsert pm-web "$WEB_IMAGE" 80 "${SIZE_WEB[@]}" AGENTS_UPSTREAM="https://$agents"
  else
    upsert pm-web "$WEB_IMAGE" 80 "${SIZE_WEB[@]}"
  fi
}

deploy_hello() {
  build "$HELLO_IMAGE" deploy/hello/Dockerfile
  upsert pm-hello "$HELLO_IMAGE" 8000 0.25 0.5Gi 0 1
}

# Managed identity for Foundry. The system-assigned identity already exists
# (created with the app for ACR pulls); this grants it "Azure AI User" on the
# Foundry resource so DefaultAzureCredential / ManagedIdentityCredential get
# a token. Needs Owner or User Access Administrator on that resource.
setup_foundry() {
  local principal
  principal="$(az containerapp identity assign -n pm-agents -g "$RESOURCE_GROUP" \
    --system-assigned --query principalId -o tsv)"
  if [[ -n "${AZURE_AI_FOUNDRY_RESOURCE_ID:-}" ]]; then
    log "granting Azure AI User on the Foundry resource to pm-agents ($principal)"
    az role assignment create --assignee-object-id "$principal" \
      --assignee-principal-type ServicePrincipal --role "Azure AI User" \
      --scope "$AZURE_AI_FOUNDRY_RESOURCE_ID" > /dev/null 2>&1 || \
      log "role assignment failed or exists; check IAM on the Foundry resource"
  else
    log "set AZURE_AI_FOUNDRY_RESOURCE_ID to grant access automatically, or in the portal:"
    log "  Foundry resource > Access control (IAM) > Add role assignment > Azure AI User >"
    log "  Managed identity > Container App > pm-agents  (principal $principal)"
  fi
  echo "$principal"
}

# Foundry resource + project + model deployment, all from the CLI. Prints the
# three .env lines the agents need. If a step fails (CLI too old, no quota for
# the model in this region), do that step in the portal at ai.azure.com.
foundry_create() {
  local name="${FOUNDRY_NAME:-${ACR_NAME}-ai}" project="${FOUNDRY_PROJECT:-pm-project}"
  local model="${FOUNDRY_MODEL:-gpt-4o-mini}" version="${FOUNDRY_MODEL_VERSION:-}"
  register Microsoft.CognitiveServices
  az cognitiveservices account show -n "$name" -g "$RESOURCE_GROUP" > /dev/null 2>&1 || {
    log "creating Foundry resource $name in $LOCATION"
    az cognitiveservices account create -n "$name" -g "$RESOURCE_GROUP" -l "$LOCATION" \
      --kind AIServices --sku S0 --custom-domain "$name" --allow-project-management --yes > /dev/null
  }
  az cognitiveservices account project show -n "$name" -g "$RESOURCE_GROUP" \
      --project-name "$project" > /dev/null 2>&1 || {
    log "creating Foundry project $project"
    az cognitiveservices account project create -n "$name" -g "$RESOURCE_GROUP" \
      --project-name "$project" -l "$LOCATION" > /dev/null
  }
  if [[ -z "$version" ]]; then
    version="$(az cognitiveservices account list-models -n "$name" -g "$RESOURCE_GROUP" \
      --query "[?name=='$model' && format=='OpenAI'].version | sort(@) | [-1]" -o tsv)"
  fi
  [[ -n "$version" ]] || { echo "model $model is not offered in $LOCATION; set FOUNDRY_MODEL (e.g. gpt-4.1-mini)" >&2; exit 1; }
  az cognitiveservices account deployment show -n "$name" -g "$RESOURCE_GROUP" \
      --deployment-name "$model" > /dev/null 2>&1 || {
    log "deploying $model $version (GlobalStandard, 20K tokens/min)"
    az cognitiveservices account deployment create -n "$name" -g "$RESOURCE_GROUP" \
      --deployment-name "$model" --model-name "$model" --model-version "$version" \
      --model-format OpenAI --sku-name GlobalStandard --sku-capacity 20 > /dev/null
  }
  echo "# add to .env, then: ./deploy/deploy.sh agents"
  echo "PM_AGENT_BACKEND=foundry"
  echo "AZURE_AI_FOUNDRY_PROJECT_ENDPOINT=https://$name.services.ai.azure.com/api/projects/$project"
  echo "AZURE_AI_FOUNDRY_MODEL=$model"
  echo "AZURE_AI_FOUNDRY_RESOURCE_ID=$(az cognitiveservices account show -n "$name" -g "$RESOURCE_GROUP" --query id -o tsv)"
}

# pause: everything to zero replicas (cost ~ registry only). resume: judging sizes.
scale_all() {
  local min_web="$1" min_api="$2" min_agents="$3"
  for pair in "pm-web:$min_web" "pm-api:$min_api" "pm-agents:$min_agents" "pm-history-mcp:0" "pm-hello:0"; do
    local app="${pair%%:*}" min="${pair##*:}"
    exists "$app" || continue
    log "$app min replicas -> $min"
    az containerapp update -n "$app" -g "$RESOURCE_GROUP" --min-replicas "$min" > /dev/null
  done
}

urls() {
  for app in pm-web pm-api pm-agents pm-history-mcp pm-hello; do
    local f; f="$(fqdn "$app")"
    [[ -z "$f" ]] && continue
    if [[ "$app" == pm-history-mcp ]]; then echo "$app: https://$f/mcp"; else echo "$app: https://$f"; fi
  done
}

case "$WHAT" in
  setup)   setup; echo "setup done: ./deploy/deploy.sh to deploy" ;;
  foundry-create) foundry_create ;;
  pause)   scale_all 0 0 0 ;;
  resume)  scale_all "${SIZE_WEB[2]}" "${SIZE_API[2]}" "${SIZE_AGENTS[2]}" ;;
  teardown)
    read -r -p "Delete resource group $RESOURCE_GROUP and everything in it? Type its name: " ans
    [[ "$ans" == "$RESOURCE_GROUP" ]] || { echo "cancelled"; exit 1; }
    az group delete -n "$RESOURCE_GROUP" --yes --no-wait; echo "deleting $RESOURCE_GROUP" ;;
  api)     ensure_env; echo "api: $(deploy_api)" ;;
  agents)  ensure_env; echo "agents: $(deploy_agents)" ;;
  mcp)     ensure_env; echo "mcp: $(deploy_mcp)/mcp" ;;
  web)     ensure_env; echo "web: $(deploy_web)" ;;
  hello)   ensure_env; echo "hello: $(deploy_hello)" ;;
  foundry) setup_foundry > /dev/null ;;
  urls)    urls ;;
  all)
    setup
    echo "api: $(deploy_api)"
    echo "agents: $(deploy_agents)"
    echo "mcp: $(deploy_mcp)/mcp"
    echo "web: $(deploy_web)"
    echo
    echo "Smoke test:  ./deploy/smoke.sh"
    ;;
  *) echo "unknown target: $WHAT (setup|all|api|agents|mcp|web|hello|urls|foundry|foundry-create|pause|resume|teardown)" >&2; exit 2 ;;
esac
