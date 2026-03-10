"""
Comprehensive tests for book name translation dicts and normalization.

Covers:
- Structural integrity of all 10 language dicts (count, key coverage, no duplicate values)
- Round-trip normalization: every localized value → normalize_book_name() → English key
- Parametrized normalize_book_name() tests for all 66 books in each language
- EXTRA_REVERSE_MAPPINGS exhaustive alias tests
- Russian Synodal ordinal oddities (1-я/2-я/3-я/4-я Царств)
- ALL_BOOK_NAMES set membership (localized forms from verse_parser)
- parse_verse_reference() end-to-end for non-English languages
- get_localized_book_name() parametrized for all non-English languages
"""

import pytest

from utils.book_names import (
    get_localized_book_name,
    normalize_book_name,
)
from utils.translation_registry import (
    ENGLISH_TO_ARABIC,
    ENGLISH_TO_CHINESE,
    ENGLISH_TO_FRENCH,
    ENGLISH_TO_GERMAN,
    ENGLISH_TO_HINDI,
    ENGLISH_TO_ITALIAN,
    ENGLISH_TO_KOREAN,
    ENGLISH_TO_PORTUGUESE,
    ENGLISH_TO_RUSSIAN,
    ENGLISH_TO_SPANISH,
    EXTRA_REVERSE_MAPPINGS,
)

# ---------------------------------------------------------------------------
# Reference: the canonical 66-book Protestant canon English names.
# We derive this from ENGLISH_TO_ITALIAN (all dicts share the same key set).
# ---------------------------------------------------------------------------
ALL_BOOKS = list(ENGLISH_TO_ITALIAN.keys())

# ---------------------------------------------------------------------------
# Helper: expected 66-entry count
# ---------------------------------------------------------------------------
EXPECTED_COUNT = 66


# ===========================================================================
# 3a — Structural integrity tests (per language)
# ===========================================================================


class TestItalianDictIntegrity:
    def test_italian_dict_has_66_entries(self):
        assert len(ENGLISH_TO_ITALIAN) == EXPECTED_COUNT

    def test_italian_dict_covers_all_canonical_english_books(self):
        assert set(ENGLISH_TO_ITALIAN.keys()) == set(ALL_BOOKS)

    def test_italian_dict_has_no_duplicate_values(self):
        values = list(ENGLISH_TO_ITALIAN.values())
        assert len(values) == len(set(values)), "ENGLISH_TO_ITALIAN has duplicate values"

    def test_italian_all_values_round_trip_via_normalize(self):
        for eng_key, localized_val in ENGLISH_TO_ITALIAN.items():
            result = normalize_book_name(localized_val)
            assert (
                result == eng_key
            ), f"normalize_book_name({localized_val!r}) returned {result!r}, expected {eng_key!r}"


class TestGermanDictIntegrity:
    def test_german_dict_has_66_entries(self):
        assert len(ENGLISH_TO_GERMAN) == EXPECTED_COUNT

    def test_german_dict_covers_all_canonical_english_books(self):
        assert set(ENGLISH_TO_GERMAN.keys()) == set(ALL_BOOKS)

    def test_german_dict_has_no_duplicate_values(self):
        values = list(ENGLISH_TO_GERMAN.values())
        assert len(values) == len(set(values)), "ENGLISH_TO_GERMAN has duplicate values"

    def test_german_all_values_round_trip_via_normalize(self):
        for eng_key, localized_val in ENGLISH_TO_GERMAN.items():
            result = normalize_book_name(localized_val)
            assert (
                result == eng_key
            ), f"normalize_book_name({localized_val!r}) returned {result!r}, expected {eng_key!r}"


