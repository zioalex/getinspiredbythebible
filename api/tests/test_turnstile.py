"""
Tests for Cloudflare Turnstile verification.

Tests:
- Token verification with mocked Cloudflare API
- Missing/invalid token handling
- Timeout and error handling (fail open)
- Path skipping logic
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.turnstile import (
    TurnstileVerifier,
    _get_client_ip,
    _should_skip_path,
    require_turnstile,
)


class TestTurnstileVerifier:
    """Tests for TurnstileVerifier class."""

    @pytest.mark.asyncio
    async def test_verify_success(self):
        """Valid token should verify successfully."""
        verifier = TurnstileVerifier("test-secret")

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True, "hostname": "example.com"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(verifier, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            success, error = await verifier.verify("valid-token", "192.168.1.1")

            assert success is True
            assert error is None
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_failure(self):
        """Invalid token should fail verification (AC1 regression: explicit
        rejection fails closed) and must NOT trip the breaker or fail-open metric —
        siteverify answering means the endpoint is healthy."""
        verifier = TurnstileVerifier("test-secret")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": False,
            "error-codes": ["invalid-input-response"],
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(verifier, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            with patch("utils.turnstile.turnstile_fail_open_counter") as mock_counter:
                success, error = await verifier.verify("invalid-token")

                assert success is False
                assert "invalid-input-response" in error
                mock_counter.add.assert_not_called()

            assert verifier._breaker.is_open() is False

    @pytest.mark.asyncio
    async def test_verify_missing_token(self):
        """Missing token should fail."""
        verifier = TurnstileVerifier("test-secret")

        success, error = await verifier.verify("")

        assert success is False
        assert "Missing" in error

    @pytest.mark.asyncio
    async def test_verify_timeout_fails_open(self):
        """Timeout should fail open (allow request) and emit the fail-open metric
        with a 'timeout' reason, while the breaker stays closed for an isolated blip."""
        verifier = TurnstileVerifier("test-secret")

        with patch.object(verifier, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.TimeoutException("Connection timeout")
            mock_get_client.return_value = mock_client

            with patch("utils.turnstile.turnstile_fail_open_counter") as mock_counter:
                success, error = await verifier.verify("token")

                # Should fail open on an isolated timeout
                assert success is True
                assert error is None
                mock_counter.add.assert_called_once()
                args, kwargs = mock_counter.add.call_args
                assert args[0] == 1
                assert "timeout" in args[1]["reason"]

            assert verifier._breaker.is_open() is False

    @pytest.mark.asyncio
    async def test_verify_http_error_fails_open(self):
        """HTTP error should fail open (allow request) and emit the fail-open metric
        with a reason derived from the exception type."""
        verifier = TurnstileVerifier("test-secret")

        with patch.object(verifier, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.HTTPError("Server error")
            mock_get_client.return_value = mock_client

            with patch("utils.turnstile.turnstile_fail_open_counter") as mock_counter:
                success, error = await verifier.verify("token")

                # Should fail open on HTTP error
                assert success is True
                assert error is None
                mock_counter.add.assert_called_once()
                args, kwargs = mock_counter.add.call_args
                assert args[0] == 1
                assert "reason" in args[1]

            assert verifier._breaker.is_open() is False

    @pytest.mark.asyncio
    async def test_verify_repeated_transient_errors_trip_breaker(self):
        """Repeated siteverify failures should trip the circuit breaker to fail
        closed, and once open, verify() must short-circuit without re-invoking
        the network client."""
        verifier = TurnstileVerifier("test-secret")
        failure_threshold = verifier._breaker.failure_threshold

        with patch.object(verifier, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.TimeoutException("Connection timeout")
            mock_get_client.return_value = mock_client

            with patch("utils.turnstile.turnstile_fail_open_counter") as mock_counter:
                results = []
                for _ in range(failure_threshold + 2):
                    results.append(await verifier.verify("token"))

                # Failures 1..threshold-1 fail open; the threshold-th call trips
                # the breaker and fails closed; subsequent calls also fail closed.
                for success, _ in results[: failure_threshold - 1]:
                    assert success is True
                for success, _ in results[failure_threshold - 1 :]:
                    assert success is False

                # The network was only ever hit up to (and including) the call
                # that tripped the breaker — later calls short-circuit.
                assert mock_client.post.call_count == failure_threshold

                # The fail-open metric only fires for the isolated blips, not
                # for the call that trips the breaker or any call after.
                assert mock_counter.add.call_count == failure_threshold - 1

        assert verifier._breaker.is_open() is True


class TestPathSkipping:
    """Tests for path skip logic (prefix matching)."""

    def test_should_skip_health_endpoint(self):
        """Health endpoint should be skipped."""
        with patch("utils.turnstile.settings") as mock_settings:
            mock_settings.turnstile_skip_paths = "/health,/docs,/"
            assert _should_skip_path("/health") is True

    def test_should_skip_health_subpath(self):
        """Health subpaths like /health/live should be skipped via prefix."""
        with patch("utils.turnstile.settings") as mock_settings:
            mock_settings.turnstile_skip_paths = "/health,/docs,/"
            assert _should_skip_path("/health/live") is True
            assert _should_skip_path("/health/ready") is True

    def test_should_skip_root(self):
        """Root path should be skipped."""
        with patch("utils.turnstile.settings") as mock_settings:
            mock_settings.turnstile_skip_paths = "/health,/docs,/"
            assert _should_skip_path("/") is True

    def test_should_not_skip_api_path(self):
        """API paths should not be skipped."""
        with patch("utils.turnstile.settings") as mock_settings:
            mock_settings.turnstile_skip_paths = "/health,/docs,/"
            assert _should_skip_path("/api/v1/chat") is False
            assert _should_skip_path("/api/v1/scripture/search") is False

    def test_should_not_match_partial_prefix(self):
        """'/healthz' should NOT match the '/health' skip prefix."""
        with patch("utils.turnstile.settings") as mock_settings:
            mock_settings.turnstile_skip_paths = "/health,/docs"
            assert _should_skip_path("/healthz") is False


class TestClientIPExtraction:
    """Tests for client IP extraction."""

    def test_cf_connecting_ip_header(self):
        """CF-Connecting-IP header should be preferred."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"CF-Connecting-IP": "1.2.3.4"}
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"

        ip = _get_client_ip(mock_request)
        assert ip == "1.2.3.4"

    def test_x_forwarded_for_header(self):
        """X-Forwarded-For header should be used as fallback."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"X-Forwarded-For": "5.6.7.8, 192.168.1.1"}
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"

        ip = _get_client_ip(mock_request)
        assert ip == "5.6.7.8"

    def test_direct_client_ip(self):
        """Direct client IP should be used when no proxy headers."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {}
        mock_request.client = MagicMock()
        mock_request.client.host = "10.0.0.1"

        ip = _get_client_ip(mock_request)
        assert ip == "10.0.0.1"


