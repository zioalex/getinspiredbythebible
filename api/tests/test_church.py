"""
Tests for church finder endpoint.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

# Add parent directory to path to import main
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app

client = TestClient(app)


class TestChurchSearchEndpoint:
    """Tests for POST /api/v1/church/search endpoint."""

    def test_search_churches_success(self):
        """Test successful church search returns normalized results."""
        mock_response = {
            "success": True,
            "results": [
                {
                    "id": "792",
                    "name": "Zurich Church of Christ",
                    "city": "Zurich",
                    "state": "",
                    "country": "Switzerland",
                    "contact_phone": "+41 78 123 4567",
                    "contact_email": "info@church.ch",
                    "website": "http://www.church.ch",
                }
            ],
            "count": 1,
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = httpx.Response(
                200, json=mock_response, request=httpx.Request("POST", "test")
            )

            response = client.post("/api/v1/church/search", json={"location": "Switzerland"})

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["location"] == "Switzerland"
            assert len(data["churches"]) == 1
            assert data["churches"][0]["name"] == "Zurich Church of Christ"
            assert data["churches"][0]["city"] == "Zurich"
            assert data["churches"][0]["country"] == "Switzerland"

    def test_search_churches_empty_results(self):
        """Test search with no results returns empty list."""
        mock_response = {"success": True, "results": [], "message": "No churches found"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = httpx.Response(
                200, json=mock_response, request=httpx.Request("POST", "test")
            )

            response = client.post("/api/v1/church/search", json={"location": "Nonexistent Place"})

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
            assert data["churches"] == []

    def test_search_churches_empty_location_rejected(self):
        """Test that empty location is rejected with 400."""
        response = client.post("/api/v1/church/search", json={"location": ""})
        assert response.status_code == 400
        assert "Location is required" in response.json()["detail"]

    def test_search_churches_whitespace_location_rejected(self):
        """Test that whitespace-only location is rejected with 400."""
        response = client.post("/api/v1/church/search", json={"location": "   "})
        assert response.status_code == 400
        assert "Location is required" in response.json()["detail"]

    def test_search_churches_missing_location_rejected(self):
        """Test that missing location field is rejected with 422."""
        response = client.post("/api/v1/church/search", json={})
        assert response.status_code == 422

    def test_search_churches_timeout_returns_504(self):
        """Test that timeout from external API returns 504."""
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Connection timed out")

            response = client.post("/api/v1/church/search", json={"location": "Switzerland"})

            assert response.status_code == 504
            assert "timed out" in response.json()["detail"]

    def test_search_churches_http_error_returns_502(self):
        """Test that HTTP error from external API returns 502."""
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = httpx.Response(
                503,
                json={"error": "Service unavailable"},
                request=httpx.Request("POST", "test"),
            )

            response = client.post("/api/v1/church/search", json={"location": "Switzerland"})

            assert response.status_code == 502
            assert "503" in response.json()["detail"]

    def test_search_churches_connection_error_returns_502(self):
        """Test that connection error returns 502."""
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Failed to connect")

            response = client.post("/api/v1/church/search", json={"location": "Switzerland"})

            assert response.status_code == 502
            assert "Failed to connect" in response.json()["detail"]

    def test_search_churches_normalizes_fields(self):
        """Test that church fields are properly normalized."""
        mock_response = {
            "success": True,
            "results": [
                {
                    "name": "Test Church",
                    "city": "Test City",
                    "state": "",  # Empty string should become None
                    "country": "Test Country",
                    "contact_phone": "",  # Empty should become None
                    "contact_email": "test@test.com",
                    "website": "http://test.com",
                }
            ],
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = httpx.Response(
                200, json=mock_response, request=httpx.Request("POST", "test")
            )

            response = client.post("/api/v1/church/search", json={"location": "Test"})

            assert response.status_code == 200
            church = response.json()["churches"][0]
            assert church["state"] is None
            assert church["phone"] is None
            assert church["email"] == "test@test.com"

    def test_search_churches_trims_location(self):
        """Test that location is trimmed of whitespace."""
        mock_response = {"success": True, "results": []}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = httpx.Response(
                200, json=mock_response, request=httpx.Request("POST", "test")
            )

            response = client.post("/api/v1/church/search", json={"location": "  Switzerland  "})

            assert response.status_code == 200
            assert response.json()["location"] == "Switzerland"


class TestChurchSearchIntegration:
    """Integration tests that call the real external API."""

    @pytest.mark.skipif(
        True,  # Skip by default - enable for manual integration testing
        reason="Integration test - calls real external API",
    )
    def test_real_api_search(self):
        """Test actual API call to disciplestoday.org."""
        response = client.post("/api/v1/church/search", json={"location": "Switzerland"})

        assert response.status_code == 200
        data = response.json()
        assert "churches" in data
        assert "total" in data
        assert data["location"] == "Switzerland"