class TestSpanishDictIntegrity:
    def test_spanish_dict_has_66_entries(self):
        assert len(ENGLISH_TO_SPANISH) == EXPECTED_COUNT

    def test_spanish_dict_covers_all_canonical_english_books(self):
        assert set(ENGLISH_TO_SPANISH.keys()) == set(ALL_BOOKS)

    def test_spanish_dict_has_no_duplicate_values(self):
        values = list(ENGLISH_TO_SPANISH.values())
        assert len(values) == len(set(values)), "ENGLISH_TO_SPANISH has duplicate values"

    def test_spanish_all_values_round_trip_via_normalize(self):
        for eng_key, localized_val in ENGLISH_TO_SPANISH.items():
            result = normalize_book_name(localized_val)
            assert (
                result == eng_key
            ), f"normalize_book_name({localized_val!r}) returned {result!r}, expected {eng_key!r}"


class TestFrenchDictIntegrity:
    def test_french_dict_has_66_entries(self):
        assert len(ENGLISH_TO_FRENCH) == EXPECTED_COUNT

    def test_french_dict_covers_all_canonical_english_books(self):
        assert set(ENGLISH_TO_FRENCH.keys()) == set(ALL_BOOKS)

    def test_french_dict_has_no_duplicate_values(self):
        values = list(ENGLISH_TO_FRENCH.values())
        assert len(values) == len(set(values)), "ENGLISH_TO_FRENCH has duplicate values"

    def test_french_all_values_round_trip_via_normalize(self):
        for eng_key, localized_val in ENGLISH_TO_FRENCH.items():
            result = normalize_book_name(localized_val)
            assert (
                result == eng_key
            ), f"normalize_book_name({localized_val!r}) returned {result!r}, expected {eng_key!r}"


class TestPortugueseDictIntegrity:
    def test_portuguese_dict_has_66_entries(self):
        assert len(ENGLISH_TO_PORTUGUESE) == EXPECTED_COUNT

    def test_portuguese_dict_covers_all_canonical_english_books(self):
        assert set(ENGLISH_TO_PORTUGUESE.keys()) == set(ALL_BOOKS)

    def test_portuguese_dict_has_no_duplicate_values(self):
        values = list(ENGLISH_TO_PORTUGUESE.values())
        assert len(values) == len(set(values)), "ENGLISH_TO_PORTUGUESE has duplicate values"

    def test_portuguese_all_values_round_trip_via_normalize(self):
        for eng_key, localized_val in ENGLISH_TO_PORTUGUESE.items():
            result = normalize_book_name(localized_val)
            assert (
                result == eng_key
            ), f"normalize_book_name({localized_val!r}) returned {result!r}, expected {eng_key!r}"


class TestArabicDictIntegrity:
    def test_arabic_dict_has_66_entries(self):
        assert len(ENGLISH_TO_ARABIC) == EXPECTED_COUNT

    def test_arabic_dict_covers_all_canonical_english_books(self):
        assert set(ENGLISH_TO_ARABIC.keys()) == set(ALL_BOOKS)

    def test_arabic_dict_has_no_duplicate_values(self):
        values = list(ENGLISH_TO_ARABIC.values())
        assert len(values) == len(set(values)), "ENGLISH_TO_ARABIC has duplicate values"

    def test_arabic_all_values_round_trip_via_normalize(self):
        for eng_key, localized_val in ENGLISH_TO_ARABIC.items():
            result = normalize_book_name(localized_val)
            assert (
                result == eng_key
            ), f"normalize_book_name({localized_val!r}) returned {result!r}, expected {eng_key!r}"


class TestRussianDictIntegrity:
    def test_russian_dict_has_66_entries(self):
        assert len(ENGLISH_TO_RUSSIAN) == EXPECTED_COUNT

    def test_russian_dict_covers_all_canonical_english_books(self):
        assert set(ENGLISH_TO_RUSSIAN.keys()) == set(ALL_BOOKS)

    def test_russian_dict_has_no_duplicate_values(self):
        values = list(ENGLISH_TO_RUSSIAN.values())
        assert len(values) == len(set(values)), "ENGLISH_TO_RUSSIAN has duplicate values"

    def test_russian_all_values_round_trip_via_normalize(self):
        for eng_key, localized_val in ENGLISH_TO_RUSSIAN.items():
            result = normalize_book_name(localized_val)
            assert (
                result == eng_key
            ), f"normalize_book_name({localized_val!r}) returned {result!r}, expected {eng_key!r}"


