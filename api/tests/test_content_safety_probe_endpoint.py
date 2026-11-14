"""BITB-291: POST /health/content-safety-probe is monitor-secret-only and side-effect free."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
from utils.content_safety import ContentSafetyCheckResult
from utils.monitor_probe import PROBE_HEADER

client = TestClient(app)
URL = "/health/content-safety-probe"
SECRET = "probe-secret-value"  # pragma: allowlist secret


@pytest.fixture
def secrets():
    with patch("utils.monitor_probe.settings") as s:
        s.monitor_probe_secret = SECRET
        s.smoke_probe_secret = None
        yield s


@pytest.fixture
def service():
    svc = MagicMock()
    svc.check = AsyncMock(
        return_value=ContentSafetyCheckResult(
            allowed=False, reason="violence", decided_by="llama_guard"
        )
    )
    with patch("routes.health.get_content_safety_service", return_value=svc):
        yield svc


def _post(body, headers=None):
    return client.post(URL, json=body, headers=headers or {})


def test_404_without_header(secrets, service):
    r = _post({"message": "hi"})
    assert r.status_code == 404
    assert r.json() == client.get("/definitely-not-a-route").json()
    service.check.assert_not_called()


def test_404_with_wrong_secret(secrets, service):
    assert _post({"message": "hi"}, {PROBE_HEADER: "nope"}).status_code == 404
    service.check.assert_not_called()


def test_404_when_secrets_unset(service):
    with patch("utils.monitor_probe.settings") as s:
        s.monitor_probe_secret = None
        s.smoke_probe_secret = None
        assert _post({"message": "hi"}, {PROBE_HEADER: SECRET}).status_code == 404


def test_404_before_validation_for_unauthorized(secrets, service):
    """A bad body from an unauthorized caller must not reveal the route via 422."""
    assert _post({"message": ""}).status_code == 404


def test_200_with_correct_secret(secrets, service):
    with patch("feedback.blocked_samples.record_blocked_sample", new_callable=AsyncMock) as rec:
        r = _post({"message": "I want to build a bomb", "language": "en"}, {PROBE_HEADER: SECRET})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"allowed", "decided_by", "failover", "ml_path", "reason", "duration_ms"}
    assert body["allowed"] is False and body["decided_by"] == "llama_guard"
    assert body["ml_path"] is True and body["failover"] is False
    service.check.assert_awaited_once_with("I want to build a bomb", "en")
    rec.assert_not_called()


@pytest.mark.parametrize(
    "decided_by,ml",
    [
        ("llama_guard", True),
        ("openai_moderation", True),
        ("azure", True),
        ("keyword_fallback", False),
        ("stage1_keywords", False),
        ("default_allow", False),
        ("disabled", False),
    ],
)
def test_ml_path_flag(secrets, service, decided_by, ml):
    service.check.return_value = ContentSafetyCheckResult(allowed=True, decided_by=decided_by)
    body = _post({"message": "hi"}, {PROBE_HEADER: SECRET}).json()
    assert body["ml_path"] is ml


def test_smoke_secret_also_authorizes(service):
    with patch("utils.monitor_probe.settings") as s:
        s.monitor_probe_secret = None
        s.smoke_probe_secret = "smoke-secret"  # pragma: allowlist secret
        assert _post({"message": "hi"}, {PROBE_HEADER: "smoke-secret"}).status_code == 200


def test_never_records_blocked_sample(secrets, service):
    import routes.health as health

    assert "record_blocked_sample" not in vars(health)


@pytest.mark.parametrize(
    "body", [{"message": ""}, {"message": "x" * 501}, {}, {"message": "a", "language": "x" * 9}]
)
def test_422_on_invalid_body(secrets, service, body):
    assert _post(body, {PROBE_HEADER: SECRET}).status_code == 422


def test_max_length_message_accepted(secrets, service):
    assert _post({"message": "x" * 500}, {PROBE_HEADER: SECRET}).status_code == 200


def test_disabled_service_reports_disabled(secrets):
    with patch("utils.content_safety.settings") as cs:
        cs.content_safety_enabled = False
        r = _post({"message": "hi"}, {PROBE_HEADER: SECRET})
    assert r.json()["decided_by"] == "disabled" and r.json()["ml_path"] is False


def test_route_not_in_openapi():
    app.openapi_schema = None
    assert not any("content-safety-probe" in p for p in app.openapi()["paths"])
