"""
Tests for the language detection and translation mapping utilities.
"""

from utils.language import (
    DEFAULT_TRANSLATION,
    ENGLISH_TO_GERMAN_BOOKS,
    ENGLISH_TO_ITALIAN_BOOKS,
    LANGUAGE_TO_TRANSLATION,
    LANGUAGE_TRANSLATIONS,
    TRANSLATION_INFO,
    detect_language,
    detect_translation,
    get_all_translations,
    get_localized_book_name,
    get_translation_for_language,
    get_translation_info,
    get_translations_for_language,
    is_valid_translation,
    resolve_translation,
)


class TestLanguageDetection:
    """Tests for language detection."""

    def test_detect_english(self):
        """Test detection of English text."""
        texts = [
            "Hello, I need help with my life",
            "I am feeling anxious about the future",
            "What does the Bible say about forgiveness?",
        ]
        for text in texts:
            assert detect_language(text) == "en"

    def test_detect_italian(self):
        """Test detection of Italian text."""
        texts = [
            "Ciao, ho bisogno di aiuto con la mia vita",
            "Mi sento ansioso per il futuro",
            "Cosa dice la Bibbia sul perdono?",
        ]
        for text in texts:
            assert detect_language(text) == "it"

    def test_detect_german(self):
        """Test detection of German text."""
        texts = [
            "Hallo, ich brauche Hilfe mit meinem Leben",
            "Ich fühle mich ängstlich über die Zukunft",
            "Was sagt die Bibel über Vergebung?",
        ]
        for text in texts:
            assert detect_language(text) == "de"

    def test_short_text_defaults_to_english(self):
        """Test that very short text defaults to English."""
        assert detect_language("Hi") == "en"
        assert detect_language("") == "en"
        assert detect_language("   ") == "en"

    def test_none_text_defaults_to_english(self):
        """Test that None-like text defaults to English."""
        assert detect_language("") == "en"


class TestTranslationMapping:
    """Tests for translation mapping."""

    def test_get_translation_for_english(self):
        """Test English maps to WEB (default)."""
        assert get_translation_for_language("en") == "web"

    def test_get_translation_for_italian(self):
        """Test Italian maps to Riveduta 1927."""
        assert get_translation_for_language("it") == "ita1927"

    def test_get_translation_for_german(self):
        """Test German maps to Schlachter."""
        assert get_translation_for_language("de") == "schlachter"

    def test_get_translation_for_unknown_language(self):
        """Test unknown language defaults to KJV."""
        assert get_translation_for_language("fr") == DEFAULT_TRANSLATION
        assert get_translation_for_language("es") == DEFAULT_TRANSLATION
        assert get_translation_for_language("xx") == DEFAULT_TRANSLATION

    def test_detect_translation_english(self):
        """Test full detection pipeline for English."""
        assert detect_translation("I need encouragement today") == "web"

    def test_detect_translation_italian(self):
        """Test full detection pipeline for Italian."""
        assert detect_translation("Ho bisogno di incoraggiamento oggi") == "ita1927"

    def test_detect_translation_german(self):
        """Test full detection pipeline for German."""
        assert detect_translation("Ich brauche heute Ermutigung") == "schlachter"


class TestTranslationInfo:
    """Tests for translation info retrieval."""

    def test_get_kjv_info(self):
        """Test KJV translation info."""
        info = get_translation_info("kjv")
        assert info["code"] == "kjv"
        assert info["name"] == "King James Version"
        assert info["short_name"] == "KJV"
        assert info["language"] == "English"
        assert info["language_code"] == "en"

    def test_get_italian_info(self):
        """Test Italian translation info."""
        info = get_translation_info("ita1927")
        assert info["code"] == "ita1927"
        assert info["name"] == "Riveduta 1927"
        assert info["short_name"] == "Riveduta"
        assert info["language"] == "Italian"
        assert info["language_code"] == "it"

    def test_get_german_info(self):
        """Test German translation info."""
        info = get_translation_info("schlachter")
        assert info["code"] == "schlachter"
        assert info["name"] == "Schlachter 1951"
        assert info["short_name"] == "Schlachter"
        assert info["language"] == "German"
        assert info["language_code"] == "de"

    def test_get_unknown_translation_returns_default(self):
        """Test unknown translation returns default (WEB)."""
        info = get_translation_info("unknown")
        assert info["code"] == "web"

    def test_all_translations_have_required_fields(self):
        """Test all translations have required fields."""
        required_fields = ["code", "name", "short_name", "language", "language_code"]
        for code in TRANSLATION_INFO:
            info = get_translation_info(code)
            for field in required_fields:
                assert field in info, f"{code} missing {field}"