class TestChineseDictIntegrity:
    def test_chinese_dict_has_66_entries(self):
        assert len(ENGLISH_TO_CHINESE) == EXPECTED_COUNT

    def test_chinese_dict_covers_all_canonical_english_books(self):
        assert set(ENGLISH_TO_CHINESE.keys()) == set(ALL_BOOKS)

    def test_chinese_dict_has_no_duplicate_values(self):
        values = list(ENGLISH_TO_CHINESE.values())
        assert len(values) == len(set(values)), "ENGLISH_TO_CHINESE has duplicate values"

    def test_chinese_all_values_round_trip_via_normalize(self):
        for eng_key, localized_val in ENGLISH_TO_CHINESE.items():
            result = normalize_book_name(localized_val)
            assert (
                result == eng_key
            ), f"normalize_book_name({localized_val!r}) returned {result!r}, expected {eng_key!r}"


class TestKoreanDictIntegrity:
    def test_korean_dict_has_66_entries(self):
        assert len(ENGLISH_TO_KOREAN) == EXPECTED_COUNT

    def test_korean_dict_covers_all_canonical_english_books(self):
        assert set(ENGLISH_TO_KOREAN.keys()) == set(ALL_BOOKS)

    def test_korean_dict_has_no_duplicate_values(self):
        values = list(ENGLISH_TO_KOREAN.values())
        assert len(values) == len(set(values)), "ENGLISH_TO_KOREAN has duplicate values"

    def test_korean_all_values_round_trip_via_normalize(self):
        for eng_key, localized_val in ENGLISH_TO_KOREAN.items():
            result = normalize_book_name(localized_val)
            assert (
                result == eng_key
            ), f"normalize_book_name({localized_val!r}) returned {result!r}, expected {eng_key!r}"


class TestHindiDictIntegrity:
    def test_hindi_dict_has_66_entries(self):
        assert len(ENGLISH_TO_HINDI) == EXPECTED_COUNT

    def test_hindi_dict_covers_all_canonical_english_books(self):
        assert set(ENGLISH_TO_HINDI.keys()) == set(ALL_BOOKS)

    def test_hindi_dict_has_no_duplicate_values(self):
        values = list(ENGLISH_TO_HINDI.values())
        assert len(values) == len(set(values)), "ENGLISH_TO_HINDI has duplicate values"

    def test_hindi_all_values_round_trip_via_normalize(self):
        for eng_key, localized_val in ENGLISH_TO_HINDI.items():
            result = normalize_book_name(localized_val)
            assert (
                result == eng_key
            ), f"normalize_book_name({localized_val!r}) returned {result!r}, expected {eng_key!r}"


# ===========================================================================
# 3b — normalize_book_name() exhaustive parametrized (all 66 books, per lang)
# ===========================================================================


@pytest.mark.parametrize("expected_english,localized", list(ENGLISH_TO_RUSSIAN.items()))
def test_normalize_russian_all_books(expected_english, localized):
    assert normalize_book_name(localized) == expected_english


@pytest.mark.parametrize("expected_english,localized", list(ENGLISH_TO_CHINESE.items()))
def test_normalize_chinese_all_books(expected_english, localized):
    assert normalize_book_name(localized) == expected_english


@pytest.mark.parametrize("expected_english,localized", list(ENGLISH_TO_KOREAN.items()))
def test_normalize_korean_all_books(expected_english, localized):
    assert normalize_book_name(localized) == expected_english


@pytest.mark.parametrize("expected_english,localized", list(ENGLISH_TO_HINDI.items()))
def test_normalize_hindi_all_books(expected_english, localized):
    assert normalize_book_name(localized) == expected_english