class TestRequireTurnstile:
    """Tests for require_turnstile dependency."""

    @pytest.mark.asyncio
    async def test_disabled_turnstile_allows_request(self):
        """Disabled Turnstile should allow all requests."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/api/v1/chat"
        mock_request.headers = {}

        with patch("utils.turnstile.settings") as mock_settings:
            mock_settings.turnstile_enabled = False

            # Should not raise
            result = await require_turnstile(mock_request)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_on_skipped_path_allowed(self):
        """GET on a skipped path (health) should be allowed without token."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/health/ready"

        with patch("utils.turnstile.settings") as mock_settings:
            mock_settings.turnstile_enabled = True
            mock_settings.turnstile_secret_key = "test-secret"  # pragma: allowlist secret
            mock_settings.turnstile_skip_paths = "/health,/docs,/"

            # Should not raise — path is skipped
            result = await require_turnstile(mock_request)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_on_api_path_requires_token(self):
        """GET on an API path should require a Turnstile token."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/api/v1/scripture/search"
        mock_request.headers = {}
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"

        with patch("utils.turnstile.settings") as mock_settings:
            mock_settings.turnstile_enabled = True
            mock_settings.turnstile_secret_key = "test-secret"  # pragma: allowlist secret
            mock_settings.turnstile_skip_paths = "/health,/docs,/"

            with pytest.raises(HTTPException) as exc_info:
                await require_turnstile(mock_request)

            assert exc_info.value.status_code == 403
            assert "TURNSTILE_REQUIRED" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_options_request_allowed(self):
        """OPTIONS requests (CORS preflight) should be allowed without token."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "OPTIONS"
        mock_request.url.path = "/api/v1/chat"

        with patch("utils.turnstile.settings") as mock_settings:
            mock_settings.turnstile_enabled = True
            mock_settings.turnstile_secret_key = "test-secret"  # pragma: allowlist secret
            mock_settings.turnstile_skip_paths = "/health"

            result = await require_turnstile(mock_request)
            assert result is None

    @pytest.mark.asyncio
    async def test_missing_token_raises_403(self):
        """Missing token should raise 403."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/api/v1/chat"
        mock_request.headers = {}
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"

        with patch("utils.turnstile.settings") as mock_settings:
            mock_settings.turnstile_enabled = True
            mock_settings.turnstile_secret_key = "test-secret"  # pragma: allowlist secret
            mock_settings.turnstile_skip_paths = "/health"

            with pytest.raises(HTTPException) as exc_info:
                await require_turnstile(mock_request)

            assert exc_info.value.status_code == 403
            assert "TURNSTILE_REQUIRED" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_valid_token_allows_request(self):
        """Valid token should allow request."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/api/v1/chat"
        mock_request.headers = {"X-Turnstile-Token": "valid-token"}
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"

        with patch("utils.turnstile.settings") as mock_settings:
            mock_settings.turnstile_enabled = True
            mock_settings.turnstile_secret_key = "test-secret"  # pragma: allowlist secret
            mock_settings.turnstile_skip_paths = "/health"

            with patch("utils.turnstile.get_turnstile_verifier") as mock_get_verifier:
                mock_verifier = AsyncMock()
                mock_verifier.verify.return_value = (True, None)
                mock_get_verifier.return_value = mock_verifier

                # Should not raise
                result = await require_turnstile(mock_request)
                assert result is None

    @pytest.mark.asyncio
    async def test_invalid_token_raises_403(self):
        """Invalid token should raise 403."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/api/v1/chat"
        mock_request.headers = {"X-Turnstile-Token": "invalid-token"}
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"

        with patch("utils.turnstile.settings") as mock_settings:
            mock_settings.turnstile_enabled = True
            mock_settings.turnstile_secret_key = "test-secret"  # pragma: allowlist secret
            mock_settings.turnstile_skip_paths = "/health"

            with patch("utils.turnstile.get_turnstile_verifier") as mock_get_verifier:
                mock_verifier = AsyncMock()
                mock_verifier.verify.return_value = (False, "Invalid token")
                mock_get_verifier.return_value = mock_verifier

                with pytest.raises(HTTPException) as exc_info:
                    await require_turnstile(mock_request)

                assert exc_info.value.status_code == 403
                assert "TURNSTILE_FAILED" in str(exc_info.value.detail)


class TestTurnstileIntegration:
    """Integration tests with the FastAPI app."""

    def test_chat_endpoint_works_when_disabled(self):
        """Chat endpoint should work when Turnstile is disabled."""
        # This test just verifies the endpoint doesn't break with Turnstile middleware
        # The actual chat functionality is tested elsewhere
        with patch("utils.turnstile.settings") as mock_settings:
            mock_settings.turnstile_enabled = False

            from main import app

            client = TestClient(app)
            # Just check that the endpoint exists and doesn't crash on input validation
            response = client.post("/api/v1/chat", json={"message": "test"})
            # Either 200/503 (LLM) or 429 (rate limit) - not 403 (Turnstile)
            assert response.status_code != 403 or "TURNSTILE" not in response.text
