"""Agent behaviour tests, run against the committed fixtures and the
deterministic template provider (no network, no model)."""

import json
import os
import unittest

from agents import historian, intervention, law_explainer, narrator
from agents.guardrails import check_output
from agents.provider import phrase
from mcp_history.store import default_store

from tests.fixture_ids import FOUL, FORK_M012, NO_FOUL, OFFSIDE, score_text

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _store():
    return default_store(os.path.join(REPO, "fixtures"),
                         os.path.join(REPO, "data", "dev_season"))


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
    def test_phrases_only_computed_numbers(self):
        store = _store()
        event, _ = store.event("m012", FOUL)
        result = historian.run(store.match("m012"), event, store.query("m012", FOUL))
        self.assertEqual(check_output(result["text"], result["facts"]), [])
        stats = result["stats"]
        self.assertIn(f"{stats['n']} moment", result["text"])
        self.assertIn(f"{stats['n_other_call']} of them", result["text"])

    def test_empty_history_says_so(self):
        match = {"match_id": "mX", "home": "HAR", "away": "NOR", "score": [0, 0],
                 "events": [{"id": "mX-0001", "min": "5", "t": 300, "type": "foul",
                             "team": "HAR", "player": "H7", "xy": [90, 34],
                             "contact": 0.5, "margin": 0.0, "call": "free_kick",
                             "law": "Law 12", "score": [0, 0], "step": 1, "period": 1}]}
        from mcp_history.store import HistoryStore, QueryResult
        store = HistoryStore([match])
        result = historian.run(match, match["events"][0], store.query("mX", "mX-0001"))
        self.assertIn("No comparable moment", result["text"])


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
