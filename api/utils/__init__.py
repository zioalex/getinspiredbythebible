"""Utility modules."""

from .language import (
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

__all__ = [
    "detect_language",
    "detect_translation",
    "get_all_translations",
    "get_localized_book_name",
    "get_translation_for_language",
    "get_translation_info",
    "get_translations_for_language",
    "is_valid_translation",
    "resolve_translation",
]
