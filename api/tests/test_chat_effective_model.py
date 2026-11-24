"""BITB-311: chat responses report the model the provider really uses.

Under Compose, ``LLM_MODEL`` is now empty and the Ollama model comes from
``OLLAMA_LLM_MODEL``. The paths in ``chat/service.py`` that fill ``model`` from
settings (scripture-unavailable reply, clarification stream metadata) must use
``effective_llm_model``. Otherwise the response and the feedback ``model_used`` say
``llama3:8b`` while Ollama runs ``mistral:7b``.
"""

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chat.service import ChatRequest, ChatService, _SafetyOutcome
from config import Settings
from providers.base import LLMResponse
from providers.claude import DEFAULT_CLAUDE_MODEL

CLEAN = _SafetyOutcome(allowed=True, compassionate=False, reason="clean", categories={})


def _service():
    llm = MagicMock()
    llm.chat = AsyncMock(return_value=LLMResponse(content="ok", model="m", provider="p"))
    emb = MagicMock()
    emb.embed = AsyncMock()
    return ChatService(MagicMock(), llm, emb)


def _patched(service, cfg: Settings, path: str) -> ExitStack:
    stack = ExitStack()
    stack.enter_context(patch("chat.service.settings", cfg))
    stack.enter_context(
        patch.object(service, "_check_content_safety", AsyncMock(return_value=CLEAN))
    )
    intent = "NEEDS_CLARIFICATION" if path == "clarification" else "COMFORT"
    stack.enter_context(patch.object(service, "_detect_intent", AsyncMock(return_value=intent)))
    stack.enter_context(
        patch.object(
            service, "_wants_clarification", MagicMock(return_value=path == "clarification")
        )
    )
    stack.enter_context(
        patch.object(service, "_search_scripture", AsyncMock(return_value=(None, "")))
    )
    stack.enter_context(
        patch.object(
            service,
            "_scripture_grounding_unavailable",
            MagicMock(return_value=path == "scripture_unavailable"),
        )
    )
    stack.enter_context(patch("chat.service.get_translation_info", return_value=None))
    return stack


def _settings(monkeypatch, **env):
    for key in ("LLM_MODEL", "OLLAMA_LLM_MODEL", "LLM_PROVIDER"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None, anthropic_api_key="x")


CASES = [
    # Compose Ollama stack: LLM_MODEL blank, OLLAMA_LLM_MODEL supplies the model.
    (
        {"LLM_PROVIDER": "ollama", "LLM_MODEL": "", "OLLAMA_LLM_MODEL": "mistral:7b"},
        "mistral:7b",
    ),
    # Compose with LLM_PROVIDER=claude: the Claude default, never the Ollama name.
    (
        {"LLM_PROVIDER": "claude", "LLM_MODEL": "", "OLLAMA_LLM_MODEL": "mistral:7b"},
        DEFAULT_CLAUDE_MODEL,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("env,expected", CASES)
async def test_scripture_unavailable_reply_reports_effective_model(monkeypatch, env, expected):
    cfg = _settings(monkeypatch, **env)
    service = _service()
    with _patched(service, cfg, "scripture_unavailable"):
        response = await service.chat(ChatRequest(message="I am struggling", language="en"))
    assert response.model == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("env,expected", CASES)
async def test_clarification_stream_metadata_reports_effective_model(monkeypatch, env, expected):
    cfg = _settings(monkeypatch, **env)
    service = _service()
    events = []
    with _patched(service, cfg, "clarification"):
        async for event in service.chat_stream(ChatRequest(message="help", language="en")):
            events.append(event)
    metadata = [e for e in events if e.get("type") == "metadata"]
    assert metadata, events
    assert all(e["model"] == expected for e in metadata)


def test_service_never_reads_raw_llm_model():
    """Guard: the raw setting is wrong for Claude and for the Compose Ollama stack."""
    source = (Path(__file__).resolve().parents[1] / "chat" / "service.py").read_text("utf-8")
    assert "settings.llm_model" not in source
