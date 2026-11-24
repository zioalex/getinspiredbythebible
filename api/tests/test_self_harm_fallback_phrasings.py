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
    ("en", "I keep killing myself in my head"),
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
    ("ko", "나를 죽이고 싶다"),
    ("ko", "날죽이고 싶어"),
    ("ko", "나 자신을 죽이고 싶어"),
    ("ko", "내가 나를 죽이고 싶어"),
    ("en", "I'm going to end it all"),
    ("en", "I'm thinking about ending it all"),
    ("en", "Everyone would be better off if I was dead"),
    ("es", "Quiero acabar con todo."),
    ("pt", "Quero acabar com tudo."),
    ("it", "Voglio farla finita ormai"),
    ("hi", "मैं खुद को मार डालना चाहता हूँ"),
    ("en", "I’m going to end it all"),
    ("en", "I’ll end it all tonight"),
    ("en", "I’m better off dead"),
    ("en", "im better off dead"),
    ("en", "im going to end it all"),
    ("de", "Ich will mich selbst töten"),
    ("de", "Ich will mir das Leben nehmen"),
    ("en", "I want to take my own life"),
    ("en", "I keep thinking about taking my own life"),
    ("it", "Voglio ammazzarmi"),
    ("it", "Voglio togliermi la vita"),
    ("it", "Mi voglio suicidare"),
    ("es", "Quiero quitarme la vida"),
    ("fr", "Je veux mettre fin à mes jours"),
    ("pt", "Penso em tirar minha própria vida"),
    ("ko", "나를 죽이고 싶어"),
    ("ko", "나 자신을 죽이고 싶어"),
    ("zh", "我想杀了我自己"),
    ("it", "Voglio farla finita"),
    ("en", "I feel suicidal"),
    ("fr", "Je suis suicidaire"),
    ("es", "Quiero acabar con mi vida"),
    ("pt", "Quero acabar com minha vida"),
    ("ar", "أريد أن أنهي حياتي"),
    ("en", "I want to take my own life"),
    ("en", "I'm going to take my life tonight"),
    ("en", "I keep killing myself"),
    ("en", "I'm gonna end it all"),
    ("it", "Voglio farla finita"),
    ("it", "Voglio farla finita ormai"),
    ("it", "Ho deciso di farla finita stasera"),
    ("ru", "Я хочу покончить с жизнью"),
    ("zh", "我想杀了我自己"),
    ("zh", "我要杀了自己"),
    ("zh", "想杀了自己"),
    ("es", "Quiero acabar con mi vida"),
    ("ar", "أريد أن أنهي حياتي"),
    ("fr", "Je veux en finir"),
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
    ("ko", "그가 나를 죽이려 한다", CLEAN),
    ("ko", "남편이 날 죽이겠다고 협박해요", CLEAN),
    ("ko", "아버지가 나를 죽이려고 해요", CLEAN),
    ("ko", "사탄이 나를 죽이려 해요", CLEAN),
    ("ko", "적들이 날 죽이려고 해요", CLEAN),
    ("ko", "그는 나를 죽이고 싶어해", CLEAN),
    ("ko", "사울이 나를 죽이고 싶어한다", CLEAN),
    ("ko", "사울은 나를 죽이려 했다고 다윗이 말했다", CLEAN),
    ("es", "Quiero acabar con todo el mal", CLEAN),
    ("es", "Quiero acabar con todo el pecado de mi vida", CLEAN),
    ("es", "Quiero acabar con todo lo que me separa de Dios", CLEAN),
    ("pt", "Quero acabar com tudo isso de pecado", CLEAN),
    ("it", "Voglio farla finita con la pornografia", CLEAN),
    ("it", "Voglio farla finita con questa dipendenza", CLEAN),
    ("it", "Come farla finita con l'ansia", CLEAN),
    ("en", "Jesus came to end it all - sin, death and fear", CLEAN),
    ("en", "Let's end it all on a positive note", CLEAN),
    ("en", "I want to end it all with a prayer", CLEAN),
    ("en", "How do I help a suicidal friend?", CLEAN),
    ("en", "Was Saul better off dead?", CLEAN),
    ("en", "I was killing myself with laughter", CLEAN),
    ("de", "Ich will nicht mehr leben für mich selbst", CLEAN),
    ("de", "Ich will nicht mehr leben, wie ich gelebt habe", CLEAN),
    ("zh", "参孙要杀了自己和非利士人", CLEAN),
    ("zh", "要杀了自己里面的骄傲", CLEAN),
    ("zh", "去杀了自己心中的偶像", CLEAN),
    ("de", "Er will mich töten", "keyword_violation:violence (fallback)"),
    ("de", "Mein Mann will mich töten, was soll ich tun?", "keyword_violation:violence (fallback)"),
    ("de", "Jemand versucht, mich zu töten", "keyword_violation:violence (fallback)"),
    ("de", "Sie wollen mich töten, weil ich Christ bin", "keyword_violation:violence (fallback)"),
    ("de", "Er will mir das Leben nehmen", CLEAN),
    ("de", "Er will nicht mehr leben", CLEAN),
    ("en", "He threatened to take my life", CLEAN),
    ("en", "He wants to take my life", CLEAN),
    ("en", "my ex is trying to take my life", CLEAN),
    ("en", "Take my life and let it be consecrated, Lord, to Thee", CLEAN),
    ("en", "God, please take my life into your hands", CLEAN),
    ("en", "They want to take my life savings", CLEAN),
    ("it", "Mio marito vuole ammazzarmi", CLEAN),
    ("it", "Qualcuno vuole togliermi la vita", CLEAN),
    ("it", "Il nemico vuole ammazzarmi", CLEAN),
    ("es", "Me amenazaron con quitarme la vida", CLEAN),
    ("es", "Alguien quiere quitarme la vida", CLEAN),
    ("es", "Mi esposo quiere quitarme la vida", CLEAN),
    ("fr", "Mon mari menace de mettre fin à mes jours", CLEAN),
    ("pt", "Ele quer tirar minha vida", CLEAN),
    ("pt", "Meu marido ameaçou tirar a minha vida", CLEAN),
    ("ko", "형, 나를 죽이고 싶어?", CLEAN),
    ("ko", "다들 나를 죽이고 싶은가 봐", CLEAN),
    ("zh", "有人想杀了我自己都不知道", CLEAN),
    ("hi", "मैं खुद को और अपने बच्चों को मारने से बचाना चाहता हूँ", CLEAN),
    ("hi", "खुद को और परिवार को मारने की धमकी मिली है", CLEAN),
    ("it", "Signore, voglio farla finita col peccato", CLEAN),
    ("it", "Voglio farla finita coi vizi", CLEAN),
    ("it", "Voglio farla finita una volta per tutte con il fumo", CLEAN),
    ("fr", "Mon ami suicidaire", CLEAN),
    ("es", "Quiero acabar con mi vida pasada", CLEAN),
    ("pt", "Quero acabar com minha vida antiga", CLEAN),
    ("ar", "أريد أن أنهي حياتي القديمة", CLEAN),
    ("es", "Mi padre quiere matarme", HELP),
    ("fr", "Mon mari veut me tuer", HELP),
    ("pt", "Meu marido quer me matar", HELP),
    ("de", "Mein Vater will mich umbringen", HELP),
    ("en", "I want to take my life back from addiction", CLEAN),
    ("en", "I need to take my life back", CLEAN),
    ("en", "I'm going to take my life in a new direction with God", CLEAN),
    ("en", "I decided to take my life more seriously", CLEAN),
    ("en", "I want to take my life to the next level spiritually", CLEAN),
    ("en", "I've been killing myself at work all week", CLEAN),
    ("en", "I'm killing myself trying to please everyone", CLEAN),
    ("en", "Stop killing myself over this mistake", CLEAN),
    ("en", "I'm killing myself laughing at this sermon", CLEAN),
    ("en", "I'm gonna end it all — the fighting, the lying", CLEAN),
    ("it", "Giuda voleva farla finita", CLEAN),
    ("it", "Mio figlio vuole farla finita", CLEAN),
    ("it", "Voglio farla finita qui, la discussione è chiusa", CLEAN),
    ("ru", "Почему Иуда решил покончить с жизнью?", CLEAN),
    ("ru", "Мой сын хочет покончить с жизнью", CLEAN),
    ("zh", "约拿想杀了自己吗？", CLEAN),
    ("zh", "以利亚想杀了自己", CLEAN),
    ("zh", "妈妈想杀了自己", CLEAN),
    ("zh", "孩子会杀了自己", CLEAN),
    ("es", "Quiero acabar con mi vida sedentaria", CLEAN),
    ("ar", "أريد أن أنهي حياتي الجامعية", CLEAN),
    ("ar", "سأنهي حياتي المهنية", CLEAN),
    ("fr", "Je veux en finir une fois pour toutes avec le péché", CLEAN),
    ("fr", "Je veux en finir rapidement", CLEAN),
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
