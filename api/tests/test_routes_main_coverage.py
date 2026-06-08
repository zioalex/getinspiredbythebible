"""
Tests for routes (chat, health, scripture, feedback) and main.py.

Coverage targets:
- routes/chat.py: chat, chat_stream, get_verse_context
- routes/health.py: check_database_health, check_llm_health, check_embedding_health,
  get_memory_info, health_check, liveness_probe, readiness_probe
- routes/scripture.py: get_translations, get_books, get_verse, get_chapter,
  get_verse_range, search_scripture, search_text, get_stats
- routes/feedback.py: submit_feedback, submit_contact
- main.py: lifespan, root, config, debug_embeddings, provider_error_handler, _get_cors_origins
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from providers import EmbeddingResponse, ProviderError

# ==================== Health Route Tests ====================


class TestCheckDatabaseHealth:
    """Tests for check_database_health()."""

    @pytest.mark.asyncio
    @patch("routes.health.async_session_factory")
    async def test_healthy(self, mock_factory):
        from routes.health import check_database_health

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_session

        result = await check_database_health()
        assert result.status == "healthy"
        assert result.latency_ms is not None

    @pytest.mark.asyncio
    @patch("routes.health.async_session_factory")
    async def test_timeout(self, mock_factory):
        import asyncio

        from routes.health import check_database_health

        mock_session = AsyncMock()

        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(100)

        mock_session.execute = slow_execute
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_session

        with patch("routes.health.settings") as mock_settings:
            mock_settings.health_check_timeout = 0.001
            result = await check_database_health()

        assert result.status == "unhealthy"
        assert "timed out" in result.error

    @pytest.mark.asyncio
    @patch("routes.health.async_session_factory")
    async def test_exception(self, mock_factory):
        from routes.health import check_database_health

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=ConnectionError("Connection refused"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_session

        result = await check_database_health()
        assert result.status == "unhealthy"
        assert result.error is not None
        assert result.latency_ms is not None


class TestCheckLlmHealth:
    """Tests for check_llm_health()."""

    @pytest.mark.asyncio
    @patch("routes.health.settings")
    @patch("routes.health.get_llm_provider")
    async def test_healthy(self, mock_get_provider, mock_settings):
        from routes.health import check_llm_health

        mock_settings.health_check_timeout = 5.0
        provider = AsyncMock()
        provider.provider_name = "ollama"
        provider.health_check = AsyncMock(return_value=True)
        mock_get_provider.return_value = provider

        result = await check_llm_health()
        assert result.status == "healthy"
        assert result.details["provider"] == "ollama"

    @pytest.mark.asyncio
    @patch("routes.health.settings")
    @patch("routes.health.get_llm_provider")
    async def test_unhealthy(self, mock_get_provider, mock_settings):
        from routes.health import check_llm_health

        mock_settings.health_check_timeout = 5.0
        provider = AsyncMock()
        provider.provider_name = "ollama"
        provider.health_check = AsyncMock(return_value=False)
        mock_get_provider.return_value = provider

        result = await check_llm_health()
        assert result.status == "unhealthy"

    @pytest.mark.asyncio
    @patch("routes.health.settings")
    @patch("routes.health.get_llm_provider")
    async def test_timeout(self, mock_get_provider, mock_settings):
        import asyncio

        from routes.health import check_llm_health

        mock_settings.health_check_timeout = 0.001
        mock_settings.llm_provider = "ollama"

        async def slow_check():
            await asyncio.sleep(100)
            return True

        provider = AsyncMock()
        provider.health_check = slow_check
        mock_get_provider.return_value = provider

        result = await check_llm_health()
        assert result.status == "unhealthy"
        assert "timed out" in result.error

    @pytest.mark.asyncio
    @patch("routes.health.settings")
    @patch("routes.health.get_llm_provider")
    async def test_provider_error(self, mock_get_provider, mock_settings):
        from routes.health import check_llm_health

        mock_settings.health_check_timeout = 5.0
        mock_settings.llm_provider = "ollama"
        provider = AsyncMock()
        provider.health_check = AsyncMock(side_effect=ProviderError("Provider down"))
        mock_get_provider.return_value = provider

        result = await check_llm_health()
        assert result.status == "unhealthy"
        assert "Provider down" in result.error

    @pytest.mark.asyncio
    @patch("routes.health.settings")
    @patch("routes.health.get_llm_provider")
    async def test_generic_exception(self, mock_get_provider, mock_settings):
        from routes.health import check_llm_health

        mock_settings.health_check_timeout = 5.0
        mock_settings.llm_provider = "ollama"
        provider = AsyncMock()
        provider.health_check = AsyncMock(side_effect=RuntimeError("unexpected"))
        mock_get_provider.return_value = provider

        result = await check_llm_health()
        assert result.status == "unhealthy"
        assert "unexpected" in result.error


class TestCheckEmbeddingHealth:
    """Tests for check_embedding_health()."""

    @pytest.mark.asyncio
    @patch("routes.health.settings")
    @patch("routes.health.get_embedding_provider")
    async def test_healthy(self, mock_get_provider, mock_settings):
        from routes.health import check_embedding_health

        mock_settings.health_check_timeout = 5.0
        provider = AsyncMock()
        provider.provider_name = "ollama"
        provider.embed = AsyncMock(
            return_value=EmbeddingResponse(embedding=[0.1] * 1024, provider="ollama", model="mxbai")
        )
        mock_get_provider.return_value = provider

        result = await check_embedding_health()
        assert result.status == "healthy"
        assert result.details["dimensions"] == 1024

    @pytest.mark.asyncio
    @patch("routes.health.settings")
    @patch("routes.health.get_embedding_provider")
    async def test_timeout(self, mock_get_provider, mock_settings):
        import asyncio

        from routes.health import check_embedding_health

        mock_settings.health_check_timeout = 0.001
        mock_settings.embedding_provider = "ollama"

        async def slow_embed(text):
            await asyncio.sleep(100)

        provider = AsyncMock()
        provider.embed = slow_embed
        mock_get_provider.return_value = provider

        result = await check_embedding_health()
        assert result.status == "unhealthy"
        assert "timed out" in result.error

    @pytest.mark.asyncio
    @patch("routes.health.settings")
    @patch("routes.health.get_embedding_provider")
    async def test_provider_error(self, mock_get_provider, mock_settings):
        from routes.health import check_embedding_health

        mock_settings.health_check_timeout = 5.0
        mock_settings.embedding_provider = "ollama"
        provider = AsyncMock()
        provider.embed = AsyncMock(side_effect=ProviderError("Embedding down"))
        mock_get_provider.return_value = provider

        result = await check_embedding_health()
        assert result.status == "unhealthy"
        assert "Embedding down" in result.error

    @pytest.mark.asyncio
    @patch("routes.health.settings")
    @patch("routes.health.get_embedding_provider")
    async def test_generic_exception(self, mock_get_provider, mock_settings):
        from routes.health import check_embedding_health

        mock_settings.health_check_timeout = 5.0
        mock_settings.embedding_provider = "ollama"
        provider = AsyncMock()
        provider.embed = AsyncMock(side_effect=RuntimeError("unexpected"))
        mock_get_provider.return_value = provider

        result = await check_embedding_health()
        assert result.status == "unhealthy"


class TestGetMemoryInfo:
    """Tests for get_memory_info()."""

    def test_returns_dict(self):
        from routes.health import get_memory_info

        result = get_memory_info()
        assert isinstance(result, dict)
        # Should have memory info keys
        assert "used_mb" in result or "error" in result

    @patch("routes.health.resource")
    def test_returns_memory_info(self, mock_resource):
        from routes.health import get_memory_info

        mock_usage = MagicMock()
        mock_usage.ru_maxrss = 512 * 1024  # 512 MB in KB
        mock_resource.getrusage.return_value = mock_usage
        mock_resource.RUSAGE_SELF = 0

        with patch("routes.health.settings") as mock_settings:
            mock_settings.memory_warning_threshold_mb = 1024

            result = get_memory_info()

        assert result["used_mb"] == 512.0
        assert result["limit_mb"] == 1024
        assert result["warning"] is False

    @patch("routes.health.resource")
    def test_warning_when_over_threshold(self, mock_resource):
        from routes.health import get_memory_info

        mock_usage = MagicMock()
        mock_usage.ru_maxrss = 2048 * 1024  # 2048 MB
        mock_resource.getrusage.return_value = mock_usage
        mock_resource.RUSAGE_SELF = 0

        with patch("routes.health.settings") as mock_settings:
            mock_settings.memory_warning_threshold_mb = 1024

            result = get_memory_info()

        assert result["warning"] is True

    @patch("routes.health.resource")
    def test_exception_returns_error(self, mock_resource):
        from routes.health import get_memory_info

        mock_resource.getrusage.side_effect = Exception("not supported")
        mock_resource.RUSAGE_SELF = 0

        result = get_memory_info()
        assert "error" in result


class TestLivenessProbe:
    """Tests for liveness_probe endpoint."""

    @pytest.mark.asyncio
    async def test_liveness(self):
        from routes.health import liveness_probe

        result = await liveness_probe()
        assert result == {"status": "alive"}


class TestReadinessProbe:
    """Tests for readiness_probe endpoint."""

    @pytest.mark.asyncio
    @patch("routes.health.check_embedding_health")
    @patch("routes.health.check_llm_health")
    @patch("routes.health.check_database_health")
    async def test_ready(self, mock_db_health, mock_llm_health, mock_embedding_health):
        from routes.health import ComponentHealth, readiness_probe

        mock_db_health.return_value = ComponentHealth(status="healthy", latency_ms=5.0)
        mock_llm_health.return_value = ComponentHealth(status="healthy", latency_ms=10.0)
        mock_embedding_health.return_value = ComponentHealth(status="healthy", latency_ms=8.0)
        result = await readiness_probe()
        assert result["status"] == "ready"
        assert result["database_latency_ms"] == 5.0
        assert result["dependencies"]["database"] == "healthy"

    @pytest.mark.asyncio
    @patch("routes.health.check_embedding_health")
    @patch("routes.health.check_llm_health")
    @patch("routes.health.check_database_health")
    async def test_not_ready(self, mock_db_health, mock_llm_health, mock_embedding_health):
        from routes.health import ComponentHealth, readiness_probe

        mock_db_health.return_value = ComponentHealth(
            status="unhealthy", error="Connection refused"
        )
        mock_llm_health.return_value = ComponentHealth(status="healthy")
        mock_embedding_health.return_value = ComponentHealth(status="healthy")
        result = await readiness_probe()
        assert result.status_code == 503
        body = result.body
        assert b"not_ready" in body


# ==================== Main App Tests ====================


class TestMainApp:
    """Tests for main.py app configuration."""

    def test_root_endpoint(self):
        with (
            patch("main.init_db", new_callable=AsyncMock),
            patch("main.close_db", new_callable=AsyncMock),
        ):
            from main import app

            client = TestClient(app)
            response = client.get("/")
            assert response.status_code == 200
            data = response.json()
            assert "name" in data
            assert "version" in data
            assert "docs" in data
            assert "health" in data

    def test_config_endpoint(self):
        with (
            patch("main.init_db", new_callable=AsyncMock),
            patch("main.close_db", new_callable=AsyncMock),
        ):
            from main import app

            client = TestClient(app)
            response = client.get("/config")
            assert response.status_code == 200
            data = response.json()
            assert "llm" in data
            assert "embedding" in data
            assert "chat" in data
            assert "provider" in data["llm"]
            assert "model" in data["llm"]

    def test_provider_error_handler(self):
        with (
            patch("main.init_db", new_callable=AsyncMock),
            patch("main.close_db", new_callable=AsyncMock),
        ):
            from main import app

            # Add a test route that raises ProviderError
            @app.get("/test-provider-error")
            async def trigger_error():
                raise ProviderError("Test provider error")

            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/test-provider-error")
            assert response.status_code == 503
            data = response.json()
            assert "error" in data
            assert "LLM Provider Error" in data["error"]

    def test_get_cors_origins(self):
        from main import _get_cors_origins

        origins = _get_cors_origins()
        assert "http://localhost:3000" in origins
        assert "http://127.0.0.1:3000" in origins

    @patch("main.settings")
    def test_get_cors_origins_with_custom(self, mock_settings):
        from main import _get_cors_origins

        mock_settings.cors_origins = "https://custom.example.com, https://other.example.com"
        origins = _get_cors_origins()
        assert "https://custom.example.com" in origins
        assert "https://other.example.com" in origins

    @patch("main.settings")
    def test_get_cors_origins_empty_custom(self, mock_settings):
        from main import _get_cors_origins

        mock_settings.cors_origins = ""
        origins = _get_cors_origins()
        assert "http://localhost:3000" in origins


class TestMainLifespan:
    """Tests for the lifespan context manager."""

    @pytest.mark.asyncio
    async def test_lifespan_startup_and_shutdown(self):
        from main import lifespan

        mock_app = MagicMock()

        with (
            patch("main.init_db", new_callable=AsyncMock) as mock_init,
            patch("main.close_db", new_callable=AsyncMock) as mock_close,
        ):
            async with lifespan(mock_app):
                mock_init.assert_awaited_once()

            mock_close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lifespan_db_init_failure(self):
        from main import lifespan

        mock_app = MagicMock()

        with (
            patch("main.init_db", new_callable=AsyncMock, side_effect=Exception("DB error")),
            patch("main.close_db", new_callable=AsyncMock) as mock_close,
        ):
            # Should not raise - logs the error and continues
            async with lifespan(mock_app):
                pass

            mock_close.assert_awaited_once()


# ==================== Feedback Route Tests ====================


class TestFeedbackRoutes:
    """Tests for feedback route functions."""

    @pytest.mark.asyncio
    async def test_submit_feedback_success(self):
        from datetime import UTC, datetime

        from feedback.models import Feedback, FeedbackRequest
        from routes.feedback import submit_feedback

        mock_repo = AsyncMock()
        mock_feedback = MagicMock(spec=Feedback)
        mock_feedback.id = 1
        mock_feedback.message_id = "550e8400-e29b-41d4-a716-446655440000"
        mock_feedback.rating = "positive"
        mock_feedback.created_at = datetime.now(UTC)
        mock_repo.save_feedback = AsyncMock(return_value=mock_feedback)

        request = FeedbackRequest(
            message_id="550e8400-e29b-41d4-a716-446655440000",
            rating="positive",
            user_message="What does John 3:16 mean?",
            assistant_response="John 3:16 tells us about God's love...",
        )

        result = await submit_feedback(request, mock_repo)
        assert result.id == 1
        assert result.rating == "positive"

    @pytest.mark.asyncio
    async def test_submit_feedback_negative_sends_email(self):
        from datetime import UTC, datetime

        from feedback.models import Feedback, FeedbackRequest
        from routes.feedback import submit_feedback

        mock_repo = AsyncMock()
        mock_feedback = MagicMock(spec=Feedback)
        mock_feedback.id = 2
        mock_feedback.message_id = "550e8400-e29b-41d4-a716-446655440000"
        mock_feedback.rating = "negative"
        mock_feedback.created_at = datetime.now(UTC)
        mock_repo.save_feedback = AsyncMock(return_value=mock_feedback)

        request = FeedbackRequest(
            message_id="550e8400-e29b-41d4-a716-446655440000",
            rating="negative",
            comment="Bad answer",
            user_message="test",
            assistant_response="response",
        )

        with patch("routes.feedback.email_service") as mock_email:
            result = await submit_feedback(request, mock_repo)
            mock_email.send_feedback_notification.assert_called_once()

        assert result.rating == "negative"

    @pytest.mark.asyncio
    async def test_submit_feedback_value_error(self):
        from fastapi import HTTPException

        from feedback.models import FeedbackRequest
        from routes.feedback import submit_feedback

        mock_repo = AsyncMock()
        mock_repo.save_feedback = AsyncMock(side_effect=ValueError("Invalid UUID"))

        request = FeedbackRequest(
            message_id="invalid",
            rating="positive",
            user_message="test",
            assistant_response="response",
        )

        with pytest.raises(HTTPException) as exc_info:
            await submit_feedback(request, mock_repo)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_submit_feedback_generic_error(self):
        from fastapi import HTTPException

        from feedback.models import FeedbackRequest
        from routes.feedback import submit_feedback

        mock_repo = AsyncMock()
        mock_repo.save_feedback = AsyncMock(side_effect=RuntimeError("DB down"))

        request = FeedbackRequest(
            message_id="550e8400-e29b-41d4-a716-446655440000",
            rating="positive",
            user_message="test",
            assistant_response="response",
        )

        with pytest.raises(HTTPException) as exc_info:
            await submit_feedback(request, mock_repo)
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_submit_contact_success(self):
        from datetime import UTC, datetime

        from feedback.models import ContactRequest, ContactSubmission
        from routes.feedback import submit_contact

        mock_repo = AsyncMock()
        mock_contact = MagicMock(spec=ContactSubmission)
        mock_contact.id = 1
        mock_contact.subject = "bug"
        mock_contact.created_at = datetime.now(UTC)
        mock_repo.save_contact = AsyncMock(return_value=mock_contact)

        request = ContactRequest(
            subject="bug",
            message="Found a bug in the chat",
            email="user@example.com",
        )

        with patch("routes.feedback.email_service") as mock_email:
            mock_email.send_contact_notification.return_value = True
            result = await submit_contact(request, mock_repo)

        assert result.id == 1
        assert result.subject == "bug"

    @pytest.mark.asyncio
    async def test_submit_contact_email_not_sent(self):
        from datetime import UTC, datetime

        from feedback.models import ContactRequest, ContactSubmission
        from routes.feedback import submit_contact

        mock_repo = AsyncMock()
        mock_contact = MagicMock(spec=ContactSubmission)
        mock_contact.id = 2
        mock_contact.subject = "feedback"
        mock_contact.created_at = datetime.now(UTC)
        mock_repo.save_contact = AsyncMock(return_value=mock_contact)

        request = ContactRequest(
            subject="feedback",
            message="Great app!",
            email="user@example.com",
        )

        with patch("routes.feedback.email_service") as mock_email:
            mock_email.send_contact_notification.return_value = False
            result = await submit_contact(request, mock_repo)

        assert result.id == 2

    @pytest.mark.asyncio
    async def test_submit_contact_generic_error(self):
        from fastapi import HTTPException

        from feedback.models import ContactRequest
        from routes.feedback import submit_contact

        mock_repo = AsyncMock()
        mock_repo.save_contact = AsyncMock(side_effect=RuntimeError("DB down"))

        request = ContactRequest(
            subject="bug",
            message="Test message",
            email="user@example.com",
        )

        with pytest.raises(HTTPException) as exc_info:
            await submit_contact(request, mock_repo)
        assert exc_info.value.status_code == 500


# ==================== Chat Route Tests ====================


class TestChatRoutes:
    """Tests for chat route functions."""

    @staticmethod
    def _mock_http_request():
        """Create a mock HTTP request with headers for chat route tests."""
        mock_req = MagicMock()
        mock_req.headers = {"user-agent": "test-agent", "accept-language": "en-US"}
        return mock_req

    @pytest.mark.asyncio
    async def test_chat_success(self):
        from chat.service import ChatRequest, ChatResponse
        from routes.chat import chat

        mock_db = AsyncMock()
        mock_llm = AsyncMock()
        mock_embedding = AsyncMock()
        mock_http = self._mock_http_request()

        request = ChatRequest(message="I need encouragement")

        expected_response = ChatResponse(
            message_id="test-id",
            message="God loves you!",
            provider="test",
            model="test-model",
        )

        with (
            patch("routes.chat.ChatService") as mock_service_cls,
            patch("routes.chat.track_session", new_callable=AsyncMock),
        ):
            mock_service = AsyncMock()
            mock_service.chat = AsyncMock(return_value=expected_response)
            mock_service_cls.return_value = mock_service

            result = await chat(request, mock_http, mock_db, mock_llm, mock_embedding)

        assert result.message == "God loves you!"

    @pytest.mark.asyncio
    async def test_chat_rate_limit_error(self):
        from fastapi import HTTPException

        from chat.service import ChatRequest
        from routes.chat import chat

        mock_db = AsyncMock()
        mock_llm = AsyncMock()
        mock_embedding = AsyncMock()
        mock_http = self._mock_http_request()

        request = ChatRequest(message="Hello")

        with patch("routes.chat.ChatService") as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.chat = AsyncMock(
                side_effect=RuntimeError("All models rate limited or failed")
            )
            mock_service_cls.return_value = mock_service

            with pytest.raises(HTTPException) as exc_info:
                await chat(request, mock_http, mock_db, mock_llm, mock_embedding)

            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_chat_runtime_error(self):
        from fastapi import HTTPException

        from chat.service import ChatRequest
        from routes.chat import chat

        mock_db = AsyncMock()
        mock_llm = AsyncMock()
        mock_embedding = AsyncMock()
        mock_http = self._mock_http_request()

        request = ChatRequest(message="Hello")

        with patch("routes.chat.ChatService") as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.chat = AsyncMock(side_effect=RuntimeError("Some other runtime error"))
            mock_service_cls.return_value = mock_service

            with pytest.raises(HTTPException) as exc_info:
                await chat(request, mock_http, mock_db, mock_llm, mock_embedding)

            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_chat_generic_error(self):
        from fastapi import HTTPException

        from chat.service import ChatRequest
        from routes.chat import chat

        mock_db = AsyncMock()
        mock_llm = AsyncMock()
        mock_embedding = AsyncMock()
        mock_http = self._mock_http_request()

        request = ChatRequest(message="Hello")

        with patch("routes.chat.ChatService") as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.chat = AsyncMock(side_effect=ValueError("bad input"))
            mock_service_cls.return_value = mock_service

            with pytest.raises(HTTPException) as exc_info:
                await chat(request, mock_http, mock_db, mock_llm, mock_embedding)

            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_get_verse_context_success(self):
        from routes.chat import get_verse_context

        mock_db = AsyncMock()
        mock_llm = AsyncMock()
        mock_embedding = AsyncMock()

        expected = {"target_verse": 16, "verses": []}

        with patch("routes.chat.ChatService") as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.get_verse_context = AsyncMock(return_value=expected)
            mock_service_cls.return_value = mock_service

            result = await get_verse_context("John", 3, 16, mock_db, mock_llm, mock_embedding)

        assert result == expected

    @pytest.mark.asyncio
    async def test_get_verse_context_error(self):
        from fastapi import HTTPException

        from routes.chat import get_verse_context

        mock_db = AsyncMock()
        mock_llm = AsyncMock()
        mock_embedding = AsyncMock()

        with patch("routes.chat.ChatService") as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.get_verse_context = AsyncMock(side_effect=Exception("DB error"))
            mock_service_cls.return_value = mock_service

            with pytest.raises(HTTPException) as exc_info:
                await get_verse_context("John", 3, 16, mock_db, mock_llm, mock_embedding)

            assert exc_info.value.status_code == 500


class TestChatStreamRoute:
    """Tests for chat_stream route function."""

    @pytest.mark.asyncio
    async def test_chat_stream_returns_streaming_response(self):
        from chat.service import ChatRequest
        from routes.chat import chat_stream

        mock_db = AsyncMock()
        mock_llm = AsyncMock()
        mock_embedding = AsyncMock()

        request = ChatRequest(message="Hello")

        async def mock_gen(req):
            yield {
                "type": "metadata",
                "message_id": "test-id",
                "scripture_context": None,
                "provider": "test",
                "model": "test-model",
            }
            yield {"type": "content", "content": "Hello "}
            yield {"type": "content", "content": "world!"}

        with patch("routes.chat.ChatService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.chat_stream = mock_gen
            mock_service_cls.return_value = mock_service

            response = await chat_stream(request, mock_db, mock_llm, mock_embedding)

        # Should be a StreamingResponse
        assert response.media_type == "text/event-stream"


# ==================== Scripture Route Tests ====================


class TestScriptureRoutes:
    """Tests for scripture route functions."""

    @pytest.mark.asyncio
    async def test_get_translations(self):
        from routes.scripture import get_translations

        with patch("routes.scripture.get_all_translations") as mock_get:
            mock_get.return_value = [
                {"code": "kjv", "name": "King James Version"},
                {"code": "ita1927", "name": "Italian Riveduta"},
            ]
            result = await get_translations()

        assert "translations" in result
        assert len(result["translations"]) == 2

    @pytest.mark.asyncio
    async def test_get_books(self):
        from routes.scripture import get_books

        mock_db = AsyncMock()

        mock_book = MagicMock()
        mock_book.id = 1
        mock_book.name = "Genesis"
        mock_book.abbreviation = "Gen"
        mock_book.testament = "OT"
        mock_book.position = 1

        with patch("routes.scripture.ScriptureRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_all_books = AsyncMock(return_value=[mock_book])
            mock_repo_cls.return_value = mock_repo

            result = await get_books(mock_db)

        assert len(result.books) == 1
        assert result.books[0]["name"] == "Genesis"

    @pytest.mark.asyncio
    async def test_get_verse_found(self):
        from routes.scripture import get_verse

        mock_db = AsyncMock()
        mock_embedding = AsyncMock()

        mock_verse = MagicMock()
        mock_verse.reference = "John 3:16"
        mock_verse.text = "For God so loved the world..."
        mock_verse.book.name = "John"
        mock_verse.chapter_number = 3
        mock_verse.verse_number = 16
        mock_verse.translation = "kjv"

        with patch("routes.scripture.ScriptureRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_verse = AsyncMock(return_value=mock_verse)
            mock_repo_cls.return_value = mock_repo

            with patch("routes.scripture.get_localized_book_name", return_value="John"):
                result = await get_verse("John", 3, 16, mock_db, mock_embedding, None)

        assert result["reference"] == "John 3:16"

    @pytest.mark.asyncio
    async def test_get_verse_not_found(self):
        from fastapi import HTTPException

        from routes.scripture import get_verse

        mock_db = AsyncMock()
        mock_embedding = AsyncMock()

        with patch("routes.scripture.ScriptureRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_verse = AsyncMock(return_value=None)
            mock_repo_cls.return_value = mock_repo

            with pytest.raises(HTTPException) as exc_info:
                await get_verse("NotABook", 1, 1, mock_db, mock_embedding, None)

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_chapter_found(self):
        from routes.scripture import get_chapter

        mock_db = AsyncMock()

        mock_verse = MagicMock()
        mock_verse.reference = "Genesis 1:1"
        mock_verse.text = "In the beginning..."
        mock_verse.book.name = "Genesis"
        mock_verse.chapter_number = 1
        mock_verse.verse_number = 1
        mock_verse.translation = "kjv"

        with (
            patch("routes.scripture.ScriptureRepository") as mock_repo_cls,
            patch("routes.scripture.get_localized_book_name", return_value="Genesis"),
            patch(
                "routes.scripture.get_translation_info", return_value={"name": "King James Version"}
            ),
        ):
            mock_repo = AsyncMock()
            mock_repo.get_chapter_verses = AsyncMock(return_value=[mock_verse])
            mock_repo_cls.return_value = mock_repo

            mock_http = MagicMock()
            mock_http.headers = {"accept-language": "en-US"}
            result = await get_chapter("Genesis", 1, mock_db, None, http_request=mock_http)

        assert result.book == "Genesis"
        assert result.chapter == 1
        assert len(result.verses) == 1

    @pytest.mark.asyncio
    async def test_get_chapter_not_found(self):
        from fastapi import HTTPException

        from routes.scripture import get_chapter

        mock_db = AsyncMock()

        with patch("routes.scripture.ScriptureRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_chapter_verses = AsyncMock(return_value=[])
            mock_repo_cls.return_value = mock_repo

            with pytest.raises(HTTPException) as exc_info:
                await get_chapter("NotABook", 1, mock_db, None)

            assert exc_info.value.status_code == 404

    @staticmethod
    def _chapter_verse(translation: str):
        """Build a mock verse for a given translation (John 3:16)."""
        v = MagicMock()
        v.reference = "John 3:16"
        v.text = "For God so loved the world..."
        v.book.name = "John"
        v.chapter_number = 3
        v.verse_number = 16
        v.translation = translation
        return v

    @pytest.mark.asyncio
    async def test_get_chapter_default_is_deterministic_across_translations(self):
        """Regression (Bug 1): with no translation requested, the chapter must
        return the same version every call regardless of DB row order, instead
        of a random translation. Picks the Accept-Language default (English ->
        web) when available."""
        from routes.scripture import get_chapter

        mock_db = AsyncMock()
        # The DB returns the chapter across many translations, in arbitrary order.
        all_translations = ["ita1927", "schlachter", "kjv", "web", "valera", "ls1910"]

        mock_http = MagicMock()
        mock_http.headers = {"accept-language": "en-US,en;q=0.9"}

        results = []
        for order in (all_translations, list(reversed(all_translations))):
            with (
                patch("routes.scripture.ScriptureRepository") as mock_repo_cls,
                patch("routes.scripture.get_localized_book_name", return_value="John"),
            ):
                mock_repo = AsyncMock()
                mock_repo.get_chapter_verses = AsyncMock(
                    return_value=[self._chapter_verse(t) for t in order]
                )
                mock_repo_cls.return_value = mock_repo
                result = await get_chapter("John", 3, mock_db, None, http_request=mock_http)
            results.append(result.translation)

        # Stable across differing DB orderings, and resolves to the English default.
        assert results[0] == results[1] == "web"

    @pytest.mark.asyncio
    async def test_get_chapter_default_honors_accept_language(self):
        """Regression (Bug 1): the default version follows the caller's
        Accept-Language (Italian -> ita1927) when that translation is present."""
        from routes.scripture import get_chapter

        mock_db = AsyncMock()
        translations = ["web", "kjv", "ita1927", "schlachter"]

        mock_http = MagicMock()
        mock_http.headers = {"accept-language": "it-IT,it;q=0.9"}

        with (
            patch("routes.scripture.ScriptureRepository") as mock_repo_cls,
            patch("routes.scripture.get_localized_book_name", return_value="Giovanni"),
        ):
            mock_repo = AsyncMock()
            mock_repo.get_chapter_verses = AsyncMock(
                return_value=[self._chapter_verse(t) for t in translations]
            )
            mock_repo_cls.return_value = mock_repo
            result = await get_chapter("John", 3, mock_db, None, http_request=mock_http)

        assert result.translation == "ita1927"
        assert all(v["translation"] == "ita1927" for v in result.verses)

    @pytest.mark.asyncio
    async def test_get_chapter_default_prefers_lang_over_accept_language(self):
        """The explicit UI language (`lang`) wins over the browser's
        Accept-Language: a German UI on an English browser gets schlachter."""
        from routes.scripture import get_chapter

        mock_db = AsyncMock()
        translations = ["web", "kjv", "ita1927", "schlachter"]

        mock_http = MagicMock()
        mock_http.headers = {"accept-language": "en-US,en;q=0.9"}

        with (
            patch("routes.scripture.ScriptureRepository") as mock_repo_cls,
            patch("routes.scripture.get_localized_book_name", return_value="Johannes"),
        ):
            mock_repo = AsyncMock()
            mock_repo.get_chapter_verses = AsyncMock(
                return_value=[self._chapter_verse(t) for t in translations]
            )
            mock_repo_cls.return_value = mock_repo
            result = await get_chapter("John", 3, mock_db, None, lang="de", http_request=mock_http)

        assert result.translation == "schlachter"

    @pytest.mark.asyncio
    async def test_get_verse_range_found(self):
        from routes.scripture import get_verse_range
        from scripture.search import VerseResult

        mock_db = AsyncMock()
        mock_embedding = AsyncMock()

        mock_verses = [
            VerseResult(reference="John 3:16", text="Verse 16", book="John", chapter=3, verse=16),
            VerseResult(reference="John 3:17", text="Verse 17", book="John", chapter=3, verse=17),
        ]

        with patch("routes.scripture.ScriptureSearchService") as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.get_verse_range = AsyncMock(return_value=mock_verses)
            mock_service_cls.return_value = mock_service

            result = await get_verse_range("John", 3, 16, 17, mock_db, mock_embedding)

        assert len(result["verses"]) == 2

    @pytest.mark.asyncio
    async def test_get_verse_range_not_found(self):
        from fastapi import HTTPException

        from routes.scripture import get_verse_range

        mock_db = AsyncMock()
        mock_embedding = AsyncMock()

        with patch("routes.scripture.ScriptureSearchService") as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.get_verse_range = AsyncMock(return_value=[])
            mock_service_cls.return_value = mock_service

            with pytest.raises(HTTPException) as exc_info:
                await get_verse_range("NotABook", 1, 1, 5, mock_db, mock_embedding)

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_search_scripture(self):
        from routes.scripture import search_scripture
        from scripture.search import SearchResults

        mock_db = AsyncMock()
        mock_embedding = AsyncMock()

        expected = SearchResults(query="love", verses=[], passages=[])

        with patch("routes.scripture.ScriptureSearchService") as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.search = AsyncMock(return_value=expected)
            mock_service_cls.return_value = mock_service

            result = await search_scripture("love", 5, 2, None, mock_db, mock_embedding)

        assert result.query == "love"

    @pytest.mark.asyncio
    async def test_search_text(self):
        from routes.scripture import search_text

        mock_db = AsyncMock()
        mock_embedding = AsyncMock()

        with patch("routes.scripture.ScriptureSearchService") as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.text_search = AsyncMock(return_value=[])
            mock_service_cls.return_value = mock_service

            result = await search_text("love", 20, mock_db, mock_embedding)

        assert result["query"] == "love"
        assert result["verses"] == []

    @pytest.mark.asyncio
    async def test_get_stats(self):
        from routes.scripture import get_stats

        mock_db = AsyncMock()
        expected_stats = {"total_verses": 31102, "total_books": 66}

        with patch("routes.scripture.ScriptureRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_stats = AsyncMock(return_value=expected_stats)
            mock_repo_cls.return_value = mock_repo

            result = await get_stats(mock_db)

        assert result == expected_stats


# ==================== Health Check Endpoint Integration ====================


class TestHealthCheckEndpoint:
    """Tests for the health_check endpoint (integration of check functions)."""

    @pytest.mark.asyncio
    @patch("routes.health.get_memory_info")
    @patch("routes.health.check_embedding_health")
    @patch("routes.health.check_llm_health")
    @patch("routes.health.check_database_health")
    async def test_all_healthy(self, mock_db, mock_llm, mock_emb, mock_mem):
        from routes.health import ComponentHealth, health_check

        mock_db.return_value = ComponentHealth(status="healthy", latency_ms=5.0)
        mock_llm.return_value = ComponentHealth(
            status="healthy", latency_ms=10.0, details={"provider": "ollama"}
        )
        mock_emb.return_value = ComponentHealth(
            status="healthy", latency_ms=20.0, details={"provider": "ollama", "dimensions": 1024}
        )
        mock_mem.return_value = {"used_mb": 100, "limit_mb": 1024, "percent": 9.8, "warning": False}

        result = await health_check()
        assert result.status == "healthy"

    @pytest.mark.asyncio
    @patch("routes.health.get_memory_info")
    @patch("routes.health.check_embedding_health")
    @patch("routes.health.check_llm_health")
    @patch("routes.health.check_database_health")
    async def test_db_unhealthy_returns_503(self, mock_db, mock_llm, mock_emb, mock_mem):
        from routes.health import ComponentHealth, health_check

        mock_db.return_value = ComponentHealth(status="unhealthy", error="Connection refused")
        mock_llm.return_value = ComponentHealth(
            status="healthy", latency_ms=10.0, details={"provider": "ollama"}
        )
        mock_emb.return_value = ComponentHealth(
            status="healthy", latency_ms=20.0, details={"provider": "ollama", "dimensions": 1024}
        )
        mock_mem.return_value = {"used_mb": 100, "limit_mb": 1024, "percent": 9.8, "warning": False}

        result = await health_check()
        # When DB is unhealthy, it returns a JSONResponse with 503
        assert result.status_code == 503

    @pytest.mark.asyncio
    @patch("routes.health.get_memory_info")
    @patch("routes.health.check_embedding_health")
    @patch("routes.health.check_llm_health")
    @patch("routes.health.check_database_health")
    async def test_llm_unhealthy_returns_degraded(self, mock_db, mock_llm, mock_emb, mock_mem):
        from routes.health import ComponentHealth, health_check

        mock_db.return_value = ComponentHealth(status="healthy", latency_ms=5.0)
        mock_llm.return_value = ComponentHealth(
            status="unhealthy", error="LLM down", details={"provider": "ollama"}
        )
        mock_emb.return_value = ComponentHealth(
            status="healthy", latency_ms=20.0, details={"provider": "ollama", "dimensions": 1024}
        )
        mock_mem.return_value = {"used_mb": 100, "limit_mb": 1024, "percent": 9.8, "warning": False}

        result = await health_check()
        assert result.status == "degraded"

    @pytest.mark.asyncio
    @patch("routes.health.get_memory_info")
    @patch("routes.health.check_embedding_health")
    @patch("routes.health.check_llm_health")
    @patch("routes.health.check_database_health")
    async def test_embedding_unhealthy_returns_degraded(
        self, mock_db, mock_llm, mock_emb, mock_mem
    ):
        from routes.health import ComponentHealth, health_check

        mock_db.return_value = ComponentHealth(status="healthy", latency_ms=5.0)
        mock_llm.return_value = ComponentHealth(
            status="healthy", latency_ms=10.0, details={"provider": "ollama"}
        )
        mock_emb.return_value = ComponentHealth(
            status="unhealthy", error="Emb down", details={"provider": "ollama"}
        )
        mock_mem.return_value = {"used_mb": 100, "limit_mb": 1024, "percent": 9.8, "warning": False}

        result = await health_check()
        assert result.status == "degraded"