@pytest.mark.parametrize("expected_english,localized", list(ENGLISH_TO_PORTUGUESE.items()))
def test_normalize_portuguese_all_books(expected_english, localized):
    assert normalize_book_name(localized) == expected_english


@pytest.mark.parametrize("expected_english,localized", list(ENGLISH_TO_ARABIC.items()))
def test_normalize_arabic_all_books(expected_english, localized):
    assert normalize_book_name(localized) == expected_english


@pytest.mark.parametrize("expected_english,localized", list(ENGLISH_TO_ITALIAN.items()))
def test_normalize_italian_all_books(expected_english, localized):
    assert normalize_book_name(localized) == expected_english


@pytest.mark.parametrize("expected_english,localized", list(ENGLISH_TO_GERMAN.items()))
def test_normalize_german_all_books(expected_english, localized):
    assert normalize_book_name(localized) == expected_english


@pytest.mark.parametrize("expected_english,localized", list(ENGLISH_TO_SPANISH.items()))
def test_normalize_spanish_all_books(expected_english, localized):
    assert normalize_book_name(localized) == expected_english


@pytest.mark.parametrize("expected_english,localized", list(ENGLISH_TO_FRENCH.items()))
def test_normalize_french_all_books(expected_english, localized):
    assert normalize_book_name(localized) == expected_english


# ===========================================================================
# 3c — EXTRA_REVERSE_MAPPINGS exhaustive
# ===========================================================================


@pytest.mark.parametrize("alias,expected_english", list(EXTRA_REVERSE_MAPPINGS.items()))
def test_extra_reverse_mappings_all(alias, expected_english):
    """Every alias in EXTRA_REVERSE_MAPPINGS must round-trip via normalize_book_name()."""
    assert normalize_book_name(alias) == expected_english, (
        f"normalize_book_name({alias!r}) returned {normalize_book_name(alias)!r}, "
        f"expected {expected_english!r}"
    )


# ===========================================================================
# 3d — Russian Synodal ordinal oddities
# ===========================================================================


