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
# Public route modules must never put raw exception text in a response. Logging it
# (``extra={"error": str(e)}``) is fine, so the module scan only looks for ``detail=str(e)``.
# health.py is scanned only for readiness_probe(), where any ``error=str(e)`` /
# ``"error": str(e)`` is a leak: its other helpers (check_llm_health, get_memory_info, ...)
# only surface through the require_local_access-guarded GET /health, so they are exempt.
_ROUTES = Path(__file__).resolve().parent.parent / "routes"
_DETAIL_LEAK = re.compile(r"detail\s*=\s*str\(e\)")
_ERROR_LEAK = re.compile(r"\"error\"\s*:\s*str\(e\)|error\s*=\s*str\(e\)")


def _readiness_probe_source() -> str:
    src = (_ROUTES / "health.py").read_text()
    start = src.index("async def readiness_probe")
    end = re.search(r"^(?:@|def |async def |class )", src[start + 1 :], re.M)
    return src[start : start + 1 + end.start()] if end else src[start:]


@pytest.mark.parametrize(
    "module", ["feedback.py", "church.py", "scripture.py", "chat.py", "crisis.py", "admin.py"]
)
def test_public_route_modules_do_not_echo_exception_text(module):
    assert _DETAIL_LEAK.search((_ROUTES / module).read_text()) is None


def test_readiness_probe_does_not_echo_exception_text():
    source = _readiness_probe_source()
    assert "db_health.error" in source  # sanity: we scanned the right function
    assert _DETAIL_LEAK.search(source) is None
    assert _ERROR_LEAK.search(source) is None
