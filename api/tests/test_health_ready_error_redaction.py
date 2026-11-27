"""BITB-317: the public /health/ready probe must not echo raw DB exception text."""

import logging
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from routes.health import (
    _PUBLIC_DB_TIMEOUT_ERROR,
    _PUBLIC_DB_UNAVAILABLE_ERROR,
    check_database_health,
)

SENTINEL_HOST = "secret-db-host.postgres.database.azure.com"
SENTINEL_USER = "svc_admin_user"
SENTINEL_SQL = "SELECT 1 FROM pg_secret_table"
SENTINEL_TEXT = (
    f'connection to server at "{SENTINEL_HOST}", port 5432 failed: '
    f'FATAL: password authentication failed for user "{SENTINEL_USER}" [SQL: {SENTINEL_SQL}]'
)
SENTINELS = (SENTINEL_HOST, SENTINEL_USER, SENTINEL_SQL, "5432")

client = TestClient(app)


def _factory_raising(exc: Exception) -> MagicMock:
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=exc)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=session)


def _factory_ok() -> MagicMock:
    session = AsyncMock()
    result = MagicMock()
    result.scalar.return_value = 1
    session.execute = AsyncMock(return_value=result)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=session)


def test_ready_503_does_not_leak_exception_text(caplog):
    with (
        patch("routes.health.async_session_factory", _factory_raising(RuntimeError(SENTINEL_TEXT))),
        caplog.at_level(logging.WARNING, logger="routes.health"),
    ):
        response = client.get("/health/ready")

    assert response.status_code == 503
    for sentinel in SENTINELS:
        assert sentinel not in response.text
    body = response.json()
    assert body["error"] == _PUBLIC_DB_UNAVAILABLE_ERROR == "database unavailable"
    assert body["reason"] == "database_unavailable"
    assert body["status"] == "not_ready"
    assert body["dependencies"] == {"database": "unhealthy"}
    # The full exception is still logged for operators.
    assert SENTINEL_HOST in caplog.text


def test_ready_timeout_returns_fixed_message(caplog):
    with (
        patch("routes.health.async_session_factory", _factory_raising(TimeoutError())),
        caplog.at_level(logging.WARNING, logger="routes.health"),
    ):
        response = client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["error"] == _PUBLIC_DB_TIMEOUT_ERROR == "database check timed out"
    assert "after" not in body["error"]
    assert body["reason"] == "database_unavailable"
    assert "timed out" in caplog.text


def test_ready_happy_path_unchanged():
    with patch("routes.health.async_session_factory", _factory_ok()):
        response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert "database_latency_ms" in body
    assert body["dependencies"] == {"database": "healthy"}


@pytest.mark.asyncio
async def test_default_mode_keeps_detail_for_local_only_health():
    with patch(
        "routes.health.async_session_factory", _factory_raising(RuntimeError(SENTINEL_TEXT))
    ):
        result = await check_database_health()
    assert result.status == "unhealthy"
    assert result.error == SENTINEL_TEXT


@pytest.mark.asyncio
async def test_redacted_mode_hides_detail():
    with patch(
        "routes.health.async_session_factory", _factory_raising(RuntimeError(SENTINEL_TEXT))
    ):
        result = await check_database_health(redact_errors=True)
    assert result.error == _PUBLIC_DB_UNAVAILABLE_ERROR


# --- Static guard -----------------------------------------------------------------------
# Public routes must never put raw exception text in a response. Logging it
# (``extra={"error": str(e)}``) is legitimate, so the scan looks only at ``detail=``.
#
# The module list is globbed rather than hardcoded, so a NEW ``api/routes/*.py`` is
# covered automatically. ``api/main.py`` is included too: it hosts public routes of its
# own (``/``, ``/config``, the client-error and tts-event POSTs) plus the global
# ProviderError handler.
#
# ``health.py`` is exempt from the module scan and checked separately below. Its
# ``check_llm_health`` / ``check_embedding_health`` / ``get_memory_info`` helpers keep the
# full detail on purpose, because they surface only through the
# ``require_local_access``-guarded ``GET /health`` (BITB-348 pins that guard).
#
# Known gap, tracked as BITB-349: this is a text scan, so it does not catch
# ``detail=f"...{e}"`` interpolation. ``api/routes/church.py`` has that shape today and
# discloses an upstream HTTP status code only (BITB-351).
_API = Path(__file__).resolve().parent.parent
_ROUTES = _API / "routes"
_EXEMPT_MODULES = {"__init__.py", "health.py"}
# ``str``/``repr`` of the caught exception under any of the usual binding names.
_EXC_CALL = r"(?:str|repr)\((?:error|exc|err|e)\)"
_DETAIL_LEAK = re.compile(rf"detail\s*=\s*{_EXC_CALL}")
_ERROR_LEAK = re.compile(rf"\"error\"\s*:\s*{_EXC_CALL}|error\s*=\s*{_EXC_CALL}")


def _public_source_files() -> list[Path]:
    """Every source file that can answer a request without a local-access guard."""
    modules = [p for p in sorted(_ROUTES.glob("*.py")) if p.name not in _EXEMPT_MODULES]
    return modules + [_API / "main.py"]


def _readiness_probe_source() -> str:
    src = (_ROUTES / "health.py").read_text()
    start = src.index("async def readiness_probe")
    end = re.search(r"^(?:@|def |async def |class )", src[start + 1 :], re.M)
    return src[start : start + 1 + end.start()] if end else src[start:]


def test_scanned_sources_cover_every_public_route_module():
    """Without this, a mis-globbed path would make the guard below silently vacuous."""
    names = {p.name for p in _public_source_files()}
    assert {
        "feedback.py",
        "church.py",
        "scripture.py",
        "chat.py",
        "crisis.py",
        "admin.py",
    } <= names
    assert "main.py" in names
    assert "health.py" not in names


@pytest.mark.parametrize("source", _public_source_files(), ids=lambda p: p.name)
def test_public_sources_do_not_echo_exception_text(source):
    assert _DETAIL_LEAK.search(source.read_text()) is None


def test_readiness_probe_asks_for_redaction():
    """The real regression guard: readiness must request redaction.

    Scanning ``readiness_probe()`` for ``error=str(e)`` alone passes on the PRE-FIX code,
    because the leak lived in ``check_database_health()`` while readiness only reads
    ``db_health.error``. Asserting the ``redact_errors=True`` argument is what actually
    fails if someone reverts the fix.
    """
    source = _readiness_probe_source()
    assert "db_health.error" in source  # sanity: we scanned the right function
    assert "redact_errors=True" in source
    assert _DETAIL_LEAK.search(source) is None
    assert _ERROR_LEAK.search(source) is None
