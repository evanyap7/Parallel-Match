"""Agents service (FastAPI).

Endpoints (all POST bodies are JSON):

- GET  /health                     -> service + provider + season status
- POST /narrate                    {fork_response, match_id?}
- POST /explain                    {match_id, event_id}
- POST /precedents                 {match_id, event_id, fork_response?}
                                   (fetched through the MCP server when
                                   PM_HISTORY_MCP_URL is set; `source` says)
- POST /parse                      {text, match_id, event_id}

Matches are the real 90-match season (parallel_match/data/season.json,
replayed once at startup). Precedent numbers come from history_for(), the
same source as the `history` block of POST /fork. Pass the fork response to
/precedents to get the simulation's estimate alongside and the
`agrees_with_simulation` flag for the "these disagree" card.

Run:  PM_AGENT_BACKEND=template uvicorn agents.server:app --port 8001
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import history_client, historian, intervention, law_explainer, narrator
from .provider import get_provider, provider_error
from mcp_history import HistoryStore, default_store
from mcp_history.precedent import compare_with_simulation, source


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    default_store()   # replay the season before taking traffic
    get_provider()    # build (or fall back from) the model provider once
    yield


app = FastAPI(title="Parallel Match agents", version="0.2.0", lifespan=_lifespan)

# The hosted front end calls this API from another origin. Comma-separated
# list; "*" (default) is fine: no cookies or credentials are used.
_origins = [o.strip() for o in os.environ.get("PM_CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"])


def _store() -> HistoryStore:
    return default_store()


def _match_or_404(store: HistoryStore, match_id: str) -> dict:
    match = store.match(match_id)
    if match is None:
        raise HTTPException(404, f"match '{match_id}' not found")
    return match


def _event_or_404(store: HistoryStore, match_id: str, event_id: str):
    _match_or_404(store, match_id)
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
    fork_response: dict | None = None
    limit: int | None = None   # accepted for backward compatibility; unused


class ParseBody(EventBody):
    text: str


@app.get("/health")
def health():
    store = _store()
    provider = get_provider()
    configured = os.environ.get("PM_AGENT_BACKEND", "template")
    return {
        "status": "ok",
        "backend_configured": configured,
        "provider": provider.name,
        "provider_error": provider_error(),
        "model": getattr(provider, "model", None),
        "model_last_error": getattr(provider, "last_error", None),
        "precedent_source": source(),
        "history_mcp": history_client.status(),
        "season": store.season_summary(),
    }


@app.post("/narrate")
def narrate(body: NarrateBody):
    store = _store()
    fork = body.fork_response
    match_id = (body.match_id or fork.get("match_id")
                or (fork.get("request") or {}).get("match_id") or "")
    return narrator.run(fork, store.match(match_id), get_provider())


@app.post("/explain")
def explain(body: EventBody):
    store = _store()
    event, _index = _event_or_404(store, body.match_id, body.event_id)
    return law_explainer.run(store.match(body.match_id), event, get_provider())


@app.post("/precedents")
def precedents(body: PrecedentsBody):
    store = _store()
    event, _index = _event_or_404(store, body.match_id, body.event_id)
    block, via = history_client.precedent(body.match_id, body.event_id)
    if block is None:
        raise HTTPException(404, "moment is not a contestable call (foul or offside decision)")
    fork = body.fork_response
    if fork and (fork.get("match_id"), fork.get("event_id")) not in (
            (body.match_id, body.event_id), (None, None)):
        raise HTTPException(422, "fork_response is for a different moment")
    if fork is not None and "match" not in fork:
        fork = {**fork, "match": store.match(body.match_id)}
    block = compare_with_simulation(block, fork)
    result = historian.run(store.match(body.match_id), event, block, get_provider())
    result["source"] = via   # "mcp" (via pm-history-mcp) or "in-process" fallback
    return result


@app.post("/parse")
def parse(body: ParseBody):
    store = _store()
    match = _match_or_404(store, body.match_id)
    return intervention.parse_and_validate(body.text, match, body.event_id)
