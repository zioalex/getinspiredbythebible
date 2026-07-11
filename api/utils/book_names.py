"""
Book name localization utilities.

All book name data lives in ``utils/translation_registry.py`` — the single
source of truth.  This module re-exports the forward dicts for backward
compatibility and derives all reverse dicts dynamically, so adding a new
translation to ``translation_registry.py`` automatically updates everything
here without any manual edits.

Supported translations: ita1927, schlachter, valera, ls1910, almeida,
                        arabicsv, synodal, cuv, krv, kjv, web.
"""

import unicodedata

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
    TRANSLATION_REGISTRY,
)

# ---------------------------------------------------------------------------
# Re-export the registry under the legacy name used across the codebase
# ---------------------------------------------------------------------------
TRANSLATION_BOOK_NAMES = TRANSLATION_REGISTRY

# ---------------------------------------------------------------------------
# Reverse mappings  (localized → English)
# Built automatically from the forward dicts — no manual maintenance needed.
# ---------------------------------------------------------------------------

ITALIAN_TO_ENGLISH: dict[str, str] = {v: k for k, v in ENGLISH_TO_ITALIAN.items()}
GERMAN_TO_ENGLISH: dict[str, str] = {v: k for k, v in ENGLISH_TO_GERMAN.items()}
SPANISH_TO_ENGLISH: dict[str, str] = {v: k for k, v in ENGLISH_TO_SPANISH.items()}
FRENCH_TO_ENGLISH: dict[str, str] = {v: k for k, v in ENGLISH_TO_FRENCH.items()}
PORTUGUESE_TO_ENGLISH: dict[str, str] = {v: k for k, v in ENGLISH_TO_PORTUGUESE.items()}
ARABIC_TO_ENGLISH: dict[str, str] = {v: k for k, v in ENGLISH_TO_ARABIC.items()}
ARABIC_TO_ENGLISH.update(
    {
        alias: eng
        for alias, eng in EXTRA_REVERSE_MAPPINGS.items()
        if any(0x0600 <= ord(c) <= 0x06FF for c in alias)  # Arabic Unicode block
    }
)
RUSSIAN_TO_ENGLISH: dict[str, str] = {v: k for k, v in ENGLISH_TO_RUSSIAN.items()}
RUSSIAN_TO_ENGLISH.update(
    {
        alias: eng
        for alias, eng in EXTRA_REVERSE_MAPPINGS.items()
        if any(0x0400 <= ord(c) <= 0x04FF for c in alias)  # Cyrillic Unicode block
    }
)

CHINESE_TO_ENGLISH: dict[str, str] = {v: k for k, v in ENGLISH_TO_CHINESE.items()}
CHINESE_TO_ENGLISH.update(
    {
        alias: eng
        for alias, eng in EXTRA_REVERSE_MAPPINGS.items()
        if any(
            (0x4E00 <= ord(c) <= 0x9FFF)
            or (0x3400 <= ord(c) <= 0x4DBF)
            or (0xF900 <= ord(c) <= 0xFAFF)
            or c == "\ufeff"
            for c in alias
        )
    }
)

HINDI_TO_ENGLISH: dict[str, str] = {v: k for k, v in ENGLISH_TO_HINDI.items()}

KOREAN_TO_ENGLISH: dict[str, str] = {v: k for k, v in ENGLISH_TO_KOREAN.items()}
KOREAN_TO_ENGLISH.update(
    {
        alias: eng
        for alias, eng in EXTRA_REVERSE_MAPPINGS.items()
        if any(0xAC00 <= ord(c) <= 0xD7A3 for c in alias)
    }
)

# Combined reverse mapping for all languages (canonical forms + all aliases)
LOCALIZED_TO_ENGLISH: dict[str, str] = {}
for _forward_dict in TRANSLATION_REGISTRY.values():
    if _forward_dict is not None:
        LOCALIZED_TO_ENGLISH.update({v: k for k, v in _forward_dict.items()})
# Add alias / variant forms that don't appear as canonical values
LOCALIZED_TO_ENGLISH.update(EXTRA_REVERSE_MAPPINGS)


def get_localized_book_name(english_name: str, translation_code: str | None) -> str:
    """
    Get the localized book name for a given English book name.

    Args:
        english_name: Standard English book name (e.g., "Genesis", "Psalms")
        translation_code: Translation code (e.g., "ita1927", "schlachter")

    Returns:
        Localized book name (e.g., "Genesi", "Psalmen") or English name if no mapping
    """
    if translation_code is None:
        return english_name

    book_names = TRANSLATION_BOOK_NAMES.get(translation_code)

    if book_names is None:
        # English translations use standard names
        return english_name

    return book_names.get(english_name, english_name)


def _fold(text: str) -> str:
    """Case- and diacritic-insensitive fold.

    NFKD-decomposes and drops combining marks before lower-casing, so
    "Ésaïe" and "Esaie" both fold to "esaie". Uses ``.lower()`` (not
    ``.casefold()``) to keep this a strict widening of the pre-existing
    case-insensitive fallback — no book name in any supported language
    contains a character where the two diverge.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.lower()


# Case- and diacritic-insensitive fallback map built once at import time.
# Seeded first with all 66 canonical English names so that "genesis" → "Genesis"
# even though English translations have no forward dict in TRANSLATION_REGISTRY.
# Localized forms and aliases are then layered in; first writer wins to avoid
# one language's abbreviation colliding with another's canonical form.
# Verified against all 814 source keys: 0 cross-book collisions from folding
# (guarded by test_diacritic_fold_has_no_cross_book_collisions).
_LOCALIZED_TO_ENGLISH_FOLDED: dict[str, str] = {_fold(k): k for k in ENGLISH_TO_ITALIAN}
for _key, _val in LOCALIZED_TO_ENGLISH.items():
    _folded = _fold(_key)
    if _folded not in _LOCALIZED_TO_ENGLISH_FOLDED:
        _LOCALIZED_TO_ENGLISH_FOLDED[_folded] = _val


def normalize_book_name(book_name: str) -> str:
    """
    Convert a localized book name to standard English.

    Handles book names in any supported language (Italian, German, Spanish,
    French, Portuguese, Arabic, Russian, Chinese, Korean, English).

    Args:
        book_name: Book name in any language (e.g., "Giovanni", "Jean", "Juan",
                   "Иоанна", "John")

    Returns:
        Standard English book name (e.g., "John")
    """
    # First check if it's already English (exists as a key in any mapping)
    if book_name in ENGLISH_TO_ITALIAN:
        return book_name

    # Exact-case lookup (preferred — avoids false collisions across languages)
    exact = LOCALIZED_TO_ENGLISH.get(book_name)
    if exact is not None:
        return exact

    # Case- and diacritic-insensitive fallback (handles "salmi", "GENESIS",
    # "psalm", and accent-dropped forms like "Esaie" for "Ésaïe", etc.)
    return _LOCALIZED_TO_ENGLISH_FOLDED.get(_fold(book_name), book_name)
