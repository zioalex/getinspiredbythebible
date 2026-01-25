"""
Tests for translation configurations and book name mappings
"""

import sys
from pathlib import Path

import httpx
import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from translations import (
    GERMAN_BOOK_NAMES,
    ITALIAN_BOOK_NAMES,
    TRANSLATIONS,
    get_translation_config,
    list_available_translations,
    map_book_name,
)


def test_italian_book_names_complete():
    """Test that all 66 Bible books have Italian mappings"""
    assert len(ITALIAN_BOOK_NAMES) == 66
    # Check a few key books
    assert ITALIAN_BOOK_NAMES["Genesi"] == "Genesis"
    assert ITALIAN_BOOK_NAMES["Matteo"] == "Matthew"
    assert ITALIAN_BOOK_NAMES["Apocalisse"] == "Revelation"


def test_german_book_names_complete():
    """Test that all 66 Bible books have German mappings"""
    assert len(GERMAN_BOOK_NAMES) == 66
    # Check a few key books
    assert GERMAN_BOOK_NAMES["1. Mose"] == "Genesis"
    assert GERMAN_BOOK_NAMES["Matthäus"] == "Matthew"
    assert GERMAN_BOOK_NAMES["Offenbarung"] == "Revelation"


def test_italian_old_testament_books():
    """Test Italian Old Testament book mappings"""
    old_testament_samples = {
        "Genesi": "Genesis",
        "Esodo": "Exodus",
        "Salmi": "Psalms",
        "Isaia": "Isaiah",
        "Geremia": "Jeremiah",
    }
    for italian, english in old_testament_samples.items():
        assert ITALIAN_BOOK_NAMES[italian] == english


def test_italian_new_testament_books():
    """Test Italian New Testament book mappings"""
    new_testament_samples = {
        "Matteo": "Matthew",
        "Marco": "Mark",
        "Luca": "Luke",
        "Giovanni": "John",
        "Romani": "Romans",
        "1 Corinzi": "1 Corinthians",
        "Apocalisse": "Revelation",
    }
    for italian, english in new_testament_samples.items():
        assert ITALIAN_BOOK_NAMES[italian] == english


def test_german_old_testament_books():
    """Test German Old Testament book mappings"""
    old_testament_samples = {
        "1. Mose": "Genesis",
        "2. Mose": "Exodus",
        "Psalmen": "Psalms",
        "Jesaja": "Isaiah",
        "Jeremia": "Jeremiah",
    }
    for german, english in old_testament_samples.items():
        assert GERMAN_BOOK_NAMES[german] == english


def test_german_new_testament_books():
    """Test German New Testament book mappings"""
    new_testament_samples = {
        "Matthäus": "Matthew",
        "Markus": "Mark",
        "Lukas": "Luke",
        "Johannes": "John",
        "Römer": "Romans",
        "1. Korinther": "1 Corinthians",
        "Offenbarung": "Revelation",
    }
    for german, english in new_testament_samples.items():
        assert GERMAN_BOOK_NAMES[german] == english


def test_translations_config_exists():
    """Test that translations configuration exists for all expected translations"""
    assert "kjv" in TRANSLATIONS
    assert "web" in TRANSLATIONS
    assert "ita1927" in TRANSLATIONS
    assert "deu1912" in TRANSLATIONS


def test_kjv_translation_config():
    """Test KJV translation configuration"""
    kjv = TRANSLATIONS["kjv"]
    assert kjv["code"] == "kjv"
    assert kjv["name"] == "King James Version"
    assert kjv["language"] == "English"
    assert kjv["language_code"] == "en"
    assert kjv["is_default"] is True
    assert kjv["book_names"] is None  # English uses standard names


def test_italian_translation_config():
    """Test Italian translation configuration"""
    ita = TRANSLATIONS["ita1927"]
    assert ita["code"] == "ita1927"
    assert ita["name"] == "Riveduta 1927"
    assert ita["language"] == "Italian"
    assert ita["language_code"] == "it"
    assert ita["is_default"] is False
    assert ita["book_names"] == ITALIAN_BOOK_NAMES


def test_german_translation_config():
    """Test German translation configuration"""
    deu = TRANSLATIONS["deu1912"]
    assert deu["code"] == "deu1912"
    assert deu["name"] == "Lutherbibel 1912"
    assert deu["language"] == "German"
    assert deu["language_code"] == "de"
    assert deu["is_default"] is False
    assert deu["book_names"] == GERMAN_BOOK_NAMES


def test_get_translation_config():
    """Test get_translation_config function"""
    config = get_translation_config("kjv")
    assert config["code"] == "kjv"
    assert config["name"] == "King James Version"


