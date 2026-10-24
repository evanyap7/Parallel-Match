"""Agent behaviour tests, run against the committed fixtures and the
deterministic template provider (no network, no model)."""

import json
import os
import unittest

from agents import historian, intervention, law_explainer, narrator
from agents.guardrails import check_output
from agents.provider import phrase
from mcp_history.precedent import compare_with_simulation, history_for
from mcp_history.store import default_store

from tests.fixture_ids import FOUL, FORK_M012, NO_FOUL, OFFSIDE, score_text

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _store():
    return default_store()   # the real 90-match season


def _m012():
    with open(os.path.join(REPO, "fixtures", "m012.json")) as fh:
        return json.load(fh)


class NarratorTests(unittest.TestCase):
    def setUp(self):
        self.fork = json.load(open(os.path.join(REPO, "fixtures", "fork_m012.json")))
        self.match = _m012()
        self.result = narrator.run(self.fork, self.match)

    def test_script_has_four_segments(self):
        self.assertEqual([s["timeline"] for s in self.result["script"]],
                         ["real", "divergence", "alternate", "verdict"])

    def test_alternate_is_labelled_model_world(self):
        joined = " ".join(s["text"] for s in self.result["script"])
        self.assertIn("Model world", joined)

    def test_every_segment_passes_guardrails(self):
        for segment in self.result["script"]:
            with self.subTest(timeline=segment["timeline"]):
                self.assertEqual(check_output(segment["text"], self.result["facts"]), [])

    def test_outcome_uses_rollout_shares_not_last_winprob(self):
        verdict = next(s for s in self.result["script"] if s["timeline"] == "verdict")
        orig = round(FORK_M012["original"]["outcome"]["home"] * 100)
        alt = round(FORK_M012["alternate"]["outcome"]["home"] * 100)
        self.assertIn(f"{alt}% of finishes instead of {orig}%", verdict["text"])

    def test_reads_top_level_fork_ids(self):
        self.assertEqual(self.result["match_id"], FORK_M012["match_id"])
        self.assertEqual(self.result["event_id"], FORK_M012["event_id"])

    def test_alternate_call_is_named(self):
        alternate = next(s for s in self.result["script"] if s["timeline"] == "alternate")
        self.assertNotIn("the decision is changed", alternate["text"])

    def test_scores_come_from_the_fork_response(self):
        verdict = next(s for s in self.result["script"] if s["timeline"] == "verdict")
        self.assertIn(score_text(FORK_M012["original"]["final_score"]), verdict["text"])
        self.assertIn(score_text(FORK_M012["alternate"]["final_score"]), verdict["text"])


class LawExplainerTests(unittest.TestCase):
    def test_foul_event_states_law_and_boundary(self):
        store = _store()
        match, (event, _) = store.match("m012"), store.event("m012", FOUL)
        result = law_explainer.run(match, event)
        self.assertIn("Law 12", result["text"])
        self.assertIn(f"{event['contact']:.2f}", result["text"])
        self.assertIn("boundary", result["text"])
        self.assertEqual(check_output(result["text"], result["facts"]), [])

    def test_offside_event_states_margin(self):
        store = _store()
        event, _ = store.event("m012", OFFSIDE)
        result = law_explainer.run(store.match("m012"), event)
        self.assertIn("Law 11", result["text"])
        self.assertIn(f"{abs(event['margin']):.2f}", result["text"])
        self.assertEqual(check_output(result["text"], result["facts"]), [])

    def test_never_judges_the_decision(self):
        store = _store()
        for event_id in (FOUL, OFFSIDE, NO_FOUL):
            event, _ = store.event("m012", event_id)
            result = law_explainer.run(store.match("m012"), event)
            self.assertEqual(check_output(result["text"], result["facts"]), [],
                             result["text"])


class HistorianTests(unittest.TestCase):
    def setUp(self):
        self.fork = json.load(open(os.path.join(REPO, "fixtures", "fork_m052.json")))
        self.block = history_for(self.fork["match_id"], self.fork["event_id"])

    def test_same_numbers_as_fork_history(self):
        # One precedent source: the Historian and POST /fork never disagree.
        for key in ("n", "when_given", "when_not_given", "attacking_team",
                    "history_shift_att_win"):
            with self.subTest(key=key):
                self.assertEqual(self.block[key], self.fork["history"][key])

    def test_phrases_only_computed_numbers(self):
        result = historian.run(None, None, self.block)
        self.assertEqual(check_output(result["text"], result["facts"]), [])
        self.assertIn(f"{self.block['n']} comparable", result["text"])
        self.assertIn(f"({self.block['when_given']['n']} cases)", result["text"])

    def test_states_simulation_and_agreement(self):
        block = compare_with_simulation(self.block, self.fork)
        result = historian.run(None, None, block)
        self.assertEqual(check_output(result["text"], result["facts"]), [])
        self.assertIn("paired simulation", result["text"])
        self.assertEqual(result["agrees_with_simulation"],
                         self.fork["history"]["agrees_with_simulation"])

    def test_disagreement_is_said_plainly(self):
        block = {**self.block, "sim_shift_att_win": 0.2,
                 "history_shift_att_win": -0.1, "agrees_with_simulation": False}
        result = historian.run(None, None, block)
        self.assertIn("These disagree", result["text"])
        self.assertEqual(check_output(result["text"], result["facts"]), [])

    def test_small_sample_gives_no_estimate(self):
        block = {**self.block, "history_shift_att_win": None}
        self.assertIn("fewer than 5 cases", historian.run(None, None, block)["text"])

    def test_empty_history_says_so(self):
        result = historian.run(None, None, {"n": 0})
        self.assertIn("No comparable moment", result["text"])

    def test_non_call_is_none(self):
        kickoff = self.fork["match_id"] + "-0001"
        self.assertIsNone(history_for(self.fork["match_id"], kickoff))


