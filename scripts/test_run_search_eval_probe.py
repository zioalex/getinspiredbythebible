"""Tests for run_search_eval.py's --probe-embedding mode (BITB-107).

--probe-embedding needs no database, so this monkeypatches the app's real
provider factory (providers.factory.create_embedding_provider) rather than
spinning up Postgres. Follows the sys.path-insert style of
scripts/migrations/test_run_migrations.py.
"""

import argparse
import os
import sys
from unittest.mock import AsyncMock

import pytest

# Make both `scripts/` (for run_search_eval) and `api/` (for config,
# providers.factory) importable, mirroring run_search_eval.py's own
# sys.path setup.
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_API_DIR = os.path.join(os.path.dirname(_SCRIPTS_DIR), "api")
for _dir in (_SCRIPTS_DIR, _API_DIR):
    if _dir not in sys.path:
        sys.path.insert(0, _dir)

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://user:pass@localhost:5432/bibledb",  # pragma: allowlist secret
)

import run_search_eval  # noqa: E402
from config import settings  # noqa: E402

FAKE_SECRET = "sk-super-secret-fake-key-should-never-leak"  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def _azure_settings(monkeypatch):
    """Point settings at a fake Azure config so the probe's printed fields
    (and the code path it exercises) match a real azure_openai deployment."""
    monkeypatch.setattr(settings, "embedding_provider", "azure_openai")
    monkeypatch.setattr(settings, "azure_openai_endpoint", "https://fake.openai.azure.com/")
    monkeypatch.setattr(settings, "azure_embedding_deployment", "text-embedding-3-small")
    monkeypatch.setattr(settings, "embedding_dimensions", 1536)
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", FAKE_SECRET)


def test_probe_embedding_success_exits_zero(monkeypatch, capsys):
    fake_provider = AsyncMock()
    fake_provider.embed.return_value = argparse.Namespace(embedding=[0.0] * 1536)
    monkeypatch.setattr(
        "providers.factory.create_embedding_provider", lambda config: fake_provider
    )

    exit_code = run_search_eval._cmd_probe_embedding(argparse.Namespace())

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "OK" in out
    assert "1536-dimensional" in out


def test_probe_embedding_failure_exits_one_and_hides_secret(monkeypatch, capsys):
    def _raise_provider(config):
        raise RuntimeError("boom: connection error")

    monkeypatch.setattr("providers.factory.create_embedding_provider", _raise_provider)

    exit_code = run_search_eval._cmd_probe_embedding(argparse.Namespace())

    assert exit_code == 1
    captured = capsys.readouterr()
    assert FAKE_SECRET not in captured.out
    assert FAKE_SECRET not in captured.err
    assert "RuntimeError" in captured.err


def test_probe_embedding_prints_key_length_not_key(monkeypatch, capsys):
    fake_provider = AsyncMock()
    fake_provider.embed.return_value = argparse.Namespace(embedding=[0.0] * 1536)
    monkeypatch.setattr(
        "providers.factory.create_embedding_provider", lambda config: fake_provider
    )

    run_search_eval._cmd_probe_embedding(argparse.Namespace())

    out = capsys.readouterr().out
    assert FAKE_SECRET not in out
    assert f"api key length:                     {len(FAKE_SECRET)}" in out
