"""Agent output in the fan's language.

The 18 interface languages are also the 18 languages agent text can come in.
The model writes straight from the guarded reference phrasing, so facts and
numbers still come only from code. A translated answer is accepted only if:

- every number in it appears in the fact bundle (grounding, after digits and
  decimal commas are normalised to the ASCII form the facts use),
- it passes the English neutrality screen (catches untranslated slips) and a
  per-language screen for wording that judges officials,
- it really is in the requested language (script or differs from the template).

Anything else falls back to the English reference text and the response says
`translated: false`, so the UI can tell the fan.
"""

from __future__ import annotations

import re
import unicodedata

LANGUAGES: dict[str, str] = {
    "en": "English", "es": "Spanish", "pt": "Brazilian Portuguese",
    "fr": "French", "de": "German", "it": "Italian", "nl": "Dutch",
    "pl": "Polish", "ru": "Russian", "tr": "Turkish", "ar": "Arabic",
    "hi": "Hindi", "id": "Indonesian", "th": "Thai", "vi": "Vietnamese",
    "zh": "Simplified Chinese", "ja": "Japanese", "ko": "Korean",
}

# Wording that judges a decision or an official, per language (lowercase
# substrings). The English screen in guardrails.py still runs on every output.
# Arabic "خطأ" alone is football's word for "foul", so only judging phrases are listed.
_BANNED: dict[str, list[str]] = {
    "es": ["equivoc", "error arbitral", "error del árbitro", "robo", "escándalo", "injust", "vergüenza"],
    "pt": ["errou", "erro do árbitro", "erro de arbitragem", "roubo", "escândalo", "injust", "vergonha"],
    "fr": ["se trompe", "erreur d", "scandale", "injust", "volé", "honteu"],
    "de": ["fehlentscheidung", "irrtum", "fehler des schiedsrichters", "skandal", "ungerecht", "betrug", "blamage"],
    "it": ["errore dell", "sbagli", "scandalo", "ingiust", "rubat", "vergogna"],
    "nl": ["fout van de scheids", "vergissing", "schandaal", "onrechtvaardig", "bestolen", "schande"],
    "pl": ["błąd sędzi", "pomyli", "skandal", "niesprawiedliw", "okradz"],
    "ru": ["ошибк", "ошибся", "скандал", "несправедлив", "обокрал", "позор"],
    "tr": ["hata", "yanlış", "skandal", "haksız", "soygun", "rezalet"],
    "ar": ["خطأ الحكم", "أخطأ", "فضيحة", "ظلم", "سرقة", "خطأ تحكيمي"],
    "hi": ["गलती", "ग़लत", "गलत", "घोटाला", "अन्याय", "शर्मनाक"],
    "id": ["salah wasit", "kesalahan wasit", "keliru", "skandal", "tidak adil", "dirampok", "memalukan"],
    "th": ["ตัดสินผิด", "ผิดพลาด", "เรื่องอื้อฉาว", "ไม่ยุติธรรม", "โดนโกง", "น่าอับอาย"],
    "vi": ["sai lầm", "trọng tài sai", "bê bối", "bất công", "bị cướp", "đáng xấu hổ"],
    "zh": ["错判", "误判", "判错", "丑闻", "不公", "黑哨", "抢劫"],
    "ja": ["誤審", "ミス", "間違", "スキャンダル", "不公平", "奪われ"],
    "ko": ["오심", "실수", "잘못", "스캔들", "불공정", "도둑"],
}

# Languages whose script is not Latin: a real translation is mostly that script.
_SCRIPT = {
    "ru": (0x0400, 0x04FF), "ar": (0x0600, 0x06FF), "hi": (0x0900, 0x097F),
    "th": (0x0E00, 0x0E7F), "zh": (0x4E00, 0x9FFF), "ja": (0x3040, 0x9FFF),
    "ko": (0xAC00, 0xD7AF),
}


def norm_lang(code: str | None) -> str:
    """A supported language code, English when missing or unknown."""
    base = (code or "en").strip().lower().replace("_", "-").split("-")[0]
    return base if base in LANGUAGES else "en"


def normalise_digits(text: str) -> str:
    """Native digits (Arabic-Indic, Devanagari, Thai, ...) to ASCII, and a
    decimal comma between digits to a period, the form the facts use."""
    out = "".join(str(unicodedata.digit(ch)) if ch.isdigit() and not ch.isascii() else ch
                  for ch in text)
    return re.sub(r"(?<=\d)[,٫](?=\d)", ".", out)


def language_issues(text: str, lang: str) -> list[str]:
    low = text.lower()
    return [f"banned phrase ({lang}): '{w}'" for w in _BANNED.get(lang, []) if w in low]


def looks_translated(text: str, reference: str, lang: str) -> bool:
    if lang in _SCRIPT:
        lo, hi = _SCRIPT[lang]
        letters = [c for c in text if c.isalpha()]
        if not letters:
            return False
        return sum(lo <= ord(c) <= hi for c in letters) / len(letters) >= 0.3
    return text.strip().lower() != reference.strip().lower()


def instruction(lang: str) -> str:
    return (
        f"Write the answer in {LANGUAGES[lang]}. Keep club names, player names, "
        "team codes and ids exactly as given, in Latin letters. Write every "
        "number with ASCII digits and a period as the decimal separator. Do "
        "not add, drop or change any fact or number, and never judge "
        "officials, players or decisions."
    )


def to_english_prompt(lang: str) -> str:
    return (
        f"Translate this football fan's {LANGUAGES[lang]} question into plain "
        "English. Reply with the English sentence only, nothing else."
    )
