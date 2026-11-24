"""
BITB-203 / BITB-204: common suicidal phrasings must reach the compassionate path in the
keyword fallback (ML moderation down), in all 11 UI languages.

Before the fix "I feel suicidal", "Quiero suicidarme", "Хочу себя убить", "我想杀了我自己",
"나를 죽이고 싶어" ... all returned ``clean (fallback)``. Murder-suicide phrasings that now
have a self-harm span ("... and take everyone with me") reach the AMBIGUOUS crisis block.

Decision (BITB-203): a murder-suicide third-party match WITHOUT any self-harm span is NOT
escalated, because "Pray for me and my family." would then be blocked. The ambiguity is
reached through the new self-harm spans instead.
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.content_safety import AMBIGUOUS_REASON, ContentSafetyService

LANGUAGES = ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"]
HELP = "possible_help_seeking (fallback)"
CLEAN = "clean (fallback)"


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(
        "utils.content_safety.settings",
        MagicMock(
            content_safety_enabled=True,
            content_safety_mode="hybrid",
            azure_content_safety_enabled=False,
            content_safety_second_opinion_enabled=False,
        ),
    )
    return ContentSafetyService()


def _fallback(service, text, language):
    return service._full_keyword_fallback(text, language, time.monotonic())


CRISIS = [
    # (language, text) -- each was clean on main unless noted
    ("en", "I feel suicidal"),
    ("en", "I want to end it all"),
    ("en", "I keep thinking about taking my own life"),
    ("en", "I keep killing myself over this in my head"),
    ("en", "Sometimes I want to be dead"),
    ("en", "I'd be better off dead"),
    ("it", "Voglio suicidarmi"),
    ("it", "Mi voglio suicidare"),
    ("it", "Voglio farla finita"),
    ("it", "Voglio togliermi la vita"),
    ("de", "Ich bin suizidal"),
    ("de", "Ich bringe mich um"),
    ("de", "Ich will mich selbst töten"),
    ("de", "Ich will mir das Leben nehmen"),
    ("de", "Ich will nicht mehr leben"),
    ("es", "Quiero suicidarme"),
    ("es", "Me quiero suicidar"),
    ("es", "Quiero quitarme la vida"),
    ("es", "Me quiero morir"),
    ("fr", "Je veux me suicider"),
    ("fr", "Je veux mettre fin à mes jours"),
    ("fr", "Je suis suicidaire"),
    ("fr", "Je veux en finir"),
    ("pt", "Quero me suicidar"),
    ("pt", "Quero suicidar-me"),
    ("pt", "Quero tirar minha própria vida"),
    ("ar", "أريد أن أنتحر"),
    ("ar", "سأنتحر الليلة"),
    ("ru", "Хочу себя убить"),
    ("ru", "Я хочу покончить с жизнью"),
    ("zh", "我想杀了我自己"),
    ("zh", "我想杀死自己"),
    ("zh", "我想殺了自己"),
    ("ko", "나를 죽이고 싶어"),
    ("ko", "날 죽이고 싶어"),
    ("hi", "मैं खुद को मार डालना चाहता हूँ"),
]


@pytest.mark.parametrize("language,text", CRISIS)
def test_crisis_phrasing_is_compassionate(service, language, text):
    result = _fallback(service, text, language)
    assert result.allowed is True
    assert result.reason == HELP
    assert result.compassionate_response_needed is True


def test_every_language_has_a_crisis_case():
    assert {lang for lang, _ in CRISIS} == set(LANGUAGES)


MURDER_SUICIDE = [
    ("en", "I want to end it all and take everyone with me"),
    ("de", "Ich bringe mich um und nehme alle mit"),
    ("zh", "我想杀了自己和家人"),
    ("hi", "मैं खुद को और अपने परिवार को मारना चाहता हूँ"),
    ("es", "Quiero suicidarme y llevarme a todos conmigo"),
]


@pytest.mark.parametrize("language,text", MURDER_SUICIDE)
def test_murder_suicide_is_ambiguous_crisis_block(service, language, text):
    result = _fallback(service, text, language)
    assert result.reason == AMBIGUOUS_REASON
    assert result.allowed is False
    assert result.is_help_seeking is True


# Benign / Bible-study inputs. Expected reasons are the behaviour on main BEFORE this change
# and must not move. (Third-person suicide questions in zh/ko/hi/en-Saul were already
# compassionate via 自杀 / 자살 / आत्महत्या / "suicide"; en "Judas kill himself" is a violence block.)
BENIGN = [
    ("en", "Pray for me and my family.", CLEAN),
    ("it", "Prega per me e la mia famiglia.", CLEAN),
    ("de", "Bete für mich und meine Familie.", CLEAN),
    ("es", "Ora por mí y mi familia.", CLEAN),
    ("fr", "Priez pour moi et ma famille.", CLEAN),
    ("pt", "Ore por mim e minha família.", CLEAN),
    ("ar", "صلّ من أجلي ومن أجل عائلتي", CLEAN),
    ("ru", "Помолитесь за меня и мою семью.", CLEAN),
    ("zh", "请为自己和家人祈祷。", CLEAN),
    ("hi", "मैं अपने परिवार के लिए प्रार्थना करना चाहता हूँ", CLEAN),
    ("ko", "하나님은 나를 사랑하실까?", CLEAN),
    ("ko", "하나님이 나를 죽이고 싶어하실까?", CLEAN),
    ("en", "Is it a sin to end a marriage?", CLEAN),
    ("en", "I want to end my addiction", CLEAN),
    ("en", "What does the Bible say about the end of all things?", CLEAN),
    ("es", "acabar con el pecado", CLEAN),
    ("es", "Dios me ayudará a acabar con todo mal", CLEAN),
    ("fr", "Je veux en finir avec le péché", CLEAN),
    ("pt", "Quero acabar com tudo que é mau", CLEAN),
    ("it", "Voglio farla finita con il peccato", CLEAN),
    ("de", "Ich möchte nicht mehr leben wie früher, sondern neu anfangen", CLEAN),
    ("zh", "他杀了自己的儿子吗？", CLEAN),
    ("zh", "他杀了自己", CLEAN),
    ("zh", "她想杀死自己的敌人吗", CLEAN),
    ("it", "Perché Giuda si è suicidato?", CLEAN),
    ("es", "¿Por qué Judas se suicidó?", CLEAN),
    ("fr", "Pourquoi Judas s'est-il suicidé ?", CLEAN),
    ("pt", "Por que Judas se suicidou?", CLEAN),
    ("de", "Warum hat Judas sich umgebracht?", CLEAN),
    ("ru", "Почему Иуда убил себя?", CLEAN),
    ("ar", "لماذا انتحر يهوذا؟", CLEAN),
    ("en", "Judas took his own life", CLEAN),
    ("en", "Samson wanted to be dead", CLEAN),
    ("en", "Did Saul commit suicide?", HELP),
    ("zh", "犹大为什么自杀？", HELP),
    ("ko", "유다는 왜 자살했나요?", HELP),
    ("hi", "यहूदा ने आत्महत्या क्यों की?", HELP),
    ("en", "Why did Judas kill himself?", "keyword_violation:violence (fallback)"),
]


@pytest.mark.parametrize("language,text,reason", BENIGN)
def test_benign_behaviour_unchanged(service, language, text, reason):
    assert _fallback(service, text, language).reason == reason


def test_every_language_has_a_benign_case():
    assert {lang for lang, _, _ in BENIGN} == set(LANGUAGES)


@pytest.mark.asyncio
@pytest.mark.parametrize("language,text", [("en", "I feel suicidal"), ("ko", "나를 죽이고 싶어")])
async def test_async_keyword_fallback_end_to_end(service, language, text):
    result = await service._keyword_fallback(text, language, time.monotonic())
    assert result.allowed is True
    assert result.reason == HELP
    assert result.compassionate_response_needed is True
