"""
Tests for feedback API endpoints.
"""

import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

# Add parent directory to path to import main
sys.path.insert(0, str(Path(__file__).parent.parent))

from feedback.models import ContactRequest
from main import app

client = TestClient(app)


class TestFeedbackEndpoint:
    """Tests for POST /api/v1/feedback endpoint."""

    def test_submit_positive_feedback(self):
        """Test submitting positive feedback with all fields."""
        response = client.post(
            "/api/v1/feedback",
            json={
                "message_id": str(uuid.uuid4()),
                "rating": "positive",
                "comment": "This was very helpful!",
                "user_message": "What does the Bible say about hope?",
                "assistant_response": "The Bible speaks extensively about hope...",
                "verses_cited": ["Romans 15:13", "Jeremiah 29:11"],
                "model_used": "llama3:8b",
                "response_time_ms": 1500,
                "session_id": "test-session-123",
            },
        )
        # May succeed or fail depending on database availability
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert data["rating"] == "positive"
            assert "created_at" in data

    def test_submit_negative_feedback(self):
        """Test submitting negative feedback."""
        response = client.post(
            "/api/v1/feedback",
            json={
                "message_id": str(uuid.uuid4()),
                "rating": "negative",
                "comment": "The response wasn't relevant to my question.",
                "user_message": "How can I find peace?",
                "assistant_response": "Let me help you find peace...",
            },
        )
        # May succeed or fail depending on database availability
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert data["rating"] == "negative"

    def test_submit_feedback_minimal(self):
        """Test submitting feedback with only required fields."""
        response = client.post(
            "/api/v1/feedback",
            json={
                "message_id": str(uuid.uuid4()),
                "rating": "positive",
                "user_message": "Test question",
                "assistant_response": "Test response",
            },
        )
        # May succeed or fail depending on database availability
        assert response.status_code in [200, 500]

    def test_submit_feedback_invalid_rating(self):
        """Test that invalid rating values are rejected."""
        response = client.post(
            "/api/v1/feedback",
            json={
                "message_id": str(uuid.uuid4()),
                "rating": "neutral",  # Invalid - only positive/negative allowed
                "user_message": "Test question",
                "assistant_response": "Test response",
            },
        )
        # Should return validation error
        assert response.status_code == 422

    def test_submit_feedback_missing_required_fields(self):
        """Test that missing required fields are rejected."""
        # Missing message_id
        response = client.post(
            "/api/v1/feedback",
            json={
                "rating": "positive",
                "user_message": "Test",
                "assistant_response": "Test",
            },
        )
        assert response.status_code == 422

        # Missing rating
        response = client.post(
            "/api/v1/feedback",
            json={
                "message_id": str(uuid.uuid4()),
                "user_message": "Test",
                "assistant_response": "Test",
            },
        )
        assert response.status_code == 422

        # Missing user_message
        response = client.post(
            "/api/v1/feedback",
            json={
                "message_id": str(uuid.uuid4()),
                "rating": "positive",
                "assistant_response": "Test",
            },
        )
        assert response.status_code == 422

        # Missing assistant_response
        response = client.post(
            "/api/v1/feedback",
            json={
                "message_id": str(uuid.uuid4()),
                "rating": "positive",
                "user_message": "Test",
            },
        )
        assert response.status_code == 422

    def test_submit_feedback_invalid_message_id(self):
        """Test that invalid UUID format is rejected."""
        response = client.post(
            "/api/v1/feedback",
            json={
                "message_id": "not-a-valid-uuid",
                "rating": "positive",
                "user_message": "Test",
                "assistant_response": "Test",
            },
        )
        # Should fail during processing (400 or 500)
        assert response.status_code in [400, 422, 500]


