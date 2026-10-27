"""Match Desk: the agents working one moment together, end to end.

One request, six roles, one verified answer:

1. Producer plans the run (a Historian only for a flipped, contestable call)
   and opens a shared case file: the fork result, the moment, its Law and,
   once fetched, the season precedent.
2. Narrator, Law Explainer and Historian draft in parallel, each from its own
   fact bundle (the existing agents, unchanged).
3. Fact-Checker reviews every draft against the case file through tools:
   get_fork_result, get_precedent, get_law and check_numbers. The code checks
   are the hard gate: guardrails, the key numbers each piece must state, and
   that the agents agree with one another. With a model backend the
   Fact-Checker is also a Microsoft Agent Framework agent that calls the same
   tools and may reject a draft with a reason.
4. Editor rewrites each rejected draft with the Fact-Checker's notes. The
   rewrite is checked again; if it still fails, the deterministic reference
   phrasing is restored. Nothing reaches the screen unchecked.
5. Recap Writer turns the approved pieces into one broadcast recap.

Every step is recorded in a trace (role, status, time, tool calls) so the
viewer can see who did what. Without a model every role still runs, on the
deterministic template provider, so dev, CI and an outage behave the same.
"""

from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

from . import historian, law_explainer, narrator, prompts, translate
from .guardrails import check_output, grounding_issues, neutrality_issues
from .laws import law_text
from .provider import ChatProvider, TemplateProvider, phrase_in

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
_LAW_NUMBER_RE = re.compile(r"Law (\d+)")


class Trace:
    """Ordered record of what each role did, with timings in milliseconds."""

    def __init__(self):
        self._t0 = time.perf_counter()
        self._lock = threading.Lock()
        self.steps: list[dict] = []

    def now_ms(self) -> int:
        return round((time.perf_counter() - self._t0) * 1000)

    def add(self, role: str, status: str, start_ms: int, **detail) -> dict:
        step = {"role": role, "status": status, "start_ms": start_ms,
                "ms": max(0, self.now_ms() - start_ms), **detail}
        with self._lock:
            self.steps.append(step)
        return step


class CaseFile:
    """Shared state for one desk run, and the tools the Fact-Checker uses.

    The tool methods are what an Agent Framework agent calls (wrapped as
    function tools); the deterministic checks call the same methods, so both
    paths read the same evidence and every call lands in the trace."""

    def __init__(self, fork: dict, event: dict, facts: dict[str, dict]):
        self.fork = fork
        self.event = event
        self.facts = facts               # piece -> its fact bundle
        self.precedent: dict | None = None
        self.calls: list[dict] = []
        self._lock = threading.Lock()

    def _log(self, name: str, args: dict, ok: bool) -> None:
        with self._lock:
            self.calls.append({"tool": name, "args": args, "ok": ok})

    def get_fork_result(self) -> str:
        """Simulation result for the moment: final scores and the home, draw and
        away outcome shares in both timelines, rollouts and divergence minute."""
        f = self.fork
        out = {
            "rollouts": f.get("rollouts"),
            "divergence_min": (f.get("divergence") or {}).get("min"),
            "original": {"final_score": (f.get("original") or {}).get("final_score"),
                         "outcome": (f.get("original") or {}).get("outcome")},
            "alternate": {"final_score": (f.get("alternate") or {}).get("final_score"),
                          "outcome": (f.get("alternate") or {}).get("outcome")},
        }
        self._log("get_fork_result", {}, True)
        return json.dumps(out)

    def get_precedent(self) -> str:
        """Season precedent for the moment (fetched through the MCP server):
        comparable calls, outcome shares when given and not given."""
        self._log("get_precedent", {}, self.precedent is not None)
        return json.dumps(self.precedent or {"note": "no precedent for this moment"})

    def get_law(self) -> str:
        """The Law of the Game the decision falls under, in neutral words."""
        law = self.event.get("law", "")
        self._log("get_law", {"law": law}, bool(law))
        return json.dumps({"law": law, **law_text(law)})

    def check_numbers(self,
                      piece: Annotated[str, "narrator, law or historian"],
                      text: Annotated[str, "the draft text to check"]) -> str:
        """Numbers in a draft that are not in that piece's facts, and any
        wording that judges an official. Empty lists mean the draft is clean."""
        facts = self.facts.get(piece, {})
        issues = {"not_in_facts": grounding_issues(translate.normalise_digits(text), facts),
                  "judging_words": neutrality_issues(text)}
        self._log("check_numbers", {"piece": piece}, not any(issues.values()))
        return json.dumps(issues)

    def tools(self) -> list:
        return [self.get_fork_result, self.get_precedent, self.get_law, self.check_numbers]


def _plan(fork: dict, event: dict, has_precedent_source: bool) -> list[str]:
    roles = ["narrator", "law"]
    if ((fork.get("change") or {}).get("type") == "flip_call"
            and event.get("contestable") and has_precedent_source):
        roles.append("historian")
    return roles


