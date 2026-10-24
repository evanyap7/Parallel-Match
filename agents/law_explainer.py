"""Law Explainer agent: neutral statement of the relevant Law.

Input is one event. Output states what was decided, paraphrases the Law,
and - for contestable moments - notes that the decision sat close to the
boundary and could reasonably have gone either way. It never evaluates the
decision as right or wrong.
"""

from __future__ import annotations

from . import prompts
from .facts import moment_facts
from .laws import call_phrase, law_text
from .provider import ChatProvider, TemplateProvider, phrase


def build_facts(match: dict, event: dict) -> dict:
    facts = moment_facts(match, event)
    law = law_text(event.get("law", ""))
    facts["law_statement"] = law["statement"]
    facts["law_judgement"] = law["judgement"]
    facts["call_phrase"] = call_phrase(event.get("call"))
    # Display-rounded values are facts too, so grounding checks pass on the
    # exact strings the template prints.
    if facts.get("contact") is not None:
        facts["contact_display"] = f"{facts['contact']:.2f}"
    if facts.get("margin") is not None:
        facts["margin_display"] = f"{abs(facts['margin']):.2f}"
        facts["margin_side"] = "above" if facts["margin"] >= 0 else "below"
    if facts.get("offside_margin") is not None:
        facts["offside_margin_display"] = f"{abs(facts['offside_margin']):.2f}"
        facts["offside_side"] = "beyond" if facts["offside_margin"] >= 0 else "inside"
    return facts


def template(facts: dict) -> str:
    parts = [
        f"At {facts['min']}', a {facts['type']} moment involving {facts['player']} "
        f"({facts['team']}) against {facts['opponent']}: {facts['call_phrase']}."
    ]
    if "contact_display" in facts and "margin_display" in facts:
        parts.append(
            f"Measured contact was {facts['contact_display']}, sitting {facts['margin_display']} "
            f"{facts['margin_side']} the judgement threshold, so the decision was close to the boundary."
        )
    elif "offside_margin_display" in facts:
        parts.append(
            f"The attacker was {facts['offside_margin_display']} m {facts['offside_side']} "
            f"the second-last defender, a margin small enough that the decision was close to the boundary."
        )
    elif "margin_display" in facts:
        parts.append(
            f"The attacker was {facts['margin_display']} m {facts['margin_side']} "
            f"the second-last defender, a margin small enough that the decision was close to the boundary."
        )
    parts.append(f"Under {facts['law']}: {facts['law_statement']}")
    if facts.get("contestable") and facts.get("law_judgement"):
        parts.append(facts["law_judgement"])
    return " ".join(parts)


def run(match: dict, event: dict, provider: ChatProvider | None = None) -> dict:
    facts = build_facts(match, event)
    text, fell_back = phrase(
        provider or TemplateProvider(),
        prompts.LAW_EXPLAINER,
        facts,
        template(facts),
    )
    return {
        "event_id": event.get("id"),
        "law": facts.get("law", ""),
        "text": text,
        "facts": facts,
        "fell_back": fell_back,
    }
