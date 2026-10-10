"""
BITB-179: keyword self-harm fallback must cover all 11 UI languages.

When ML moderation is unavailable, ``ContentSafetyService._full_keyword_fallback``
is the only thing that triggers the compassionate-response path. These tests
assert that every supported language (including ru/zh/hi/ko, which previously
had no patterns) detects crisis phrasing and does not fire on ordinary
Bible-study questions.
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


def _fallback(service, text, language):
    return service._full_keyword_fallback(text, language, time.monotonic())


# (language, crisis text)
CRISIS = [
    ("en", "I want to die"),
    ("en", "Sometimes I think about suicide."),
    ("en", "I want to end my life"),
    ("en", "I cut myself last night"),
    ("it", "Voglio morire"),
    ("it", "Penso al suicidio"),
    ("de", "Ich will sterben"),
    ("de", "Ich denke an Selbstmord"),
    ("es", "Quiero morir"),
    ("es", "Pienso en el suicidio"),
    ("fr", "Je veux mourir"),
    ("fr", "J'ai des pensées de suicide"),
    ("pt", "Quero morrer"),
    ("pt", "Penso em suicídio"),
    ("ar", "أريد أن أموت"),
    ("ar", "أفكر في الانتحار"),
    ("ru", "Я хочу умереть"),
    ("ru", "Думаю о самоубийстве"),
    ("ru", "Я хочу покончить с собой"),
    ("ru", "Мне хочется порезать себя"),
    ("ru", "Нет смысла жить"),
    ("zh", "我想自杀"),
    ("zh", "我想死"),
    ("zh", "我不想活了"),
    ("zh", "我想结束生命"),
    ("zh", "我想自残"),
    ("hi", "मैं आत्महत्या करना चाहता हूँ"),
    ("hi", "मैं मरना चाहता हूँ"),
    ("hi", "मैं मरना चाहती हूँ"),
    ("hi", "मैं खुद को नुकसान पहुँचाना चाहता हूँ"),
    ("hi", "जीने का कोई मतलब नहीं है"),
    ("ko", "자살하고 싶어요"),
    ("ko", "살기 싫어요"),
    ("ko", "죽어버릴래"),
    ("ko", "살 이유가 없어요"),
    ("zh", "我想去死"),
    ("zh", "我想要死"),
    ("zh", "我想轻生"),
    ("zh", "我想寻死"),
    ("zh", "我想自尽"),
    ("ru", "Не хочу больше жить"),
    ("ru", "Жить не хочу"),
    ("ru", "Мне хочется умереть"),
    ("ru", "Я убью себя"),
    ("ru", "Режу себя"),
    ("hi", "खुदकुशी के विचार आते हैं"),
    ("hi", "\u0959ुद को नुकसान पहुँचाना है"),
    ("hi", "\u0959ुदकुशी"),
    ("hi", "मैं मर जाना चाहता हूँ"),
    ("hi", "\u0959ुद को नु\u0958सान पहुँचाना"),
    ("hi", "ख\u093cुद को नुक\u093cसान पहुँचाना"),
    ("hi", "ख\u093cुद को मार लूँगा"),
    ("hi", "\u0959ुद को मार दूँगा"),
    ("ko", "죽고 싶어요"),
    ("ko", "목숨을 끊고 싶다"),
    ("ko", "자해를 했어요"),
]

# Fullwidth punctuation / wrapped / embedded-in-sentence variants.
CRISIS_VARIANTS = [
    ("zh", "我想自杀！"),
    ("zh", "（我不想活了）"),
    ("zh", "「我想死」，请帮帮我。"),
    ("zh", "最近我很痛苦，真的想结束生命：怎么办？"),
    ("ko", "죽고 싶어요？"),
    ("ko", "（자살하고 싶어요）"),
    ("ko", "「목숨을 끊고 싶다」，도와주세요."),
    ("ko", "요즘 너무 힘들어서 죽고 싶다는 생각이 들어요. 성경이 뭐라고 하나요?"),
    ("ru", "(Я хочу умереть)"),
    ("ru", "Мне очень тяжело, и я хочу покончить с собой. Что говорит Библия?"),
    ("hi", "(मैं आत्महत्या करना चाहता हूँ)"),
    ("hi", "मैं बहुत परेशान हूँ और मरना चाहता हूँ। बाइबल क्या कहती है?"),
    ("hi", "“मैं मरना चाहती हूँ”"),
    ("en", "(I want to die)"),
    ("en", "I feel hopeless and honestly [I want to die]. What does the Bible say?"),
    ("ar", "(أريد أن أموت)"),
    ("it", "[Voglio morire]"),
    ("de", "(Ich will sterben)"),
]

# Ordinary Bible-study questions about death/resurrection.
BENIGN = [
    ("en", "What does the Bible say about death and resurrection?"),
    ("it", "Cosa dice la Bibbia sulla morte e la risurrezione?"),
    ("de", "Was sagt die Bibel über Tod und Auferstehung?"),
    ("es", "¿Qué dice la Biblia sobre la muerte y la resurrección?"),
    ("fr", "Que dit la Bible sur la mort et la résurrection ?"),
    ("pt", "O que a Bíblia diz sobre a morte e a ressurreição?"),
    ("ar", "ماذا يقول الكتاب المقدس عن الموت والقيامة؟"),
    ("ru", "Что говорит Библия о смерти и воскресении?"),
    ("zh", "圣经对死亡和复活有什么说法？"),
    ("zh", "耶稣为什么要为我们死？我想了解死亡的意义。"),
    ("hi", "बाइबल मृत्यु और पुनरुत्थान के बारे में क्या कहती है?"),
    ("hi", "यीशु हमारे लिए क्यों मरा?"),
    ("ko", "성경은 죽음과 부활에 대해 무엇이라고 말합니까?"),
    ("ko", "예수님은 왜 우리를 위해 죽으셨나요?"),
    ("ru", "Почему Иисус умер за нас?"),
    ("zh", "我想死后会去哪里？"),
    ("zh", "我想死後的世界"),
    ("zh", "我不想死后下地狱"),
    ("zh", "想死你了"),
    ("ko", "성경을 문자해석해야 하나요?"),
    ("ko", "저자해설"),
    ("ko", "혼자살고 있는데"),
    ("hi", "वे अपनी जान लेकर भागे"),
    ("zh", "我想要死后上天堂"),
    ("zh", "我想死人会复活"),
    ("zh", "我想死刑是对的吗"),
    ("zh", "我想去死海旅游"),
    ("zh", "我不想活在罪中"),
    ("ko", "죽고 싶지 않아요"),
]


@pytest.mark.parametrize("language,text", CRISIS + CRISIS_VARIANTS)
def test_crisis_phrase_triggers_compassionate_path(service, language, text):
    result = _fallback(service, text, language)
    assert result.allowed is True
    assert result.compassionate_response_needed is True
    assert result.is_help_seeking is True
    assert result.pattern_matched


@pytest.mark.parametrize("language,text", BENIGN)
def test_benign_bible_question_does_not_trigger(service, language, text):
    result = _fallback(service, text, language)
    assert result.allowed is True
    assert result.compassionate_response_needed is not True
    assert result.pattern_matched is None


def test_every_ui_language_has_self_harm_patterns():
    flt = MultiLanguageContentFilter()
    for lang in LANGUAGES:
        assert flt.SELF_HARM_PATTERNS.get(lang), f"no self-harm patterns for {lang}"
        assert lang in flt._self_harm_regex


def test_every_language_has_crisis_and_benign_coverage():
    assert {lang for lang, _ in CRISIS} == set(LANGUAGES)
    assert {lang for lang, _ in BENIGN} == set(LANGUAGES)


@pytest.mark.parametrize("language,text", CRISIS + CRISIS_VARIANTS)
def test_normalize_text_preserves_script(language, text):
    """normalize_text must not mangle ru/zh/hi/ko (leet map only touches ASCII)."""
    normalized = normalize_text(text)
    flt = MultiLanguageContentFilter()
    assert flt._self_harm_regex[language].search(normalized)


@pytest.mark.parametrize("language,text", [c for c in CRISIS if c[0] in ("zh", "hi", "ko", "ru")])
def test_zero_width_evasion_still_detected(service, language, text):
    """Zero-width chars inserted mid-phrase are stripped before matching."""
    mid = len(text) // 2
    evaded = text[:mid] + "\u200b" + text[mid:]
    result = _fallback(service, evaded, language)
    assert result.compassionate_response_needed is True


def test_cross_language_fallback_to_english(service):
    """English crisis text sent with a ru/zh/hi/ko UI language still triggers."""
    for lang in ("ru", "zh", "hi", "ko"):
        result = _fallback(service, "I want to die", lang)
        assert result.compassionate_response_needed is True
