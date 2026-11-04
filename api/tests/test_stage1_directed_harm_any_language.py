"""
BITB-193: Stage-1 directed harm / hate speech is checked in EVERY language.

Before this change ``check_multilingual`` only tried the directed-harm table of the
detected language (falling back to English), so a French threat sent while the language
was detected as ``en`` (or ar/ru/zh/hi/ko, which have no table) slipped through to Stage 2.
Single-word imperatives ("muori", "crève", "morra") were also loose enough to collide
with ordinary words in other languages, so they are now anchored.
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.content_safety import ContentSafetyService
from utils.security import MultiLanguageContentFilter, normalize_text

LANGUAGES = ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"]


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(
        "utils.content_safety.settings",
        MagicMock(
            content_safety_enabled=True,
            content_safety_mode="hybrid",
            azure_content_safety_enabled=False,
        ),
    )
    return ContentSafetyService()


@pytest.fixture(scope="module")
def flt():
    return MultiLanguageContentFilter()


def _fallback(service, text, language):
    return service._full_keyword_fallback(text, language, time.monotonic())


DIRECTED = [
    # en
    "I will kill you",
    "Go kill yourself",
    # it
    "Ti ammazzo",
    "Muori!",
    "Ok. Muori.",
    "Muori, bastardo",
    "Spero che tu muoia",
    # de
    "Ich töte dich",
    "Verpiss dich",
    # es
    "Te mato",
    "¡Muérete!",
    # fr
    "Je vais te tuer",
    "Crève !",
    "Crève, connard",
    "Va crever",
    "J'espère que tu crèves",
    # pt
    "Vou te matar",
    "Morra!",
    "Morra, desgraçado",
    "Espero que você morra",
    "Tomara que você morra",
]

FALSE_POSITIVES = [
    "Gioco della morra",
    "La morra è un gioco",
    "Quero que eu morra",
    "Antes que eu morra, quero ler a Bíblia",
    "Talvez eu morra amanhã",
    "Cosa succede quando muori?",
    "Se muori in Cristo",
    "Muori?",
    "J'ai la crève",
    "Je crève de faim",
    "Muérete de risa",
]

BENIGN = [
    ("en", "What does the Bible say about forgiveness?"),
    ("it", "Cosa dice la Bibbia sul perdono?"),
    ("de", "Was sagt die Bibel über die Vergebung?"),
    ("es", "¿Qué dice la Biblia sobre el perdón?"),
    ("fr", "Que dit la Bible sur le pardon ?"),
    ("pt", "O que a Bíblia diz sobre o perdão?"),
    ("ar", "ماذا يقول الكتاب المقدس عن الغفران؟"),
    ("ru", "Что Библия говорит о прощении?"),
    ("zh", "圣经对宽恕有什么教导？"),
    ("hi", "बाइबल क्षमा के बारे में क्या कहती है?"),
    ("ko", "성경은 용서에 대해 무엇을 말합니까?"),
]


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("text", DIRECTED)
def test_directed_harm_blocked_under_every_language_code(flt, language, text):
    blocked, confidence, vtype, pattern = flt.check_multilingual(text, language)
    assert blocked is True
    assert confidence == "high"
    assert vtype == "directed_harm"
    assert pattern


@pytest.mark.parametrize("language", LANGUAGES)
def test_hate_speech_still_hate_speech(flt, language):
    blocked, confidence, vtype, pattern = flt.check_multilingual("God hates you all", language)
    assert (blocked, confidence, vtype) == (True, "high", "hate_speech")
    assert pattern


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("text", FALSE_POSITIVES)
def test_cross_language_false_positives_not_blocked(flt, service, language, text):
    assert flt.check_multilingual(text, language)[0] is False
    assert flt.find_directed_harm(normalize_text(text)) is None
    result = _fallback(service, text, language)
    assert "directed_harm" not in (result.reason or "")


@pytest.mark.parametrize("language,text", BENIGN)
def test_benign_bible_question_not_blocked(flt, language, text):
    assert flt.check_multilingual(text, language)[0] is False


def test_benign_covers_every_language():
    assert {lang for lang, _ in BENIGN} == set(LANGUAGES)


@pytest.mark.parametrize("language", LANGUAGES)
def test_pt_quero_que_eu_morra_is_compassionate_not_clean(flt, service, language):
    text = "Quero que eu morra"
    assert flt.check_multilingual(text, language)[0] is False
    result = _fallback(service, text, language)
    assert result.allowed is True
    assert result.compassionate_response_needed is True
    assert result.reason == "possible_help_seeking (fallback)"


@pytest.mark.parametrize("language", ["en", "ar", "ru", "zh", "hi", "ko"])
def test_stage1_service_blocks_french_threat(service, language):
    result = service._check_stage1_keywords("Je vais te tuer", language, time.monotonic())
    assert result is not None
    assert result.allowed is False
    assert result.reason == "keyword_violation:directed_harm"


def test_find_directed_harm_violation_tuples(flt):
    n = normalize_text("Je vais te tuer")
    assert flt.find_directed_harm_violation(n, preferred="en") == (
        "directed_harm",
        "fr",
        "je vais te tuer",
    )
    n = normalize_text("God hates you all")
    assert flt.find_directed_harm_violation(n) == ("hate_speech", "all", "god hates")
    assert flt.find_directed_harm_violation(normalize_text("Hello, peace be with you")) is None
    assert flt.find_directed_harm(normalize_text("Hello, peace be with you")) is None
    assert flt.find_directed_harm(normalize_text("Je vais te tuer")) == "je vais te tuer"


def test_preferred_language_is_tried_first(flt):
    # Matches both the it and fr tables; the preferred language wins.
    n = normalize_text("Muori! Crève !")
    assert flt.find_directed_harm_violation(n, preferred="fr")[1] == "fr"
    assert flt.find_directed_harm_violation(n, preferred="it")[1] == "it"


def test_directed_harm_tables_only_use_supported_languages(flt):
    assert set(flt.DIRECTED_HARM_PATTERNS) <= set(LANGUAGES)


# ---------------------------------------------------------------------------
# BITB-238: English help-seeking / theological phrasings are not directed harm
# ---------------------------------------------------------------------------

HELP_SEEKING_EN = [
    "Is it a sin to kill yourself?",
    "What happens if you kill yourself?",
    "Is it wrong to want to kill yourself?",
    "Do you go to hell if you kill yourself?",
    "If you kill yourself, do you go to heaven?",
    "Will God forgive you if you kill yourself?",
    "How do I stop wanting to kill yourself",
    "(Is it a sin to kill yourself?)",
]

THEOLOGICAL_EN = [
    "Why did Jesus have to go die on the cross?",
    "Does Paul say you should die to sin daily?",
    "Why did Christ go die for our sins?",
    "You should die to self every day",
]

GENUINE_THREATS_EN = [
    "Go kill yourself",
    "go kill yourself!",
    "Kill yourself.",
    "Just kill yourself",
    "You should kill yourself",
    "Why don't you go kill yourself?",
    "I hope you kill yourself",
    "Nobody would care if you kill yourself",
    "You should die",
    "You should die, loser",
    "Go die",
    "Go die in a fire",
    "Go die for all I care",
    "Go die for your sins",
    "What happens if you kill yourself? Find out, go kill yourself.",
    "Is it a sin to kill yourself? You idiot, go kill yourself.",
]


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("text", HELP_SEEKING_EN)
def test_help_seeking_not_directed_harm_and_compassionate(flt, service, language, text):
    assert flt.find_directed_harm(normalize_text(text)) is None
    result = _fallback(service, text, language)
    assert result.allowed is True
    assert result.compassionate_response_needed is True
    assert result.is_help_seeking is True
    assert result.reason == "possible_help_seeking (fallback)"


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("text", THEOLOGICAL_EN)
def test_theological_phrases_not_blocked(flt, service, language, text):
    assert flt.find_directed_harm(normalize_text(text)) is None
    result = _fallback(service, text, language)
    assert result.allowed is True
    assert result.reason != "directed_harm"


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("text", GENUINE_THREATS_EN)
def test_genuine_english_threats_still_blocked(flt, service, language, text):
    found = flt.find_directed_harm_violation(normalize_text(text), preferred=language)
    assert found is not None and found[0] == "directed_harm"
    result = _fallback(service, text, language)
    assert result.allowed is False
    assert "directed_harm" in result.reason


def test_exempt_helper_unit():
    en = MultiLanguageContentFilter._is_directed_harm_exempt
    text = normalize_text("Is it a sin to kill yourself?")
    m = flt_regex_match(text)
    assert en("en", text, m) is True
    assert en("it", text, m) is False
    assert en("fr", text, m) is False


def flt_regex_match(text):
    return MultiLanguageContentFilter()._directed_harm_regex["en"].search(text)
