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
        """Invalid token should fail verification."""
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

            success, error = await verifier.verify("invalid-token")

            assert success is False
            assert "invalid-input-response" in error

    @pytest.mark.asyncio
    async def test_verify_missing_token(self):
        """Missing token should fail."""
        verifier = TurnstileVerifier("test-secret")

        success, error = await verifier.verify("")

        assert success is False
        assert "Missing" in error

    @pytest.mark.asyncio
    async def test_verify_timeout_fails_open(self):
        """Timeout should fail open (allow request)."""
        verifier = TurnstileVerifier("test-secret")

        with patch.object(verifier, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.TimeoutException("Connection timeout")
            mock_get_client.return_value = mock_client

            success, error = await verifier.verify("token")

            # Should fail open on timeout
            assert success is True
            assert error is None

    @pytest.mark.asyncio
    async def test_verify_http_error_fails_open(self):
        """HTTP error should fail open (allow request)."""
        verifier = TurnstileVerifier("test-secret")

        with patch.object(verifier, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.HTTPError("Server error")
            mock_get_client.return_value = mock_client

            success, error = await verifier.verify("token")

            # Should fail open on HTTP error
            assert success is True
            assert error is None


class TestPathSkipping:
    """Tests for path skip logic."""

    def test_should_skip_health_endpoint(self):
        """Health endpoint should be skipped."""
        with patch("utils.turnstile.settings") as mock_settings:
            mock_settings.turnstile_skip_paths = "/health,/docs,/"
            assert _should_skip_path("/health") is True

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
    async def test_get_request_allowed(self):
        """GET requests should be allowed without token."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/api/v1/scripture/search"

        with patch("utils.turnstile.settings") as mock_settings:
            mock_settings.turnstile_enabled = True
            mock_settings.turnstile_secret_key = "test-secret"  # pragma: allowlist secret
            mock_settings.turnstile_skip_paths = "/health"

            # Should not raise
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
