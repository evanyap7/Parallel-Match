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
# Usage:
#   ./deploy/deploy.sh            # api, agents, mcp, then web (pointed at them)
#   ./deploy/deploy.sh api        # simulator API only
#   ./deploy/deploy.sh agents     # agents API only
#   ./deploy/deploy.sh mcp        # MCP history server only
#   ./deploy/deploy.sh web        # front end only (reads the live api/agents URLs)
#   ./deploy/deploy.sh hello      # smoke-test app
#   ./deploy/deploy.sh urls       # print the HTTPS URLs of everything deployed
#   ./deploy/deploy.sh foundry    # managed identity + Foundry role on pm-agents
#
# Required environment (see docs/deployment.md and .env.example):
#   AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP, AZURE_LOCATION,
#   AZURE_CONTAINER_REGISTRY (name, e.g. pmdugoutacr, or pmdugoutacr.azurecr.io)
# Optional:
#   PM_AGENT_BACKEND (template | foundry), AZURE_AI_FOUNDRY_PROJECT_ENDPOINT,
#   AZURE_AI_FOUNDRY_MODEL, AZURE_AI_FOUNDRY_RESOURCE_ID (to grant the agents'
#   managed identity access automatically), PM_ENV (default pm-env),
#   MIN_REPLICAS (default 1: no cold starts while judges are looking),
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

ensure_env() {
  az provider show -n Microsoft.App --query registrationState -o tsv 2>/dev/null | grep -q Registered || \
    az provider register -n Microsoft.App --wait
  az provider show -n Microsoft.OperationalInsights --query registrationState -o tsv 2>/dev/null | grep -q Registered || \
    az provider register -n Microsoft.OperationalInsights --wait
  az containerapp env show -n "$ENV_NAME" -g "$RESOURCE_GROUP" > /dev/null 2>&1 || {
    log "creating Container Apps environment $ENV_NAME"
    az containerapp env create -n "$ENV_NAME" -g "$RESOURCE_GROUP" --location "$LOCATION" > /dev/null
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

# upsert NAME IMAGE PORT CPU MEMORY [ENV=VAR ...]
# Creates the app the first time (system identity pulls from ACR); afterwards
# only rolls a new revision with the new image and env.
upsert() {
  local name="$1" image="$2" port="$3" cpu="$4" mem="$5"; shift 5
  if exists "$name"; then
    log "updating $name"
    if (($#)); then
      az containerapp update -n "$name" -g "$RESOURCE_GROUP" --image "$image" \
        --cpu "$cpu" --memory "$mem" --min-replicas "$MIN_REPLICAS" --max-replicas 3 \
        --set-env-vars "$@" > /dev/null
    else
      az containerapp update -n "$name" -g "$RESOURCE_GROUP" --image "$image" \
        --cpu "$cpu" --memory "$mem" --min-replicas "$MIN_REPLICAS" --max-replicas 3 > /dev/null
    fi
  else
    log "creating $name"
    local env_args=()
    if (($#)); then env_args=(--env-vars "$@"); fi
    az containerapp create -n "$name" -g "$RESOURCE_GROUP" --environment "$ENV_NAME" \
      --image "$image" --target-port "$port" --ingress external \
      --registry-server "$ACR_SERVER" --registry-identity system \
      --cpu "$cpu" --memory "$mem" --min-replicas "$MIN_REPLICAS" --max-replicas 3 \
      ${env_args[@]+"${env_args[@]}"} > /dev/null
  fi
  echo "https://$(fqdn "$name")"
}

deploy_api() {          # simulator API: forks run rollouts in a process pool
  build "$API_IMAGE" Dockerfile
  upsert pm-api "$API_IMAGE" 8000 2.0 4Gi
}

deploy_agents() {
  build "$AGENTS_IMAGE" deploy/Dockerfile
  upsert pm-agents "$AGENTS_IMAGE" 8000 1.0 2Gi \
    PM_SERVICE=api PM_AGENT_BACKEND="$BACKEND" \
    AZURE_AI_FOUNDRY_PROJECT_ENDPOINT="${AZURE_AI_FOUNDRY_PROJECT_ENDPOINT:-}" \
    AZURE_AI_FOUNDRY_MODEL="${AZURE_AI_FOUNDRY_MODEL:-gpt-4o-mini}"
  if [[ "$BACKEND" == "foundry" ]]; then setup_foundry > /dev/null; fi
}

deploy_mcp() {
  # Same image as the agents; build only if this run has not built it.
  az acr repository show --name "$ACR_NAME" --image "${AGENTS_IMAGE#*/}" > /dev/null 2>&1 || \
    build "$AGENTS_IMAGE" deploy/Dockerfile
  upsert pm-history-mcp "$AGENTS_IMAGE" 8080 0.5 1Gi PM_SERVICE=mcp
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
    upsert pm-web "$WEB_IMAGE" 80 0.25 0.5Gi AGENTS_UPSTREAM="https://$agents"
  else
    upsert pm-web "$WEB_IMAGE" 80 0.25 0.5Gi
  fi
}

deploy_hello() {
  build "$HELLO_IMAGE" deploy/hello/Dockerfile
  upsert pm-hello "$HELLO_IMAGE" 8000 0.25 0.5Gi
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

urls() {
  for app in pm-web pm-api pm-agents pm-history-mcp pm-hello; do
    local f; f="$(fqdn "$app")"
    [[ -z "$f" ]] && continue
    if [[ "$app" == pm-history-mcp ]]; then echo "$app: https://$f/mcp"; else echo "$app: https://$f"; fi
  done
}

case "$WHAT" in
  api)     ensure_env; echo "api: $(deploy_api)" ;;
  agents)  ensure_env; echo "agents: $(deploy_agents)" ;;
  mcp)     ensure_env; echo "mcp: $(deploy_mcp)/mcp" ;;
  web)     ensure_env; echo "web: $(deploy_web)" ;;
  hello)   ensure_env; echo "hello: $(deploy_hello)" ;;
  foundry) setup_foundry > /dev/null ;;
  urls)    urls ;;
  all)
    ensure_env
    echo "api: $(deploy_api)"
    echo "agents: $(deploy_agents)"
    echo "mcp: $(deploy_mcp)/mcp"
    echo "web: $(deploy_web)"
    echo
    echo "Smoke test:  ./deploy/smoke.sh"
    ;;
  *) echo "unknown target: $WHAT (all|api|agents|mcp|web|hello|urls|foundry)" >&2; exit 2 ;;
esac
