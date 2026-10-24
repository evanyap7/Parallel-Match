# Parallel Match agents + MCP history image.
# Build context is the repo root:  az acr build --file deploy/Dockerfile .
# One image, two services (PM_SERVICE selects):
#   PM_SERVICE=api  -> uvicorn agents.server:app        (agents REST API, :8000)
#   PM_SERVICE=mcp  -> python -m mcp_history.server      (MCP streamable-http, :8080/mcp)
# Both read the real 90-match season from parallel_match/data/season.json and
# replay it once at startup (a few seconds).
FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY parallel_match ./parallel_match
COPY agents ./agents
COPY mcp_history ./mcp_history

# foundry extra: Microsoft Agent Framework + azure-identity (managed identity).
# PM_AGENT_BACKEND=template still works with no Azure configuration at all.
RUN pip install --no-cache-dir ".[agents,mcp,foundry]"

ENV PYTHONUNBUFFERED=1 \
    PM_SERVICE=api \
    PORT=8000 \
    PM_MCP_HOST=0.0.0.0 \
    PM_MCP_PORT=8080

EXPOSE 8000 8080

CMD ["sh", "-c", "if [ \"$PM_SERVICE\" = \"mcp\" ]; then PM_MCP_HTTP=1 exec python -m mcp_history.server; else exec uvicorn agents.server:app --host 0.0.0.0 --port ${PORT:-8000}; fi"]