class TestRussianSynodalOrdinals:
    """
    The Russian Synodal translation uses a non-standard numbering:
      1-я Царств  → 1 Samuel  (Western "1 Samuel")
      2-я Царств  → 2 Samuel  (Western "2 Samuel")
      3-я Царств  → 1 Kings   (Western "1 Kings")
      4-я Царств  → 2 Kings   (Western "2 Kings")

    The dash-ordinal forms are the canonical values in ENGLISH_TO_RUSSIAN.
    The no-dash variants (1 Царств, etc.) live in EXTRA_REVERSE_MAPPINGS.
    """

    def test_normalize_1_samuel_russian_synodal_canonical(self):
        """Canonical dashed form: 1-я Царств → 1 Samuel."""
        assert ENGLISH_TO_RUSSIAN["1 Samuel"] == "1-я Царств"
        assert normalize_book_name("1-я Царств") == "1 Samuel"

    def test_normalize_2_samuel_russian_synodal_canonical(self):
        """Canonical dashed form: 2-я Царств → 2 Samuel."""
        assert ENGLISH_TO_RUSSIAN["2 Samuel"] == "2-я Царств"
        assert normalize_book_name("2-я Царств") == "2 Samuel"

    def test_normalize_1_kings_russian_synodal_canonical(self):
        """Canonical dashed form: 3-я Царств → 1 Kings."""
        assert ENGLISH_TO_RUSSIAN["1 Kings"] == "3-я Царств"
        assert normalize_book_name("3-я Царств") == "1 Kings"

    def test_normalize_2_kings_russian_synodal_canonical(self):
        """Canonical dashed form: 4-я Царств → 2 Kings."""
        assert ENGLISH_TO_RUSSIAN["2 Kings"] == "4-я Царств"
        assert normalize_book_name("4-я Царств") == "2 Kings"

    def test_normalize_1_samuel_nodash_alias(self):
        """No-dash alias 1 Царств (EXTRA_REVERSE_MAPPINGS) → 1 Samuel."""
        assert "1 Царств" in EXTRA_REVERSE_MAPPINGS
        assert normalize_book_name("1 Царств") == "1 Samuel"

    def test_normalize_2_samuel_nodash_alias(self):
        """No-dash alias 2 Царств (EXTRA_REVERSE_MAPPINGS) → 2 Samuel."""
        assert normalize_book_name("2 Царств") == "2 Samuel"

    def test_normalize_1_kings_nodash_alias(self):
        """No-dash alias 3 Царств (EXTRA_REVERSE_MAPPINGS) → 1 Kings."""
        assert normalize_book_name("3 Царств") == "1 Kings"

    def test_normalize_2_kings_nodash_alias(self):
        """No-dash alias 4 Царств (EXTRA_REVERSE_MAPPINGS) → 2 Kings."""
        assert normalize_book_name("4 Царств") == "2 Kings"

    def test_normalize_1_chronicles_russian_canonical(self):
        """1-я Паралипоменон → 1 Chronicles."""
        assert normalize_book_name("1-я Паралипоменон") == "1 Chronicles"

    def test_normalize_2_chronicles_russian_canonical(self):
        """2-я Паралипоменон → 2 Chronicles."""
        assert normalize_book_name("2-я Паралипоменон") == "2 Chronicles"

    def test_normalize_1_chronicles_nodash_alias(self):
        """No-dash alias 1 Паралипоменон → 1 Chronicles."""
        assert normalize_book_name("1 Паралипоменон") == "1 Chronicles"

    def test_normalize_2_chronicles_nodash_alias(self):
        """No-dash alias 2 Паралипоменон → 2 Chronicles."""
        assert normalize_book_name("2 Паралипоменон") == "2 Chronicles"


# ===========================================================================
# 3e — ALL_BOOK_NAMES set contains localized forms
# ===========================================================================


