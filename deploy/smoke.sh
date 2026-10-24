#!/usr/bin/env bash
# End-to-end smoke test of the deployed (or local) services.
#
#   ./deploy/smoke.sh                 # URLs from Azure (az containerapp show)
#   API=http://localhost:8000 AGENTS=http://localhost:8001 \
#     MCP=http://localhost:8080 WEB= ./deploy/smoke.sh      # local run
#
# Checks: health of every service, the featured m052 penalty fork is cached,
# the Historian gives the same precedent count as the fork, the narrator
# phrases rollout shares, and the MCP server answers an initialize call.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
if [[ -f .env ]]; then set -a; source .env; set +a; fi

url_of() {
  local f
  f="$(az containerapp show -n "$1" -g "${AZURE_RESOURCE_GROUP:?}" \
        --query properties.configuration.ingress.fqdn -o tsv 2>/dev/null)"
  [[ -n "$f" ]] && echo "https://$f"
}
API="${API-$(url_of pm-api)}"
AGENTS="${AGENTS-$(url_of pm-agents)}"
MCP="${MCP-$(url_of pm-history-mcp)}"
WEB="${WEB-$(url_of pm-web)}"

PY="$(command -v python3 || command -v python)"
fail=0
ok()  { echo "  ok    $*"; }
bad() { echo "  FAIL  $*"; fail=1; }
json() { "$PY" -c "import json,sys; d=json.load(sys.stdin); print($1)"; }

echo "api:    ${API:-<none>}"
echo "agents: ${AGENTS:-<none>}"
echo "mcp:    ${MCP:-<none>}"
echo "web:    ${WEB:-<none>}"

if [[ -n "$API" ]]; then
  curl -fsS "$API/health" > /dev/null && ok "api /health" || bad "api /health"
  fork="$(curl -fsS -X POST "$API/fork" -H 'content-type: application/json' \
    -d '{"match_id":"m052","event_id":"m052-0715","change":{"type":"flip_call"}}')" \
    || bad "api POST /fork m052 penalty"
  if [[ -n "${fork:-}" ]]; then
    [[ "$(echo "$fork" | json 'd["cached"]')" == "True" ]] \
      && ok "m052 penalty fork is cached" || bad "m052 penalty fork not cached"
  fi
fi

if [[ -n "$AGENTS" ]]; then
  health="$(curl -fsS "$AGENTS/health")" && ok "agents /health: provider $(echo "$health" | json 'd["provider"]'), $(echo "$health" | json 'd["season"]["matches"]') matches" \
    || bad "agents /health"
  err="$(echo "${health:-{}}" | json 'd.get("provider_error") or ""' 2>/dev/null)"
  [[ -n "$err" ]] && echo "        provider_error: $err"
  if [[ -n "${fork:-}" ]]; then
    body="$("$PY" -c 'import json,sys; print(json.dumps({"match_id":"m052","event_id":"m052-0715","fork_response":json.loads(sys.argv[1])}))' "$fork")"
    prec="$(curl -fsS -X POST "$AGENTS/precedents" -H 'content-type: application/json' -d "$body")" \
      || bad "agents /precedents"
    if [[ -n "${prec:-}" ]]; then
      a="$(echo "$prec" | json 'd["history"]["n"]')"; b="$(echo "$fork" | json 'd["history"]["n"]')"
      [[ "$a" == "$b" ]] && ok "Historian and /fork agree on precedent n=$a" || bad "Historian n=$a but /fork n=$b"
      via="$(echo "$prec" | json 'd.get("source")')"
      [[ "$via" == "mcp" ]] && ok "Historian fetched precedent via MCP" \
        || bad "Historian used '$via', not MCP (see /health history_mcp.mcp_last_error)"
    fi
    narr="$(curl -fsS -X POST "$AGENTS/narrate" -H 'content-type: application/json' \
      -d "$("$PY" -c 'import json,sys; print(json.dumps({"fork_response":json.loads(sys.argv[1])}))' "$fork")")" \
      || bad "agents /narrate"
    if [[ -n "${narr:-}" ]]; then
      verdict="$(echo "$narr" | json '[s["text"] for s in d["script"] if s["timeline"]=="verdict"][0]')"
      [[ "$verdict" == *"0% instead of 0%"* ]] && bad "narrator: $verdict" || ok "narrator: ${verdict:0:110}..."
    fi
  fi
  curl -fsS -X POST "$AGENTS/explain" -H 'content-type: application/json' \
    -d '{"match_id":"m052","event_id":"m052-0715"}' > /dev/null && ok "agents /explain" || bad "agents /explain"
fi

if [[ -n "$MCP" ]]; then
  init='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"smoke","version":"1"}}}'
  curl -fsS -X POST "$MCP/mcp" -H 'content-type: application/json' \
    -H 'accept: application/json, text/event-stream' -d "$init" | grep -q 'parallel-match-history' \
    && ok "mcp initialize" || bad "mcp initialize at $MCP/mcp"
fi

if [[ -n "$WEB" ]]; then
  curl -fsS "$WEB/" | grep -qi '<div id="root"' && ok "web serves the app" || bad "web /"
fi

exit $fail
