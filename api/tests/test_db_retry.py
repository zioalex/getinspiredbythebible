"""
Tests for utils/db_retry.py (BITB-057 Phase 2).

Generalizes the retry-on-transient-disconnect pattern previously bespoke to
chat/service.py::_search_scripture. These tests mirror the disconnect-error
classification tests in test_chat_coverage.py::TestIsDisconnectionError, plus
new coverage for the run_with_disconnect_retry loop itself.
"""

from unittest.mock import AsyncMock

import pytest

from utils.db_retry import is_disconnection_error, run_with_disconnect_retry


class TestIsDisconnectionError:
    """Tests for is_disconnection_error() — mirrors chat/service.py's original suite."""

    def test_matches_asyncpg_connection_dropped_by_name(self):
        class ConnectionDoesNotExistError(Exception):
            pass

        assert is_disconnection_error(ConnectionDoesNotExistError("closed mid-op")) is True

    def test_matches_wrapped_cause(self):
        class InterfaceError(Exception):
            pass

        wrapper = RuntimeError("DBAPIError")
        wrapper.__cause__ = InterfaceError("connection lost")
        assert is_disconnection_error(wrapper) is True

    def test_ignores_unrelated_errors(self):
        assert is_disconnection_error(ValueError("bad query")) is False


class TestRunWithDisconnectRetry:
    """Tests for run_with_disconnect_retry()."""

    @pytest.mark.asyncio
    async def test_transient_error_retries_once_then_succeeds(self):
        class ConnectionDoesNotExistError(Exception):
            pass

        fn = AsyncMock(side_effect=[ConnectionDoesNotExistError("dropped"), "ok"])

        result = await run_with_disconnect_retry(fn, op_name="test_op")

        assert result == "ok"
        assert fn.await_count == 2

    @pytest.mark.asyncio
    async def test_non_transient_error_raises_immediately_without_retry(self):
        fn = AsyncMock(side_effect=ValueError("bad query"))

        with pytest.raises(ValueError):
            await run_with_disconnect_retry(fn, op_name="test_op")

        assert fn.await_count == 1

    @pytest.mark.asyncio
    async def test_exhausted_retries_raise_the_last_error(self):
        class FakeTransientError(Exception):
            pass

        # Name the class ConnectionResetError to match the transient-name set
        # is_disconnection_error() matches on (utils/db_retry.py).
        FakeTransientError.__name__ = "ConnectionResetError"

        errors = [FakeTransientError("1"), FakeTransientError("2")]
        fn = AsyncMock(side_effect=errors)

        with pytest.raises(FakeTransientError) as exc_info:
            await run_with_disconnect_retry(fn, max_attempts=2, op_name="test_op")

        assert exc_info.value is errors[-1]
        assert fn.await_count == 2

    @pytest.mark.asyncio
    async def test_success_on_first_attempt_no_retry(self):
        fn = AsyncMock(return_value="value")

        result = await run_with_disconnect_retry(fn, op_name="test_op")

        assert result == "value"
        assert fn.await_count == 1

    @pytest.mark.asyncio
    async def test_respects_custom_max_attempts(self):
        class InterfaceError(Exception):
            pass

        fn = AsyncMock(side_effect=[InterfaceError("1"), InterfaceError("2"), "ok"])

        result = await run_with_disconnect_retry(fn, max_attempts=3, op_name="test_op")

        assert result == "ok"
        assert fn.await_count == 3
