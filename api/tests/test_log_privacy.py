"""BITB-265: no info/warning log record may carry the user's message or the LLM expansion text."""

import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from providers.base import LLMResponse
from tests.test_chat_crisis_path import (
    CLEAN,
    LANGUAGES,
    _collect_stream,
    _patched,
    _request,
    _service,
)
from utils.security import ViolationType, log_security_violation

SENTINEL = "ZQXSENTINEL"
EXPANSION_SENTINEL = "QWVEXPANSIONSENTINEL"

# Message must be >50 chars so a leftover [:50] preview would still contain the sentinel.
_PAD = {
    "en": "Please help me with my private worry about",
    "it": "Per favore aiutami con la mia preoccupazione privata su",
    "de": "Bitte hilf mir bei meiner privaten Sorge um",
    "es": "Por favor ayudame con mi preocupacion privada sobre",
    "fr": "Aide-moi s'il te plait avec mon souci prive de",
    "pt": "Por favor ajude me com minha preocupacao privada sobre",
    "ar": "من فضلك ساعدني في قلقي الخاص بشأن",
    "ru": "Пожалуйста помоги мне с моей личной тревогой о",
    "zh": "请帮助我解决我私人的担忧关于这件事情的所有细节",
    "hi": "कृपया मेरी निजी चिंता के बारे में मेरी मदद करें",
    "ko": "제 개인적인 걱정에 대해서 저를 좀 도와주세요 부탁드립니다",
}


def _message(language):
    return f"{SENTINEL} {_PAD[language]} {SENTINEL}"


def _leaks(caplog, *needles):
    leaked = []
    for record in caplog.records:
        if record.levelno < logging.INFO:
            continue
        blob = record.getMessage() + " " + repr(record.__dict__)
        if any(n in blob for n in needles):
            leaked.append((record.name, record.getMessage()))
    return leaked


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGUAGES)
async def test_chat_logs_no_message_text(language, caplog):
    service = _service()
    caplog.set_level(logging.INFO)
    with _patched(service, CLEAN):
        await service.chat(_request(language, message=_message(language)))
    assert any("Language detection" in r.getMessage() for r in caplog.records)
    assert _leaks(caplog, SENTINEL) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGUAGES)
async def test_chat_stream_logs_no_message_text(language, caplog):
    service = _service()
    caplog.set_level(logging.INFO)
    with _patched(service, CLEAN):
        await _collect_stream(service, _request(language, message=_message(language)))
    assert any("Language detection" in r.getMessage() for r in caplog.records)
    assert _leaks(caplog, SENTINEL) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGUAGES)
async def test_expand_query_logs_lengths_only(language, caplog):
    service = _service()
    message = _message(language)
    service.llm.chat = AsyncMock(
        return_value=LLMResponse(
            content=f"peace trust {EXPANSION_SENTINEL}", provider="p", model="m"
        )
    )
    caplog.set_level(logging.INFO)
    result = await service._expand_query(message, language)
    assert EXPANSION_SENTINEL in result  # behaviour unchanged
    done = [r for r in caplog.records if r.getMessage() == "Query expansion completed"]
    assert len(done) == 1
    assert done[0].original_query_chars == len(message)
    assert done[0].expanded_query_chars == len(result)
    assert _leaks(caplog, SENTINEL, EXPANSION_SENTINEL) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_security_violation_log_has_length_not_text(language, caplog):
    caplog.set_level(logging.INFO)
    message = _message(language)
    log_security_violation(ViolationType.PROFANITY, "1.2.3.4", "s1", len(message), "why")
    rec = [r for r in caplog.records if r.getMessage() == "Security violation detected"]
    assert len(rec) == 1 and rec[0].message_length == len(message)
    assert _leaks(caplog, SENTINEL) == []
