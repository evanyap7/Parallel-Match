"""Agents service (FastAPI).

Endpoints (all POST bodies are JSON):

- GET  /health                     -> service + provider + season status
- POST /narrate                    {fork_response, match_id?}
- POST /explain                    {match_id, event_id}
- POST /precedents                 {match_id, event_id, limit?}
- POST /parse                      {text, match_id, event_id}

Matches come from the local fixture/history directories (the shared contract
fixture first). When Evan's match API is live, PM_FIXTURES_DIR points at the
exported season and nothing else changes: the agents only read match JSON.

Run:  PM_AGENT_BACKEND=template uvicorn agents.server:app --port 8001
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from . import historian, intervention, law_explainer, narrator
from .provider import get_provider
from mcp_history import HistoryStore, default_store

FIXTURES_DIR = os.environ.get("PM_FIXTURES_DIR", "fixtures")
HISTORY_DIR = os.environ.get("PM_HISTORY_DIR", "data/dev_season")

app = FastAPI(title="Parallel Match agents", version="0.1.0")


def _store() -> HistoryStore:
    return default_store(FIXTURES_DIR, HISTORY_DIR)


def _event_or_404(store: HistoryStore, match_id: str, event_id: str):
    found = store.event(match_id, event_id)
    if found is None:
        raise HTTPException(404, f"event '{event_id}' not found in match '{match_id}'")
    return found


class NarrateBody(BaseModel):
    fork_response: dict
    match_id: str | None = None


class EventBody(BaseModel):
    match_id: str
    event_id: str


class PrecedentsBody(EventBody):
    limit: int = 8


class ParseBody(EventBody):
    text: str


@app.get("/health")
def health():
    store = _store()
    try:
        provider = get_provider()
        provider_name, error = provider.name, None
    except Exception as exc:  # unconfigured foundry: report, stay up on template
        provider_name, error = "template (foundry misconfigured)", str(exc)
    return {
        "status": "ok",
        "provider": provider_name,
        "provider_error": error,
        "season": store.season_summary(),
    }


@app.post("/narrate")
def narrate(body: NarrateBody):
    store = _store()
    match = store.match(body.match_id or body.fork_response.get("request", {}).get("match_id", ""))
    result = narrator.run(body.fork_response, match, get_provider())
    return result


@app.post("/explain")
def explain(body: EventBody):
    store = _store()
    event, _index = _event_or_404(store, body.match_id, body.event_id)
    return law_explainer.run(store.match(body.match_id), event, get_provider())


@app.post("/precedents")
def precedents(body: PrecedentsBody):
    store = _store()
    event, _index = _event_or_404(store, body.match_id, body.event_id)
    result = store.query(body.match_id, body.event_id, limit=body.limit)
    if result is None:
        raise HTTPException(404, "moment is not a contestable family event")
    return historian.run(store.match(body.match_id), event, result, get_provider())


@app.post("/parse")
def parse(body: ParseBody):
    store = _store()
    match = store.match(body.match_id)
    if match is None:
        raise HTTPException(404, f"match '{body.match_id}' not found")
    return intervention.parse_and_validate(body.text, match, body.event_id)
