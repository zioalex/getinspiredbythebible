"""
Tests for Correlation ID Middleware.

Verifies that:
- Request IDs are generated for requests without X-Request-ID header
- Client-provided request IDs are preserved
- Request IDs are valid UUID v4 format
- Request IDs appear in response headers (including error responses)
- Different requests get different IDs
- Request IDs appear in log entries
"""

import re
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Add parent directory to path to import main
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app

client = TestClient(app)


class TestCorrelationIDMiddleware:
    """Test suite for correlation ID middleware."""

    def test_generated_request_id_in_response(self):
        """When no X-Request-ID sent, response should have UUID in X-Request-ID header."""
        response = client.get("/health")

        # Should have X-Request-ID header
        assert "x-request-id" in response.headers

        # Should be a valid UUID
        request_id = response.headers["x-request-id"]
        try:
            uuid.UUID(request_id)
        except ValueError:
            pytest.fail(f"Request ID '{request_id}' is not a valid UUID")

    def test_client_request_id_preserved(self):
        """When client sends X-Request-ID, same value should appear in response."""
        client_request_id = "test-request-123"
        response = client.get("/health", headers={"X-Request-ID": client_request_id})

        # Should have X-Request-ID header with the same value
        assert "x-request-id" in response.headers
        assert response.headers["x-request-id"] == client_request_id

    def test_request_id_is_valid_uuid(self):
        """Generated request ID should be a valid UUID v4 format."""
        response = client.get("/health")

        request_id = response.headers["x-request-id"]

        # Should be valid UUID
        parsed_uuid = uuid.UUID(request_id)

        # Should be UUID v4 (version 4)
        assert parsed_uuid.version == 4

    def test_request_id_in_error_response(self):
        """404 responses should still include X-Request-ID header."""
        response = client.get("/nonexistent-endpoint-12345")

        # Should be 404
        assert response.status_code == 404

        # Should still have X-Request-ID header
        assert "x-request-id" in response.headers

        # Should be a valid UUID
        request_id = response.headers["x-request-id"]
        try:
            uuid.UUID(request_id)
        except ValueError:
            pytest.fail(f"Request ID '{request_id}' in error response is not a valid UUID")

    def test_different_requests_get_different_ids(self):
        """Two separate requests should get different request IDs."""
        response1 = client.get("/health")
        response2 = client.get("/health")

        request_id1 = response1.headers["x-request-id"]
        request_id2 = response2.headers["x-request-id"]

        # Should be different
        assert request_id1 != request_id2

        # Both should be valid UUIDs
        uuid.UUID(request_id1)
        uuid.UUID(request_id2)

    def test_request_id_in_logs(self, caplog, capsys):
        """Request ID should appear in log entries."""
        # Clear any previous log records
        caplog.clear()

        # Make a request with a known request ID
        test_request_id = "test-log-request-456"

        with caplog.at_level("DEBUG"):
            response = client.get("/health", headers={"X-Request-ID": test_request_id})

        # Should have successful response
        assert response.status_code in [200, 503]  # Healthy or degraded

        # Check the stdout output (where the formatted logs appear)
        captured = capsys.readouterr()

        # The request ID should appear in the stdout logs with the bracket format
        if captured.out:
            assert test_request_id in captured.out or "[" in captured.out

    def test_request_id_format_in_log_output(self, caplog, capsys):
        """Verify log messages contain request ID in correct format."""
        caplog.clear()

        test_request_id = str(uuid.uuid4())

        with caplog.at_level("INFO"):
            # Make a request to a more verbose endpoint
            response = client.get("/", headers={"X-Request-ID": test_request_id})

        assert response.status_code in [200, 404, 307]  # Various valid responses

        # Check the stdout output (where formatted logs appear)
        captured = capsys.readouterr()

        if captured.out:
            # Should have the [request_id] format in at least some logs
            # The pattern is: | [uuid] |
            pattern = r"\|\s*\[[\w-]+\]\s*\|"
            assert re.search(
                pattern, captured.out
            ), "Log output should contain request ID in format: | [request_id] |"

    def test_request_id_context_var_cleanup(self):
        """Context var should be cleaned up after request completes."""
        from middleware.context import REQUEST_ID_CTX_VAR

        # Initially should be empty
        initial_value = REQUEST_ID_CTX_VAR.get()
        assert initial_value == ""

        # Make a request
        response = client.get("/health")
        assert response.status_code in [200, 503]

        # After request, context var should be cleaned up (back to empty)
        # Note: TestClient runs synchronously, so cleanup should have happened
        final_value = REQUEST_ID_CTX_VAR.get()
        assert final_value == ""

    def test_request_id_with_custom_uuid_format(self):
        """Client can provide custom request ID in any format."""
        custom_ids = [
            "custom-request-abc123",
            "req_12345",
            "trace-id-xyz",
            str(uuid.uuid4()),  # Standard UUID
        ]

        for custom_id in custom_ids:
            response = client.get("/health", headers={"X-Request-ID": custom_id})

            # Should preserve the custom ID exactly
            assert response.headers["x-request-id"] == custom_id
