"""
BITB-238: English "kill yourself" / "go die" / "you should die" question and theological
forms are no longer blocked at Stage 1 as directed harm.

Stage 1 runs every language's directed-harm table under all 11 language codes (BITB-193), so
the English phrases must be context-sensitive: genuine second-person threats still block,
while help-seeking questions go to the compassionate path and theology passes through.
"""

import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from chat.service import ChatService
from utils.content_safety import ContentSafetyService
from utils.security import MultiLanguageContentFilter, normalize_text

LANGUAGES = ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"]

HELP_SEEKING = [
    "Is it a sin to kill yourself?",
    "What happens if you kill yourself?",
    "Is it wrong to kill yourself?",
    "Is it a sin to kill  yourself?",
    "Is it ok to kill yourself?",
    "Will God forgive you if you kill yourself?",
]

THEOLOGICAL = [
    "Why did Jesus have to go die on the cross?",
    "Does Paul say you should die to sin daily?",
    "Jesus had to go die for our sins",
    "We must die to self daily",
    "Why did Jesus go die on the cross?",
]


def test_long_input_has_no_backtracking_blowup(flt):
    text = ("a " * 20000) + "go die"
    start = time.monotonic()
    assert flt.find_directed_harm_violation(normalize_text(text)) is not None
    assert time.monotonic() - start < 2


THREATS = [
    "Go kill yourself",
    "You should die",
    "Kill yourself",
    "Why don't you just kill yourself?",
    "You should kill yourself?",
    "Go die",
    "You should die in a fire",
    "Is it a sin to kill yourself? Go kill yourself",
    # BITB-238 verifier probes: exemptions must not be over-broad
    "go die for all I care",
    "go die for the sake of everyone",
    "Go die on the cross like your Jesus",
    "Why did you go die",
    "did u go die",
    "you have to go die",
    "you had to go die",
    "you should die daily you worthless idiot",
    "you should die to yourself... in a fire",
    "it is okay to kill yourself",
    "it is not a sin to kill yourself, so do it",
    "Is it a sin to kill yourself, so do it?",
    "You should   die",
]


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(
        "utils.content_safety.settings",
        MagicMock(
            content_safety_enabled=True,
            content_safety_mode="keyword_only",
            azure_content_safety_enabled=False,
        ),
    )
    return ContentSafetyService()


@pytest.fixture(scope="module")
def flt():
    return MultiLanguageContentFilter()


def _fallback(service, text, language):
    return service._full_keyword_fallback(text, language, time.monotonic())


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("text", HELP_SEEKING + THEOLOGICAL)
def test_question_and_theology_not_blocked_at_stage1(flt, language, text):
    assert flt.check_multilingual(text, language)[0] is False
    assert flt.find_directed_harm(normalize_text(text)) is None


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("text", HELP_SEEKING[:2])
def test_help_seeking_fallback_is_compassionate(service, language, text):
    result = _fallback(service, text, language)
    assert result.allowed is True
    assert result.compassionate_response_needed is True
    assert result.is_help_seeking is True


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("text", THEOLOGICAL)
def test_theology_fallback_allowed_not_compassionate(service, language, text):
    result = _fallback(service, text, language)
    assert result.allowed is True
    assert result.compassionate_response_needed is False


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("text", THREATS)
def test_threats_still_block_at_stage1_and_fallback(flt, service, language, text):
    blocked, confidence, vtype, pattern = flt.check_multilingual(text, language)
    assert (blocked, confidence, vtype) == (True, "high", "directed_harm")
    assert pattern
    result = _fallback(service, text, language)
    assert result.allowed is False
    assert result.reason.startswith("keyword_violation:directed_harm")


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("text", HELP_SEEKING[:2])
async def test_check_help_seeking_not_blocked(service, language, text):
    result = await service.check(text, language)
    assert result.allowed is True
    assert result.compassionate_response_needed is True


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("text", THEOLOGICAL)
async def test_check_theology_not_blocked(service, language, text):
    result = await service.check(text, language)
    assert result.allowed is True
    assert result.compassionate_response_needed is False


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("text", THREATS)
async def test_check_threats_blocked(service, language, text):
    result = await service.check(text, language)
    assert result.allowed is False
    assert "directed_harm" in (result.reason or "")


def _chat_service():
    embedding = MagicMock()
    embedding.embed = AsyncMock(return_value=MagicMock(embedding=[0.1] * 1536))
    return ChatService(MagicMock(), MagicMock(), embedding)


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("text", HELP_SEEKING[:2] + THREATS[:2])
async def test_chat_service_check_content_safety(service, language, text):
    chat = _chat_service()
    with (
        patch("chat.service.settings") as mock_settings,
        patch("chat.service.get_content_safety_service", return_value=service),
    ):
        mock_settings.content_safety_enabled = True
        outcome = await chat._check_content_safety(text, language, None)
    if text in HELP_SEEKING:
        assert outcome.allowed is True
        assert outcome.compassionate is True
    else:
        assert outcome.allowed is False
