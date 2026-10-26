"""Agent text in the fan's language: accepted only when it keeps the facts
and the neutrality rules, otherwise the English reference text is served."""

import json
import os
import unittest

from agents import narrator, translate
from agents.provider import TemplateProvider, phrase_in

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACTS = {"min": "52", "team": "Westfield Rangers"}
REF = "At 52', Westfield Rangers: the decision stands."


class Fake:
    name = "fake"

    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def complete(self, system, user):
        self.calls.append((system, user))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


class PhraseInTests(unittest.TestCase):
    def test_good_translation_is_used(self):
        p = Fake("En el minuto 52, Westfield Rangers: la decisión se mantiene.")
        text, fell_back, translated = phrase_in(p, "sys", FACTS, REF, lang="es")
        self.assertEqual((fell_back, translated), (False, True))
        self.assertIn("minuto 52", text)
        self.assertIn("Spanish", p.calls[0][0])

    def test_native_digits_become_ascii(self):
        p = Fake("في الدقيقة ٥٢ يواصل فريق Westfield Rangers اللعب.")
        text, _fb, translated = phrase_in(p, "sys", FACTS, REF, lang="ar")
        self.assertTrue(translated)
        self.assertIn("52", text)

    def test_invented_number_falls_back_to_english(self):
        p = Fake("En el minuto 52 el equipo marcó 7 goles.")
        self.assertEqual(phrase_in(p, "sys", FACTS, REF, lang="es"), (REF, True, False))

    def test_judging_wording_in_the_language_falls_back(self):
        p = Fake("En el minuto 52 el árbitro se equivocó.")
        self.assertEqual(phrase_in(p, "sys", FACTS, REF, lang="es"), (REF, True, False))

    def test_english_answer_for_a_foreign_request_falls_back(self):
        p = Fake("At 52', Westfield Rangers: the decision stands.")
        self.assertEqual(phrase_in(p, "sys", FACTS, REF, lang="ja"), (REF, True, False))

    def test_non_latin_script_is_required(self):
        p = Fake("在52分钟,Westfield Rangers 的判罚维持原判。")
        self.assertTrue(phrase_in(p, "sys", FACTS, REF, lang="zh")[2])

    def test_model_error_falls_back(self):
        p = Fake(RuntimeError("down"))
        self.assertEqual(phrase_in(p, "sys", FACTS, REF, lang="de"), (REF, True, False))

    def test_template_provider_answers_in_english(self):
        self.assertEqual(phrase_in(TemplateProvider(), "sys", FACTS, REF, lang="fr"),
                         (REF, False, False))

    def test_english_request_is_unchanged(self):
        p = Fake("At 52', Westfield Rangers keep the call.")
        text, fell_back, translated = phrase_in(p, "sys", FACTS, REF, lang="en")
        self.assertEqual((fell_back, translated), (False, False))
        self.assertNotIn("Write the answer in", p.calls[0][0])


class LanguageTests(unittest.TestCase):
    def test_norm_lang(self):
        self.assertEqual(translate.norm_lang("pt-BR"), "pt")
        self.assertEqual(translate.norm_lang("xx"), "en")
        self.assertEqual(translate.norm_lang(None), "en")

    def test_all_eighteen_languages_are_supported(self):
        self.assertEqual(len(translate.LANGUAGES), 18)
        for code in translate.LANGUAGES:
            if code != "en":
                self.assertIn(code, translate._BANNED)

    def test_decimal_comma_is_normalised(self):
        self.assertEqual(translate.normalise_digits("0,46 und ٣٫٥"), "0.46 und 3.5")


class NarratorLangTests(unittest.TestCase):
    def test_narrator_reports_language_and_translation(self):
        fork = json.load(open(os.path.join(REPO, "fixtures", "fork_m012.json")))
        en = narrator.run(fork, None, TemplateProvider(), "es")
        self.assertEqual((en["lang"], en["translated"]), ("es", False))

        class Echo(Fake):
            def complete(self, system, user):
                ref = user.rsplit("style without changing any fact or number):\n", 1)[1]
                return "Traducción: " + ref   # grounded, differs from the reference
        out = narrator.run(fork, None, Echo(""), "es")
        self.assertTrue(out["translated"])
        self.assertTrue(all(s["text"].startswith("Traducción:") for s in out["script"]))


if __name__ == "__main__":
    unittest.main()
