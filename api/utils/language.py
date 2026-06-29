"""
Language detection and translation mapping utilities.

This module provides a pluggable language detection system that supports
multiple backends (lingua-py, langdetect, etc.) through a common interface.
"""

from abc import ABC, abstractmethod
from typing import Literal

# Supported languages for this application
SUPPORTED_LANGUAGES = ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"]
DEFAULT_LANGUAGE = "en"

# Map ISO 639-1 language codes to default translation codes
# First translation in each list is the default
LANGUAGE_TRANSLATIONS = {
    "en": ["web", "kjv"],  # English: WEB (default), KJV
    "it": ["ita1927"],  # Italian: Riveduta 1927
    "de": ["schlachter"],  # German: Schlachter 1951
    "es": ["valera"],  # Spanish: Reina Valera 1909
    "fr": ["ls1910"],  # French: Louis Segond 1910
    "pt": ["almeida"],  # Portuguese: Almeida Atualizada
    "ar": ["arabicsv"],  # Arabic: Smith & Van Dyke
    "ru": ["synodal"],  # Russian: Synodal (1876)
    "zh": ["cuv"],  # Chinese: Chinese Union Version
    "hi": ["hindi"],  # Hindi: IRV Hindi Bible
    "ko": ["krv"],  # Korean: Korean Revised Version
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
    "valera": {
        "code": "valera",
        "name": "Reina Valera 1909",
        "short_name": "Valera",
        "language": "Spanish",
        "language_code": "es",
    },
    "ls1910": {
        "code": "ls1910",
        "name": "Louis Segond 1910",
        "short_name": "Segond",
        "language": "French",
        "language_code": "fr",
    },
    "almeida": {
        "code": "almeida",
        "name": "Almeida Atualizada",
        "short_name": "Almeida",
        "language": "Portuguese",
        "language_code": "pt",
    },
    "arabicsv": {
        "code": "arabicsv",
        "name": "Smith & Van Dyke",
        "short_name": "SVD",
        "language": "Arabic",
        "language_code": "ar",
    },
    "synodal": {
        "code": "synodal",
        "name": "Синодальный перевод",
        "short_name": "Synodal",
        "language": "Russian",
        "language_code": "ru",
    },
    "cuv": {
        "code": "cuv",
        "name": "中文和合本",
        "short_name": "CUV",
        "language": "Chinese",
        "language_code": "zh",
    },
    "hindi": {
        "code": "hindi",
        "name": "Hindi IRV Bible",
        "short_name": "IRV",
        "language": "Hindi",
        "language_code": "hi",
    },
    "krv": {
        "code": "krv",
        "name": "개역개정",
        "short_name": "KRV",
        "language": "Korean",
        "language_code": "ko",
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

    def detect_confident(self, text: str) -> str | None:
        """
        Detect language only when confident; otherwise return None.

        Default implementation always returns None (conservative — no suggestion).
        Override in concrete classes that support confidence scoring.

        Returns:
            ISO 639-1 code when text is long enough AND confidence is high,
            else None.
        """
        return None

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
            "es": Language.SPANISH,
            "fr": Language.FRENCH,
            "pt": Language.PORTUGUESE,
            "ar": Language.ARABIC,
            "ru": Language.RUSSIAN,
            "zh": Language.CHINESE,
            "hi": Language.HINDI,
            "ko": Language.KOREAN,
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
                return str(top_lang)
            else:
                return DEFAULT_LANGUAGE
        except Exception:
            return DEFAULT_LANGUAGE

    def detect_confident(self, text: str) -> str | None:
        """Detect language only when text is long enough and confidence is high."""
        if not text or len(text.strip()) < self._min_text_length:
            return None
        try:
            confidence_values = self._detector.compute_language_confidence_values(text)
            if not confidence_values:
                return None
            top = confidence_values[0]
            top_lang = top.language.iso_code_639_1.name.lower()
            top_conf = top.value
            if top_conf >= self._confidence_threshold:
                return str(top_lang)
            return None
        except Exception:
            return None


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


def detect_language_confident(text: str) -> str | None:
    """
    Detect the language only when confident enough to suggest a UI switch.

    Unlike detect_language(), returns None when text is too short or detection
    confidence is below threshold, so callers can distinguish "probably X" from
    "confidently X". Use this to gate language-switch suggestions.

    Args:
        text: Text to analyze

    Returns:
        ISO 639-1 code when confident, or None when uncertain / text too short
    """
    return get_detector().detect_confident(text)


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


def get_model_override_for_language(language_code: str) -> str | None:
    """Return model override for a language, or None to use the default model.

    Reads from settings.language_model_overrides (e.g. "ar=qwen/qwen-2.5-72b-instruct").
    """
    from config import get_settings

    raw = get_settings().language_model_overrides
    if not raw or not raw.strip():
        return None
    for pair in raw.split(","):
        pair = pair.strip()
        if "=" in pair:
            lang, model = pair.split("=", 1)
            if lang.strip() == language_code:
                return model.strip()
    return None


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

ENGLISH_TO_SPANISH_BOOKS = {
    # Old Testament
    "Genesis": "Génesis",
    "Exodus": "Éxodo",
    "Leviticus": "Levítico",
    "Numbers": "Números",
    "Deuteronomy": "Deuteronomio",
    "Joshua": "Josué",
    "Judges": "Jueces",
    "Ruth": "Rut",
    "1 Samuel": "1 Samuel",
    "2 Samuel": "2 Samuel",
    "1 Kings": "1 Reyes",
    "2 Kings": "2 Reyes",
    "1 Chronicles": "1 Crónicas",
    "2 Chronicles": "2 Crónicas",
    "Ezra": "Esdras",
    "Nehemiah": "Nehemías",
    "Esther": "Ester",
    "Job": "Job",
    "Psalms": "Salmos",
    "Proverbs": "Proverbios",
    "Ecclesiastes": "Eclesiastés",
    "Song of Solomon": "Cantares",
    "Isaiah": "Isaías",
    "Jeremiah": "Jeremías",
    "Lamentations": "Lamentaciones",
    "Ezekiel": "Ezequiel",
    "Daniel": "Daniel",
    "Hosea": "Oseas",
    "Joel": "Joel",
    "Amos": "Amós",
    "Obadiah": "Abdías",
    "Jonah": "Jonás",
    "Micah": "Miqueas",
    "Nahum": "Nahúm",
    "Habakkuk": "Habacuc",
    "Zephaniah": "Sofonías",
    "Haggai": "Hageo",
    "Zechariah": "Zacarías",
    "Malachi": "Malaquías",
    # New Testament
    "Matthew": "Mateo",
    "Mark": "Marcos",
    "Luke": "Lucas",
    "John": "Juan",
    "Acts": "Hechos",
    "Romans": "Romanos",
    "1 Corinthians": "1 Corintios",
    "2 Corinthians": "2 Corintios",
    "Galatians": "Gálatas",
    "Ephesians": "Efesios",
    "Philippians": "Filipenses",
    "Colossians": "Colosenses",
    "1 Thessalonians": "1 Tesalonicenses",
    "2 Thessalonians": "2 Tesalonicenses",
    "1 Timothy": "1 Timoteo",
    "2 Timothy": "2 Timoteo",
    "Titus": "Tito",
    "Philemon": "Filemón",
    "Hebrews": "Hebreos",
    "James": "Santiago",
    "1 Peter": "1 Pedro",
    "2 Peter": "2 Pedro",
    "1 John": "1 Juan",
    "2 John": "2 Juan",
    "3 John": "3 Juan",
    "Jude": "Judas",
    "Revelation": "Apocalipsis",
}

ENGLISH_TO_FRENCH_BOOKS = {
    # Old Testament
    "Genesis": "Genèse",
    "Exodus": "Exode",
    "Leviticus": "Lévitique",
    "Numbers": "Nombres",
    "Deuteronomy": "Deutéronome",
    "Joshua": "Josué",
    "Judges": "Juges",
    "Ruth": "Ruth",
    "1 Samuel": "1 Samuel",
    "2 Samuel": "2 Samuel",
    "1 Kings": "1 Rois",
    "2 Kings": "2 Rois",
    "1 Chronicles": "1 Chroniques",
    "2 Chronicles": "2 Chroniques",
    "Ezra": "Esdras",
    "Nehemiah": "Néhémie",
    "Esther": "Esther",
    "Job": "Job",
    "Psalms": "Psaumes",
    "Proverbs": "Proverbes",
    "Ecclesiastes": "Ecclésiaste",
    "Song of Solomon": "Cantique des Cantiques",
    "Isaiah": "Ésaïe",
    "Jeremiah": "Jérémie",
    "Lamentations": "Lamentations",
    "Ezekiel": "Ézéchiel",
    "Daniel": "Daniel",
    "Hosea": "Osée",
    "Joel": "Joël",
    "Amos": "Amos",
    "Obadiah": "Abdias",
    "Jonah": "Jonas",
    "Micah": "Michée",
    "Nahum": "Nahum",
    "Habakkuk": "Habacuc",
    "Zephaniah": "Sophonie",
    "Haggai": "Aggée",
    "Zechariah": "Zacharie",
    "Malachi": "Malachie",
    # New Testament
    "Matthew": "Matthieu",
    "Mark": "Marc",
    "Luke": "Luc",
    "John": "Jean",
    "Acts": "Actes des Apôtres",
    "Romans": "Romains",
    "1 Corinthians": "1 Corinthiens",
    "2 Corinthians": "2 Corinthiens",
    "Galatians": "Galates",
    "Ephesians": "Éphésiens",
    "Philippians": "Philippiens",
    "Colossians": "Colossiens",
    "1 Thessalonians": "1 Thessaloniciens",
    "2 Thessalonians": "2 Thessaloniciens",
    "1 Timothy": "1 Timothée",
    "2 Timothy": "2 Timothée",
    "Titus": "Tite",
    "Philemon": "Philémon",
    "Hebrews": "Hébreux",
    "James": "Jacques",
    "1 Peter": "1 Pierre",
    "2 Peter": "2 Pierre",
    "1 John": "1 Jean",
    "2 John": "2 Jean",
    "3 John": "3 Jean",
    "Jude": "Jude",
    "Revelation": "Apocalypse",
}

ENGLISH_TO_PORTUGUESE_BOOKS = {
    # Old Testament
    "Genesis": "Gênesis",
    "Exodus": "Êxodo",
    "Leviticus": "Levítico",
    "Numbers": "Números",
    "Deuteronomy": "Deuteronômio",
    "Joshua": "Josué",
    "Judges": "Juízes",
    "Ruth": "Rute",
    "1 Samuel": "1 Samuel",
    "2 Samuel": "2 Samuel",
    "1 Kings": "1 Reis",
    "2 Kings": "2 Reis",
    "1 Chronicles": "1 Crônicas",
    "2 Chronicles": "2 Crônicas",
    "Ezra": "Esdras",
    "Nehemiah": "Neemias",
    "Esther": "Ester",
    "Job": "Jó",
    "Psalms": "Salmos",
    "Proverbs": "Provérbios",
    "Ecclesiastes": "Eclesiastes",
    "Song of Solomon": "Cântico dos Cânticos",
    "Isaiah": "Isaías",
    "Jeremiah": "Jeremias",
    "Lamentations": "Lamentações",
    "Ezekiel": "Ezequiel",
    "Daniel": "Daniel",
    "Hosea": "Oseias",
    "Joel": "Joel",
    "Amos": "Amós",
    "Obadiah": "Obadias",
    "Jonah": "Jonas",
    "Micah": "Miquéias",
    "Nahum": "Naum",
    "Habakkuk": "Habacuque",
    "Zephaniah": "Sofonias",
    "Haggai": "Ageu",
    "Zechariah": "Zacarias",
    "Malachi": "Malaquias",
    # New Testament
    "Matthew": "Mateus",
    "Mark": "Marcos",
    "Luke": "Lucas",
    "John": "João",
    "Acts": "Atos",
    "Romans": "Romanos",
    "1 Corinthians": "1 Coríntios",
    "2 Corinthians": "2 Coríntios",
    "Galatians": "Gálatas",
    "Ephesians": "Efésios",
    "Philippians": "Filipenses",
    "Colossians": "Colossenses",
    "1 Thessalonians": "1 Tessalonicenses",
    "2 Thessalonians": "2 Tessalonicenses",
    "1 Timothy": "1 Timóteo",
    "2 Timothy": "2 Timóteo",
    "Titus": "Tito",
    "Philemon": "Filemom",
    "Hebrews": "Hebreus",
    "James": "Tiago",
    "1 Peter": "1 Pedro",
    "2 Peter": "2 Pedro",
    "1 John": "1 João",
    "2 John": "2 João",
    "3 John": "3 João",
    "Jude": "Judas",
    "Revelation": "Apocalipse",
}

ENGLISH_TO_ARABIC_BOOKS = {
    # Old Testament
    "Genesis": "تكوين",
    "Exodus": "خروج",
    "Leviticus": "لاويين",
    "Numbers": "عدد",
    "Deuteronomy": "تثنية",
    "Joshua": "يشوع",
    "Judges": "القضاة",
    "Ruth": "راعوث",
    "1 Samuel": "1 صموئيل",
    "2 Samuel": "2 صموئيل",
    "1 Kings": "1 الملوك",
    "2 Kings": "2 الملوك",
    "1 Chronicles": "1 أخبار الأيام",
    "2 Chronicles": "2 أخبار الأيام",
    "Ezra": "عزرا",
    "Nehemiah": "نحميا",
    "Esther": "أستير",
    "Job": "أيوب",
    "Psalms": "المزامير",
    "Proverbs": "الأمثال",
    "Ecclesiastes": "الجامعة",
    "Song of Solomon": "نشيد الأنشاد",
    "Isaiah": "إشعياء",
    "Jeremiah": "إرميا",
    "Lamentations": "مراثي إرميا",
    "Ezekiel": "حزقيال",
    "Daniel": "دانيال",
    "Hosea": "هوشع",
    "Joel": "يوئيل",
    "Amos": "عاموس",
    "Obadiah": "عوبديا",
    "Jonah": "يونان",
    "Micah": "ميخا",
    "Nahum": "ناحوم",
    "Habakkuk": "حبقوق",
    "Zephaniah": "صفنيا",
    "Haggai": "حجي",
    "Zechariah": "زكريا",
    "Malachi": "ملاخي",
    # New Testament
    "Matthew": "متى",
    "Mark": "مرقس",
    "Luke": "لوقا",
    "John": "يوحنا",
    "Acts": "أعمال الرسل",
    "Romans": "رومية",
    "1 Corinthians": "1 كورنثوس",
    "2 Corinthians": "2 كورنثوس",
    "Galatians": "غلاطية",
    "Ephesians": "أفسس",
    "Philippians": "فيليبي",
    "Colossians": "كولوسي",
    "1 Thessalonians": "1 تسالونيكي",
    "2 Thessalonians": "2 تسالونيكي",
    "1 Timothy": "1 تيموثاوس",
    "2 Timothy": "2 تيموثاوس",
    "Titus": "تيطس",
    "Philemon": "فليمون",
    "Hebrews": "عبرانيين",
    "James": "يعقوب",
    "1 Peter": "1 بطرس",
    "2 Peter": "2 بطرس",
    "1 John": "1 يوحنا",
    "2 John": "2 يوحنا",
    "3 John": "3 يوحنا",
    "Jude": "يهوذا",
    "Revelation": "الرؤيا",
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

ENGLISH_TO_RUSSIAN_BOOKS = {
    # Old Testament
    "Genesis": "Бытие",
    "Exodus": "Исход",
    "Leviticus": "Левит",
    "Numbers": "Числа",
    "Deuteronomy": "Второзаконие",
    "Joshua": "Иисус Навин",
    "Judges": "Судьи",
    "Ruth": "Руфь",
    "1 Samuel": "1 Царств",
    "2 Samuel": "2 Царств",
    "1 Kings": "3 Царств",
    "2 Kings": "4 Царств",
    "1 Chronicles": "1 Паралипоменон",
    "2 Chronicles": "2 Паралипоменон",
    "Ezra": "Ездра",
    "Nehemiah": "Неемия",
    "Esther": "Есфирь",
    "Job": "Иов",
    "Psalms": "Псалтирь",
    "Proverbs": "Притчи",
    "Ecclesiastes": "Екклесиаст",
    "Song of Solomon": "Песня Песней",
    "Isaiah": "Исаия",
    "Jeremiah": "Иеремия",
    "Lamentations": "Плач Иеремии",
    "Ezekiel": "Иезекиль",
    "Daniel": "Даниил",
    "Hosea": "Осия",
    "Joel": "Иоиль",
    "Amos": "Амос",
    "Obadiah": "Авдий",
    "Jonah": "Иона",
    "Micah": "Михей",
    "Nahum": "Наум",
    "Habakkuk": "Аввакум",
    "Zephaniah": "Софония",
    "Haggai": "Аггей",
    "Zechariah": "Захария",
    "Malachi": "Малахия",
    # New Testament
    "Matthew": "Матфей",
    "Mark": "Марк",
    "Luke": "Лука",
    "John": "Иоанн",
    "Acts": "Деяния апостолов",
    "Romans": "Римлянам",
    "1 Corinthians": "1 Коринфянам",
    "2 Corinthians": "2 Коринфянам",
    "Galatians": "Галатам",
    "Ephesians": "Ефесянам",
    "Philippians": "Филиппийцам",
    "Colossians": "Колоссянам",
    "1 Thessalonians": "1 Фессалоникийцам",
    "2 Thessalonians": "2 Фессалоникийцам",
    "1 Timothy": "1 Тимофею",
    "2 Timothy": "2 Тимофею",
    "Titus": "Титу",
    "Philemon": "Филимону",
    "Hebrews": "Евреям",
    "James": "Иаков",
    "1 Peter": "1 Петра",
    "2 Peter": "2 Петра",
    "1 John": "1 Иоанна",
    "2 John": "2 Иоанна",
    "3 John": "3 Иоанна",
    "Jude": "Иуда",
    "Revelation": "Откровение",
}

ENGLISH_TO_CHINESE_BOOKS = {
    "Genesis": "创世记",
    "Exodus": "出埃及记",
    "Leviticus": "利未记",
    "Numbers": "民数记",
    "Deuteronomy": "申命记",
    "Joshua": "约书亚记",
    "Judges": "士师记",
    "Ruth": "路得记",
    "1 Samuel": "撒母耳记上",
    "2 Samuel": "撒母耳记下",
    "1 Kings": "列王纪上",
    "2 Kings": "列王纪下",
    "1 Chronicles": "历代志上",
    "2 Chronicles": "历代志下",
    "Ezra": "以斯拉记",
    "Nehemiah": "尼希米记",
    "Esther": "以斯帖记",
    "Job": "约伯记",
    "Psalms": "诗篇",
    "Proverbs": "箴言",
    "Ecclesiastes": "传道书",
    "Song of Solomon": "雅歌",
    "Isaiah": "以赛亚书",
    "Jeremiah": "耶利米书",
    "Lamentations": "耶利米哀歌",
    "Ezekiel": "以西结书",
    "Daniel": "但以理书",
    "Hosea": "何西阿书",
    "Joel": "约珥书",
    "Amos": "阿摩司书",
    "Obadiah": "俄巴底亚书",
    "Jonah": "约拿书",
    "Micah": "弥迦书",
    "Nahum": "那鸿书",
    "Habakkuk": "哈巴谷书",
    "Zephaniah": "西番雅书",
    "Haggai": "哈该书",
    "Zechariah": "撒迦利亚书",
    "Malachi": "玛拉基书",
    "Matthew": "马太福音",
    "Mark": "马可福音",
    "Luke": "路加福音",
    "John": "约翰福音",
    "Acts": "使徒行传",
    "Romans": "罗马书",
    "1 Corinthians": "哥林多前书",
    "2 Corinthians": "哥林多后书",
    "Galatians": "加拉太书",
    "Ephesians": "以弗所书",
    "Philippians": "腓立比书",
    "Colossians": "歌罗西书",
    "1 Thessalonians": "帖撒罗尼迦前书",
    "2 Thessalonians": "帖撒罗尼迦后书",
    "1 Timothy": "提摩太前书",
    "2 Timothy": "提摩太后书",
    "Titus": "提多书",
    "Philemon": "腓利门书",
    "Hebrews": "希伯来书",
    "James": "雅各书",
    "1 Peter": "彼得前书",
    "2 Peter": "彼得后书",
    "1 John": "约翰一书",
    "2 John": "约翰二书",
    "3 John": "约翰三书",
    "Jude": "犹大书",
    "Revelation": "启示录",
}

ENGLISH_TO_HINDI_BOOKS = {
    "Genesis": "उत्पत्ति",
    "Exodus": "निर्गमन",
    "Leviticus": "लैव्यव्यवस्था",
    "Numbers": "गिनती",
    "Deuteronomy": "व्यवस्थाविवरण",
    "Joshua": "यहोशू",
    "Judges": "न्यायियों",
    "Ruth": "रूत",
    "1 Samuel": "1 शमूएल",
    "2 Samuel": "2 शमूएल",
    "1 Kings": "1 राजाओं",
    "2 Kings": "2 राजाओं",
    "1 Chronicles": "1 इतिहास",
    "2 Chronicles": "2 इतिहास",
    "Ezra": "एज्रा",
    "Nehemiah": "नहेम्याह",
    "Esther": "एस्तेर",
    "Job": "अय्यूब",
    "Psalms": "भजन संहिता",
    "Proverbs": "नीतिवचन",
    "Ecclesiastes": "सभोपदेशक",
    "Song of Solomon": "श्रेष्ठगीत",
    "Isaiah": "यशायाह",
    "Jeremiah": "यिर्मयाह",
    "Lamentations": "विलापगीत",
    "Ezekiel": "यहेजकेल",
    "Daniel": "दानिय्येल",
    "Hosea": "होशे",
    "Joel": "योएल",
    "Amos": "आमोस",
    "Obadiah": "ओबद्याह",
    "Jonah": "योना",
    "Micah": "मीका",
    "Nahum": "नहूम",
    "Habakkuk": "हबक्कूक",
    "Zephaniah": "सपन्याह",
    "Haggai": "हाग्गै",
    "Zechariah": "जकर्याह",
    "Malachi": "मलाकी",
    "Matthew": "मत्ती",
    "Mark": "मरकुस",
    "Luke": "लूका",
    "John": "यूहन्ना",
    "Acts": "प्रेरितों के काम",
    "Romans": "रोमियों",
    "1 Corinthians": "1 कुरिन्थियों",
    "2 Corinthians": "2 कुरिन्थियों",
    "Galatians": "गलातियों",
    "Ephesians": "इफिसियों",
    "Philippians": "फिलिप्पियों",
    "Colossians": "कुलुस्सियों",
    "1 Thessalonians": "1 थिस्सलुनीकियों",
    "2 Thessalonians": "2 थिस्सलुनीकियों",
    "1 Timothy": "1 तीमुथियुस",
    "2 Timothy": "2 तीमुथियुस",
    "Titus": "तीतुस",
    "Philemon": "फिलेमोन",
    "Hebrews": "इब्रानियों",
    "James": "याकूब",
    "1 Peter": "1 पतरस",
    "2 Peter": "2 पतरस",
    "1 John": "1 यूहन्ना",
    "2 John": "2 यूहन्ना",
    "3 John": "3 यूहन्ना",
    "Jude": "यहूदा",
    "Revelation": "प्रकाशितवाक्य",
}

ENGLISH_TO_KOREAN_BOOKS = {
    "Genesis": "창세기",
    "Exodus": "출애굽기",
    "Leviticus": "레위기",
    "Numbers": "민수기",
    "Deuteronomy": "신명기",
    "Joshua": "여호수아",
    "Judges": "사사기",
    "Ruth": "룻기",
    "1 Samuel": "사무엘상",
    "2 Samuel": "사무엘하",
    "1 Kings": "열왕기상",
    "2 Kings": "열왕기하",
    "1 Chronicles": "역대상",
    "2 Chronicles": "역대하",
    "Ezra": "에스라",
    "Nehemiah": "느헤미야",
    "Esther": "에스더",
    "Job": "욥기",
    "Psalms": "시편",
    "Proverbs": "잠언",
    "Ecclesiastes": "전도서",
    "Song of Solomon": "아가",
    "Isaiah": "이사야",
    "Jeremiah": "예레미야",
    "Lamentations": "예레미야애가",
    "Ezekiel": "에스겔",
    "Daniel": "다니엘",
    "Hosea": "호세아",
    "Joel": "요엘",
    "Amos": "아모스",
    "Obadiah": "오바댜",
    "Jonah": "요나",
    "Micah": "미가",
    "Nahum": "나훔",
    "Habakkuk": "하박국",
    "Zephaniah": "스바냐",
    "Haggai": "학개",
    "Zechariah": "스가랴",
    "Malachi": "말라기",
    "Matthew": "마태복음",
    "Mark": "마가복음",
    "Luke": "누가복음",
    "John": "요한복음",
    "Acts": "사도행전",
    "Romans": "로마서",
    "1 Corinthians": "고린도전서",
    "2 Corinthians": "고린도후서",
    "Galatians": "갈라디아서",
    "Ephesians": "에베소서",
    "Philippians": "빌립보서",
    "Colossians": "골로새서",
    "1 Thessalonians": "데살로니가전서",
    "2 Thessalonians": "데살로니가후서",
    "1 Timothy": "디모데전서",
    "2 Timothy": "디모데후서",
    "Titus": "디도서",
    "Philemon": "빌레몬서",
    "Hebrews": "히브리서",
    "James": "야고보서",
    "1 Peter": "베드로전서",
    "2 Peter": "베드로후서",
    "1 John": "요한일서",
    "2 John": "요한이서",
    "3 John": "요한삼서",
    "Jude": "유다서",
    "Revelation": "요한계시록",
}


VERSE_UNAVAILABLE_NOTE: dict[str, str] = {
    "en": "[This verse isn't available in your translation yet]",
    "it": "[Questo versetto non è ancora disponibile nella tua traduzione]",
    "de": "[Dieser Vers ist in deiner Übersetzung noch nicht verfügbar]",
    "es": "[Este versículo no está disponible aún en tu traducción]",
    "fr": "[Ce verset n'est pas encore disponible dans votre traduction]",
    "pt": "[Este versículo ainda não está disponível na sua tradução]",
    "ar": "[هذه الآية غير متوفرة بعد في ترجمتك]",
    "ru": "[Этот стих ещё недоступен в вашем переводе]",
    "zh": "[此节经文暂未在您的译本中提供]",
    "hi": "[यह पद अभी तक आपके अनुवाद में उपलब्ध नहीं है]",
    "ko": "[이 구절은 아직 당신의 번역본에서 제공되지 않습니다]",
}


def get_verse_unavailable_note(language_code: str) -> str:
    """Return a localized note for an unresolvable verse citation."""
    return VERSE_UNAVAILABLE_NOTE.get(language_code, VERSE_UNAVAILABLE_NOTE["en"])


def get_localized_book_name(english_name: str, translation_code: str) -> str:
    """
    Get the localized book name for a given translation.

    Args:
        english_name: Book name in English (e.g., "Genesis", "Matthew")
        translation_code: Translation code (e.g., "kjv", "ita1927")

    Returns:
        Localized book name, or original if no mapping exists
    """
    book_map = {
        "ita1927": ENGLISH_TO_ITALIAN_BOOKS,
        "schlachter": ENGLISH_TO_GERMAN_BOOKS,
        "valera": ENGLISH_TO_SPANISH_BOOKS,
        "ls1910": ENGLISH_TO_FRENCH_BOOKS,
        "almeida": ENGLISH_TO_PORTUGUESE_BOOKS,
        "arabicsv": ENGLISH_TO_ARABIC_BOOKS,
        "synodal": ENGLISH_TO_RUSSIAN_BOOKS,
        "cuv": ENGLISH_TO_CHINESE_BOOKS,
        "hindi": ENGLISH_TO_HINDI_BOOKS,
        "krv": ENGLISH_TO_KOREAN_BOOKS,
    }
    mapping = book_map.get(translation_code)
    if mapping is None:
        return english_name
    return mapping.get(english_name, english_name)
