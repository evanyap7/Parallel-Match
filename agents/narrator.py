"""Narrator agent: commentary for both timelines of a fork.

Input is a POST /fork response (fixtures/fork_m012.json shape). Output is a
short script: the real timeline, the alternate timeline, the divergence
point and a verdict card, all phrased from computed facts. Alternate-timeline
results are labelled model world, per the competition plan.
"""

from __future__ import annotations

from . import prompts
from .facts import fork_facts
from .laws import CALL_PHRASES
from .provider import ChatProvider, TemplateProvider, phrase


def _score(facts: dict, key: str) -> str:
    home, away = facts[key]
    return f"{facts.get('home_label', 'home')} {home}-{away} {facts.get('away_label', 'away')}"


def _pct(value) -> int | None:
    return round(value * 100) if isinstance(value, (int, float)) else None


def build_facts(fork_response: dict, match: dict | None = None) -> dict:
    facts = fork_facts(fork_response)
    if match:
        facts["home_label"] = match["home"]
        facts["away_label"] = match["away"]
    else:
        facts["home_label"] = "home"
        facts["away_label"] = "away"
    change = facts.get("change") or {}
    alt_call = change.get("call")
    facts["moment_call_phrase"] = CALL_PHRASES.get(
        facts.get("moment_call"), "the decision stands"
    )
    facts["alternate_call_phrase"] = CALL_PHRASES.get(
        alt_call, f"the decision becomes '{alt_call}'" if alt_call else "the decision is changed"
    )
    orig_p = _pct((facts.get("original_last_winprob") or {}).get("home"))
    alt_p = _pct((facts.get("alternate_last_winprob") or {}).get("home"))
    # Percentages are stored as facts (ints) so grounding checks pass exactly.
    if orig_p is not None:
        facts["original_home_win_pct"] = orig_p
    if alt_p is not None:
        facts["alternate_home_win_pct"] = alt_p
    if orig_p is not None and alt_p is not None:
        facts["winprob_shift_sentence"] = (
            f"Model world: the home win probability finishes at {alt_p}% "
            f"instead of {orig_p}%."
        )
    else:
        facts["winprob_shift_sentence"] = "Model world: win-probability lines diverge from the fork onward."
    return facts


def _real_line(facts: dict) -> str:
    minute = facts["divergence_min"]
    return (
        f"At {minute}', {facts['moment_call_phrase']} in the "
        f"recorded match: the real timeline runs on and finishes {_score(facts, 'original_final_score')}."
    )


def _alternate_line(facts: dict) -> str:
    return (
        f"In the alternate timeline the same moment is re-judged: "
        f"{facts['alternate_call_phrase']}. The simulation plays on from there and "
        f"finishes {_score(facts, 'alternate_final_score')}."
    )


def _divergence_line(facts: dict) -> str:
    return (
        f"Both timelines share every event up to {facts['divergence_min']}', "
        f"then diverge."
    )


def _verdict_line(facts: dict) -> str:
    return (
        f"Turning point at {facts['divergence_min']}': "
        f"{facts['alternate_call_phrase']}, so the model world finishes "
        f"{_score(facts, 'alternate_final_score')} against the recorded "
        f"{_score(facts, 'original_final_score')}. {facts['winprob_shift_sentence']}"
    )


def template_script(facts: dict) -> list[dict]:
    return [
        {"timeline": "real", "text": _real_line(facts)},
        {"timeline": "divergence", "text": _divergence_line(facts)},
        {"timeline": "alternate", "text": _alternate_line(facts)},
        {"timeline": "verdict", "text": _verdict_line(facts)},
    ]


def run(fork_response: dict, match: dict | None = None,
        provider: ChatProvider | None = None) -> dict:
    facts = build_facts(fork_response, match)
    provider = provider or TemplateProvider()
    script = []
    fell_back = False
    for line in template_script(facts):
        text, fb = phrase(provider, prompts.NARRATOR, facts, line["text"])
        fell_back = fell_back or fb
        script.append({"timeline": line["timeline"], "text": text})
    return {
        "match_id": facts["match_id"],
        "event_id": facts["event_id"],
        "script": script,
        "facts": facts,
        "fell_back": fell_back,
    }
