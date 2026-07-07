"""Tests for the client-error reporting endpoint (BITB-066)."""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import _normalize_client_error_type, app  # noqa: E402

client = TestClient(app)


def test_client_errors_accepts_valid_report():
    resp = client.post(
        "/api/v1/client-errors",
        json={"type": "window_onerror", "detail": "boom"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_client_errors_defaults_missing_fields():
    # Empty body is valid — both fields default.
    resp = client.post("/api/v1/client-errors", json={})
    assert resp.status_code == 200


def test_client_errors_rejects_oversized_detail():
    # detail has a max_length of 4096 on the model → 422.
    resp = client.post(
        "/api/v1/client-errors",
        json={"type": "api_failure", "detail": "x" * 5000},
    )
    assert resp.status_code == 422


def test_normalize_client_error_type_bounds_cardinality():
    assert _normalize_client_error_type("window_onerror") == "window_onerror"
    assert _normalize_client_error_type("unhandledrejection") == "unhandledrejection"
    # Turnstile reports (prefixed) collapse to a single label.
    assert _normalize_client_error_type("turnstile_error") == "turnstile"
    # Anything unknown collapses to "other" to bound metric cardinality.
    assert _normalize_client_error_type("some_random_type") == "other"