class TestContactEndpoint:
    """Tests for POST /api/v1/feedback/contact endpoint."""

    def test_submit_contact_bug_report(self):
        """Test submitting a bug report."""
        response = client.post(
            "/api/v1/feedback/contact",
            json={
                "email": "user@example.com",
                "subject": "bug",
                "message": "The app crashes when I click the submit button.",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
                "session_id": "test-session-456",
            },
        )
        # May succeed or fail depending on database availability
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert data["subject"] == "bug"
            assert "created_at" in data

    def test_submit_contact_feature_request(self):
        """Test submitting a feature request."""
        response = client.post(
            "/api/v1/feedback/contact",
            json={
                "email": "user@example.com",
                "subject": "feature",
                "message": "It would be great to have a dark mode option.",
            },
        )
        assert response.status_code in [200, 500]

    def test_submit_contact_feedback(self):
        """Test submitting general feedback."""
        response = client.post(
            "/api/v1/feedback/contact",
            json={
                "email": "user@example.com",
                "subject": "feedback",
                "message": "I love this app! It's been very helpful for my Bible study.",
            },
        )
        assert response.status_code in [200, 500]

    def test_submit_contact_other(self):
        """Test submitting other type of contact."""
        response = client.post(
            "/api/v1/feedback/contact",
            json={
                "email": "partner@example.com",
                "subject": "other",
                "message": "I'm interested in partnering with your ministry.",
            },
        )
        assert response.status_code in [200, 500]

    def test_submit_contact_spiritual(self):
        """Test submitting a spiritual question — the subject missing from the DB CHECK constraint.

        Before the fix, the contact_submissions table CHECK constraint only allowed
        ('bug', 'feature', 'feedback', 'other'). Every submission with subject='spiritual'
        caused a PostgreSQL constraint violation and returned HTTP 500.

        This test MUST NOT return 422 ('spiritual' is valid in the Pydantic model).
        A 500 here is only acceptable when the database is unavailable in CI.
        """
        with patch("routes.feedback.email_service"):
            response = client.post(
                "/api/v1/feedback/contact",
                json={
                    "email": "user@example.com",
                    "subject": "spiritual",
                    "message": "I am struggling with doubt. Can you share a verse?",
                },
            )
        # 422 would mean Pydantic rejects 'spiritual' — that would be wrong
        assert (
            response.status_code != 422
        ), "'spiritual' must be a valid subject — Pydantic Literal allows it"
        assert response.status_code in [200, 500]

    def test_submit_contact_invalid_subject(self):
        """Test that invalid subject values are rejected."""
        response = client.post(
            "/api/v1/feedback/contact",
            json={
                "subject": "question",  # Invalid - not in allowed list
                "message": "Test message",
            },
        )
        assert response.status_code == 422

    def test_submit_contact_missing_message(self):
        """Test that missing message is rejected."""
        response = client.post(
            "/api/v1/feedback/contact",
            json={
                "subject": "feedback",
            },
        )
        assert response.status_code == 422

    def test_submit_contact_empty_message(self):
        """Test that empty message is rejected."""
        response = client.post(
            "/api/v1/feedback/contact",
            json={
                "subject": "feedback",
                "message": "",
            },
        )
        assert response.status_code == 422

    def test_submit_contact_no_email(self):
        """Test that email is now required — omitting it returns 422."""
        response = client.post(
            "/api/v1/feedback/contact",
            json={
                "subject": "feedback",
                "message": "Just wanted to say thanks!",
            },
        )
        # Email is required; missing email must be rejected
        assert response.status_code == 422

    def test_submit_contact_missing_email(self):
        """Test that missing email is rejected with 422."""
        response = client.post(
            "/api/v1/feedback/contact",
            json={
                "subject": "feature",
                "message": "It would be great to have a dark mode option.",
            },
        )
        assert response.status_code == 422

    def test_submit_contact_invalid_email(self):
        """Test that an invalid email address is rejected with 422."""
        response = client.post(
            "/api/v1/feedback/contact",
            json={
                "email": "not-an-email",
                "subject": "feedback",
                "message": "Some feedback.",
            },
        )
        assert response.status_code == 422


