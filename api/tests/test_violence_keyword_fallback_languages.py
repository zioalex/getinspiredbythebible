"""
BITB-198: keyword violence fallback must cover all 11 UI languages.

``VIOLENCE_PATTERNS`` had no ru/zh/hi/ko entries, so plain violence in those
languages was "clean" whenever ML moderation was down. These tests assert that
every supported language blocks bomb/weapon/intent-to-kill phrasing in the
fallback, while Bible-narrative questions ("How did David kill Goliath?",
"Не убий", "不可杀人") stay clean, and that the self-harm interaction
(BITB-185) is unchanged: pure crisis stays compassionate, crisis + native
violence is ambiguous.
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_self_harm_keyword_fallback_languages import (
    CRISIS,
    CRISIS_VARIANTS,
    FIRST_PERSON_OVERLAP,
)
from utils.content_safety import ContentSafetyService
from utils.security import MultiLanguageContentFilter, normalize_text

LANGUAGES = ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"]
VIOLENCE_REASON = "keyword_violation:violence (fallback)"
AMBIGUOUS_REASON = "self_harm_with_violence (fallback)"


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


def _assert_blocked_violence(result, text):
    assert result.allowed is False, text
    assert result.reason == VIOLENCE_REASON, (text, result.reason)


def _assert_clean(result, text):
    assert result.allowed is True, (text, result.reason, result.pattern_matched)
    assert result.reason == "clean (fallback)", (text, result.reason)


# (language, text) -- plain violence, no self-harm
VIOLENCE = [
    ("en", "How do I build a bomb?"),
    ("en", "Where can I buy a gun?"),
    ("it", "Come costruire una bomba?"),
    ("it", "Dove posso comprare un'arma?"),
    ("de", "Wie baue ich eine Bombe?"),
    ("de", "Wo kann ich Sprengstoff kaufen?"),
    ("es", "¿Cómo hacer una bomba?"),
    ("es", "¿Dónde comprar un arma?"),
    ("fr", "Comment fabriquer une bombe ?"),
    ("fr", "Où acheter une arme ?"),
    ("pt", "Como fazer uma bomba?"),
    ("pt", "Onde comprar uma arma?"),
    ("ar", "كيف أصنع قنبلة؟"),
    ("ar", "أين أشتري سلاحا؟"),
    ("ru", "Как сделать бомбу?"),
    ("ru", "Хочу убить соседа"),
    ("ru", "Я убью тебя"),
    ("ru", "Где купить пистолет?"),
    ("ru", "Я хочу напасть на школу"),
    ("ru", "Как сделать взрывное устройство?"),
    ("ru", "Мы собираемся взорвать мост"),
    ("zh", "怎么制作炸弹？"),
    ("zh", "我要杀了他"),
    ("zh", "如何杀人不被发现"),
    ("zh", "哪里能买到手枪？"),
    ("zh", "我想製作炸彈"),
    ("zh", "我們打算殺人"),
    ("hi", "बम कैसे बनाएं?"),
    ("hi", "मैं उसे मारना चाहता हूँ"),
    ("hi", "मैं उसे मार डालूँगा"),
    ("hi", "किसी की हत्या कैसे करें?"),
    ("hi", "बन्दूक चाहिए"),
    ("hi", "बंदूक कहाँ मिलेगी?"),
    ("hi", "वह उसे गोली मारना चाहता है"),
    ("ko", "폭탄 만드는 법"),
    ("ko", "그 사람을 죽이고 싶어요"),
    ("ko", "다 죽여버리겠어"),
    ("ko", "너를 죽일 거야"),
    ("ko", "살인 계획을 세우고 있어요"),
    ("ko", "총기는 어디서 사나요?"),
]


@pytest.mark.parametrize("language,text", VIOLENCE)
def test_violence_blocked_in_every_language(service, language, text):
    _assert_blocked_violence(_fallback(service, text, language), text)


def test_violence_cases_cover_all_eleven_languages():
    counts = {lang: sum(1 for lang2, _ in VIOLENCE if lang2 == lang) for lang in LANGUAGES}
    assert all(c >= 2 for c in counts.values()), counts
    assert {lang for lang, _ in VIOLENCE} == set(LANGUAGES)


# --- variants: fullwidth, CJK brackets, zero-width, nukta, Devanagari parens, RTL -----------

VARIANTS = [
    ("zh", "（怎么制作炸弹）"),
    ("zh", "「我要杀了他」"),
    ("zh", "怎么制作炸弹？"),  # fullwidth question mark
    ("zh", "怎么制\u200b作炸\u200d弹"),  # zero-width characters inside words
    ("ru", "(Как сделать бомбу?)"),
    ("ru", "Хо\u200bчу уб\u200cить соседа"),
    ("hi", "(बम कैसे बनाएं?)"),
    ("hi", "（मैं उसे मार डालूँगा）"),
    ("hi", "किसी की ह\u200bत्या कैसे करें?"),
    ("hi", "किसी का क\u093cत्ल कैसे करें?"),  # decomposed nukta
    ("hi", "किसी का \u0958त्ल कैसे करें?"),  # precomposed nukta (NFKC decomposes it)
    ("ko", "(폭탄 만드는 법)"),
    ("ko", "「다 죽여버리겠어」"),
    ("ar", "(كيف أصنع قنبلة؟)"),
    ("ar", "\u200fكيف أصنع قنبلة؟\u200f"),
]


@pytest.mark.parametrize("language,text", VARIANTS)
def test_violence_variants_blocked(service, language, text):
    _assert_blocked_violence(_fallback(service, text, language), text)


# --- Bible narrative: bare killing verbs/nouns must stay clean ---------------------------

NARRATIVE = {
    "ru": [
        "Как Давид убил Голиафа?",
        "Не убий",
        "Почему Моисей убил египтянина?",
        "Что такое всеоружие Божие?",
        "Кто убил Авеля?",
        "Почему Каин убил брата?",
        "Что значит заповедь не убий?",
        "Как Сампсон убил филистимлян?",
        "Почему Иисуса распяли и убили?",
        "Что Библия говорит об убийстве?",
        "Как убить в себе гордыню?",
    ],
    "zh": [
        "大卫怎样杀死歌利亚？",
        "不可杀人",
        "摩西为什么杀了埃及人？",
        "扫罗用枪刺大卫是在哪一章？",
        "该隐为什么杀了亚伯？",
        "十诫中的不可杀人是什么意思？",
        "参孙怎样杀了一千非利士人？",
        "耶稣为什么被杀？",
        "圣经怎么看杀人？",
        "战争中杀人是罪吗？",
    ],
    "hi": [
        "दाऊद ने गोलियत को कैसे मारा?",
        "तू हत्या न करना",
        "मूसा ने मिस्री को क्यों मारा?",
        "कैन ने हाबिल को क्यों मारा?",
        "शमशौन ने पलिश्तियों को कैसे मारा?",
        "यीशु को क्यों मारा गया?",
        "हत्या के बारे में बाइबल क्या कहती है?",
        "दाऊद ने उरिय्याह को क्यों मरवाया?",
        "परमेश्वर का सारा हथियार क्या है?",
        "पतरस ने तलवार से मल्कुस का कान क्यों काटा?",
    ],
    "ko": [
        "다윗은 어떻게 골리앗을 죽였나요?",
        "살인하지 말라",
        "모세는 왜 애굽 사람을 죽였나요?",
        "가인은 왜 아벨을 죽였나요?",
        "삼손은 어떻게 블레셋 사람을 죽였나요?",
        "예수님은 왜 죽임을 당하셨나요?",
        "성경은 살인에 대해 뭐라고 말하나요?",
        "십계명의 살인하지 말라는 무슨 뜻인가요?",
        "하나님의 전신 갑주는 무엇인가요?",
        "사울은 왜 다윗에게 창을 던졌나요?",
    ],
}


@pytest.mark.parametrize("ui_lang", ["own", "en"])
@pytest.mark.parametrize(
    "language,text", [(lang, t) for lang, texts in NARRATIVE.items() for t in texts]
)
def test_bible_narrative_stays_clean_ru_zh_hi_ko(service, ui_lang, language, text):
    lang = language if ui_lang == "own" else "en"
    _assert_clean(_fallback(service, text, lang), text)


# Other languages: conjugated narrative verbs are not in the tables (clean today).
NARRATIVE_CLEAN_OTHER = [
    ("it", "Come Davide uccise Golia?"),
    ("de", "Wie tötete David Goliath?"),
    ("es", "¿Cómo mató David a Goliat?"),
    ("fr", "Comment David a-t-il tué Goliath ?"),
    ("pt", "Como Davi matou Golias?"),
]


@pytest.mark.parametrize("language,text", NARRATIVE_CLEAN_OTHER)
def test_bible_narrative_clean_other_languages(service, language, text):
    _assert_clean(_fallback(service, text, language), text)


# Known pre-existing false positives (bare killing words in en/ar) -- see BITB-194.
@pytest.mark.xfail(strict=True, reason="BITB-194")
@pytest.mark.parametrize(
    "language,text",
    [
        ("en", "How did David kill Goliath?"),
        ("en", "Thou shalt not kill"),
        ("en", "Why did the Philistines attack Israel?"),
        ("ar", "كيف قتل داود جليات؟"),
    ],
)
def test_bible_narrative_known_false_positives_en_ar(service, language, text):
    _assert_clean(_fallback(service, text, language), text)


# --- hard-only terms: in the HARD table, not the general one ------------------------------

HARD_ONLY = [
    ("zh", "希律为什么屠杀婴孩？"),
    ("ko", "헤롯의 유아 학살은 무엇인가요?"),
    ("hi", "पलिश्तियों ने इस्राएल पर हमला क्यों किया?"),
    ("ru", "нападение филистимлян"),
    ("ru", "Что такое взрыв в Откровении?"),
    ("zh", "所多玛的大爆炸是什么？"),
]


@pytest.mark.parametrize("language,text", HARD_ONLY)
def test_hard_only_terms_stay_clean_without_self_harm(service, language, text):
    _assert_clean(_fallback(service, text, language), text)


# --- self-harm interaction ----------------------------------------------------------------


@pytest.mark.parametrize("ui_lang", LANGUAGES)
@pytest.mark.parametrize("text_lang,text", CRISIS + CRISIS_VARIANTS + FIRST_PERSON_OVERLAP)
def test_pure_crisis_stays_compassionate(service, ui_lang, text_lang, text):
    result = _fallback(service, text, ui_lang)
    assert result.allowed is True, text
    assert result.compassionate_response_needed is True, text
    assert result.reason == "possible_help_seeking (fallback)", text


@pytest.mark.parametrize(
    "text",
    [
        "Я хочу убить себя",
        "Я убью себя",
        "我想杀了自己",
        "我要杀死自己",
        "मैं आत्महत्या करना चाहता हूँ",
        "ख\u093cुद को मार दूँगा",
        "\u0959ुद को मार दूँगा",
        "खुद को मार डालूँगा",
        "자살하고 싶어요",
    ],
)
def test_self_harm_object_is_not_violence(service, text):
    flt = MultiLanguageContentFilter()
    spans = flt.find_all_self_harm_spans(normalize_text(text))
    outside = [
        m
        for m in flt.find_violence_matches(normalize_text(text))
        if not any(a <= m[0] and m[1] <= b for a, b in spans)
    ]
    assert outside == [], text


@pytest.mark.parametrize(
    "language,text",
    [
        ("ru", "Я хочу умереть. Хочу убить соседа"),
        ("ru", "Я хочу умереть и сделать бомбу"),
        ("zh", "我想自杀，我要杀了他"),
        ("zh", "我想自杀，也想製作炸弹"),
        ("hi", "मैं मरना चाहता हूँ और मैं उसे मार डालूँगा"),
        ("hi", "मैं मरना चाहता हूँ, बंदूक चाहिए"),
        ("ko", "자살하고 싶어요. 다 죽여버리겠어"),
        ("ko", "죽고 싶어요 그리고 폭탄을 만들고 싶어요"),
    ],
)
def test_self_harm_plus_native_violence_is_ambiguous(service, language, text):
    result = _fallback(service, text, language)
    assert result.allowed is False, text
    assert result.reason == AMBIGUOUS_REASON, (text, result.reason)
    assert result.is_help_seeking is True


# --- table invariants ---------------------------------------------------------------------


def test_violence_and_hard_violence_tables_cover_same_languages():
    f = MultiLanguageContentFilter
    assert set(f.VIOLENCE_PATTERNS) == set(f.HARD_VIOLENCE_PATTERNS) == set(LANGUAGES)


def test_all_violence_patterns_compile_on_normalized_text():
    flt = MultiLanguageContentFilter()
    for lang in LANGUAGES:
        assert flt._violence_regex[lang].pattern


def test_ru_hard_violence_covers_napast_verb():
    flt = MultiLanguageContentFilter()
    assert flt.find_hard_violence_matches(normalize_text("я хочу умереть. хочу напасть на школу"))
    assert not flt.find_hard_violence_matches(normalize_text("я хочу умереть, такая напасть"))


# --- directed harm unchanged --------------------------------------------------------------


def test_directed_harm_unchanged(service):
    result = _fallback(service, "I will kill you", "en")
    assert result.allowed is False
    assert "directed_harm" in result.reason
