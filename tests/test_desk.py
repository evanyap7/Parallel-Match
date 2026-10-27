"""Match Desk tests: the full multi-agent run on the committed m052 fork,
with the template provider and with a fake model that makes the kind of
mistake guardrails alone cannot see (two shares swapped)."""

import json
import os
import unittest

from agents import desk, history_client, prompts
from agents.guardrails import neutrality_issues
from mcp_history.precedent import compare_with_simulation
from mcp_history.store import default_store

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _fork():
    with open(os.path.join(REPO, "fixtures", "fork_m052.json")) as fh:
        return json.load(fh)


def _swap(text: str) -> str:
    """Swap the two Westfield shares, as a careless writer might."""
    return text.replace("15%", "\0").replace("29%", "15%").replace("\0", "29%")


class FakeModel:
    """Stands in for the Foundry provider. complete() returns the reference
    phrasing (swapping the shares in the Narrator's verdict when asked to);
    run_agent() calls the desk's tools and reports a verdict, as the
    Agent Framework fact-checker would."""

    name = "fake-model"

    def __init__(self, swap=False, review="reject", editor="fix"):
        self.swap, self.review, self.editor = swap, review, editor
        self.agent_tools = []

    def complete(self, system: str, user: str) -> str:
        if system.startswith(prompts.EDITOR):
            draft = user.split("Draft to fix:\n", 1)[1]
            return _swap(draft) if self.editor == "fix" else draft + " Attendance was 99%."
        ref = user.split("Reference phrasing", 1)[1].split(":\n", 1)[1]
        if self.swap and system.startswith(prompts.NARRATOR) and ref.startswith("Turning point"):
            return _swap(ref)
        return ref

    def run_agent(self, name, instructions, prompt, tools):
        if self.review == "error":
            raise TimeoutError("model did not answer")
        self.agent_tools = [t.__name__ for t in tools]
        by_name = {t.__name__: t for t in tools}
        shares = json.loads(by_name["get_fork_result"]())
        drafts = json.loads(prompt.split("Drafts (JSON):\n", 1)[1])
        verdicts = []
        for piece, text in drafts.items():
            by_name["check_numbers"](piece, text)
            ok = True
            if piece == "narrator":
                alt = round(shares["alternate"]["outcome"]["home"] * 100)
                orig = round(shares["original"]["outcome"]["home"] * 100)
                ok = text.index(f"{alt}%") < text.index(f"{orig}%")
            verdicts.append({"piece": piece, "ok": ok, "issue": "" if ok else "home shares swapped"})
        return json.dumps({"verdicts": verdicts})


class DeskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = default_store()
        cls.fork = _fork()
        cls.match = cls.store.match("m052")
        cls.event, _ = cls.store.event("m052", cls.fork["event_id"])

    def run_desk(self, provider=None, fork=None, precedent=True):
        return desk.run(fork or self.fork, self.match, self.event, provider, "en",
                        history_client.precedent if precedent else None,
                        compare_with_simulation)

    def test_every_role_runs_in_order(self):
        roles = [s["role"] for s in self.run_desk()["trace"]]
        self.assertEqual(roles[0], "producer")
        self.assertEqual(roles[-3:], ["fact_checker", "editor", "recap"])
        self.assertEqual(set(roles[1:4]), {"narrator", "law", "historian"})

    def test_template_run_is_approved_and_neutral(self):
        result = self.run_desk()
        self.assertTrue(all(p["status"] == "approved" for p in result["pieces"]))
        self.assertTrue(all(c["ok"] for c in result["checks"]["consistency"]))
        self.assertGreaterEqual(result["checks"]["tool_calls"], 4)
        for text in [p["text"] for p in result["pieces"]] + [result["recap"]["text"]]:
            self.assertEqual(neutrality_issues(text), [])
        self.assertIn("15%", result["recap"]["text"])
        self.assertIn("29%", result["recap"]["text"])
        self.assertFalse(result["fell_back"])

    def test_precedent_count_matches_the_fork(self):
        result = self.run_desk()
        check = next(c for c in result["checks"]["consistency"] if c["check"] == "precedent_count")
        self.assertTrue(check["ok"])

    def test_no_historian_without_a_flipped_call(self):
        fork = {**self.fork, "change": {"type": "card", "card": "red"}}
        result = self.run_desk(fork=fork)
        self.assertEqual(result["plan"], ["narrator", "law"])
        self.assertNotIn("historian", [p["role"] for p in result["pieces"]])

    def test_fact_checker_agent_catches_swapped_shares_and_editor_repairs(self):
        model = FakeModel(swap=True)
        result = self.run_desk(model)
        narr = next(p for p in result["pieces"] if p["role"] == "narrator")
        self.assertEqual(narr["status"], "repaired")
        self.assertIn("home shares swapped", narr["issues"])
        self.assertLess(narr["text"].index("15%"), narr["text"].index("29%"))
        checker = next(s for s in result["trace"] if s["role"] == "fact_checker")
        self.assertEqual(checker["reviewer"], "agent")
        self.assertEqual(checker["rejected"], ["narrator"])
        self.assertIn("check_numbers", model.agent_tools)
        self.assertEqual(next(s for s in result["trace"] if s["role"] == "editor")["status"], "repaired")

    def test_failed_rewrite_restores_the_reference(self):
        result = self.run_desk(FakeModel(swap=True, editor="invent"))
        narr = next(p for p in result["pieces"] if p["role"] == "narrator")
        self.assertEqual(narr["status"], "restored")
        self.assertNotIn("99", narr["text"])
        self.assertTrue(result["fell_back"])

    def test_reviewer_failure_leaves_code_checks_in_charge(self):
        result = self.run_desk(FakeModel(review="error"))
        checker = next(s for s in result["trace"] if s["role"] == "fact_checker")
        self.assertEqual(checker["reviewer"], "code")
        self.assertIn("TimeoutError", checker["review_error"])
        self.assertTrue(all(p["status"] == "approved" for p in result["pieces"]))


try:
    import agent_framework  # noqa: F401
    HAS_AGENT_FRAMEWORK = True
except ImportError:
    HAS_AGENT_FRAMEWORK = False


@unittest.skipUnless(HAS_AGENT_FRAMEWORK, "agent-framework not installed")
class AgentFrameworkToolTests(unittest.TestCase):
    """The Fact-Checker's tools, as Microsoft Agent Framework sees them."""

    def test_case_file_tools_wrap_as_function_tools(self):
        import asyncio
        from agent_framework import tool

        fork = _fork()
        case = desk.CaseFile(fork, {"id": fork["event_id"], "law": fork["moment"]["law"]},
                             {"narrator": {"share": 15}})
        wrapped = {t.name: t for t in (tool(fn) for fn in case.tools())}
        self.assertEqual(set(wrapped), {"get_fork_result", "get_precedent", "get_law", "check_numbers"})
        self.assertEqual(wrapped["check_numbers"].parameters()["required"], ["piece", "text"])
        out = asyncio.run(wrapped["check_numbers"].invoke(
            arguments={"piece": "narrator", "text": "15% instead of 99%"}))
        self.assertIn("99", str(getattr(out[0], "text", out)))
        self.assertEqual([c["tool"] for c in case.calls], ["check_numbers"])


if __name__ == "__main__":
    unittest.main()
