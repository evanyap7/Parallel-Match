"""Small in-memory answer cache for the agents API.

Judges tap the same featured moments, and an answer is fully determined by
its facts, so a repeat answer comes from memory instead of another round of
model calls. Only clean answers are kept: never one that fell back to the
template because the model failed (so it is retried once the model is back),
and never a precedent that skipped MCP while MCP is configured.
"""

from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict

_MAX = 512
_TTL_S = 6 * 3600

_lock = threading.Lock()
_items: "OrderedDict[str, tuple[float, dict]]" = OrderedDict()
_hits = 0
_misses = 0


def key(kind: str, *parts) -> str:
    return kind + ":" + json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))


def get(k: str) -> dict | None:
    global _hits, _misses
    with _lock:
        item = _items.get(k)
        if item is None or time.monotonic() - item[0] > _TTL_S:
            _items.pop(k, None)
            _misses += 1
            return None
        _items.move_to_end(k)
        _hits += 1
        return item[1]


def put(k: str, value: dict) -> None:
    with _lock:
        _items[k] = (time.monotonic(), value)
        _items.move_to_end(k)
        while len(_items) > _MAX:
            _items.popitem(last=False)


def clear() -> None:
    global _hits, _misses
    with _lock:
        _items.clear()
        _hits = _misses = 0


def stats() -> dict:
    with _lock:
        return {"entries": len(_items), "hits": _hits, "misses": _misses}
