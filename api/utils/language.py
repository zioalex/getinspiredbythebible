"""
Language detection and translation mapping utilities.

This module provides a pluggable language detection system that supports
multiple backends (lingua-py, langdetect, etc.) through a common interface.
"""

from abc import ABC, abstractmethod
from typing import Literal

# Supported languages for this application
SUPPORTED_LANGUAGES = ["en", "it", "de"]
DEFAULT_LANGUAGE = "en"

# Map ISO 639-1 language codes to default translation codes
# First translation in each list is the default
LANGUAGE_TRANSLATIONS = {
    "en": ["web", "kjv"],  # English: WEB (default), KJV
    "it": ["ita1927"],  # Italian: Riveduta 1927
    "de": ["schlachter"],  # German: Schlachter 1951
}

# Legacy mapping for backwards compatibility (uses first/default translation)
LANGUAGE_TO_TRANSLATION = {
    lang: translations[0] for lang, translations in LANGUAGE_TRANSLATIONS.items()
}

# Translation metadata for display
TRANSLATION_INFO = {
    "kjv": {
        "code": "kjv",
        "name": "King James Version",
        "short_name": "KJV",
        "language": "English",
        "language_code": "en",
    },
    "web": {
        "code": "web",
        "name": "World English Bible",
        "short_name": "WEB",
        "language": "English",
        "language_code": "en",
    },
    "ita1927": {
        "code": "ita1927",
        "name": "Riveduta 1927",
        "short_name": "Riveduta",
        "language": "Italian",
        "language_code": "it",
    },
    "schlachter": {
        "code": "schlachter",
        "name": "Schlachter 1951",
        "short_name": "Schlachter",
        "language": "German",
        "language_code": "de",
    },
}

# Default translation when language detection fails (WEB is more modern/readable)
DEFAULT_TRANSLATION = "web"


# =============================================================================
# Language Detector Interface and Implementations
# =============================================================================


class LanguageDetector(ABC):
    """
    Abstract base class for language detection.

    Implementations should detect the language of text and return an ISO 639-1
    language code. If detection fails or confidence is low, return DEFAULT_LANGUAGE.
    """

    @abstractmethod
    def detect(self, text: str) -> str:
        """
        Detect the language of the given text.

        Args:
            text: Text to analyze

        Returns:
            ISO 639-1 language code (e.g., 'en', 'it', 'de')
            Returns DEFAULT_LANGUAGE if detection fails or confidence is low
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this detector implementation."""
        pass


class LinguaLanguageDetector(LanguageDetector):
    """
    Language detector using lingua-py library.

    lingua-py is accurate for short text and uses n-grams of sizes 1-5.
    It's deterministic and doesn't require GPU or external APIs.
    """

    def __init__(
        self,
        supported_languages: list[str] | None = None,
        min_text_length: int = 10,
        confidence_threshold: float = 0.6,
    ):
        """
        Initialize the lingua detector.

        Args:
            supported_languages: List of ISO 639-1 codes to detect (default: SUPPORTED_LANGUAGES)
            min_text_length: Minimum text length for detection (shorter defaults to English)
            confidence_threshold: Minimum confidence for non-English languages (0.0-1.0)
        """
        from lingua import Language, LanguageDetectorBuilder

        self._min_text_length = min_text_length
        self._confidence_threshold = confidence_threshold
        self._supported_languages = supported_languages or SUPPORTED_LANGUAGES

        # Map ISO codes to lingua Language enums
        lang_map = {
            "en": Language.ENGLISH,
            "it": Language.ITALIAN,
            "de": Language.GERMAN,
        }
        languages = [lang_map[code] for code in self._supported_languages if code in lang_map]

        self._detector = (
            LanguageDetectorBuilder.from_languages(*languages)
            .with_preloaded_language_models()
            .build()
        )

    @property
    def name(self) -> str:
        return "lingua"

    def detect(self, text: str) -> str:
        """Detect language using lingua-py with confidence scoring."""
        # Very short text - default to English
        if not text or len(text.strip()) < self._min_text_length:
            return DEFAULT_LANGUAGE

        try:
            confidence_values = self._detector.compute_language_confidence_values(text)
            if not confidence_values:
                return DEFAULT_LANGUAGE

            top = confidence_values[0]
            top_lang = top.language.iso_code_639_1.name.lower()
            top_conf = top.value

            # If English is the top detected language, return it
            if top_lang == "en":
                return "en"

            # For non-English, require reasonable confidence
            if top_conf >= self._confidence_threshold:
                return top_lang
            else:
                return DEFAULT_LANGUAGE
        except Exception:
            return DEFAULT_LANGUAGE


# =============================================================================
# Detector Factory and Global Instance
# =============================================================================

# Type alias for supported detector providers
DetectorProvider = Literal["lingua"]

# Global detector instance (lazy initialization)
_detector: LanguageDetector | None = None
_detector_provider: DetectorProvider = "lingua"


