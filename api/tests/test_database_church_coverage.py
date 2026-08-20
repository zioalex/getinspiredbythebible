"""
Tests for scripture/database.py and routes/church.py.

Coverage targets:
- scripture/database.py: get_async_database_url, get_db_session, init_db, close_db
- routes/church.py: search_churches, _normalize_churches
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from routes.church import (
    Church,
    ChurchSearchRequest,
    ChurchSearchResponse,
    _normalize_churches,
    search_churches,
)

# ==================== Database Tests ====================


class TestGetAsyncDatabaseUrl:
    """Tests for get_async_database_url()."""

    @patch("scripture.database.settings")
    def test_plain_postgresql_url(self, mock_settings):
        mock_settings.database_url = (
            "postgresql://user:pass@localhost/db"  # pragma: allowlist secret
        )
        # Need to reimport to re-evaluate
        from scripture.database import get_async_database_url

        with patch("scripture.database.settings", mock_settings):
            url, args = get_async_database_url()

        assert "asyncpg" in url
        assert args == {}

    @patch("scripture.database.settings")
    def test_url_with_sslmode_require(self, mock_settings):
        mock_settings.database_url = (
            "postgresql://user:pass@host/db?sslmode=require"  # pragma: allowlist secret
        )
        from scripture.database import get_async_database_url

        with patch("scripture.database.settings", mock_settings):
            url, args = get_async_database_url()

        assert "sslmode" not in url
        assert "ssl" in args

    @patch("scripture.database.settings")
    def test_url_with_sslmode_verify_ca(self, mock_settings):
        mock_settings.database_url = (
            "postgresql://user:pass@host/db?sslmode=verify-ca"  # pragma: allowlist secret
        )
        from scripture.database import get_async_database_url

        with patch("scripture.database.settings", mock_settings):
            url, args = get_async_database_url()

        assert "sslmode" not in url
        assert "ssl" in args

    @patch("scripture.database.settings")
    def test_url_without_ssl(self, mock_settings):
        mock_settings.database_url = (
            "postgresql://user:pass@localhost/db"  # pragma: allowlist secret
        )
        from scripture.database import get_async_database_url

        with patch("scripture.database.settings", mock_settings):
            url, args = get_async_database_url()

        assert "ssl" not in args

    @patch("scripture.database.settings")
    def test_url_already_async(self, mock_settings):
        mock_settings.database_url = (
            "postgresql+asyncpg://user:pass@localhost/db"  # pragma: allowlist secret
        )
        from scripture.database import get_async_database_url

        with patch("scripture.database.settings", mock_settings):
            url, args = get_async_database_url()

        # Should not double-replace
        assert url.count("asyncpg") == 1

    @patch("scripture.database.settings")
    def test_url_with_ssl_require(self, mock_settings):
        """`?ssl=require` must be stripped exactly like `?sslmode=require`.

        The deploy workflow's migration job builds its DATABASE_URL with
        `?ssl=require` (.github/workflows/azure-deploy.yml, run-migrations).
        Leaving that parameter in the URL reaches asyncpg as a connect kwarg
        and fails with "parameter 'ssl' cannot be changed now" -- which would
        break `alembic upgrade head` on every deploy.
        """
        mock_settings.database_url = (
            "postgresql+asyncpg://user:pass@host/db?ssl=require"  # pragma: allowlist secret
        )
        from scripture.database import get_async_database_url

        with patch("scripture.database.settings", mock_settings):
            url, args = get_async_database_url()

        assert "ssl" not in url
        assert "ssl" in args

    @patch("scripture.database.settings")
    def test_url_with_ssl_and_sslmode(self, mock_settings):
        """Both spellings present: both stripped, one SSL context produced."""
        mock_settings.database_url = (
            "postgresql://user:pass@host/db?ssl=require&sslmode=require"  # pragma: allowlist secret
        )
        from scripture.database import get_async_database_url

        with patch("scripture.database.settings", mock_settings):
            url, args = get_async_database_url()

        assert "ssl=" not in url
        assert "sslmode" not in url
        assert "ssl" in args

    @patch("scripture.database.settings")
    def test_url_with_ssl_disable(self, mock_settings):
        """A non-TLS `ssl` value is still stripped, but yields no SSL context."""
        mock_settings.database_url = (
            "postgresql://user:pass@host/db?ssl=disable"  # pragma: allowlist secret
        )
        from scripture.database import get_async_database_url

        with patch("scripture.database.settings", mock_settings):
            url, args = get_async_database_url()

        assert "ssl" not in url
        assert "ssl" not in args

    @patch("scripture.database.settings")
    def test_url_with_other_params(self, mock_settings):
        mock_settings.database_url = "postgresql://user:pass@host/db?sslmode=require&connect_timeout=10"  # pragma: allowlist secret
        from scripture.database import get_async_database_url

        with patch("scripture.database.settings", mock_settings):
            url, args = get_async_database_url()

        assert "sslmode" not in url
        assert "connect_timeout" in url
        assert "ssl" in args


class TestGetDbSession:
    """Tests for get_db_session()."""

    @pytest.mark.asyncio
    async def test_yields_session_and_commits(self):
        from scripture.database import get_db_session

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("scripture.database.async_session_factory", return_value=mock_session):
            gen = get_db_session()
            session = await gen.__anext__()
            assert session is mock_session

            # Simulate successful completion
            try:
                await gen.__anext__()
            except StopAsyncIteration:
                pass

            mock_session.commit.assert_awaited_once()
            mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rollback_on_exception(self):
        from scripture.database import get_db_session

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock(side_effect=Exception("commit failed"))
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("scripture.database.async_session_factory", return_value=mock_session):
            gen = get_db_session()
            await gen.__anext__()

            with pytest.raises(Exception, match="commit failed"):
                await gen.__anext__()

            mock_session.rollback.assert_awaited_once()
            mock_session.close.assert_awaited_once()


class TestInitDb:
    """Tests for init_db()."""

    @pytest.mark.asyncio
    async def test_init_db_creates_tables(self):
        from scripture.database import init_db

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.run_sync = AsyncMock()

        mock_engine_ctx = AsyncMock()
        mock_engine_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("scripture.database.engine") as mock_engine:
            mock_engine.begin.return_value = mock_engine_ctx

            await init_db()

            # Should create pgvector extension and tables
            mock_conn.execute.assert_awaited_once()
            assert mock_conn.run_sync.await_count == 2  # Scripture + Feedback tables


class TestCloseDb:
    """Tests for close_db()."""

    @pytest.mark.asyncio
    async def test_close_disposes_engine(self):
        from scripture.database import close_db

        with patch("scripture.database.engine") as mock_engine:
            mock_engine.dispose = AsyncMock()
            await close_db()
            mock_engine.dispose.assert_awaited_once()


class TestApplySessionHnswEfSearch:
    """Tests for the ``connect`` event listener that sets ``hnsw.ef_search``
    on every new pooled connection. It's a plain module-level function
    (registered via @event.listens_for but still directly callable)."""

    def test_sets_guc_on_connection(self):
        from scripture.database import _apply_session_hnsw_ef_search

        cursor = MagicMock()
        dbapi_connection = MagicMock()
        dbapi_connection.cursor.return_value = cursor

        with patch("scripture.database.settings") as mock_settings:
            mock_settings.hnsw_ef_search = 150
            _apply_session_hnsw_ef_search(dbapi_connection, MagicMock())

        cursor.execute.assert_called_once_with("SET hnsw.ef_search = 150")
        cursor.close.assert_called_once()

    def test_swallows_exception_when_cursor_unavailable(self):
        from scripture.database import _apply_session_hnsw_ef_search

        dbapi_connection = MagicMock()
        dbapi_connection.cursor.side_effect = Exception("connection gone")

        with patch("scripture.database.logger") as mock_logger:
            # Must not raise -- a failure here would break every connection.
            _apply_session_hnsw_ef_search(dbapi_connection, MagicMock())

        mock_logger.warning.assert_called_once()
        assert mock_logger.warning.call_args.kwargs.get("exc_info") is True

    def test_swallows_exception_and_still_closes_cursor_on_execute_failure(self):
        from scripture.database import _apply_session_hnsw_ef_search

        cursor = MagicMock()
        cursor.execute.side_effect = Exception("SET failed")
        dbapi_connection = MagicMock()
        dbapi_connection.cursor.return_value = cursor

        with patch("scripture.database.logger") as mock_logger:
            _apply_session_hnsw_ef_search(dbapi_connection, MagicMock())

        cursor.close.assert_called_once()
        mock_logger.warning.assert_called_once()


# ==================== Church Route Tests ====================


class TestNormalizeChurches:
    """Tests for _normalize_churches() function."""

    def test_valid_data(self):
        data = {
            "success": True,
            "results": [
                {
                    "name": "Test Church",
                    "city": "Test City",
                    "state": "TX",
                    "country": "USA",
                    "contact_phone": "+1234567890",
                    "contact_email": "test@test.com",
                    "website": "http://test.com",
                }
            ],
        }
        churches = _normalize_churches(data)
        assert len(churches) == 1
        assert churches[0].name == "Test Church"
        assert churches[0].city == "Test City"
        assert churches[0].phone == "+1234567890"

    def test_empty_results(self):
        data = {"success": True, "results": []}
        churches = _normalize_churches(data)
        assert churches == []

    def test_not_a_dict(self):
        churches = _normalize_churches("not a dict")
        assert churches == []

    def test_not_a_list_results(self):
        data = {"results": "not a list"}
        churches = _normalize_churches(data)
        assert churches == []

    def test_non_dict_item_skipped(self):
        data = {"results": ["not a dict", None, 42]}
        churches = _normalize_churches(data)
        assert churches == []

    def test_missing_name_uses_default(self):
        data = {"results": [{"city": "Test City"}]}
        churches = _normalize_churches(data)
        assert len(churches) == 1
        assert churches[0].name == "Unknown Church"

    def test_empty_state_becomes_none(self):
        data = {
            "results": [
                {
                    "name": "Test Church",
                    "state": "",
                }
            ]
        }
        churches = _normalize_churches(data)
        assert churches[0].state is None

    def test_empty_phone_becomes_none(self):
        data = {
            "results": [
                {
                    "name": "Test Church",
                    "contact_phone": "",
                }
            ]
        }
        churches = _normalize_churches(data)
        assert churches[0].phone is None

    def test_multiple_results(self):
        data = {
            "results": [
                {"name": "Church A"},
                {"name": "Church B"},
                {"name": "Church C"},
            ]
        }
        churches = _normalize_churches(data)
        assert len(churches) == 3

    def test_no_results_key(self):
        data = {"success": True}
        churches = _normalize_churches(data)
        assert churches == []


class TestSearchChurchesEndpoint:
    """Tests for search_churches() route function (direct invocation)."""

    @pytest.mark.asyncio
    async def test_empty_location(self):
        request = ChurchSearchRequest(location="   ")
        with pytest.raises(Exception) as exc_info:
            await search_churches(request)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_successful_search(self):
        request = ChurchSearchRequest(location="Switzerland")

        mock_response_data = {
            "success": True,
            "results": [
                {
                    "name": "Zurich Church",
                    "city": "Zurich",
                    "country": "Switzerland",
                }
            ],
        }

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.headers = {"content-type": "application/json"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("routes.church.httpx.AsyncClient", return_value=mock_client):
            result = await search_churches(request)

        assert isinstance(result, ChurchSearchResponse)
        assert result.total == 1
        assert result.location == "Switzerland"
        assert result.churches[0].name == "Zurich Church"

    @pytest.mark.asyncio
    async def test_timeout_raises_504(self):
        request = ChurchSearchRequest(location="Switzerland")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("routes.church.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception) as exc_info:
                await search_churches(request)
            assert exc_info.value.status_code == 504

    @pytest.mark.asyncio
    async def test_http_error_raises_502(self):
        request = ChurchSearchRequest(location="Switzerland")

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503",
            request=httpx.Request("POST", "http://test"),
            response=mock_response,
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("routes.church.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception) as exc_info:
                await search_churches(request)
            assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_connection_error_raises_502(self):
        request = ChurchSearchRequest(location="Switzerland")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("routes.church.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception) as exc_info:
                await search_churches(request)
            assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_unexpected_error_raises_500(self):
        request = ChurchSearchRequest(location="Switzerland")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=RuntimeError("unexpected error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("routes.church.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception) as exc_info:
                await search_churches(request)
            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_location_trimmed(self):
        request = ChurchSearchRequest(location="  Switzerland  ")

        mock_response_data = {"success": True, "results": []}

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.headers = {"content-type": "application/json"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("routes.church.httpx.AsyncClient", return_value=mock_client):
            result = await search_churches(request)

        assert result.location == "Switzerland"


class TestChurchModel:
    """Tests for Church Pydantic model."""

    def test_minimal(self):
        church = Church(name="Test Church")
        assert church.name == "Test Church"
        assert church.address is None
        assert church.phone is None

    def test_full(self):
        church = Church(
            name="Test Church",
            address="123 Main St",
            city="Springfield",
            state="IL",
            country="USA",
            website="http://test.com",
            phone="+1234567890",
            email="info@test.com",
        )
        assert church.website == "http://test.com"


class TestChurchSearchRequest:
    """Tests for ChurchSearchRequest model."""

    def test_valid(self):
        req = ChurchSearchRequest(location="Switzerland")
        assert req.location == "Switzerland"


class TestChurchSearchResponse:
    """Tests for ChurchSearchResponse model."""

    def test_creation(self):
        resp = ChurchSearchResponse(
            churches=[Church(name="Test")],
            total=1,
            location="Test City",
        )
        assert resp.total == 1
        assert len(resp.churches) == 1