class TestBookNameLocalization:
    """Tests for book name localization."""

    def test_localize_genesis_italian(self):
        """Test Genesis localizes to Italian."""
        assert get_localized_book_name("Genesis", "ita1927") == "Genesi"

    def test_localize_genesis_german(self):
        """Test Genesis localizes to German."""
        assert get_localized_book_name("Genesis", "schlachter") == "1. Mose"

    def test_localize_genesis_english(self):
        """Test Genesis stays English for KJV."""
        assert get_localized_book_name("Genesis", "kjv") == "Genesis"

    def test_localize_matthew_italian(self):
        """Test Matthew localizes to Italian."""
        assert get_localized_book_name("Matthew", "ita1927") == "Matteo"

    def test_localize_matthew_german(self):
        """Test Matthew localizes to German."""
        assert get_localized_book_name("Matthew", "schlachter") == "Matthäus"

    def test_localize_psalms_italian(self):
        """Test Psalms localizes to Italian."""
        assert get_localized_book_name("Psalms", "ita1927") == "Salmi"

    def test_localize_psalms_german(self):
        """Test Psalms localizes to German."""
        assert get_localized_book_name("Psalms", "schlachter") == "Psalmen"

    def test_localize_revelation_italian(self):
        """Test Revelation localizes to Italian."""
        assert get_localized_book_name("Revelation", "ita1927") == "Apocalisse"

    def test_localize_revelation_german(self):
        """Test Revelation localizes to German."""
        assert get_localized_book_name("Revelation", "schlachter") == "Offenbarung"

    def test_unknown_book_returns_original(self):
        """Test unknown book returns original name."""
        assert get_localized_book_name("UnknownBook", "ita1927") == "UnknownBook"
        assert get_localized_book_name("UnknownBook", "schlachter") == "UnknownBook"

    def test_all_66_books_have_italian_translation(self):
        """Test all 66 Bible books have Italian translations."""
        assert len(ENGLISH_TO_ITALIAN_BOOKS) == 66

    def test_all_66_books_have_german_translation(self):
        """Test all 66 Bible books have German translations."""
        # German has some alternate spellings, so >= 66
        assert len(ENGLISH_TO_GERMAN_BOOKS) >= 66

    def test_italian_mappings_are_unique(self):
        """Test Italian book names are unique."""
        italian_names = list(ENGLISH_TO_ITALIAN_BOOKS.values())
        assert len(italian_names) == len(set(italian_names))

    def test_german_mappings_cover_standard_books(self):
        """Test German mappings cover standard English books."""
        standard_books = [
            "Genesis",
            "Exodus",
            "Psalms",
            "Proverbs",
            "Isaiah",
            "Matthew",
            "Mark",
            "Luke",
            "John",
            "Acts",
            "Romans",
            "Revelation",
        ]
        for book in standard_books:
            assert book in ENGLISH_TO_GERMAN_BOOKS


class TestLanguageToTranslationMapping:
    """Tests for the language to translation mapping."""

    def test_all_supported_languages_have_mappings(self):
        """Test all supported languages have translation mappings."""
        supported = ["en", "it", "de"]
        for lang in supported:
            assert lang in LANGUAGE_TO_TRANSLATION

    def test_mapping_values_exist_in_translation_info(self):
        """Test all mapped translations exist in TRANSLATION_INFO."""
        for translation in LANGUAGE_TO_TRANSLATION.values():
            assert translation in TRANSLATION_INFO

    def test_english_has_multiple_translations(self):
        """Test English has multiple translation options."""
        assert len(LANGUAGE_TRANSLATIONS["en"]) >= 2
        assert "web" in LANGUAGE_TRANSLATIONS["en"]
        assert "kjv" in LANGUAGE_TRANSLATIONS["en"]


class TestGetAllTranslations:
    """Tests for get_all_translations."""

    def test_returns_list(self):
        """Test returns a list."""
        result = get_all_translations()
        assert isinstance(result, list)

    def test_returns_all_translations(self):
        """Test returns all configured translations."""
        result = get_all_translations()
        assert len(result) == len(TRANSLATION_INFO)

    def test_each_translation_has_required_fields(self):
        """Test each translation has required fields."""
        required = ["code", "name", "short_name", "language", "language_code"]
        for trans in get_all_translations():
            for field in required:
                assert field in trans


class TestGetTranslationsForLanguage:
    """Tests for get_translations_for_language."""

    def test_english_returns_multiple(self):
        """Test English has multiple translations."""
        result = get_translations_for_language("en")
        assert len(result) >= 2

    def test_italian_returns_one(self):
        """Test Italian has one translation."""
        result = get_translations_for_language("it")
        assert len(result) == 1
        assert result[0]["code"] == "ita1927"

    def test_german_returns_one(self):
        """Test German has one translation."""
        result = get_translations_for_language("de")
        assert len(result) == 1
        assert result[0]["code"] == "schlachter"

    def test_unknown_language_returns_empty(self):
        """Test unknown language returns empty list."""
        result = get_translations_for_language("fr")
        assert result == []


class TestIsValidTranslation:
    """Tests for is_valid_translation."""

    def test_valid_translations(self):
        """Test valid translation codes."""
        assert is_valid_translation("kjv") is True
        assert is_valid_translation("web") is True
        assert is_valid_translation("ita1927") is True
        assert is_valid_translation("schlachter") is True

    def test_invalid_translations(self):
        """Test invalid translation codes."""
        assert is_valid_translation("invalid") is False
        assert is_valid_translation("") is False
        assert is_valid_translation("KJV") is False  # Case sensitive


class TestResolveTranslation:
    """Tests for resolve_translation."""

    def test_preferred_translation_used(self):
        """Test user preference is used when valid."""
        assert resolve_translation("kjv", "en") == "kjv"
        assert resolve_translation("ita1927", "en") == "ita1927"

    def test_invalid_preference_falls_back_to_language(self):
        """Test invalid preference falls back to language default."""
        assert resolve_translation("invalid", "it") == "ita1927"
        assert resolve_translation("invalid", "de") == "schlachter"

    def test_no_preference_uses_language(self):
        """Test no preference uses language-based default."""
        assert resolve_translation(None, "en") == "web"
        assert resolve_translation(None, "it") == "ita1927"
        assert resolve_translation(None, "de") == "schlachter"

    def test_no_preference_no_language_uses_default(self):
        """Test no preference and no language uses global default."""
        assert resolve_translation(None, None) == DEFAULT_TRANSLATION

    def test_empty_string_preference_falls_back(self):
        """Test empty string preference falls back."""
        assert resolve_translation("", "it") == "ita1927"