def create_language_detector(
    provider: DetectorProvider = "lingua",
    **kwargs,
) -> LanguageDetector:
    """
    Factory function to create a language detector.

    Args:
        provider: The detection library to use ('lingua')
        **kwargs: Additional arguments passed to the detector constructor

    Returns:
        A LanguageDetector instance

    Raises:
        ValueError: If provider is not supported
    """
    if provider == "lingua":
        return LinguaLanguageDetector(**kwargs)
    else:
        raise ValueError(f"Unsupported language detector provider: {provider}")


def get_detector() -> LanguageDetector:
    """Get the global language detector instance (creates it if needed)."""
    global _detector
    if _detector is None:
        _detector = create_language_detector(_detector_provider)
    return _detector


def set_detector(detector: LanguageDetector) -> None:
    """
    Set the global language detector instance.

    Useful for testing or switching implementations at runtime.
    """
    global _detector
    _detector = detector


def set_detector_provider(provider: DetectorProvider) -> None:
    """
    Set the detector provider and reset the global instance.

    The new detector will be created on the next call to get_detector().
    """
    global _detector, _detector_provider
    _detector_provider = provider
    _detector = None


# =============================================================================
# Public API Functions
# =============================================================================


def detect_language(text: str) -> str:
    """
    Detect the language of the given text.

    This is the main entry point for language detection. It uses the
    configured detector backend (default: lingua-py).

    Args:
        text: Text to analyze

    Returns:
        ISO 639-1 language code (e.g., 'en', 'it', 'de')
        Returns 'en' if detection fails, text is too short, or confidence is low
    """
    return get_detector().detect(text)


def get_translation_for_language(language_code: str) -> str:
    """
    Get the translation code for a given language.

    Args:
        language_code: ISO 639-1 language code

    Returns:
        Translation code (e.g., 'kjv', 'ita1927', 'schlachter')
    """
    return LANGUAGE_TO_TRANSLATION.get(language_code, DEFAULT_TRANSLATION)


def detect_translation(text: str) -> str:
    """
    Detect the language of text and return the appropriate translation code.

    Args:
        text: User's message text

    Returns:
        Translation code for the detected language
    """
    language = detect_language(text)
    return get_translation_for_language(language)


def get_translation_info(translation_code: str) -> dict:
    """
    Get translation metadata for display.

    Args:
        translation_code: Translation code (e.g., 'kjv', 'ita1927')

    Returns:
        Dictionary with translation info (name, short_name, language)
    """
    return TRANSLATION_INFO.get(translation_code, TRANSLATION_INFO[DEFAULT_TRANSLATION])


def get_all_translations() -> list[dict]:
    """
    Get all available translations.

    Returns:
        List of translation info dictionaries
    """
    return list(TRANSLATION_INFO.values())


def get_translations_for_language(language_code: str) -> list[dict]:
    """
    Get available translations for a specific language.

    Args:
        language_code: ISO 639-1 language code (e.g., 'en', 'it', 'de')

    Returns:
        List of translation info dictionaries for that language
    """
    translations = LANGUAGE_TRANSLATIONS.get(language_code, [])
    return [TRANSLATION_INFO[code] for code in translations if code in TRANSLATION_INFO]


def is_valid_translation(translation_code: str) -> bool:
    """
    Check if a translation code is valid.

    Args:
        translation_code: Translation code to validate

    Returns:
        True if valid, False otherwise
    """
    return translation_code in TRANSLATION_INFO


def resolve_translation(
    preferred_translation: str | None, detected_language: str | None = None
) -> str:
    """
    Resolve which translation to use based on preference and language.

    Priority:
    1. User's preferred translation (if valid)
    2. Default translation for detected language
    3. Global default translation

    Args:
        preferred_translation: User's preferred translation code (optional)
        detected_language: Detected language code (optional)

    Returns:
        Translation code to use
    """
    # If user has a valid preference, use it
    if preferred_translation and is_valid_translation(preferred_translation):
        return preferred_translation

    # Otherwise use language-based default
    if detected_language:
        return get_translation_for_language(detected_language)

    return DEFAULT_TRANSLATION


# =============================================================================
# Book Name Localization
# =============================================================================

