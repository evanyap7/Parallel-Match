"""Agents service (FastAPI).

Endpoints (all POST bodies are JSON):

- GET  /health                     -> service + provider + season status
- POST /narrate                    {fork_response, match_id?}
- POST /explain                    {match_id, event_id}
- POST /precedents                 {match_id, event_id, fork_response?}
                                   (fetched through the MCP server when
                                   PM_HISTORY_MCP_URL is set; `source` says)
- POST /parse                      {text, match_id, event_id}
- POST /desk                       {fork_response, match_id?} - the Match Desk:
                                   every agent on one moment, fact-checked
                                   through tools, with a trace (agents/desk.py)

Matches are the real 90-match season (parallel_match/data/season.json,
replayed once at startup). Precedent numbers come from history_for(), the
same source as the `history` block of POST /fork. Pass the fork response to
/precedents to get the simulation's estimate alongside and the
`agrees_with_simulation` flag for the "these disagree" card.

Run:  PM_AGENT_BACKEND=template uvicorn agents.server:app --port 8001
"""

from __future__ import annotations

import glob
import json
import logging
import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import cache, desk, history_client, historian, intervention, law_explainer, narrator, translate
from .facts import fork_facts
from .provider import TemplateProvider, get_provider, provider_error
from mcp_history import HistoryStore, default_store
from mcp_history.precedent import compare_with_simulation, source


log = logging.getLogger("agents")
FIXTURES_DIR = os.environ.get("PM_FIXTURES_DIR", os.path.join(os.path.dirname(__file__), "..", "fixtures"))


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    default_store()   # replay the season before taking traffic
    get_provider()    # build (or fall back from) the model provider once
    if os.environ.get("PM_WARM", "1") == "1":
        threading.Thread(target=_warm, name="warm-cache", daemon=True).start()
    yield


def _warm() -> None:
    """Answer the featured moments once in the background, so the first judge
    to tap them gets a cached answer. Failures are fine: nothing is cached."""
    time.sleep(float(os.environ.get("PM_WARM_DELAY_S", "20")))  # let MCP come up
    for path in sorted(glob.glob(os.path.join(FIXTURES_DIR, "fork_*.json"))):
        try:
            with open(path) as fh:
                fork = json.load(fh)
            mid, eid = fork.get("match_id"), fork.get("event_id")
            narrate(NarrateBody(fork_response=fork, match_id=mid))
            explain(EventBody(match_id=mid, event_id=eid))
            precedents(PrecedentsBody(match_id=mid, event_id=eid, fork_response=fork))
            precedents(PrecedentsBody(match_id=mid, event_id=eid))
            run_desk(NarrateBody(fork_response=fork, match_id=mid))
        except Exception as exc:  # pragma: no cover - best effort
            log.warning("warm-up skipped %s: %s", path, exc)


def _model_backend() -> bool:
    return not isinstance(get_provider(), TemplateProvider)


def _cacheable(result: dict) -> bool:
    if result.get("fell_back") and _model_backend():
        return False   # model failed: retry once it is back
    if result.get("lang", "en") != "en" and not result.get("translated") and _model_backend():
        return False   # translation failed: retry
    if result.get("source") == "in-process" and history_client.MCP_URL:
        return False   # MCP was skipped: retry through MCP
    return True


def _cached(k: str, compute) -> dict:
    hit = cache.get(k)
    if hit is not None:
        return {**hit, "cached": True}
    result = compute()
    if _cacheable(result):
        cache.put(k, result)
    return {**result, "cached": False}


app = FastAPI(title="Parallel Match agents", version="0.2.0", lifespan=_lifespan)

# The hosted front end calls this API from another origin. Comma-separated
# list; "*" (default) is fine: no cookies or credentials are used.
_origins = [o.strip() for o in os.environ.get("PM_CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"],
                   expose_headers=["Server-Timing"])


@app.middleware("http")
async def _timing(request: Request, call_next):
    """Server-Timing header on every response, to see where time goes."""
    t0 = time.perf_counter()
    response = await call_next(request)
    response.headers["Server-Timing"] = f"app;dur={(time.perf_counter() - t0) * 1000:.0f}"
    return response


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
    lang: str = "en"    # one of translate.LANGUAGES; unknown means English


