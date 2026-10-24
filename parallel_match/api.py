"""HTTP API for the front end and the agents.

Run locally:  uvicorn parallel_match.api:app --reload
All responses are synthetic, model-world data.
"""

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import history, season
from .fork import DEFAULT_ROLLOUTS, ForkError, fork, moments
from .teams import build_league, club_by_code

FORK_CACHE = Path(__file__).parent / "data" / "forks"
MAX_ROLLOUTS = 1000

app = FastAPI(title="Parallel Match API", version="0.1.0",
              description="Seeded, forkable football simulator. Synthetic data only.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@lru_cache(maxsize=1)
def _season() -> dict:
    return season.load()


def _fixture(match_id: str) -> dict:
    for m in _season()["matches"]:
        if m["match_id"] == match_id:
            return m
    raise HTTPException(404, f"no match {match_id!r}")


@lru_cache(maxsize=32)
def _record(match_id: str):
    _fixture(match_id)
    return season.record(_season(), match_id)


@lru_cache(maxsize=1)
def _history_rows() -> list[dict]:
    rows = []
    for m in _season()["matches"]:
        rows.extend(history.moment_rows(_record(m["match_id"])))
    return rows


def change_key(change: dict) -> str:
    # flip_call is fully determined by the moment; the agents' parser adds the
    # target call ("no_foul", "onside"), which must not split the cache.
    if change.get("type") == "flip_call":
        change = {"type": "flip_call"}
    return hashlib.sha1(json.dumps(change, sort_keys=True).encode()).hexdigest()[:10]


def cache_path(match_id: str, event_id: str | None, change: dict) -> Path:
    return FORK_CACHE / match_id / f"{event_id or 'kickoff'}__{change_key(change)}.json"


def run_fork(match_id: str, event_id: str | None, change: dict, rollouts: int,
             use_cache: bool = True) -> dict:
    path = cache_path(match_id, event_id, change)
    if use_cache and path.exists():
        cached = json.loads(path.read_text())
        if cached["rollouts"] >= rollouts:
            cached["cached"] = True
            return cached
    m = _fixture(match_id)
    clubs = build_league()
    home, away = club_by_code(clubs, m["home"]), club_by_code(clubs, m["away"])
    rec = _record(match_id)
    result = fork(home, away, m["seed"], match_id, event_id, change,
                  rollouts=rollouts, record=rec)
    result["history"] = history.history_check(result, rec, _history_rows())
    result["cached"] = False
    return result


class ForkRequest(BaseModel):
    match_id: str
    event_id: str | None = None
    change: dict = Field(..., examples=[{"type": "flip_call"}])
    rollouts: int = Field(DEFAULT_ROLLOUTS, ge=10, le=MAX_ROLLOUTS)


@app.get("/health")
def health():
    return {"ok": True, "model_world": True}


@app.get("/clubs")
def clubs():
    return [{"code": c.code, "name": c.name, "formation": c.formation, "archetype": c.archetype,
             "style": c.style(),
             "squad": [{"id": p.id, "name": p.name, "pos": p.pos, "number": p.number} for p in c.squad]}
            for c in build_league()]


@app.get("/matches")
def matches():
    return _season()["matches"]


@app.get("/standings")
def standings():
    return season.standings(_season())


@app.get("/match/{match_id}")
def match(match_id: str):
    out = _record(match_id).to_dict()
    out["story"] = _fixture(match_id).get("story")
    return out


@app.get("/moments/{match_id}")
def match_moments(match_id: str):
    return moments(_record(match_id))


@app.post("/fork")
def post_fork(req: ForkRequest):
    try:
        return run_fork(req.match_id, req.event_id, req.change, req.rollouts)
    except ForkError as e:
        raise HTTPException(422, str(e))