class TestAllBookNamesSetMembership:
    """Verify that ALL_BOOK_NAMES (used by the verse parser regex) contains
    localized forms so that they can be matched in text."""

    def test_all_book_names_contains_english_books(self):
        from utils.verse_parser import ALL_BOOK_NAMES

        for book in ALL_BOOKS:
            assert book in ALL_BOOK_NAMES, f"English book '{book}' missing from ALL_BOOK_NAMES"

    def test_all_book_names_contains_russian_genitive_aliases(self):
        from utils.verse_parser import ALL_BOOK_NAMES

        # A selection of unambiguous Russian genitive citation forms
        russian_genitive_samples = [
            "Иоанна",
            "Матфея",
            "Луки",
            "Марка",
            "Деяний",
            "Откровения",
            "Бытия",
            "Псалтири",
            "Притч",
            "Иакова",
        ]
        for form in russian_genitive_samples:
            assert form in ALL_BOOK_NAMES, f"Russian genitive '{form}' missing from ALL_BOOK_NAMES"

    def test_all_book_names_contains_russian_canonical_forms(self):
        from utils.verse_parser import ALL_BOOK_NAMES

        russian_canonical_samples = [
            "Бытие",
            "Псалтирь",
            "Иоанн",
            "1-я Царств",
            "3-я Царств",
            "Откровение",
        ]
        for form in russian_canonical_samples:
            assert (
                form in ALL_BOOK_NAMES
            ), f"Russian canonical form '{form}' missing from ALL_BOOK_NAMES"

    def test_all_book_names_contains_chinese_books(self):
        from utils.verse_parser import ALL_BOOK_NAMES

        chinese_samples = [
            "创世记",  # Genesis
            "约翰福音",  # John
            "诗篇",  # Psalms
            "哥林多前书",  # 1 Corinthians
            "启示录",  # Revelation (alias)
            "啟示錄",  # Revelation (canonical)
        ]
        for form in chinese_samples:
            assert form in ALL_BOOK_NAMES, f"Chinese book '{form}' missing from ALL_BOOK_NAMES"

    def test_all_book_names_contains_korean_books(self):
        from utils.verse_parser import ALL_BOOK_NAMES

        korean_samples = [
            "창세기",  # Genesis
            "요한복음",  # John
            "시편",  # Psalms
            "고린도전서",  # 1 Corinthians
            "요한계시록",  # Revelation
            "예레미야애가",  # Lamentations (no-space alias)
        ]
        for form in korean_samples:
            assert form in ALL_BOOK_NAMES, f"Korean book '{form}' missing from ALL_BOOK_NAMES"

    def test_all_book_names_contains_hindi_books(self):
        from utils.verse_parser import ALL_BOOK_NAMES

        hindi_samples = [
            "उत्पत्ति",  # Genesis
            "यूहन्ना",  # John
            "भजन संहिता",  # Psalms
            "प्रकाशितवाक्य",  # Revelation
        ]
        for form in hindi_samples:
            assert form in ALL_BOOK_NAMES, f"Hindi book '{form}' missing from ALL_BOOK_NAMES"

    def test_all_book_names_contains_italian_books(self):
        from utils.verse_parser import ALL_BOOK_NAMES

        italian_samples = ["Genesi", "Giovanni", "Salmi", "1 Corinzi", "Apocalisse"]
        for form in italian_samples:
            assert form in ALL_BOOK_NAMES, f"Italian book '{form}' missing from ALL_BOOK_NAMES"

    def test_all_book_names_contains_german_books(self):
        from utils.verse_parser import ALL_BOOK_NAMES

        german_samples = ["1. Mose", "Johannes", "Psalmen", "1. Korinther", "Offenbarung"]
        for form in german_samples:
            assert form in ALL_BOOK_NAMES, f"German book '{form}' missing from ALL_BOOK_NAMES"

    def test_all_book_names_contains_arabic_books(self):
        from utils.verse_parser import ALL_BOOK_NAMES

        arabic_samples = [
            "تكوين",  # Genesis
            "يوحنا",  # John
            "المزامير",  # Psalms
            "الرؤيا",  # Revelation
        ]
        for form in arabic_samples:
            assert form in ALL_BOOK_NAMES, f"Arabic book '{form}' missing from ALL_BOOK_NAMES"

    def test_all_book_names_contains_extra_reverse_mapping_aliases(self):
        from utils.verse_parser import ALL_BOOK_NAMES

        for alias in EXTRA_REVERSE_MAPPINGS:
            assert (
                alias in ALL_BOOK_NAMES
            ), f"EXTRA_REVERSE_MAPPINGS alias '{alias}' missing from ALL_BOOK_NAMES"


# ===========================================================================
# 3g — get_localized_book_name() parametrized (all 66 books, per language)
# ===========================================================================


# Russian — translation code: "synodal"
@pytest.mark.parametrize("english_book", list(ENGLISH_TO_RUSSIAN.keys()))
def test_get_localized_russian_all_books(english_book):
    result = get_localized_book_name(english_book, "synodal")
    assert result == ENGLISH_TO_RUSSIAN[english_book], (
        f"get_localized_book_name({english_book!r}, 'synodal') = {result!r}, "
        f"expected {ENGLISH_TO_RUSSIAN[english_book]!r}"
    )


# Chinese — translation code: "cuv"
@pytest.mark.parametrize("english_book", list(ENGLISH_TO_CHINESE.keys()))
def test_get_localized_chinese_all_books(english_book):
    result = get_localized_book_name(english_book, "cuv")
    assert result == ENGLISH_TO_CHINESE[english_book], (
        f"get_localized_book_name({english_book!r}, 'cuv') = {result!r}, "
        f"expected {ENGLISH_TO_CHINESE[english_book]!r}"
    )