def _required_numbers(piece: str, facts: dict) -> list[str]:
    """Numbers a piece must state for the viewer to get the point."""
    if piece == "narrator":
        need = [facts.get("original_home_share_pct"), facts.get("alternate_home_share_pct")]
    elif piece == "law":
        m = _LAW_NUMBER_RE.search(str(facts.get("law", "")))
        need = [m.group(1)] if m else []
    else:   # historian
        need = [facts.get("n")]
    return [str(n) for n in need if n not in (None, "")]


def _code_check(piece: str, text: str, facts: dict) -> list[str]:
    """The hard gate: guardrails plus the numbers the piece must state."""
    clean = translate.normalise_digits(text)
    issues = check_output(clean, facts)
    present = set(_NUMBER_RE.findall(clean))
    issues += [f"missing key number: {n}" for n in _required_numbers(piece, facts) if n not in present]
    return issues


def _consistency(case: CaseFile) -> list[dict]:
    """Do the agents' fact bundles describe the same moment and numbers?"""
    nf, lf = case.facts.get("narrator", {}), case.facts.get("law", {})
    checks = [
        {"check": "same_moment",
         "ok": str(nf.get("event_id")) == str(case.event.get("id"))},
        {"check": "same_call",
         "ok": nf.get("moment_call") in (None, lf.get("call"))},
    ]
    hf = case.facts.get("historian")
    if hf is not None:
        fork_n = (case.fork.get("history") or {}).get("n")
        checks.append({"check": "precedent_count",
                       "ok": fork_n is None or fork_n == hf.get("n")})
    return checks


def _model_review(provider: ChatProvider, case: CaseFile, drafts: dict[str, str],
                  lang: str) -> tuple[dict[str, str], str | None]:
    """Fact-Checker as an Agent Framework agent with tools.

    Returns ({piece: issue} for rejected pieces, error). Any failure, or a
    reply that is not the agreed JSON, leaves the code checks in charge."""
    run_agent = getattr(provider, "run_agent", None)
    if run_agent is None:
        return {}, None
    prompt = (
        f"Language of the drafts: {translate.LANGUAGES.get(lang, 'English')}.\n"
        "Drafts (JSON):\n" + json.dumps(drafts, ensure_ascii=False)
    )
    try:
        reply = run_agent("fact-checker", prompts.FACT_CHECKER, prompt, case.tools())
        match = re.search(r"\{.*\}", reply, re.S)
        verdicts = json.loads(match.group(0))["verdicts"] if match else []
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {str(exc)[:160]}"
    rejected = {}
    for v in verdicts:
        piece = v.get("piece")
        if piece in drafts and v.get("ok") is False:
            rejected[piece] = str(v.get("issue") or "rejected by fact-checker")[:200]
    return rejected, None


def _edit(provider: ChatProvider, piece: str, draft: str, issues: list[str],
          facts: dict, reference: str, lang: str) -> tuple[str, str]:
    """Editor: rewrite a rejected draft; (text, status).

    status is "repaired" when the rewrite passes every check, else
    "restored" with the deterministic reference phrasing."""
    if not isinstance(provider, TemplateProvider):
        user = (
            "Facts (JSON, the only source of truth):\n"
            + json.dumps(facts, sort_keys=True, default=str, ensure_ascii=False)
            + "\n\nFact-checker notes:\n- " + "\n- ".join(issues)
            + "\n\nDraft to fix:\n" + draft
        )
        system = prompts.EDITOR if lang == "en" else f"{prompts.EDITOR}\n\n{translate.instruction(lang)}"
        try:
            text = provider.complete(system, user).strip()
            if text and not _code_check(piece, text, facts):
                return text, "repaired"
        except Exception:
            pass
    return reference, "restored"


def _first_sentence(text: str) -> str:
    m = re.match(r"(.+?[.!?])(\s|$)", text.strip(), re.S)
    return m.group(1) if m else text.strip()


