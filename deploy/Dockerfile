# Parallel Match agents + MCP history image.
# One image, two services (PM_SERVICE selects):
#   PM_SERVICE=api  -> uvicorn agents.server:app        (agents REST API)
#   PM_SERVICE=mcp  -> python -m mcp_history.server      (MCP, streamable-http)
FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY parallel_match ./parallel_match
COPY agents ./agents
COPY mcp_history ./mcp_history
COPY fixtures ./fixtures
COPY data ./data

RUN pip install --no-cache-dir ".[agents,mcp]"

ENV PM_FIXTURES_DIR=/app/fixtures \
    PM_HISTORY_DIR=/app/data/dev_season \
    PM_SERVICE=api \
    PORT=8000

EXPOSE 8000 8080

CMD ["sh", "-c", "if [ \"$PM_SERVICE\" = \"mcp\" ]; then PM_MCP_HTTP=1 exec python -m mcp_history.server; else exec uvicorn agents.server:app --host 0.0.0.0 --port ${PORT:-8000}; fi"]
