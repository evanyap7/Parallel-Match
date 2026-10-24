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
# Sized for an Azure for Students subscription ($100 credit): about $2.5 a day
# with all four apps kept warm; see docs/deployment.md "Cost".
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
IDENTITY_NAME="${PM_IDENTITY:-pm-identity}"   # user-assigned: image pulls + Foundry
BUILDER="${PM_BUILDER:-docker}"               # docker (local buildx) | acr (ACR Tasks)
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
  # Exact match: "NotRegistered" and "Registering" must not count as done.
  local state
  state="$(az provider show -n "$1" --query registrationState -o tsv 2>/dev/null || true)"
  if [[ "$state" != "Registered" ]]; then
    log "registering $1 (once, can take a few minutes)"
    az provider register -n "$1" --wait > /dev/null
  fi
}

# One-time: resource group, Basic registry, Container Apps environment.
# Logs go to the console stream only (no Log Analytics workspace to pay for);
# read them with: az containerapp logs show -n <app> -g <rg> --follow
setup() {
  for ns in Microsoft.App Microsoft.ContainerRegistry Microsoft.CognitiveServices Microsoft.ManagedIdentity; do register "$ns"; done
  az group show -n "$RESOURCE_GROUP" > /dev/null 2>&1 || {
    log "creating resource group $RESOURCE_GROUP in $LOCATION"
    az group create -n "$RESOURCE_GROUP" -l "$LOCATION" > /dev/null
  }
  az acr show -n "$ACR_NAME" > /dev/null 2>&1 || {
    log "creating registry $ACR_NAME (Basic)"
    az acr create -n "$ACR_NAME" -g "$RESOURCE_GROUP" -l "$LOCATION" --sku Basic > /dev/null
  }
  ensure_identity
  ensure_env
}

# One user-assigned identity for every app. Express environments (and Azure
# for Students ones can be express) do not support system-assigned identities;
# a user-assigned one works in both express and standard environments.
ensure_identity() {
  az identity show -n "$IDENTITY_NAME" -g "$RESOURCE_GROUP" > /dev/null 2>&1 || {
    log "creating managed identity $IDENTITY_NAME"
    az identity create -n "$IDENTITY_NAME" -g "$RESOURCE_GROUP" -l "$LOCATION" > /dev/null
  }
  IDENTITY_ID="$(az identity show -n "$IDENTITY_NAME" -g "$RESOURCE_GROUP" --query id -o tsv)"
  IDENTITY_CLIENT_ID="$(az identity show -n "$IDENTITY_NAME" -g "$RESOURCE_GROUP" --query clientId -o tsv)"
  IDENTITY_PRINCIPAL="$(az identity show -n "$IDENTITY_NAME" -g "$RESOURCE_GROUP" --query principalId -o tsv)"
  grant "$IDENTITY_PRINCIPAL" AcrPull "$(az acr show -n "$ACR_NAME" --query id -o tsv)"
}

