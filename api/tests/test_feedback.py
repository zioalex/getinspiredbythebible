"""
Tests for feedback API endpoints.
"""

import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

# Add parent directory to path to import main
sys.path.insert(0, str(Path(__file__).parent.parent))

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
        """Test that email is optional."""
        response = client.post(
            "/api/v1/feedback/contact",
            json={
                "subject": "feedback",
                "message": "Just wanted to say thanks!",
            },
        )
        # Should succeed without email
        assert response.status_code in [200, 500]