# Korean — translation code: "krv"
@pytest.mark.parametrize("english_book", list(ENGLISH_TO_KOREAN.keys()))
def test_get_localized_korean_all_books(english_book):
    result = get_localized_book_name(english_book, "krv")
    assert result == ENGLISH_TO_KOREAN[english_book], (
        f"get_localized_book_name({english_book!r}, 'krv') = {result!r}, "
        f"expected {ENGLISH_TO_KOREAN[english_book]!r}"
    )


# Hindi — translation code: "hindi"
@pytest.mark.parametrize("english_book", list(ENGLISH_TO_HINDI.keys()))
def test_get_localized_hindi_all_books(english_book):
    result = get_localized_book_name(english_book, "hindi")
    assert result == ENGLISH_TO_HINDI[english_book], (
        f"get_localized_book_name({english_book!r}, 'hindi') = {result!r}, "
        f"expected {ENGLISH_TO_HINDI[english_book]!r}"
    )


# Portuguese — translation code: "almeida"
@pytest.mark.parametrize("english_book", list(ENGLISH_TO_PORTUGUESE.keys()))
def test_get_localized_portuguese_all_books(english_book):
    result = get_localized_book_name(english_book, "almeida")
    assert result == ENGLISH_TO_PORTUGUESE[english_book], (
        f"get_localized_book_name({english_book!r}, 'almeida') = {result!r}, "
        f"expected {ENGLISH_TO_PORTUGUESE[english_book]!r}"
    )


# Arabic — translation code: "arabicsv"
@pytest.mark.parametrize("english_book", list(ENGLISH_TO_ARABIC.keys()))
def test_get_localized_arabic_all_books(english_book):
    result = get_localized_book_name(english_book, "arabicsv")
    assert result == ENGLISH_TO_ARABIC[english_book], (
        f"get_localized_book_name({english_book!r}, 'arabicsv') = {result!r}, "
        f"expected {ENGLISH_TO_ARABIC[english_book]!r}"
    )


# Italian — translation code: "ita1927"
@pytest.mark.parametrize("english_book", list(ENGLISH_TO_ITALIAN.keys()))
def test_get_localized_italian_all_books(english_book):
    result = get_localized_book_name(english_book, "ita1927")
    assert result == ENGLISH_TO_ITALIAN[english_book], (
        f"get_localized_book_name({english_book!r}, 'ita1927') = {result!r}, "
        f"expected {ENGLISH_TO_ITALIAN[english_book]!r}"
    )


# German — translation code: "schlachter"
@pytest.mark.parametrize("english_book", list(ENGLISH_TO_GERMAN.keys()))
def test_get_localized_german_all_books(english_book):
    result = get_localized_book_name(english_book, "schlachter")
    assert result == ENGLISH_TO_GERMAN[english_book], (
        f"get_localized_book_name({english_book!r}, 'schlachter') = {result!r}, "
        f"expected {ENGLISH_TO_GERMAN[english_book]!r}"
    )


# Spanish — translation code: "valera"
@pytest.mark.parametrize("english_book", list(ENGLISH_TO_SPANISH.keys()))
def test_get_localized_spanish_all_books(english_book):
    result = get_localized_book_name(english_book, "valera")
    assert result == ENGLISH_TO_SPANISH[english_book], (
        f"get_localized_book_name({english_book!r}, 'valera') = {result!r}, "
        f"expected {ENGLISH_TO_SPANISH[english_book]!r}"
    )


# French — translation code: "ls1910"
@pytest.mark.parametrize("english_book", list(ENGLISH_TO_FRENCH.keys()))
def test_get_localized_french_all_books(english_book):
    result = get_localized_book_name(english_book, "ls1910")
    assert result == ENGLISH_TO_FRENCH[english_book], (
        f"get_localized_book_name({english_book!r}, 'ls1910') = {result!r}, "
        f"expected {ENGLISH_TO_FRENCH[english_book]!r}"
    )