# grant PRINCIPAL ROLE SCOPE (idempotent; tolerates "already exists")
grant() {
  local have
  have="$(az role assignment list --assignee "$1" --role "$2" --scope "$3" --query "length(@)" -o tsv 2>/dev/null || echo 0)"
  if [[ "$have" == "0" || -z "$have" ]]; then
    log "granting $2 to $IDENTITY_NAME"
    for _ in 1 2 3 4 5 6; do   # a new identity can take a minute to replicate
      if az role assignment create --assignee-object-id "$1" --assignee-principal-type ServicePrincipal \
           --role "$2" --scope "$3" > /dev/null 2>"${TMPDIR:-/tmp}/pm-grant.err"; then return 0; fi
      sleep 10
    done
    echo "could not grant $2 on $3:" >&2
    tail -3 "${TMPDIR:-/tmp}/pm-grant.err" >&2
    return 1
  fi
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
# Azure for Students blocks ACR Tasks (TasksOperationsNotAllowed), so the
# default is a local Docker build for linux/amd64 (Container Apps runs amd64,
# including from Apple Silicon Macs) pushed straight to the registry.
build() {
  local image="$1" dockerfile="$2"; shift 2
  log "building ${image##*/} from $dockerfile ($BUILDER)"
  if [[ "$BUILDER" == "acr" ]]; then
    az acr build --registry "$ACR_NAME" --image "${image#*/}" --file "$dockerfile" "$@" . > /dev/null
  else
    docker buildx build --platform linux/amd64 --file "$dockerfile" --tag "$image" \
      --push --progress plain "$@" . > "${TMPDIR:-/tmp}/pm-build-${image##*/}.log" 2>&1 || {
      tail -40 "${TMPDIR:-/tmp}/pm-build-${image##*/}.log" >&2
      echo "build failed: full log in ${TMPDIR:-/tmp}/pm-build-${image##*/}.log" >&2
      return 1
    }
  fi
}

docker_login() {
  [[ "$BUILDER" == "acr" ]] && return 0
  command -v docker > /dev/null || { echo "Docker is needed to build images (PM_BUILDER=docker): install Docker Desktop and start it" >&2; exit 1; }
  docker info > /dev/null 2>&1 || { echo "Docker is installed but not running: start Docker Desktop" >&2; exit 1; }
  docker buildx version > /dev/null 2>&1 || { echo "docker buildx is missing: update Docker Desktop, or with Colima: brew install docker-buildx and link it into ~/.docker/cli-plugins (see docs/deployment.md)" >&2; exit 1; }
  az acr login -n "$ACR_NAME" > /dev/null
}

exists() { az containerapp show -n "$1" -g "$RESOURCE_GROUP" > /dev/null 2>&1; }

fqdn() {
  az containerapp show -n "$1" -g "$RESOURCE_GROUP" \
    --query properties.configuration.ingress.fqdn -o tsv 2>/dev/null || true
}

# upsert NAME IMAGE PORT CPU MEMORY MIN MAX [ENV=VAR ...]
# Creates the app the first time; afterwards rolls a new revision. Either way
# the app pulls with the user-assigned identity.
upsert() {
  local name="$1" image="$2" port="$3" cpu="$4" mem="$5" min="$6" max="$7"; shift 7
  local scale=(--cpu "$cpu" --memory "$mem" --min-replicas "$min" --max-replicas "$max")
  set -- "$@" PM_RELEASE="$IMAGE_TAG"   # each deploy is visibly a new release
  if exists "$name"; then
    # Apps left by a failed first deploy can carry a system-assigned identity,
    # which express environments refuse on every update: recreate those.
    local idtype prov
    idtype="$(az containerapp show -n "$name" -g "$RESOURCE_GROUP" --query identity.type -o tsv 2>/dev/null || true)"
    prov="$(az containerapp show -n "$name" -g "$RESOURCE_GROUP" --query properties.provisioningState -o tsv 2>/dev/null || true)"
    if [[ "$idtype" == *SystemAssigned* || "$prov" == Failed ]]; then
      log "recreating $name (left over from an earlier failed deploy)"
      az containerapp delete -n "$name" -g "$RESOURCE_GROUP" --yes > /dev/null || return 1
    fi
  fi
  if exists "$name"; then
    log "updating $name"
    az containerapp identity assign -n "$name" -g "$RESOURCE_GROUP" --user-assigned "$IDENTITY_ID" > /dev/null || return 1
    az containerapp registry set -n "$name" -g "$RESOURCE_GROUP" --server "$ACR_SERVER" \
      --identity "$IDENTITY_ID" > /dev/null || return 1
    local env_args=()
    if (($#)); then env_args=(--set-env-vars "$@"); fi
    az containerapp update -n "$name" -g "$RESOURCE_GROUP" --image "$image" "${scale[@]}" \
      ${env_args[@]+"${env_args[@]}"} > /dev/null || return 1
  else
    log "creating $name"
    local env_args=()
    if (($#)); then env_args=(--env-vars "$@"); fi
    az containerapp create -n "$name" -g "$RESOURCE_GROUP" --environment "$ENV_NAME" \
      --image "$image" --target-port "$port" --ingress external \
      --user-assigned "$IDENTITY_ID" \
      --registry-server "$ACR_SERVER" --registry-identity "$IDENTITY_ID" "${scale[@]}" \
      ${env_args[@]+"${env_args[@]}"} > /dev/null || return 1
  fi
  local url; url="https://$(fqdn "$name")"
  echo "$url"
}

# Judging sizes. Featured forks are precomputed (~1 s); an uncached fork took
# ~25 s live on 1 vCPU, so the API gets 2 (rollouts run in a process pool).
# The agents service needs ~140 MB.
#        app             cpu   memory  min              max
SIZE_API=(2.0 4Gi "$MIN_REPLICAS" 2)
SIZE_AGENTS=(0.5 1Gi "$MIN_REPLICAS" 2)
SIZE_WEB=(0.25 0.5Gi "$MIN_REPLICAS" 2)
SIZE_MCP=(0.25 0.5Gi "$MIN_REPLICAS" 1)   # the Historian calls it on every card

deploy_api() {          # simulator API: forks run rollouts in a process pool
  build "$API_IMAGE" Dockerfile || return 1
  upsert pm-api "$API_IMAGE" 8000 "${SIZE_API[@]}"
}

deploy_agents() {
  build "$AGENTS_IMAGE" deploy/Dockerfile || return 1
  AGENTS_BUILT=1
  upsert pm-agents "$AGENTS_IMAGE" 8000 "${SIZE_AGENTS[@]}" \
    PM_SERVICE=api PM_AGENT_BACKEND="$BACKEND" AZURE_CLIENT_ID="$IDENTITY_CLIENT_ID" \
    AZURE_AI_FOUNDRY_PROJECT_ENDPOINT="${AZURE_AI_FOUNDRY_PROJECT_ENDPOINT:-}" \
    AZURE_AI_FOUNDRY_MODEL="${AZURE_AI_FOUNDRY_MODEL:-gpt-4.1-mini}" \
    PM_HISTORY_MCP_URL="$(mcp_url)"
  if [[ "$BACKEND" == "foundry" ]]; then setup_foundry; fi
}

deploy_mcp() {
  # Same image as the agents; build only if this run has not built it.
  if [[ -z "${AGENTS_BUILT:-}" ]] && ! az acr repository show --name "$ACR_NAME" \
      --image "${AGENTS_IMAGE#*/}" > /dev/null 2>&1; then
    build "$AGENTS_IMAGE" deploy/Dockerfile || return 1
  fi
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
    --build-arg "VITE_API_BASE_URL=https://$api" || return 1
  if [[ -n "$agents" ]]; then
    upsert pm-web "$WEB_IMAGE" 80 "${SIZE_WEB[@]}" AGENTS_UPSTREAM="https://$agents"
  else
    upsert pm-web "$WEB_IMAGE" 80 "${SIZE_WEB[@]}"
  fi
}

deploy_hello() {
  build "$HELLO_IMAGE" deploy/hello/Dockerfile || return 1
  upsert pm-hello "$HELLO_IMAGE" 8000 0.25 0.5Gi 0 1
}

# The MCP server's URL, known before it exists: apps get <name>.<env domain>.
# Express environments do not restart a running replica when only env vars
# change, so the agents get this at deploy time together with their image.
mcp_url() {
  local domain
  domain="$(az containerapp env show -n "$ENV_NAME" -g "$RESOURCE_GROUP" --query properties.defaultDomain -o tsv)"
  [[ -n "$domain" ]] && echo "https://pm-history-mcp.$domain/mcp"
}

# Foundry access: grant the user-assigned identity "Azure AI User" on the
# Foundry resource; the agents use it via AZURE_CLIENT_ID. Needs Owner (or
# User Access Administrator) there, which an Azure for Students owner has.
setup_foundry() {
  if [[ -n "${AZURE_AI_FOUNDRY_RESOURCE_ID:-}" ]]; then
    # "Azure AI User" is the Foundry role, but not every tenant has it. On the
    # student tenant, calls through the project endpoint returned 403 with only
    # "Cognitive Services OpenAI User"; "Cognitive Services User" covers them.
    # All roles are scoped to this one Foundry resource. New grants can take
    # 5-10 minutes to apply (403 until then; the agents use templates meanwhile).
    local role granted=0
    for role in "Azure AI User" "Cognitive Services OpenAI User" "Cognitive Services User"; do
      if az role definition list --name "$role" --query "[0].name" -o tsv 2>/dev/null | grep -q .; then
        grant "$IDENTITY_PRINCIPAL" "$role" "$AZURE_AI_FOUNDRY_RESOURCE_ID" && granted=1
      fi
    done
    [[ "$granted" == 1 ]] || { echo "could not grant a Foundry role to $IDENTITY_NAME; see docs/deployment.md section 3" >&2; return 1; }
  else
    log "set AZURE_AI_FOUNDRY_RESOURCE_ID to grant access automatically, or in the portal:"
    log "  Foundry resource > Access control (IAM) > Add role assignment >"
    log "  Cognitive Services OpenAI User > Managed identity > $IDENTITY_NAME"
  fi
}

# Foundry resource + project + model deployment, all from the CLI. Prints the
# three .env lines the agents need. If a step fails (CLI too old, no quota for
# the model in this region), do that step in the portal at ai.azure.com.
foundry_create() {
  local name="${FOUNDRY_NAME:-${ACR_NAME}-ai}" project="${FOUNDRY_PROJECT:-pm-project}"
  local model="${FOUNDRY_MODEL:-}" version="${FOUNDRY_MODEL_VERSION:-}"
  if [[ -n "$version" && -z "$model" ]]; then echo "FOUNDRY_MODEL_VERSION needs FOUNDRY_MODEL" >&2; exit 1; fi
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
    # First model in the preference list that this region offers as
    # GlobalStandard and that is not being retired (e.g. gpt-4o-mini
    # 2024-07-18 is "deprecating" and refuses new deployments). Fast,
    # non-reasoning models first: the agents give each call 8 s.
    local candidate
    for candidate in ${FOUNDRY_MODEL:-gpt-4.1-mini gpt-4.1-nano gpt-5-mini gpt-5-nano gpt-4o-mini}; do
      version="$(az cognitiveservices account list-models -n "$name" -g "$RESOURCE_GROUP" \
        --query "[?name=='$candidate' && format=='OpenAI' && lifecycleStatus!='Deprecating' && lifecycleStatus!='Deprecated' && skus[?name=='GlobalStandard']].version | sort(@) | [-1]" \
        -o tsv 2>/dev/null)"
      if [[ -n "$version" ]]; then model="$candidate"; break; fi
    done
  fi
  [[ -n "$version" ]] || { echo "no current model found in $LOCATION; list them with: az cognitiveservices account list-models -n $name -g $RESOURCE_GROUP -o table" >&2; exit 1; }
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

prepare() { ensure_env; ensure_identity; docker_login; }

case "$WHAT" in
  setup)   setup; echo "setup done: ./deploy/deploy.sh to deploy" ;;
  foundry-create) foundry_create ;;
  foundry) ensure_identity; setup_foundry ;;
  pause)   scale_all 0 0 0 ;;
  resume)  scale_all "${SIZE_WEB[2]}" "${SIZE_API[2]}" "${SIZE_AGENTS[2]}" ;;
  teardown)
    read -r -p "Delete resource group $RESOURCE_GROUP and everything in it? Type its name: " ans
    [[ "$ans" == "$RESOURCE_GROUP" ]] || { echo "cancelled"; exit 1; }
    az group delete -n "$RESOURCE_GROUP" --yes --no-wait; echo "deleting $RESOURCE_GROUP" ;;
  api)     prepare; u=$(deploy_api);    echo "api: $u" ;;
  agents)  prepare; u=$(deploy_agents); echo "agents: $u" ;;
  mcp)     prepare; u=$(deploy_mcp);    echo "mcp: $u/mcp" ;;
  web)     prepare; u=$(deploy_web);    echo "web: $u" ;;
  hello)   prepare; u=$(deploy_hello);  echo "hello: $u" ;;
  urls)    urls ;;
  all)
    setup; docker_login
    u=$(deploy_api);    echo "api: $u"
    u=$(deploy_agents); echo "agents: $u"
    AGENTS_BUILT=1
    u=$(deploy_mcp);    echo "mcp: $u/mcp"
    u=$(deploy_web);    echo "web: $u"
    echo
    echo "Smoke test:  ./deploy/smoke.sh"
    ;;
  *) echo "unknown target: $WHAT (setup|all|api|agents|mcp|web|hello|urls|foundry|foundry-create|pause|resume|teardown)" >&2; exit 2 ;;
esac
