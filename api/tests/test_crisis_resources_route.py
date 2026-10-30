"""BITB-255: POST /api/v1/crisis-resources (re-render the card after the user picks a country)."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
from utils.crisis_resources import CrisisKind, build_crisis_payload

client = TestClient(app, headers={"X-Real-IP": "203.0.113.7"})
URL = "/api/v1/crisis-resources"
LANGUAGES = ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"]


@pytest.fixture(autouse=True)
def _no_rate_limit_store():
    """The real limiter needs Postgres; the dependency wiring is asserted separately."""
    from utils.security import require_rate_limit

    async def _allow():
        return None

    app.dependency_overrides[require_rate_limit] = _allow
    yield
    app.dependency_overrides.pop(require_rate_limit, None)


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("kind", ["self_harm", "threat_to_others"])
def test_returns_same_payload_shape_with_override_source(kind, language):
    response = client.post(URL, json={"country": "it", "language": language, "kind": kind})
    assert response.status_code == 200
    body = response.json()
    assert body == build_crisis_payload(CrisisKind(kind), "IT", "override", language)
    assert body["country"] == "IT"
    assert body["country_source"] == "override"
    assert body["kind"] == kind
    assert body["emergency"]["number"] == "112"


def test_country_picks_that_countrys_numbers():
    us = client.post(URL, json={"country": "US", "kind": "self_harm"}).json()
    gb = client.post(URL, json={"country": "GB", "kind": "self_harm"}).json()
    assert us["emergency"]["number"] != gb["emergency"]["number"]
    assert any(line["phone"] == "988" for line in us["lines"])


@pytest.mark.parametrize("country", ["", "ZZZ", "1", "en-US", "XX", "T1", "<script>"])
def test_invalid_country_returns_international_only(country):
    response = client.post(URL, json={"country": country, "kind": "self_harm"})
    assert response.status_code == 200
    body = response.json()
    assert body["country"] is None
    assert body["emergency"] is None
    assert body["lines"] == []
    assert body["international_url"]


def test_missing_country_returns_international_only():
    body = client.post(URL, json={"kind": "threat_to_others"}).json()
    assert body["country"] is None and body["lines"] == []


@pytest.mark.parametrize("kind", ["", "other", "SELF_HARM"])
def test_invalid_kind_is_422(kind):
    assert client.post(URL, json={"country": "US", "kind": kind}).status_code == 422


def test_missing_kind_is_422():
    assert client.post(URL, json={"country": "US"}).status_code == 422


def test_is_rate_limited_with_existing_dependency():
    from fastapi import HTTPException

    from utils.security import require_rate_limit

    async def _deny():
        raise HTTPException(status_code=429, detail="slow down")

    app.dependency_overrides[require_rate_limit] = _deny  # autouse fixture pops it
    response = client.post(URL, json={"country": "US", "kind": "self_harm"})
    assert response.status_code == 429


def test_logs_only_counts_never_the_country(caplog):
    with caplog.at_level("DEBUG"), patch("routes.crisis.crisis_resources_lookup_counter") as ctr:
        client.post(URL, json={"country": "BR", "language": "pt", "kind": "self_harm"})
    ctr.add.assert_called_once_with(1, {"kind": "self_harm", "language": "pt"})
    assert "BR" not in " ".join(r.getMessage() for r in caplog.records if "crisis" in r.name)


@pytest.mark.parametrize(
    "language,expected",
    [("pt-BR", "pt"), ("zh_CN", "zh"), ("xx", "en"), ("a" * 16, "en"), (None, "en")],
)
def test_language_is_clamped_to_supported_set_for_payload_and_metric(language, expected):
    with patch("routes.crisis.crisis_resources_lookup_counter") as ctr:
        body = client.post(
            URL, json={"country": "IT", "language": language, "kind": "self_harm"}
        ).json()
    ctr.add.assert_called_once_with(1, {"kind": "self_harm", "language": expected})
    assert body == build_crisis_payload(CrisisKind.SELF_HARM, "IT", "override", expected)


def test_get_is_rejected_so_country_never_travels_in_the_url():
    response = client.get(URL, params={"country": "US", "kind": "self_harm"})
    assert response.status_code == 405


def test_country_is_read_only_from_the_body_not_the_query_string():
    body = client.post(URL + "?country=US", json={"country": "GB", "kind": "self_harm"}).json()
    assert body["country"] == "GB"
    no_body_country = client.post(URL + "?country=US", json={"kind": "self_harm"}).json()
    assert no_body_country["country"] is None
