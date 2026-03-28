"""
Tests for the /api/v1/scripture/book-names endpoint.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Add parent directory to path to import main
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app

client = TestClient(app)


def test_book_names_endpoint_returns_200():
    """Endpoint returns HTTP 200."""
    response = client.get("/api/v1/scripture/book-names")
    assert response.status_code == 200


def test_book_names_response_keys():
    """Response JSON contains both required top-level keys."""
    response = client.get("/api/v1/scripture/book-names")
    data = response.json()
    assert "localized_to_english" in data
    assert "multi_word_names" in data


def test_book_names_spot_check_italian():
    """Italian: 'Genesi' maps to 'Genesis'."""
    response = client.get("/api/v1/scripture/book-names")
    mapping = response.json()["localized_to_english"]
    assert mapping.get("Genesi") == "Genesis"


def test_book_names_spot_check_german():
    """German: 'Johannes' maps to 'John'."""
    response = client.get("/api/v1/scripture/book-names")
    mapping = response.json()["localized_to_english"]
    assert mapping.get("Johannes") == "John"


def test_book_names_spot_check_spanish():
    """Spanish: 'Juan' maps to 'John'."""
    response = client.get("/api/v1/scripture/book-names")
    mapping = response.json()["localized_to_english"]
    assert mapping.get("Juan") == "John"


def test_book_names_spot_check_french():
    """French: 'Jean' maps to 'John'."""
    response = client.get("/api/v1/scripture/book-names")
    mapping = response.json()["localized_to_english"]
    assert mapping.get("Jean") == "John"


def test_book_names_spot_check_portuguese():
    """Portuguese: 'João' maps to 'John'."""
    response = client.get("/api/v1/scripture/book-names")
    mapping = response.json()["localized_to_english"]
    assert mapping.get("João") == "John"


def test_book_names_spot_check_arabic():
    """Arabic: 'يوحنا' maps to 'John'."""
    response = client.get("/api/v1/scripture/book-names")
    mapping = response.json()["localized_to_english"]
    assert mapping.get("يوحنا") == "John"


def test_book_names_spot_check_russian():
    """Russian: 'Иоанн' maps to 'John'."""
    response = client.get("/api/v1/scripture/book-names")
    mapping = response.json()["localized_to_english"]
    assert mapping.get("Иоанн") == "John"


def test_book_names_spot_check_chinese():
    """Chinese: '约翰福音' maps to 'John'."""
    response = client.get("/api/v1/scripture/book-names")
    mapping = response.json()["localized_to_english"]
    assert mapping.get("约翰福音") == "John"


def test_book_names_spot_check_korean():
    """Korean: '요한복음' maps to 'John'."""
    response = client.get("/api/v1/scripture/book-names")
    mapping = response.json()["localized_to_english"]
    assert mapping.get("요한복음") == "John"


def test_book_names_spot_check_hindi():
    """Hindi: 'यूहन्ना' maps to 'John'."""
    response = client.get("/api/v1/scripture/book-names")
    mapping = response.json()["localized_to_english"]
    assert mapping.get("यूहन्ना") == "John"


def test_book_names_spot_check_english_alias():
    """English alias: 'Psalm' maps to 'Psalms'."""
    response = client.get("/api/v1/scripture/book-names")
    mapping = response.json()["localized_to_english"]
    assert mapping.get("Psalm") == "Psalms"


def test_multi_word_names_sorted_longest_first():
    """multi_word_names list is sorted longest-first."""
    response = client.get("/api/v1/scripture/book-names")
    names = response.json()["multi_word_names"]
    assert names == sorted(names, key=len, reverse=True)


def test_multi_word_names_no_number_prefixed_entries():
    """multi_word_names does NOT contain number-prefixed entries like '1 Samuel'."""
    response = client.get("/api/v1/scripture/book-names")
    names = response.json()["multi_word_names"]
    for name in names:
        assert not name[0].isdigit(), (
            f"Number-prefixed entry found in multi_word_names: '{name}'"
        )


def test_multi_word_names_known_entries_present():
    """Known multi-word book names are present in multi_word_names."""
    response = client.get("/api/v1/scripture/book-names")
    names = response.json()["multi_word_names"]
    names_set = set(names)

    expected = [
        "Song of Solomon",    # English
        "Плач Иеремии",       # Russian
        "مراثي إرميا",        # Arabic
        "भजन संहिता",         # Hindi
        "예레미야 애가",       # Korean
    ]
    for name in expected:
        assert name in names_set, f"Expected '{name}' in multi_word_names but it was missing"


def test_cache_control_header():
    """Response includes Cache-Control: public, max-age=86400 header."""
    response = client.get("/api/v1/scripture/book-names")
    cache_header = response.headers.get("cache-control", "")
    assert "public" in cache_header
    assert "max-age=86400" in cache_header
