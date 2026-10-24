"""Parallel Match agents.

Four agents behind one rule: all numbers and all moment-finding stay in
plain code; agents only phrase results and never invent facts.

- narrator:        commentary for both timelines of a fork
- law_explainer:   neutral statement of the relevant Law
- historian:       precedent from the recorded season (via mcp_history)
- intervention:    free text to a typed, validated change (deterministic)

See docs/agents.md.
"""

from . import facts, guardrails, laws, prompts, provider  # noqa: F401
from .law_explainer import run as run_law_explainer
from .narrator import run as run_narrator
from .historian import run as run_historian
from .intervention import parse_and_validate

__all__ = [
    "facts", "guardrails", "laws", "prompts", "provider",
    "run_narrator", "run_law_explainer", "run_historian", "parse_and_validate",
]
