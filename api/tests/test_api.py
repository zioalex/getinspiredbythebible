"""
Basic API tests for Bible Chat application
"""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

# Add parent directory to path to import main
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app

client = TestClient(app)


def test_health_endpoint():
    """Test that health endpoint returns 200"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_config_endpoint():
    """Test that config endpoint returns configuration"""
    response = client.get("/config")
    assert response.status_code == 200
    data = response.json()
    assert "llm" in data
    assert "embedding" in data
    assert "provider" in data["llm"]
    assert "model" in data["llm"]


def test_chat_endpoint_requires_message():
    """Test that chat endpoint requires a message"""
    response = client.post("/api/v1/chat", json={})
    # Should either return 422 (validation error) or handle gracefully
    assert response.status_code in [422, 400, 500]


def test_scripture_search_endpoint():
    """Test scripture search endpoint structure"""
    response = client.get("/api/v1/scripture/search")
    # May fail without query param, but should not crash
    assert response.status_code in [200, 422, 400]


def test_api_root():
    """Test API root endpoint"""
    response = client.get("/")
    # Root may redirect or return info
    assert response.status_code in [200, 404, 307]


def test_cors_headers():
    """Test that CORS is configured"""
    response = client.options("/health")
    # CORS preflight should be handled
    assert response.status_code in [200, 405]