def test_get_translation_config_invalid():
    """Test get_translation_config with invalid code raises error"""
    try:
        get_translation_config("invalid_code")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unknown translation code" in str(e)


def test_list_available_translations():
    """Test list_available_translations function"""
    translations = list_available_translations()
    assert len(translations) == 4  # kjv, web, ita1927, deu1912

    # Check structure
    assert all("code" in t for t in translations)
    assert all("name" in t for t in translations)
    assert all("language" in t for t in translations)
    assert all("language_code" in t for t in translations)


def test_map_book_name_italian():
    """Test book name mapping for Italian"""
    assert map_book_name("Genesi", "ita1927") == "Genesis"
    assert map_book_name("Matteo", "ita1927") == "Matthew"
    assert map_book_name("Apocalisse", "ita1927") == "Revelation"


def test_map_book_name_german():
    """Test book name mapping for German"""
    assert map_book_name("1. Mose", "deu1912") == "Genesis"
    assert map_book_name("Matthäus", "deu1912") == "Matthew"
    assert map_book_name("Offenbarung", "deu1912") == "Revelation"


def test_map_book_name_english():
    """Test book name mapping for English (passthrough)"""
    # English translations should return the name as-is
    assert map_book_name("Genesis", "kjv") == "Genesis"
    assert map_book_name("Matthew", "kjv") == "Matthew"
    assert map_book_name("Revelation", "web") == "Revelation"


def test_map_book_name_unknown_book():
    """Test book name mapping with unknown book returns original"""
    # Should return the original name if not in mapping
    assert map_book_name("UnknownBook", "ita1927") == "UnknownBook"


def test_all_italian_books_unique():
    """Test that all Italian book names map to unique English names"""
    english_names = list(ITALIAN_BOOK_NAMES.values())
    assert len(english_names) == len(set(english_names))


def test_all_german_books_unique():
    """Test that all German book names map to unique English names"""
    english_names = list(GERMAN_BOOK_NAMES.values())
    assert len(english_names) == len(set(english_names))


def test_translation_urls_valid():
    """Test that all translation configs have valid URLs"""
    for code, config in TRANSLATIONS.items():
        assert "url" in config
        assert config["url"].startswith("http")
        # Check URL format
        assert "://" in config["url"]


def test_translation_sources():
    """Test that translations have valid source specifications"""
    valid_sources = ["thiagobodruk", "getbible", "scrollmapper"]
    for code, config in TRANSLATIONS.items():
        assert "source" in config
        assert config["source"] in valid_sources


@pytest.mark.network
def test_translation_urls_accessible():
    """
    Test that all Bible translation URLs are accessible.

    This test makes actual HTTP requests to verify the URLs are valid.
    Run with: pytest -m network
    Skip with: pytest -m "not network"
    """
    failed_urls = []

    for code, config in TRANSLATIONS.items():
        url = config["url"]
        try:
            # Use HEAD request first (lightweight), fall back to GET if HEAD not supported
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.head(url)
                # Some servers don't support HEAD, try GET if we get 405
                if response.status_code == 405:
                    response = client.get(url)

                if response.status_code != 200:
                    failed_urls.append(f"{code}: {url} returned status {response.status_code}")
        except httpx.RequestError as e:
            failed_urls.append(f"{code}: {url} failed with error: {e}")

    if failed_urls:
        pytest.fail(
            "The following Bible translation URLs are not accessible:\n"
            + "\n".join(f"  - {url}" for url in failed_urls)
        )


@pytest.mark.network
def test_translation_urls_return_valid_json():
    """
    Test that all Bible translation URLs return valid JSON with expected structure.

    This test downloads a small portion of each Bible to verify the format.
    Run with: pytest -m network
    """
    for code, config in TRANSLATIONS.items():
        url = config["url"]
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            response = client.get(url)
            assert response.status_code == 200, f"{code}: Failed to fetch {url}"

            data = response.json()

            # Check for expected structure based on source
            if config["source"] == "getbible":
                # getbible.net format has books as keys
                assert isinstance(data, dict), f"{code}: Expected dict from getbible"
                # Should have book data
                assert len(data) > 0, f"{code}: Empty response from {url}"
            elif config["source"] == "thiagobodruk":
                # thiagobodruk format is a list of books
                assert isinstance(data, list), f"{code}: Expected list from thiagobodruk"
                assert len(data) == 66, f"{code}: Expected 66 books, got {len(data)}"
                # Check first book has expected fields
                first_book = data[0]
                assert "name" in first_book, f"{code}: Missing 'name' field"
                assert "chapters" in first_book, f"{code}: Missing 'chapters' field"