class EventBody(BaseModel):
    match_id: str
    event_id: str
    lang: str = "en"


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
        "release": os.environ.get("PM_RELEASE"),
        "backend_configured": configured,
        "provider": provider.name,
        "provider_error": provider_error(),
        "model": getattr(provider, "model", None),
        "model_last_error": getattr(provider, "last_error", None),
        "precedent_source": source(),
        "history_mcp": history_client.status(),
        "cache": cache.stats(),
        "season": store.season_summary(),
    }


@app.post("/narrate")
def narrate(body: NarrateBody):
    store = _store()
    fork = body.fork_response
    match_id = (body.match_id or fork.get("match_id")
                or (fork.get("request") or {}).get("match_id") or "")
    facts = fork_facts(fork)
    lang = translate.norm_lang(body.lang)
    return _cached(cache.key("narrate", match_id, facts, lang),
                   lambda: narrator.run(fork, store.match(match_id), get_provider(), lang))


@app.post("/explain")
def explain(body: EventBody):
    store = _store()
    event, _index = _event_or_404(store, body.match_id, body.event_id)
    lang = translate.norm_lang(body.lang)
    return _cached(cache.key("explain", body.match_id, body.event_id, lang),
                   lambda: law_explainer.run(store.match(body.match_id), event, get_provider(), lang))


@app.post("/precedents")
def precedents(body: PrecedentsBody):
    store = _store()
    event, _index = _event_or_404(store, body.match_id, body.event_id)
    fork = body.fork_response
    lang = translate.norm_lang(body.lang)
    if fork and (fork.get("match_id"), fork.get("event_id")) not in (
            (body.match_id, body.event_id), (None, None)):
        raise HTTPException(422, "fork_response is for a different moment")
    sim = None
    if fork:
        sim = [(fork.get("history") or {}).get("sim_shift_att_win"), fork.get("outcome_shift")]

    def compute() -> dict:
        block, via = history_client.precedent(body.match_id, body.event_id)
        if block is None:
            raise HTTPException(404, "moment is not a contestable call (foul or offside decision)")
        f = fork
        if f is not None and "match" not in f:
            f = {**f, "match": store.match(body.match_id)}
        result = historian.run(store.match(body.match_id), event,
                               compare_with_simulation(block, f), get_provider(), lang)
        result["source"] = via   # "mcp" (via pm-history-mcp) or "in-process" fallback
        return result

    return _cached(cache.key("precedents", body.match_id, body.event_id, sim, lang), compute)


@app.post("/desk")
def run_desk(body: NarrateBody):
    store = _store()
    fork = body.fork_response
    request = fork.get("request") or {}
    match_id = body.match_id or fork.get("match_id") or request.get("match_id") or ""
    event_id = fork.get("event_id") or request.get("event_id") or ""
    event, _index = _event_or_404(store, match_id, event_id)
    lang = translate.norm_lang(body.lang)

    def compute() -> dict:
        result = desk.run(fork, store.match(match_id), event, get_provider(), lang,
                          history_client.precedent, compare_with_simulation)
        if result["checks"]["precedent_source"]:
            result["source"] = result["checks"]["precedent_source"]
        return result

    return _cached(cache.key("desk", match_id, fork_facts(fork), lang), compute)


@app.post("/parse")
def parse(body: ParseBody):
    store = _store()
    match = _match_or_404(store, body.match_id)
    text = _to_english(body.text, translate.norm_lang(body.lang))
    result = intervention.parse_and_validate(text, match, body.event_id)
    return {**result, "translated_text": text} if text != body.text else result


def _to_english(text: str, lang: str) -> str:
    """A fan's free text in their language, as English for the parser.

    The parser itself stays plain code; the model only translates the
    sentence, and any failure leaves the text as typed."""
    provider = get_provider()
    if lang == "en" or isinstance(provider, TemplateProvider) or not text.strip():
        return text
    try:
        out = provider.complete(translate.to_english_prompt(lang), text[:300]).strip()
    except Exception:
        return text
    return out if 0 < len(out) <= 300 else text