def run(fork: dict, match: dict | None, event: dict, provider: ChatProvider | None = None,
        lang: str = "en", precedent_fn=None, compare_fn=None) -> dict:
    """Run the desk for one fork. `precedent_fn(match_id, event_id)` returns
    (block, source) as agents.history_client.precedent does, and
    `compare_fn(block, fork)` adds the simulation comparison."""
    provider = provider or TemplateProvider()
    lang = translate.norm_lang(lang)
    trace = Trace()
    model = not isinstance(provider, TemplateProvider)

    # 1. Producer
    t = trace.now_ms()
    plan = _plan(fork, event, precedent_fn is not None)
    trace.add("producer", "ok", t, plan=plan)

    # 2. Specialists, in parallel
    results: dict[str, dict] = {}
    precedent_source = None

    def narrate():
        s = trace.now_ms()
        r = narrator.run(fork, match, provider, lang)
        trace.add("narrator", "fallback" if r["fell_back"] else "ok", s)
        return r

    def explain():
        s = trace.now_ms()
        r = law_explainer.run(match, event, provider, lang)
        trace.add("law", "fallback" if r["fell_back"] else "ok", s)
        return r

    def recall():
        nonlocal precedent_source
        s = trace.now_ms()
        block, precedent_source = precedent_fn(fork.get("match_id"), event.get("id"))
        if block is None:
            trace.add("historian", "skipped", s)
            return None
        f = fork if "match" in fork else {**fork, "match": match}
        block = compare_fn(block, f) if compare_fn else block
        r = historian.run(match, event, block, provider, lang)
        trace.add("historian", "fallback" if r["fell_back"] else "ok", s,
                  source=precedent_source)
        return r

    jobs = {"narrator": narrate, "law": explain, "historian": recall}
    with ThreadPoolExecutor(max_workers=len(plan)) as pool:
        futures = {role: pool.submit(jobs[role]) for role in plan}
        for role, fut in futures.items():
            r = fut.result()
            if r is not None:
                results[role] = r

    def verdict_line(script):
        return next(s["text"] for s in script if s["timeline"] == "verdict")

    drafts = {
        "narrator": verdict_line(results["narrator"]["script"]),
        "law": results["law"]["text"],
    }
    references = {
        "narrator": verdict_line(narrator.template_script(results["narrator"]["facts"])),
        "law": law_explainer.template(results["law"]["facts"]),
    }
    facts = {"narrator": results["narrator"]["facts"], "law": results["law"]["facts"]}
    if "historian" in results:
        drafts["historian"] = results["historian"]["text"]
        references["historian"] = historian.template(results["historian"]["facts"])
        facts["historian"] = results["historian"]["facts"]

    # 3. Fact-Checker
    t = trace.now_ms()
    case = CaseFile(fork, event, facts)
    case.precedent = (results.get("historian") or {}).get("history")
    case.get_fork_result()
    case.get_law()
    if "historian" in drafts:
        case.get_precedent()
    issues = {piece: _code_check(piece, text, facts[piece]) for piece, text in drafts.items()}
    for piece, text in drafts.items():
        case.check_numbers(piece, text)
    model_rejects, review_error = _model_review(provider, case, drafts, lang) if model else ({}, None)
    for piece, why in model_rejects.items():
        issues[piece].append(why)
    consistency = _consistency(case)
    rejected = [p for p, found in issues.items() if found]
    trace.add("fact_checker", "rejected" if rejected else "ok", t,
              checked=len(drafts), rejected=rejected, tool_calls=list(case.calls),
              consistency=consistency,
              reviewer="agent" if model and review_error is None else "code",
              review_error=review_error)

    # 4. Editor
    pieces = []
    t = trace.now_ms()
    edited = {}
    for piece, text in drafts.items():
        status = "approved"
        if issues[piece]:
            text, status = _edit(provider, piece, text, issues[piece], facts[piece],
                                 references[piece], lang)
            edited[piece] = status
        pieces.append({
            "role": piece, "text": text, "status": status, "issues": issues[piece],
            "translated": status != "restored" and bool(results[piece].get("translated")),
        })
    editor_status = ("idle" if not edited else
                     "repaired" if all(s == "repaired" for s in edited.values()) else "restored")
    trace.add("editor", editor_status, t, edited=edited)

    # 5. Recap Writer
    t = trace.now_ms()
    recap_facts = {"narrator": facts["narrator"], "law": facts["law"],
                   "approved": {p["role"]: p["text"] for p in pieces}}
    if "historian" in facts:
        recap_facts["historian"] = facts["historian"]
    # What was decided, then what the model world shows, then what the season adds.
    reference = " ".join(references[p] if p == "narrator" else _first_sentence(references[p])
                         for p in ("law", "narrator", "historian") if p in references)
    text, fell_back, translated = phrase_in(provider, prompts.RECAP_WRITER, recap_facts,
                                            reference, lang=lang)
    trace.add("recap", "fallback" if fell_back else "ok", t)

    numbers = sum(len(_NUMBER_RE.findall(translate.normalise_digits(p["text"]))) for p in pieces)
    numbers += len(_NUMBER_RE.findall(translate.normalise_digits(text)))
    hist = results.get("historian")
    return {
        "match_id": fork.get("match_id"),
        "event_id": event.get("id"),
        "lang": lang,
        "plan": plan,
        "recap": {"text": text, "fell_back": fell_back, "translated": translated},
        "pieces": pieces,
        "checks": {
            "numbers_verified": numbers,
            "tool_calls": len(case.calls),
            "consistency": consistency,
            "agrees_with_simulation": (hist or {}).get("agrees_with_simulation"),
            "precedent_source": precedent_source,
        },
        "trace": trace.steps,
        "ms": trace.now_ms(),
        "fell_back": fell_back or any(p["status"] == "restored" for p in pieces),
        "translated": translated and all(p["translated"] for p in pieces),
    }
