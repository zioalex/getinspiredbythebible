"""
Tests for the probe-gated POST /api/v1/admin/weekly-report endpoint.

No DB or network: the report builder and email send are patched. Focus is on
the auth gate (fail-closed) and the dry-run / send wiring.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from main import app
from reports.weekly_report import (
    ContactStats,
    EngagementStats,
    FeedbackStats,
    WeeklyReport,
)
from scripture import get_db_session

client = TestClient(app)

ENDPOINT = "/api/v1/admin/weekly-report"
SECRET = "probe-secret"  # pragma: allowlist secret
HEADERS = {"X-Monitor-Probe-Secret": SECRET}


def _fake_report() -> WeeklyReport:
    now = datetime(2026, 6, 8, 18, 0, tzinfo=UTC)
    return WeeklyReport(
        window_start=now,
        window_end=now,
        window_days=7,
        feedback=FeedbackStats(
            total=0, positive=0, negative=0, positive_ratio=None, recent_negative=[]
        ),
        contact=ContactStats(total=0, by_subject={}),
        engagement=EngagementStats(
            active_sessions=0,
            new_sessions=0,
            total_messages=0,
            web_sessions=0,
            mobile_sessions=0,
            top_languages=[],
        ),
        feedback_total_prev=0,
        new_sessions_prev=0,
    )


def setup_module():
    app.dependency_overrides[get_db_session] = lambda: MagicMock()


def teardown_module():
    app.dependency_overrides.pop(get_db_session, None)


def test_missing_header_returns_401():
    with patch.object(settings, "monitor_probe_secret", SECRET):
        resp = client.post(ENDPOINT)
    assert resp.status_code == 401


def test_wrong_header_returns_401():
    with patch.object(settings, "monitor_probe_secret", SECRET):
        resp = client.post(ENDPOINT, headers={"X-Monitor-Probe-Secret": "nope"})
    assert resp.status_code == 401


def test_unset_secret_fails_closed():
    """Even a 'correct' header is rejected when the server secret is unset."""
    with patch.object(settings, "monitor_probe_secret", None):
        resp = client.post(ENDPOINT, headers=HEADERS)
    assert resp.status_code == 401


def test_authorized_send():
    with (
        patch.object(settings, "monitor_probe_secret", SECRET),
        patch("routes.admin.build_weekly_report", AsyncMock(return_value=_fake_report())),
        patch("routes.admin.email_service.send_email", return_value=True) as send,
    ):
        resp = client.post(ENDPOINT, headers=HEADERS)

    assert resp.status_code == 200
    body = resp.json()
    assert body["dry_run"] is False
    assert body["email_sent"] is True
    assert "report" in body
    send.assert_called_once()


def test_dry_run_does_not_send():
    with (
        patch.object(settings, "monitor_probe_secret", SECRET),
        patch("routes.admin.build_weekly_report", AsyncMock(return_value=_fake_report())),
        patch("routes.admin.email_service.send_email", return_value=True) as send,
    ):
        resp = client.post(f"{ENDPOINT}?dry_run=true", headers=HEADERS)

    assert resp.status_code == 200
    body = resp.json()
    assert body["dry_run"] is True
    assert body["email_sent"] is False
    send.assert_not_called()