class ProviderPipelineTests(unittest.TestCase):
    """The guardrail fallback: bad model output is replaced by the template."""

    class BadProvider:
        name = "bad"

        def complete(self, system, user):
            return "The referee got it wrong and it was 99-0."

    class GoodProvider:
        name = "good"

        def complete(self, system, user):
            return "A tight call at 52', contact at the threshold."

    FACTS = {"min": "52", "contact": 0.55}

    def test_bad_output_falls_back_to_template(self):
        text, fell_back = phrase(self.BadProvider(), "sys", self.FACTS, "Template at 52'.")
        self.assertTrue(fell_back)
        self.assertEqual(text, "Template at 52'.")

    def test_good_output_is_used(self):
        text, fell_back = phrase(self.GoodProvider(), "sys", self.FACTS, "Template at 52'.")
        self.assertFalse(fell_back)
        self.assertEqual(text, "A tight call at 52', contact at the threshold.")

    def test_provider_error_falls_back(self):
        class Boom:
            name = "boom"

            def complete(self, system, user):
                raise RuntimeError("foundry down")

        text, fell_back = phrase(Boom(), "sys", self.FACTS, "Template at 52'.")
        self.assertTrue(fell_back)
        self.assertEqual(text, "Template at 52'.")


class ProviderSelectionTests(unittest.TestCase):
    """Foundry misconfiguration never takes the service down."""

    def setUp(self):
        from agents import provider
        self.provider = provider
        self._env = {k: os.environ.get(k) for k in
                     ("PM_AGENT_BACKEND", "AZURE_AI_FOUNDRY_PROJECT_ENDPOINT")}
        provider.reset_provider()

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.provider.reset_provider()

    def test_foundry_without_endpoint_falls_back_to_template(self):
        os.environ["PM_AGENT_BACKEND"] = "foundry"
        os.environ.pop("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT", None)
        p = self.provider.get_provider()
        self.assertEqual(p.name, "template")
        self.assertIn("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT", self.provider.provider_error())

    def test_failed_model_call_cools_down(self):
        AFP = self.provider.AgentFrameworkProvider
        p = AFP.__new__(AFP)          # no Azure client needed
        p.timeout_s, p.cooldown_s, p._down_until, p.last_error = 1, 60, 0.0, None

        class Loop:
            calls = 0

            def run(self, coro, timeout):
                Loop.calls += 1
                raise TimeoutError("model down")

        class Agent:
            def run(self, prompt):
                return None

        p._loop, p._agent = Loop(), Agent()
        for _ in range(3):
            text, fell_back = phrase(p, "sys", {"min": "52"}, "Template at 52'.")
            self.assertTrue(fell_back)
            self.assertEqual(text, "Template at 52'.")
        self.assertEqual(Loop.calls, 1)   # one timeout, then the cooldown


class InterventionTests(unittest.TestCase):
    def setUp(self):
        self.match = _m012()
        self.store = _store()

    def _event(self, event_id):
        return self.store.event("m012", event_id)[0]

    def test_negated_foul_flips_to_no_foul(self):
        result = intervention.parse_and_validate(
            "what if that wasn't a foul?", self.match, FOUL)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["request"]["change"],
                         {"type": "flip_call", "call": "no_foul"})

    def test_penalty_request_on_foul(self):
        result = intervention.parse_and_validate(
            "that should be a penalty", self.match, FOUL)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["request"]["change"]["call"], "penalty")

    def test_onside_flip_on_offside_event(self):
        result = intervention.parse_and_validate(
            "he was onside", self.match, OFFSIDE)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["request"]["change"],
                         {"type": "flip_call", "call": "onside"})

    def test_onside_flip_on_foul_event_is_refused(self):
        result = intervention.parse_and_validate(
            "he was onside", self.match, FOUL)
        self.assertFalse(result["ok"])

    def test_same_call_is_refused(self):
        # FOUL was already called free_kick; asking for a foul cannot apply
        result = intervention.parse_and_validate(
            "give the foul", self.match, FOUL)
        self.assertFalse(result["ok"])
        self.assertIn("already", result["reason"])

    def test_card_change_on_card_event(self):
        card_event = next(e for e in self.match["events"] if e["type"] == "card")
        result = intervention.parse_and_validate(
            "no red card", self.match, card_event["id"])
        # accepted only if the recorded card is red; otherwise refused, but
        # never crashes
        self.assertIn(result["ok"], (True, False))

    def test_unrecognised_text(self):
        result = intervention.parse_and_validate(
            "the pitch was lovely", self.match, FOUL)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "no recognised change in the text")

    def test_unknown_event(self):
        result = intervention.parse_and_validate(
            "no foul", self.match, "m012-9999")
        self.assertFalse(result["ok"])
        self.assertIn("not found", result["reason"])


if __name__ == "__main__":
    unittest.main()
