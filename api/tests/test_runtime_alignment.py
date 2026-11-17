"""BITB-304: runtime/version alignment and Claude provider model configuration."""

import re
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from config import Settings
from providers.claude import DEFAULT_CLAUDE_MODEL, ClaudeProvider
from providers.factory import create_llm_provider

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_URL = "postgresql://user:pass@localhost:5432/bibledb"  # pragma: allowlist secret


# --------------------------------------------------------------------------- runtime
def test_dockerfile_python_matches_python_version_file():
    expected = (REPO_ROOT / ".python-version").read_text().strip()
    assert re.fullmatch(r"\d+\.\d+", expected), ".python-version must be X.Y"
    froms = re.findall(
        r"^FROM\s+python:(\S+)-slim\b", (REPO_ROOT / "api" / "Dockerfile").read_text(), re.M
    )
    assert len(froms) >= 2, "expected builder and production stages"
    assert set(froms) == {expected}, f"Dockerfile {froms} != .python-version {expected}"


def test_workflows_read_python_version_from_file():
    offenders = []
    for wf in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")):
        for lineno, line in enumerate(wf.read_text().splitlines(), 1):
            if re.search(r"python-version:\s*[\"']?\d", line):
                offenders.append(f"{wf.name}:{lineno}: {line.strip()}")
    assert not offenders, "use python-version-file: .python-version instead:\n" + "\n".join(
        offenders
    )


def test_jobs_checking_out_another_ref_read_python_version_from_workflow_commit():
    """A job that checks out main, a release branch or an older DEPLOY_SHA may land on a commit
    without .python-version (the 2026-11-13 auto-update-prs failure). Such jobs must read the
    version from the workflow commit's sparse checkout at .pyver/ instead."""
    yaml = pytest.importorskip("yaml")
    offenders = []
    for wf in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")):
        jobs = (yaml.safe_load(wf.read_text()) or {}).get("jobs") or {}
        for job_name, job in jobs.items():
            other_ref = False
            for step in job.get("steps") or []:
                uses = step.get("uses") or ""
                with_ = step.get("with") or {}
                if uses.startswith("actions/checkout") and "path" not in with_:
                    other_ref = "ref" in with_
                if uses.startswith("actions/setup-python") and other_ref:
                    if with_.get("python-version-file") != ".pyver/.python-version":
                        offenders.append(f"{wf.name}:{job_name}")
    assert not offenders, "read .pyver/.python-version (see auto-update-prs.yml):\n" + "\n".join(
        offenders
    )


def test_pyproject_tool_targets_match_python_version():
    major_minor = (REPO_ROOT / ".python-version").read_text().strip()
    compact = major_minor.replace(".", "")
    text = (REPO_ROOT / "api" / "pyproject.toml").read_text()
    assert f"py{compact}" in text
    assert f'python_version = "{major_minor}"' in text


# --------------------------------------------------------------------- Claude factory
def _claude_settings(monkeypatch, **overrides):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    return Settings(
        _env_file=None,
        database_url=DB_URL,
        llm_provider="claude",
        anthropic_api_key="sk-ant-test",  # pragma: allowlist secret
        **overrides,
    )


def test_claude_default_is_current_sonnet_not_ollama_name(monkeypatch):
    provider = create_llm_provider(_claude_settings(monkeypatch))
    assert isinstance(provider, ClaudeProvider)
    assert provider.model == DEFAULT_CLAUDE_MODEL
    assert provider.model != "llama3:8b"
    assert provider.model.startswith("claude-")
    assert "20250514" not in provider.model  # retired model


def test_claude_uses_explicit_llm_model_kwarg(monkeypatch):
    provider = create_llm_provider(_claude_settings(monkeypatch, llm_model="claude-custom-1"))
    assert provider.model == "claude-custom-1"


def test_claude_uses_llm_model_env_var(monkeypatch):
    """model_fields_set must reflect env-sourced values, not just constructor kwargs."""
    monkeypatch.setenv("LLM_MODEL", "claude-from-env")
    settings = Settings(
        _env_file=None,
        database_url=DB_URL,
        llm_provider="claude",
        anthropic_api_key="sk-ant-test",  # pragma: allowlist secret
    )
    assert create_llm_provider(settings).model == "claude-from-env"


def test_claude_uses_llm_model_from_dotenv(monkeypatch, tmp_path):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_MODEL=claude-from-dotenv\n")
    settings = Settings(
        _env_file=str(env_file),
        database_url=DB_URL,
        llm_provider="claude",
        anthropic_api_key="sk-ant-test",  # pragma: allowlist secret
    )
    assert create_llm_provider(settings).model == "claude-from-dotenv"


def test_ollama_default_model_unchanged(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    settings = Settings(_env_file=None, database_url=DB_URL, llm_provider="ollama")
    assert settings.llm_model == "llama3:8b"
    with patch("providers.factory.OllamaProvider") as ollama:
        create_llm_provider(settings)
    assert ollama.call_args.kwargs["model"] == "llama3:8b"


@pytest.mark.parametrize("provider", ["openai", "gpt", ""])
def test_unsupported_llm_provider_rejected(provider):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url=DB_URL, llm_provider=provider)


# ------------------------------------------------- Claude request payload / reporting
def test_effective_llm_model_reports_what_the_provider_uses(monkeypatch):
    from providers.factory import effective_llm_model

    assert effective_llm_model(_claude_settings(monkeypatch)) == DEFAULT_CLAUDE_MODEL
    assert (
        effective_llm_model(_claude_settings(monkeypatch, llm_model="claude-custom-1"))
        == "claude-custom-1"
    )


class _FakeStream:
    def __init__(self):
        async def _gen():
            yield "hi"

        self.text_stream = _gen()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.mark.asyncio
async def test_claude_chat_sends_no_temperature():
    """Current Claude models 400 on non-default sampling params (BITB-304 verifier)."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from providers.base import ChatMessage

    provider = ClaudeProvider(api_key="sk-ant-test")  # pragma: allowlist secret
    response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="ok")],
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        stop_reason="end_turn",
    )
    create = AsyncMock(return_value=response)
    provider._client = SimpleNamespace(messages=SimpleNamespace(create=create))
    await provider.chat([ChatMessage(role="user", content="hi")], temperature=0.0)
    sent = create.call_args.kwargs
    assert "temperature" not in sent
    assert "system" not in sent
    assert sent["model"] == DEFAULT_CLAUDE_MODEL


@pytest.mark.asyncio
async def test_claude_stream_sends_no_temperature_and_no_null_system():
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from providers.base import ChatMessage

    provider = ClaudeProvider(api_key="sk-ant-test")  # pragma: allowlist secret
    stream = MagicMock(return_value=_FakeStream())
    provider._client = SimpleNamespace(messages=SimpleNamespace(stream=stream))
    chunks = [
        c
        async for c in provider.chat_stream(
            [ChatMessage(role="user", content="hi")], temperature=0.3
        )
    ]
    assert chunks == ["hi"]
    sent = stream.call_args.kwargs
    assert "temperature" not in sent
    assert "system" not in sent