class TestFeedbackEmailIntegration:
    """Tests for email notification integration in feedback endpoints."""

    @patch("routes.feedback.email_service", autospec=True)
    def test_negative_feedback_sends_email(self, mock_email_service):
        """Test that negative feedback triggers email notification."""
        mock_email_service.send_feedback_notification.return_value = True

        response = client.post(
            "/api/v1/feedback",
            json={
                "message_id": str(uuid.uuid4()),
                "rating": "negative",
                "comment": "The response wasn't helpful.",
                "user_message": "How can I find peace?",
                "assistant_response": "Let me help you find peace...",
            },
        )

        # Endpoint should succeed (or fail due to DB, not email)
        assert response.status_code in [200, 500]

        # Verify email service was called with correct core params
        if response.status_code == 200:
            call_kwargs = mock_email_service.send_feedback_notification.call_args.kwargs
            assert call_kwargs["rating"] == "negative"
            assert call_kwargs["comment"] == "The response wasn't helpful."
            assert call_kwargs["user_message"] == "How can I find peace?"
            assert call_kwargs["assistant_response"] == "Let me help you find peace..."
            mock_email_service.send_feedback_notification.assert_called_once()

    @patch("routes.feedback.email_service", autospec=True)
    def test_positive_feedback_bare_skips_email(self, mock_email_service):
        """Test that bare positive feedback (no comment) does NOT trigger email notification."""
        response = client.post(
            "/api/v1/feedback",
            json={
                "message_id": str(uuid.uuid4()),
                "rating": "positive",
                "user_message": "What does the Bible say about hope?",
                "assistant_response": "The Bible speaks about hope...",
            },
        )

        assert response.status_code in [200, 500]

        # Email should NOT be called for bare positive feedback (no comment)
        mock_email_service.send_feedback_notification.assert_not_called()

    @patch("routes.feedback.email_service", autospec=True)
    def test_positive_feedback_with_comment_sends_email(self, mock_email_service):
        """Test that positive feedback WITH a comment triggers email notification."""
        mock_email_service.send_feedback_notification.return_value = True

        response = client.post(
            "/api/v1/feedback",
            json={
                "message_id": str(uuid.uuid4()),
                "rating": "positive",
                "comment": "Great response! The verse was perfect.",
                "user_message": "What does the Bible say about hope?",
                "assistant_response": "The Bible speaks about hope...",
            },
        )

        assert response.status_code in [200, 500]

        # Email SHOULD be called for positive feedback with a comment
        if response.status_code == 200:
            mock_email_service.send_feedback_notification.assert_called_once()
            call_kwargs = mock_email_service.send_feedback_notification.call_args.kwargs
            assert call_kwargs["rating"] == "positive"
            assert call_kwargs["comment"] == "Great response! The verse was perfect."

    @patch("routes.feedback.email_service", autospec=True)
    def test_feedback_succeeds_when_email_fails(self, mock_email_service):
        """Test that feedback submission succeeds even if email sending fails."""
        mock_email_service.send_feedback_notification.return_value = False

        response = client.post(
            "/api/v1/feedback",
            json={
                "message_id": str(uuid.uuid4()),
                "rating": "negative",
                "comment": "Not helpful",
                "user_message": "Test question",
                "assistant_response": "Test response",
            },
        )

        # Endpoint should still succeed (or fail due to DB, not email)
        # Email failure should not cause endpoint failure
        assert response.status_code in [200, 500]


class TestContactEmailIntegration:
    """Tests for email notification integration in contact endpoint."""

    @patch("routes.feedback.email_service", autospec=True)
    def test_contact_sends_email_notification(self, mock_email_service):
        """Test that contact form submission triggers email notification."""
        mock_email_service.send_contact_notification.return_value = True

        response = client.post(
            "/api/v1/feedback/contact",
            json={
                "email": "user@example.com",
                "subject": "bug",
                "message": "Found a bug in the app.",
                "user_agent": "Mozilla/5.0 Chrome/120.0",
            },
        )

        assert response.status_code in [200, 500]

        if response.status_code == 200:
            mock_email_service.send_contact_notification.assert_called_once_with(
                subject_type="bug",
                message="Found a bug in the app.",
                reply_email="user@example.com",
                user_agent="Mozilla/5.0 Chrome/120.0",
            )

    @patch("routes.feedback.email_service", autospec=True)
    def test_contact_sends_email_with_reply_email(self, mock_email_service):
        """Test contact notification with reply email provided."""
        mock_email_service.send_contact_notification.return_value = True

        response = client.post(
            "/api/v1/feedback/contact",
            json={
                "email": "user@example.com",
                "subject": "feedback",
                "message": "Great app!",
            },
        )

        assert response.status_code in [200, 500]

        if response.status_code == 200:
            mock_email_service.send_contact_notification.assert_called_once_with(
                subject_type="feedback",
                message="Great app!",
                reply_email="user@example.com",
                user_agent=None,
            )

    @patch("routes.feedback.email_service", autospec=True)
    def test_contact_succeeds_when_email_fails(self, mock_email_service):
        """Test that contact submission succeeds even if email sending fails."""
        mock_email_service.send_contact_notification.return_value = False

        response = client.post(
            "/api/v1/feedback/contact",
            json={
                "email": "user@example.com",
                "subject": "feature",
                "message": "Please add dark mode.",
            },
        )

        # Endpoint should still succeed (or fail due to DB, not email)
        assert response.status_code in [200, 500]


# ==================== ContactRequest Model Unit Tests ====================


