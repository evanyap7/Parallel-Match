#!/usr/bin/env bash
# Deploy the agents API and the MCP history server to Azure Container Apps.
#
# One image, two apps:
#   pm-agents      PM_SERVICE=api  public ingress   (agents REST API)
#   pm-history-mcp PM_SERVICE=mcp  public ingress   (MCP over streamable-http)
#
# Usage:
#   ./deploy/deploy.sh                     # build + deploy both apps
#   ./deploy/deploy.sh hello               # just the hello-world smoke app
#   ./deploy/deploy.sh agents              # build + deploy pm-agents only
#   ./deploy/deploy.sh mcp                 # build + deploy pm-history-mcp only
#
# Required environment (see docs/deployment.md and .env.example):
#   AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP, AZURE_LOCATION,
#   AZURE_CONTAINER_REGISTRY (e.g. pmdugoutacr.azurecr.io)
# Optional:
#   AZURE_AI_FOUNDRY_PROJECT_ENDPOINT, AZURE_AI_FOUNDRY_MODEL,
#   PM_AGENT_BACKEND (template | foundry)

set -euo pipefail

WHAT="${1:-all}"
SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:?set AZURE_SUBSCRIPTION_ID}"
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:?set AZURE_RESOURCE_GROUP}"
LOCATION="${AZURE_LOCATION:?set AZURE_LOCATION}"
ACR="${AZURE_CONTAINER_REGISTRY:?set AZURE_CONTAINER_REGISTRY}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"
IMAGE="${ACR}/the-home-dugout:${IMAGE_TAG}"
HELLO_IMAGE="${ACR}/the-home-dugout-hello:${IMAGE_TAG}"

az account show --query name -o tsv > /dev/null || az login
az account set --subscription "$SUBSCRIPTION_ID"

ensure_env() {
  az provider show -n Microsoft.App --query "registrationState" -o tsv 2>/dev/null | grep -q Registered || \
    az provider register -n Microsoft.App
  az containerapp env show -n pm-env -g "$RESOURCE_GROUP" > /dev/null 2>&1 || \
    az containerapp env create -n pm-env -g "$RESOURCE_GROUP" --location "$LOCATION"
}

build() {
  echo "==> building $1"
  az acr build --registry "$ACR" --image "$1" "$(dirname "$0")/.." > /dev/null
}

deploy_hello() {
  build "$HELLO_IMAGE"
  az containerapp create -n pm-hello -g "$RESOURCE_GROUP" \
    --image "$HELLO_IMAGE" --environment pm-env --target-port 8000 --ingress external \
    --query properties.configuration.ingress.fqdn -o tsv
}

deploy_service() {  # $1 name, $2 PM_SERVICE, $3 target port
  build "$IMAGE"
  az containerapp create -n "$1" -g "$RESOURCE_GROUP" \
    --image "$IMAGE" --environment pm-env --target-port "$3" --ingress external \
    --env-vars PM_SERVICE="$2" PM_AGENT_BACKEND="${PM_AGENT_BACKEND:-template}" \
      AZURE_AI_FOUNDRY_PROJECT_ENDPOINT="${AZURE_AI_FOUNDRY_PROJECT_ENDPOINT:-}" \
      AZURE_AI_FOUNDRY_MODEL="${AZURE_AI_FOUNDRY_MODEL:-}" \
    --query properties.configuration.ingress.fqdn -o tsv
  # Managed identity for Foundry (DefaultAzureCredential) when the backend is foundry:
  #   az containerapp identity assign -n "$1" -g "$RESOURCE_GROUP" --system-assigned
  # then grant the identity access to the Foundry project in the Azure portal.
}

case "$WHAT" in
  hello) ensure_env; FQDN=$(deploy_hello); echo "hello: https://$FQDN" ;;
  agents) ensure_env; FQDN=$(deploy_service pm-agents api 8000); echo "agents: https://$FQDN" ;;
  mcp) ensure_env; FQDN=$(deploy_service pm-history-mcp mcp 8080); echo "mcp: https://$FQDN/mcp" ;;
  all)
    ensure_env
    FQDN=$(deploy_service pm-agents api 8000); echo "agents: https://$FQDN"
    FQDN=$(deploy_service pm-history-mcp mcp 8080); echo "mcp: https://$FQDN/mcp"
    ;;
  *) echo "unknown target: $WHAT (hello|agents|mcp|all)" >&2; exit 2 ;;
esac
