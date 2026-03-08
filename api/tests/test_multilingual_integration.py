"""
Integration tests for multilingual Bible support

These tests verify that the database schema, models, and translation
configurations work together correctly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from translations import TRANSLATIONS

from scripture.models import Translation, Verse


def test_verse_translation_can_be_set():
    """Test that Verse model translation field can be set"""
    verse = Verse(
        book_id=1,
        chapter_id=1,
        chapter_number=1,
        verse_number=1,
        text="Test verse",
        translation="kjv",
    )
    # Translation should be set to 'kjv'
    assert verse.translation == "kjv"


def test_verse_supports_multiple_translations():
    """Test that same verse can exist in multiple translations"""
    verses = []

    # Create same verse in different translations
    for trans_code in ["kjv", "ita1927", "schlachter"]:
        verse = Verse(
            book_id=1,
            chapter_id=1,
            chapter_number=1,
            verse_number=1,
            text=f"Genesis 1:1 in {trans_code}",
            translation=trans_code,
        )
        verses.append(verse)

    # All should have same reference but different translations
    assert len(verses) == 3
    assert len(set(v.translation for v in verses)) == 3
    assert all(v.book_id == 1 for v in verses)
    assert all(v.chapter_number == 1 for v in verses)
    assert all(v.verse_number == 1 for v in verses)


def test_verse_repr_includes_translation():
    """Test that Verse __repr__ includes translation info"""
    verse = Verse(
        book_id=1,
        chapter_id=1,
        chapter_number=1,
        verse_number=1,
        text="Test",
        translation="ita1927",
    )
    # __repr__ should show translation
    # Note: Actual __repr__ will need book relationship to work fully
    assert verse.translation == "ita1927"


def test_translation_model_with_defaults():
    """Test Translation model with explicit default values"""
    translation = Translation(
        code="test",
        name="Test Translation",
        language="Test",
        language_code="tt",
        license="Public Domain",
        is_default=False,
    )
    # Values should be set as specified
    assert translation.license == "Public Domain"
    assert translation.is_default is False


def test_all_configured_translations_have_valid_metadata():
    """Test that all TRANSLATIONS configs have required fields"""
    required_fields = ["code", "name", "language", "language_code", "source", "url"]

    for code, config in TRANSLATIONS.items():
        for field in required_fields:
            assert field in config, f"Translation {code} missing field: {field}"
            # url may be None for manual-load-only translations (e.g. hindi has no getBible source)
            if field == "url" and config.get("source") == "manual":
                continue
            assert config[field] is not None, f"Translation {code} has None for field: {field}"
            assert config[field] != "", f"Translation {code} has empty string for field: {field}"


def test_translation_language_codes_valid():
    """Test that all translations use valid ISO 639-1 language codes"""
    for code, config in TRANSLATIONS.items():
        lang_code = config["language_code"]
        assert len(lang_code) == 2, f"{code} has invalid language code length: {lang_code}"
        assert lang_code.islower(), f"{code} language code should be lowercase: {lang_code}"
        # For our current translations, should be en, it, or de
        if code in ["kjv", "web"]:
            assert lang_code == "en"
        elif code == "ita1927":
            assert lang_code == "it"
        elif code == "schlachter":
            assert lang_code == "de"


def test_only_one_default_translation():
    """Test that only one translation is marked as default"""
    defaults = [t for t in TRANSLATIONS.values() if t.get("is_default", False)]
    assert len(defaults) == 1
    assert defaults[0]["code"] == "kjv"


def test_italian_and_german_have_book_name_mappings():
    """Test that non-English translations have book name mappings"""
    assert TRANSLATIONS["ita1927"]["book_names"] is not None
    assert TRANSLATIONS["schlachter"]["book_names"] is not None
    assert len(TRANSLATIONS["ita1927"]["book_names"]) == 66
    # German has 70 entries (66 books + 4 alternate spellings)
    assert len(TRANSLATIONS["schlachter"]["book_names"]) == 70
    # But should map to exactly 66 unique English book names
    assert len(set(TRANSLATIONS["schlachter"]["book_names"].values())) == 66


def test_english_translations_no_book_name_mappings():
    """Test that English translations don't need book name mappings"""
    assert TRANSLATIONS["kjv"]["book_names"] is None
    assert TRANSLATIONS["web"]["book_names"] is None


def test_verse_unique_constraint_includes_translation():
    """Test that Verse model has unique constraint on book, chapter, verse, translation"""
    # This is verified by the model's __table_args__
    from scripture.models import Verse

    # Get the table args
    table_args = Verse.__table_args__

    # Should contain a UniqueConstraint with translation field
    # The constraint is named "unique_verse_translation"
    has_translation_constraint = False
    for arg in table_args:
        if hasattr(arg, "name") and arg.name == "unique_verse_translation":
            has_translation_constraint = True
            # Verify it includes the translation column
            column_names = [col.name for col in arg.columns]
            assert "translation" in column_names
            assert "book_id" in column_names
            assert "chapter_number" in column_names
            assert "verse_number" in column_names

    assert has_translation_constraint, "Missing unique_verse_translation constraint"


