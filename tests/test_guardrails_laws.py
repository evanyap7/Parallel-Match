"""Guardrails and the Law table: the neutrality contract, enforced."""

import unittest

from agents.guardrails import check_output, grounding_issues, neutrality_issues
from agents.laws import CALL_PHRASES, LAWS, call_phrase, law_text


class NeutralityTests(unittest.TestCase):
    def test_judging_phrases_are_flagged(self):
        for text in [
            "The referee got it wrong.",
            "That was clearly a mistake by the assistant.",
            "He should have given a penalty.",
            "The officials robbed the away side.",
            "A terrible decision.",
            "VAR would have fixed this.",
            "This is a Premier League moment.",
        ]:
            with self.subTest(text=text):
                self.assertTrue(neutrality_issues(text), text)

    def test_neutral_phrases_pass(self):
        for text in [
            "A direct free kick was awarded for contact judged careless.",
            "The margin was 0.10 m; the decision sat close to the boundary.",
            "Play continued with no foul called, and the model world plays on.",
            "Law 12 covers direct free kick offences.",
        ]:
            with self.subTest(text=text):
                self.assertEqual(neutrality_issues(text), [])

    def test_law_texts_are_neutral(self):
        for key, entry in LAWS.items():
            for field in ("statement", "judgement"):
                with self.subTest(law=key, field=field):
                    self.assertEqual(neutrality_issues(str(entry[field])), [])


class GroundingTests(unittest.TestCase):
    FACTS = {"min": "52", "contact": 0.55, "score": [2, 0], "pct": 41}

    def test_numbers_from_facts_pass(self):
        self.assertEqual(grounding_issues(
            "At 52' the contact was 0.55, 41% and 2-0.", self.FACTS), [])

    def test_invented_numbers_are_flagged(self):
        issues = grounding_issues("He ran 40 metres and it was 3-3.", self.FACTS)
        self.assertIn("number not in facts: '40'", issues)
        self.assertIn("number not in facts: '3'", issues)

    def test_law_citations_do_not_need_the_number_as_a_fact(self):
        self.assertEqual(grounding_issues("Law 12 applies.", self.FACTS), [])

    def test_check_output_combines_both(self):
        self.assertTrue(check_output("Wrong, and it was 40 metres.", self.FACTS))
        self.assertEqual(check_output("At 52' contact was 0.55.", self.FACTS), [])


class LawTableTests(unittest.TestCase):
    def test_every_simulator_law_string_has_text(self):
        from parallel_match.rules import LAWS as SIM_LAWS  # type: ignore[attr-defined]
        sim_strings = set(SIM_LAWS.values())
        table_strings = set(LAWS)
        self.assertLessEqual(sim_strings - table_strings, set(),
                             f"missing law text for: {sim_strings - table_strings}")

    def test_fallback_for_unknown_law(self):
        entry = law_text("Law 99: Made Up")
        self.assertIn("not indexed", entry["statement"])
        self.assertEqual(entry["title"], "Law 99: Made Up")

    def test_call_phrases_known_values(self):
        self.assertEqual(call_phrase("free_kick"), CALL_PHRASES["free_kick"])
        self.assertEqual(call_phrase(None), "the decision on the field was 'None'")
        self.assertIn("penalty", call_phrase("penalty"))


if __name__ == "__main__":
    unittest.main()