# Reverse book name mappings (English -> localized)
ENGLISH_TO_ITALIAN_BOOKS = {
    # Old Testament
    "Genesis": "Genesi",
    "Exodus": "Esodo",
    "Leviticus": "Levitico",
    "Numbers": "Numeri",
    "Deuteronomy": "Deuteronomio",
    "Joshua": "Giosuè",
    "Judges": "Giudici",
    "Ruth": "Rut",
    "1 Samuel": "1 Samuele",
    "2 Samuel": "2 Samuele",
    "1 Kings": "1 Re",
    "2 Kings": "2 Re",
    "1 Chronicles": "1 Cronache",
    "2 Chronicles": "2 Cronache",
    "Ezra": "Esdra",
    "Nehemiah": "Neemia",
    "Esther": "Ester",
    "Job": "Giobbe",
    "Psalms": "Salmi",
    "Proverbs": "Proverbi",
    "Ecclesiastes": "Ecclesiaste",
    "Song of Solomon": "Cantico dei Cantici",
    "Isaiah": "Isaia",
    "Jeremiah": "Geremia",
    "Lamentations": "Lamentazioni",
    "Ezekiel": "Ezechiele",
    "Daniel": "Daniele",
    "Hosea": "Osea",
    "Joel": "Gioele",
    "Amos": "Amos",
    "Obadiah": "Abdia",
    "Jonah": "Giona",
    "Micah": "Michea",
    "Nahum": "Naum",
    "Habakkuk": "Abacuc",
    "Zephaniah": "Sofonia",
    "Haggai": "Aggeo",
    "Zechariah": "Zaccaria",
    "Malachi": "Malachia",
    # New Testament
    "Matthew": "Matteo",
    "Mark": "Marco",
    "Luke": "Luca",
    "John": "Giovanni",
    "Acts": "Atti",
    "Romans": "Romani",
    "1 Corinthians": "1 Corinzi",
    "2 Corinthians": "2 Corinzi",
    "Galatians": "Galati",
    "Ephesians": "Efesini",
    "Philippians": "Filippesi",
    "Colossians": "Colossesi",
    "1 Thessalonians": "1 Tessalonicesi",
    "2 Thessalonians": "2 Tessalonicesi",
    "1 Timothy": "1 Timoteo",
    "2 Timothy": "2 Timoteo",
    "Titus": "Tito",
    "Philemon": "Filemone",
    "Hebrews": "Ebrei",
    "James": "Giacomo",
    "1 Peter": "1 Pietro",
    "2 Peter": "2 Pietro",
    "1 John": "1 Giovanni",
    "2 John": "2 Giovanni",
    "3 John": "3 Giovanni",
    "Jude": "Giuda",
    "Revelation": "Apocalisse",
}

ENGLISH_TO_GERMAN_BOOKS = {
    # Old Testament
    "Genesis": "1. Mose",
    "Exodus": "2. Mose",
    "Leviticus": "3. Mose",
    "Numbers": "4. Mose",
    "Deuteronomy": "5. Mose",
    "Joshua": "Josua",
    "Judges": "Richter",
    "Ruth": "Ruth",
    "1 Samuel": "1. Samuel",
    "2 Samuel": "2. Samuel",
    "1 Kings": "1. Könige",
    "2 Kings": "2. Könige",
    "1 Chronicles": "1. Chronik",
    "2 Chronicles": "2. Chronik",
    "Ezra": "Esra",
    "Nehemiah": "Nehemia",
    "Esther": "Esther",
    "Job": "Hiob",
    "Psalms": "Psalmen",
    "Proverbs": "Sprüche",
    "Ecclesiastes": "Prediger",
    "Song of Solomon": "Hohelied",
    "Isaiah": "Jesaja",
    "Jeremiah": "Jeremia",
    "Lamentations": "Klagelieder",
    "Ezekiel": "Hesekiel",
    "Daniel": "Daniel",
    "Hosea": "Hosea",
    "Joel": "Joel",
    "Amos": "Amos",
    "Obadiah": "Obadja",
    "Jonah": "Jona",
    "Micah": "Micha",
    "Nahum": "Nahum",
    "Habakkuk": "Habakuk",
    "Zephaniah": "Zephanja",
    "Haggai": "Haggai",
    "Zechariah": "Sacharja",
    "Malachi": "Maleachi",
    # New Testament
    "Matthew": "Matthäus",
    "Mark": "Markus",
    "Luke": "Lukas",
    "John": "Johannes",
    "Acts": "Apostelgeschichte",
    "Romans": "Römer",
    "1 Corinthians": "1. Korinther",
    "2 Corinthians": "2. Korinther",
    "Galatians": "Galater",
    "Ephesians": "Epheser",
    "Philippians": "Philipper",
    "Colossians": "Kolosser",
    "1 Thessalonians": "1. Thessalonicher",
    "2 Thessalonians": "2. Thessalonicher",
    "1 Timothy": "1. Timotheus",
    "2 Timothy": "2. Timotheus",
    "Titus": "Titus",
    "Philemon": "Philemon",
    "Hebrews": "Hebräer",
    "James": "Jakobus",
    "1 Peter": "1. Petrus",
    "2 Peter": "2. Petrus",
    "1 John": "1. Johannes",
    "2 John": "2. Johannes",
    "3 John": "3. Johannes",
    "Jude": "Judas",
    "Revelation": "Offenbarung",
}


def get_localized_book_name(english_name: str, translation_code: str) -> str:
    """
    Get the localized book name for a given translation.

    Args:
        english_name: Book name in English (e.g., "Genesis", "Matthew")
        translation_code: Translation code (e.g., "kjv", "ita1927")

    Returns:
        Localized book name, or original if no mapping exists
    """
    if translation_code == "ita1927":
        return ENGLISH_TO_ITALIAN_BOOKS.get(english_name, english_name)
    elif translation_code == "schlachter":
        return ENGLISH_TO_GERMAN_BOOKS.get(english_name, english_name)
    else:
        return english_name
