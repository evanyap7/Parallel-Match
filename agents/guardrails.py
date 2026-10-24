"""Output guardrails: neutrality and factual grounding.

Competition rules and the team plan both require that we never say a referee
or player "got it wrong" - we explain the decision and cite the Law neutrally.
We also require that every number in an agent's output appears in the fact
bundle it was given, so an agent cannot invent facts even by accident.

These checks run on every agent output in every mode (template or LLM). An
output that fails a check is replaced by the deterministic template phrasing.
"""

from __future__ import annotations

import re

from .facts import canonical

# Phrases that judge an official's decision (banned in all agent output).
_BANNED = [
    r"\bgot it wrong\b", r"\bwrong(ly)?\b", r"\bmistake\b", r"\bmistaken(ly)?\b",
    r"\bblunder\b", r"\brobbed\b", r"\bcheat(ed|ing)?\b", r"\bscandal\b",
    r"\bdisgrace(ful)?\b", r"\bhowler\b", r"\bbias(ed)?\b", r"\binjustice\b",
    r"\bshould (have|not have|'ve)\b", r"\bought to have\b",
    r"\breferee error\b", r"\bmissed call\b", r"\bblew the call\b",
    r"\bawful\b", r"\bterrible\b", r"\bnonsense\b", r"\brobbery\b",
    r"\bvictim\b", r"\bunfair(ly)?\b",
]

_BANNED_RE = [re.compile(p, re.IGNORECASE) for p in _BANNED]

# Real-world football proper nouns must never appear; data is synthetic.
_BANNED_REAL_WORLD = re.compile(
    r"\b(premier league|la liga|serie a|bundesliga|ligue 1|champions league|"
    r"var|video assistant referee|fifa|uefa| refs?\b)",
    re.IGNORECASE,
)

# Numbers: minutes ("52'", "45+2"), decimals, percentages, counts.
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")

# Law citations contain numbers that are fine when the law title is a fact.
_LAW_NUMBER_RE = re.compile(r"Law \d+")


def neutrality_issues(text: str) -> list[str]:
    """Phrases that judge a decision or break the synthetic-data rule."""
    issues = []
    for pattern in _BANNED:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            issues.append(f"banned phrase: '{m.group(0)}'")
    m = _BANNED_REAL_WORLD.search(text)
    if m:
        issues.append(f"real-world reference: '{m.group(0)}'")
    return issues


def grounding_issues(text: str, facts: dict) -> list[str]:
    """Numbers in `text` that do not appear anywhere in the fact bundle."""
    truth = canonical(facts)
    # Remove Law citations ("Law 12") before number checking; the law title
    # carries the number and is checked as part of the facts anyway.
    stripped = _LAW_NUMBER_RE.sub("", text)
    issues = []
    for token in _NUMBER_RE.findall(stripped):
        if token not in truth:
            issues.append(f"number not in facts: '{token}'")
    return issues


def check_output(text: str, facts: dict) -> list[str]:
    """All guardrail violations for an agent output, given its facts."""
    return neutrality_issues(text) + grounding_issues(text, facts)