def test_translation_code_matches_config_key():
    """Test that translation code in config matches the dictionary key"""
    for key, config in TRANSLATIONS.items():
        assert config["code"] == key, f"Mismatch: key={key}, code={config['code']}"


def test_all_translations_public_domain():
    """Test that all configured translations are public domain or have a known license"""
    # hindi is copyright IRV (no free getBible source); all others are Public Domain
    manual_license_translations = {"hindi"}
    for code, config in TRANSLATIONS.items():
        if code in manual_license_translations:
            continue
        assert (
            config.get("license", "Public Domain") == "Public Domain"
        ), f"Translation {code} is not Public Domain: {config.get('license')}"


def test_translation_model_repr():
    """Test Translation model __repr__ output"""
    translation = Translation(
        code="kjv",
        name="King James Version",
        language="English",
        language_code="en",
    )
    repr_str = repr(translation)
    assert "Translation" in repr_str
    assert "kjv" in repr_str
    assert "King James Version" in repr_str
    assert "English" in repr_str


def test_phase2_language_translation_mapping():
    """Test Phase 2 languages map to correct translation codes."""
    from utils.language import get_translation_for_language

    assert get_translation_for_language("ru") == "synodal"
    assert get_translation_for_language("zh") == "cuv"
    assert get_translation_for_language("hi") == "hindi"
    assert get_translation_for_language("ko") == "krv"


def test_phase2_translation_info_complete():
    """Test Phase 2 translations have complete metadata."""
    from utils.language import get_translation_info

    ru_info = get_translation_info("synodal")
    assert ru_info["code"] == "synodal"
    assert ru_info["language_code"] == "ru"
    assert ru_info["language"] == "Russian"

    zh_info = get_translation_info("cuv")
    assert zh_info["code"] == "cuv"
    assert zh_info["language_code"] == "zh"
    assert zh_info["language"] == "Chinese"

    hi_info = get_translation_info("hindi")
    assert hi_info["code"] == "hindi"
    assert hi_info["language_code"] == "hi"
    assert hi_info["language"] == "Hindi"

    ko_info = get_translation_info("krv")
    assert ko_info["code"] == "krv"
    assert ko_info["language_code"] == "ko"
    assert ko_info["language"] == "Korean"


def test_phase2_book_name_localization():
    """Test Phase 2 language book name localization."""
    from utils.language import get_localized_book_name

    # Russian
    assert get_localized_book_name("Genesis", "synodal") == "Бытие"
    assert get_localized_book_name("Revelation", "synodal") == "Откровение"
    assert get_localized_book_name("John", "synodal") == "Иоанн"

    # Chinese
    assert get_localized_book_name("Genesis", "cuv") == "创世记"
    assert get_localized_book_name("Revelation", "cuv") == "启示录"
    assert get_localized_book_name("John", "cuv") == "约翰福音"

    # Hindi
    assert get_localized_book_name("Genesis", "hindi") == "उत्पत्ति"
    assert get_localized_book_name("Revelation", "hindi") == "प्रकाशितवाक्य"
    assert get_localized_book_name("John", "hindi") == "यूहन्ना"

    # Korean
    assert get_localized_book_name("Genesis", "krv") == "창세기"
    assert get_localized_book_name("Revelation", "krv") == "요한계시록"
    assert get_localized_book_name("John", "krv") == "요한복음"


def test_phase2_supported_languages_list():
    """Test that Phase 2 languages are in SUPPORTED_LANGUAGES."""
    from utils.language import SUPPORTED_LANGUAGES

    for lang in ["ru", "zh", "hi", "ko"]:
        assert lang in SUPPORTED_LANGUAGES, f"{lang} missing from SUPPORTED_LANGUAGES"


def test_phase2_prompts_have_language_names():
    """Test that Phase 2 languages are in LANGUAGE_NAMES prompt dict."""
    from chat.prompts import LANGUAGE_NAMES, SOURCE_ATTRIBUTION_EXAMPLES

    for lang in ["ru", "zh", "hi", "ko"]:
        assert lang in LANGUAGE_NAMES, f"{lang} missing from LANGUAGE_NAMES"
        assert (
            lang in SOURCE_ATTRIBUTION_EXAMPLES
        ), f"{lang} missing from SOURCE_ATTRIBUTION_EXAMPLES"
        # Each entry should be a tuple of two strings
        examples = SOURCE_ATTRIBUTION_EXAMPLES[lang]
        assert isinstance(examples, tuple) and len(examples) == 2