# ===========================================================================
# Additional edge-case / cross-language tests
# ===========================================================================


class TestNormalizeEdgeCases:
    """Edge cases for normalize_book_name()."""

    def test_english_book_name_returned_unchanged(self):
        for book in ALL_BOOKS:
            assert normalize_book_name(book) == book

    def test_unknown_name_returned_as_is(self):
        assert normalize_book_name("NotABook") == "NotABook"
        assert normalize_book_name("") == ""

    def test_russian_acts_long_form(self):
        """'Деяния апостолов' (full form) → Acts."""
        assert normalize_book_name("Деяния апостолов") == "Acts"

    def test_russian_acts_short_canonical(self):
        """'Деяния' (canonical) → Acts."""
        assert normalize_book_name("Деяния") == "Acts"

    def test_russian_acts_genitive_form(self):
        """'Деяний' (genitive) → Acts."""
        assert normalize_book_name("Деяний") == "Acts"

    def test_chinese_revelation_traditional(self):
        """Traditional Chinese Revelation '啟示錄' → Revelation."""
        assert normalize_book_name("啟示錄") == "Revelation"

    def test_chinese_revelation_simplified_alias(self):
        """Simplified Chinese alias '启示录' → Revelation."""
        assert normalize_book_name("启示录") == "Revelation"

    def test_chinese_genesis_bom_alias(self):
        """BOM-prefixed Chinese Genesis → Genesis."""
        assert normalize_book_name("\ufeff创世记") == "Genesis"

    def test_korean_lamentations_with_space_canonical(self):
        """Korean Lamentations with space '예레미야 애가' → Lamentations."""
        assert normalize_book_name("예레미야 애가") == "Lamentations"

    def test_korean_lamentations_without_space_alias(self):
        """Korean Lamentations without space '예레미야애가' → Lamentations."""
        assert normalize_book_name("예레미야애가") == "Lamentations"

    def test_german_alternate_ruth_alias(self):
        """German alternate 'Rut' (alias for Ruth) → Ruth."""
        assert normalize_book_name("Rut") == "Ruth"

    def test_german_alternate_song_of_solomon(self):
        """German alternate 'Hohes Lied' → Song of Solomon."""
        assert normalize_book_name("Hohes Lied") == "Song of Solomon"

    def test_russian_song_of_songs_alias(self):
        """Russian alternate 'Песня Песней' → Song of Solomon."""
        assert normalize_book_name("Песня Песней") == "Song of Solomon"

    def test_russian_ezekiel_one_i_alias(self):
        """Russian one-и variant 'Иезекиль' → Ezekiel."""
        assert normalize_book_name("Иезекиль") == "Ezekiel"

    def test_russian_corinthians_no_dash_aliases(self):
        """Russian no-dash '1 Коринфянам' / '2 Коринфянам' aliases."""
        assert normalize_book_name("1 Коринфянам") == "1 Corinthians"
        assert normalize_book_name("2 Коринфянам") == "2 Corinthians"

    def test_russian_peter_genitive_aliases(self):
        """Russian genitive Peter aliases."""
        assert normalize_book_name("1 Петра") == "1 Peter"
        assert normalize_book_name("2 Петра") == "2 Peter"

    def test_russian_john_epistle_genitive_aliases(self):
        """Russian genitive John epistle aliases."""
        assert normalize_book_name("1 Иоанна") == "1 John"
        assert normalize_book_name("2 Иоанна") == "2 John"
        assert normalize_book_name("3 Иоанна") == "3 John"

    def test_russian_jude_nominative_alias(self):
        """Russian nominative 'Иуда' → Jude (canonical is 'Иуде')."""
        assert normalize_book_name("Иуда") == "Jude"

    def test_russian_james_nominative_alias(self):
        """Russian nominative 'Иаков' → James (canonical is 'Иакову')."""
        assert normalize_book_name("Иаков") == "James"