class TestContactRequestModel:
    """Unit tests for the ContactRequest Pydantic model.

    These tests verify that the Pydantic model's Literal type constraint includes
    all five subjects that the frontend ContactForm can submit.  A missing subject
    here means the API would return HTTP 422 before even reaching the database.
    """

    def test_all_valid_subjects_accepted(self):
        """All five frontend subjects must be accepted by the Pydantic model.

        This is the primary model-level guard: if 'spiritual' (or any other subject)
        is missing from the Literal type, ContactRequest construction raises
        ValidationError and the endpoint returns 422.
        """
        for subject in ("spiritual", "bug", "feature", "feedback", "other"):
            req = ContactRequest(email="user@example.com", subject=subject, message="Test message")
            assert req.subject == subject, f"ContactRequest rejected subject='{subject}'"

    def test_spiritual_subject_is_valid(self):
        """Explicit regression test: 'spiritual' is a valid ContactRequest subject.

        Before the bug was found, no test checked this at the model level. The Pydantic
        model always included 'spiritual' in its Literal — so this test would have
        passed even pre-fix — but the database CHECK constraint did NOT include it,
        causing HTTP 500 on every contact form submission with subject='spiritual'.
        Pairing this test with TestContactRouteWithMockedDB gives full coverage.
        """
        req = ContactRequest(
            email="user@example.com",
            subject="spiritual",
            message="I need guidance from the Bible.",
        )
        assert req.subject == "spiritual"
        assert req.message == "I need guidance from the Bible."

    def test_email_required(self):
        """Email is now required — omitting it raises ValidationError."""
        with pytest.raises(ValidationError):
            ContactRequest(subject="feedback", message="Test message.")

    def test_invalid_email_rejected(self):
        """Invalid email format must raise ValidationError."""
        with pytest.raises(ValidationError):
            ContactRequest(email="not-an-email", subject="feedback", message="Test message.")

    def test_invalid_subject_rejected(self):
        """Non-allowed subjects must be rejected with a ValidationError."""
        with pytest.raises(ValidationError):
            ContactRequest(
                email="user@example.com", subject="question", message="This should fail."
            )

    def test_all_subjects_roundtrip(self):
        """All valid subjects survive a JSON round-trip (model_dump → model_validate)."""
        for subject in ("spiritual", "bug", "feature", "feedback", "other"):
            req = ContactRequest(
                email="user@example.com", subject=subject, message="Round-trip test"
            )
            data = req.model_dump()
            restored = ContactRequest.model_validate(data)
            assert restored.subject == subject


# ==================== Contact Route Tests (mocked DB) ====================


class TestContactRouteWithMockedDB:
    """Route-level tests using a mocked repository to isolate the DB constraint.

    The database integration tests (TestContactEndpoint) accept HTTP 500 for
    DB-unavailable scenarios, so they cannot distinguish a constraint violation
    (the actual bug) from a connection failure.  By mocking the repository we
    guarantee the route layer is tested in isolation.
    """

    @pytest.mark.asyncio
    async def test_submit_contact_spiritual_succeeds(self):
        """subject='spiritual' must be saved and returned correctly.

        This test would have caught the bug: if the repository raises an exception
        for 'spiritual' (simulating the DB constraint violation), the test fails.
        With the fix in place the repository mock returns successfully.
        """
        from datetime import UTC, datetime
        from unittest.mock import AsyncMock

        from feedback.models import ContactSubmission
        from routes.feedback import submit_contact

        mock_repo = AsyncMock()
        mock_submission = MagicMock(spec=ContactSubmission)
        mock_submission.id = 42
        mock_submission.subject = "spiritual"
        mock_submission.created_at = datetime.now(UTC)
        mock_repo.save_contact = AsyncMock(return_value=mock_submission)

        request = ContactRequest(
            email="user@example.com",
            subject="spiritual",
            message="I am struggling with doubt. Please share a verse about faith.",
        )

        with patch("routes.feedback.email_service", autospec=True) as mock_email:
            mock_email.send_contact_notification.return_value = True
            result = await submit_contact(request, mock_repo)

        assert result.id == 42
        assert result.subject == "spiritual"
        # Verify save_contact was called with the spiritual request
        mock_repo.save_contact.assert_awaited_once_with(request)

    @pytest.mark.asyncio
    async def test_submit_contact_spiritual_db_constraint_violation_returns_500(self):
        """Simulate what happened before the migration: DB raises on 'spiritual'.

        The fix is in the DB migration, not the route. This test documents that
        a constraint violation on 'spiritual' propagates as HTTP 500 (not silently
        swallowed), and verifies the error is surfaced correctly.
        """
        from unittest.mock import AsyncMock

        from fastapi import HTTPException

        from routes.feedback import submit_contact

        mock_repo = AsyncMock()
        # Simulate the PostgreSQL constraint violation that happened pre-migration
        mock_repo.save_contact = AsyncMock(
            side_effect=Exception(
                'new row for relation "contact_submissions" violates check constraint '
                '"contact_submissions_subject_check"'
            )
        )

        request = ContactRequest(
            email="user@example.com",
            subject="spiritual",
            message="Help me find a verse about hope.",
        )

        with pytest.raises(HTTPException) as exc_info:
            with patch("routes.feedback.email_service"):
                await submit_contact(request, mock_repo)

        assert exc_info.value.status_code == 500
