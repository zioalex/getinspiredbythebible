"""Tests for language detection and translation utilities.

These tests verify the behavior of the language detection system,
ensuring it works correctly regardless of the underlying implementation.
"""

import pytest

from utils.language import (
    DEFAULT_LANGUAGE,
    DEFAULT_TRANSLATION,
    SUPPORTED_LANGUAGES,
    LanguageDetector,
    LinguaLanguageDetector,
    create_language_detector,
    detect_language,
    detect_translation,
    get_all_translations,
    get_detector,
    get_localized_book_name,
    get_translation_for_language,
    get_translation_info,
    get_translations_for_language,
    is_valid_translation,
    resolve_translation,
    set_detector,
)

# =============================================================================
# Test Data
# =============================================================================

# English phrases that should be detected as English
ENGLISH_PHRASES = [
    "Help me understand John 3:16",
    "What does the Bible say about love?",
    "Tell me about the Lord's Prayer",
    "I am feeling anxious today",
    "Show me verse about hope",
    "What is the Ave Maria?",
    "Explain Romans 8:28 to me",
    "Can you help me find peace?",
    "What does it mean to have faith?",
    "I need encouragement today",
]

# Italian phrases that should be detected as Italian
ITALIAN_PHRASES = [
    "Dimmi del Padre Nostro per favore",
    "Cosa dice la Bibbia sul amore?",
    "Aiutami a capire Giovanni 3:16",
    "Ho bisogno di incoraggiamento",
    "Mi sento ansioso oggi",
    "Spiegami il significato della fede",
]

# German phrases that should be detected as German
GERMAN_PHRASES = [
    "Was sagt die Bibel über die Liebe?",
    "Hilf mir Johannes 3:16 zu verstehen",
    "Erkläre mir das Vaterunser",
    "Ich brauche Ermutigung heute",
    "Was bedeutet Glaube?",
    "Ich fühle mich heute ängstlich",
]

# Spanish phrases that should be detected as Spanish
SPANISH_PHRASES = [
    "¿Qué dice la Biblia sobre el amor y la esperanza?",
    "Ayúdame a entender el significado de este versículo",
    "Necesito ánimo y esperanza para seguir adelante hoy",
    "Explícame el significado de la fe cristiana",
    "Me siento ansioso hoy y necesito encontrar paz",
    "Quiero saber qué dice la palabra de Dios acerca del perdón",
]

# French phrases that should be detected as French
FRENCH_PHRASES = [
    "Que dit la Bible sur l'amour et l'espérance?",
    "Aidez-moi à comprendre la signification de ce verset",
    "J'ai besoin d'encouragement et de réconfort aujourd'hui",
    "Expliquez-moi la signification de la foi chrétienne",
    "Je me sens très anxieux aujourd'hui et j'ai besoin de paix",
    "Montrez-moi un verset biblique sur l'espérance et la grâce",
]

# Portuguese phrases that should be detected as Portuguese
PORTUGUESE_PHRASES = [
    "O que a Bíblia diz sobre o amor e a esperança?",
    "Me ajude a entender o significado deste versículo bíblico",
    "Preciso de encorajamento e conforto para hoje",
    "Explique para mim o significado da fé cristã",
    "Estou me sentindo muito ansioso hoje e preciso de paz",
    "Mostre-me um versículo bíblico sobre esperança e graça",
]

# Arabic phrases that should be detected as Arabic
ARABIC_PHRASES = [
    "ماذا يقول الكتاب المقدس عن المحبة؟",
    "ساعدني في فهم يوحنا الفصل الثالث الآية السادسة عشرة",
    "أحتاج إلى تشجيع اليوم",
    "اشرح لي معنى الإيمان",
    "أشعر بالقلق اليوم",
    "أرني آية عن الرجاء والأمل",
]

# Short/ambiguous phrases that should default to English
AMBIGUOUS_PHRASES = [
    "John 3:16",  # Just a reference
    "Love",  # Single word
    "Help",  # Single word
    "?",  # Just punctuation
    "",  # Empty
    "   ",  # Whitespace only
]


# =============================================================================
# Language Detection Tests
# =============================================================================


class TestLanguageDetection:
    """Tests for the detect_language function."""

    @pytest.mark.parametrize("phrase", ENGLISH_PHRASES)
    def test_detects_english(self, phrase: str):
        """English phrases should be detected as English."""
        result = detect_language(phrase)
        assert result == "en", f"Expected 'en' for '{phrase}', got '{result}'"

    @pytest.mark.parametrize("phrase", ITALIAN_PHRASES)
    def test_detects_italian(self, phrase: str):
        """Italian phrases should be detected as Italian."""
        result = detect_language(phrase)
        assert result == "it", f"Expected 'it' for '{phrase}', got '{result}'"

    @pytest.mark.parametrize("phrase", GERMAN_PHRASES)
    def test_detects_german(self, phrase: str):
        """German phrases should be detected as German."""
        result = detect_language(phrase)
        assert result == "de", f"Expected 'de' for '{phrase}', got '{result}'"

    @pytest.mark.parametrize("phrase", SPANISH_PHRASES)
    def test_detects_spanish(self, phrase: str):
        """Spanish phrases should be detected as Spanish."""
        result = detect_language(phrase)
        assert result == "es", f"Expected 'es' for '{phrase}', got '{result}'"

    @pytest.mark.parametrize("phrase", FRENCH_PHRASES)
    def test_detects_french(self, phrase: str):
        """French phrases should be detected as French."""
        result = detect_language(phrase)
        assert result == "fr", f"Expected 'fr' for '{phrase}', got '{result}'"

    @pytest.mark.parametrize("phrase", PORTUGUESE_PHRASES)
    def test_detects_portuguese(self, phrase: str):
        """Portuguese phrases should be detected as Portuguese."""
        result = detect_language(phrase)
        assert result == "pt", f"Expected 'pt' for '{phrase}', got '{result}'"

    @pytest.mark.parametrize("phrase", ARABIC_PHRASES)
    def test_detects_arabic(self, phrase: str):
        """Arabic phrases should be detected as Arabic."""
        result = detect_language(phrase)
        assert result == "ar", f"Expected 'ar' for '{phrase}', got '{result}'"

    @pytest.mark.parametrize("phrase", AMBIGUOUS_PHRASES)
    def test_ambiguous_defaults_to_english(self, phrase: str):
        """Ambiguous or short phrases should default to English."""
        result = detect_language(phrase)
        assert (
            result == DEFAULT_LANGUAGE
        ), f"Expected '{DEFAULT_LANGUAGE}' for '{phrase}', got '{result}'"

    def test_empty_string_returns_default(self):
        """Empty string should return default language."""
        assert detect_language("") == DEFAULT_LANGUAGE

    def test_none_like_input_returns_default(self):
        """Whitespace-only input should return default language."""
        assert detect_language("   ") == DEFAULT_LANGUAGE

    def test_returns_supported_language(self):
        """Detection should only return supported languages."""
        # Test with various inputs
        all_phrases = (
            ENGLISH_PHRASES
            + ITALIAN_PHRASES
            + GERMAN_PHRASES
            + SPANISH_PHRASES
            + FRENCH_PHRASES
            + PORTUGUESE_PHRASES
            + ARABIC_PHRASES
        )
        for phrase in all_phrases:
            result = detect_language(phrase)
            assert result in SUPPORTED_LANGUAGES, f"Got unsupported language '{result}'"


class TestLanguageDetectionEdgeCases:
    """Edge case tests for language detection."""

    def test_mixed_language_defaults_to_dominant(self):
        """Mixed language text should detect the dominant language."""
        # Predominantly English with some Italian words
        text = "Please help me understand the meaning of amore in the Bible"
        result = detect_language(text)
        # Should detect as English since most words are English
        assert result == "en"

    def test_bible_verse_reference_in_english_context(self):
        """Bible verse references in English context should detect as English."""
        phrases = [
            "What does Matthew 5:3-12 mean?",
            "Explain 1 Corinthians 13:4-7 to me",
            "Read me Psalm 23",
        ]
        for phrase in phrases:
            result = detect_language(phrase)
            assert result == "en", f"Expected 'en' for '{phrase}', got '{result}'"

    def test_religious_terms_in_english(self):
        """Religious terms in English should be detected correctly."""
        phrases = [
            "What is the meaning of salvation?",
            "Tell me about Jesus Christ",
            "What does the Bible say about prayer?",
            "Explain the concept of grace",
        ]
        for phrase in phrases:
            result = detect_language(phrase)
            assert result == "en", f"Expected 'en' for '{phrase}', got '{result}'"


# =============================================================================
# Language Detector Interface Tests
# =============================================================================


class TestLanguageDetectorInterface:
    """Tests for the LanguageDetector interface and implementations."""

    def test_lingua_detector_has_name(self):
        """LinguaLanguageDetector should have a name property."""
        detector = LinguaLanguageDetector()
        assert detector.name == "lingua"

    def test_lingua_detector_is_language_detector(self):
        """LinguaLanguageDetector should be a LanguageDetector."""
        detector = LinguaLanguageDetector()
        assert isinstance(detector, LanguageDetector)

    def test_create_detector_returns_lingua_by_default(self):
        """Factory should return LinguaLanguageDetector by default."""
        detector = create_language_detector()
        assert isinstance(detector, LinguaLanguageDetector)
        assert detector.name == "lingua"

    def test_create_detector_with_invalid_provider_raises(self):
        """Factory should raise ValueError for invalid provider."""
        with pytest.raises(ValueError) as exc_info:
            create_language_detector("invalid_provider")  # type: ignore
        assert "Unsupported" in str(exc_info.value)

    def test_get_detector_returns_singleton(self):
        """get_detector should return the same instance."""
        detector1 = get_detector()
        detector2 = get_detector()
        assert detector1 is detector2

    def test_set_detector_changes_global_instance(self):
        """set_detector should change the global detector."""
        original = get_detector()
        new_detector = LinguaLanguageDetector()
        set_detector(new_detector)
        assert get_detector() is new_detector
        # Restore original
        set_detector(original)

    def test_custom_detector_parameters(self):
        """LinguaLanguageDetector should accept custom parameters."""
        detector = LinguaLanguageDetector(
            min_text_length=5,
            confidence_threshold=0.8,
        )
        # Very short text should still default to English
        assert detector.detect("Hi") == DEFAULT_LANGUAGE


# =============================================================================
# Translation Mapping Tests
# =============================================================================


class TestTranslationMapping:
    """Tests for translation mapping functions."""

    def test_english_maps_to_web(self):
        """English should map to WEB translation."""
        assert get_translation_for_language("en") == "web"

    def test_italian_maps_to_ita1927(self):
        """Italian should map to Riveduta 1927."""
        assert get_translation_for_language("it") == "ita1927"

    def test_german_maps_to_schlachter(self):
        """German should map to Schlachter."""
        assert get_translation_for_language("de") == "schlachter"

    def test_spanish_maps_to_valera(self):
        """Spanish should map to Reina Valera."""
        assert get_translation_for_language("es") == "valera"

    def test_french_maps_to_ls1910(self):
        """French should map to Louis Segond."""
        assert get_translation_for_language("fr") == "ls1910"

    def test_portuguese_maps_to_almeida(self):
        """Portuguese should map to Almeida."""
        assert get_translation_for_language("pt") == "almeida"

    def test_arabic_maps_to_arabicsv(self):
        """Arabic should map to Smith & Van Dyke."""
        assert get_translation_for_language("ar") == "arabicsv"

    def test_unknown_language_maps_to_default(self):
        """Unknown language should map to default translation."""
        assert get_translation_for_language("xx") == DEFAULT_TRANSLATION
        assert get_translation_for_language("unknown") == DEFAULT_TRANSLATION

    def test_detect_translation_english(self):
        """detect_translation should return correct translation for English."""
        result = detect_translation("What does the Bible say about love?")
        assert result == "web"

    def test_detect_translation_italian(self):
        """detect_translation should return correct translation for Italian."""
        result = detect_translation("Cosa dice la Bibbia sul amore?")
        assert result == "ita1927"

    def test_detect_translation_german(self):
        """detect_translation should return correct translation for German."""
        result = detect_translation("Was sagt die Bibel über die Liebe?")
        assert result == "schlachter"


class TestTranslationInfo:
    """Tests for translation info functions."""

    def test_get_translation_info_kjv(self):
        """get_translation_info should return correct KJV info."""
        info = get_translation_info("kjv")
        assert info["code"] == "kjv"
        assert info["name"] == "King James Version"
        assert info["language"] == "English"

    def test_get_translation_info_web(self):
        """get_translation_info should return correct WEB info."""
        info = get_translation_info("web")
        assert info["code"] == "web"
        assert info["name"] == "World English Bible"

    def test_get_translation_info_invalid_returns_default(self):
        """get_translation_info should return default for invalid code."""
        info = get_translation_info("invalid")
        assert info["code"] == DEFAULT_TRANSLATION

    def test_get_all_translations(self):
        """get_all_translations should return all translations."""
        translations = get_all_translations()
        assert len(translations) == 12
        codes = [t["code"] for t in translations]
        assert "kjv" in codes
        assert "web" in codes
        assert "ita1927" in codes
        assert "schlachter" in codes
        assert "valera" in codes
        assert "ls1910" in codes
        assert "almeida" in codes
        assert "arabicsv" in codes
        assert "synodal" in codes
        assert "cuv" in codes
        assert "hindi" in codes
        assert "krv" in codes

    def test_get_translations_for_language_english(self):
        """get_translations_for_language should return English translations."""
        translations = get_translations_for_language("en")
        codes = [t["code"] for t in translations]
        assert "web" in codes
        assert "kjv" in codes
        assert "ita1927" not in codes

    def test_get_translations_for_language_italian(self):
        """get_translations_for_language should return Italian translations."""
        translations = get_translations_for_language("it")
        codes = [t["code"] for t in translations]
        assert "ita1927" in codes
        assert "kjv" not in codes

    def test_is_valid_translation(self):
        """is_valid_translation should validate translation codes."""
        assert is_valid_translation("kjv") is True
        assert is_valid_translation("web") is True
        assert is_valid_translation("ita1927") is True
        assert is_valid_translation("schlachter") is True
        assert is_valid_translation("valera") is True
        assert is_valid_translation("ls1910") is True
        assert is_valid_translation("almeida") is True
        assert is_valid_translation("arabicsv") is True
        assert is_valid_translation("invalid") is False
        assert is_valid_translation("") is False


class TestResolveTranslation:
    """Tests for resolve_translation function."""

    def test_preferred_translation_takes_priority(self):
        """Valid preferred translation should be used."""
        result = resolve_translation("kjv", "it")
        assert result == "kjv"

    def test_invalid_preferred_uses_language(self):
        """Invalid preferred translation should fall back to language."""
        result = resolve_translation("invalid", "it")
        assert result == "ita1927"

    def test_no_preference_uses_language(self):
        """No preferred translation should use language default."""
        result = resolve_translation(None, "de")
        assert result == "schlachter"

    def test_no_preference_no_language_uses_default(self):
        """No preference and no language should use global default."""
        result = resolve_translation(None, None)
        assert result == DEFAULT_TRANSLATION


# =============================================================================
# Book Name Localization Tests
# =============================================================================


class TestBookNameLocalization:
    """Tests for book name localization."""

    def test_english_book_unchanged_for_english_translation(self):
        """English book names should be unchanged for English translations."""
        assert get_localized_book_name("Genesis", "kjv") == "Genesis"
        assert get_localized_book_name("Matthew", "web") == "Matthew"

    def test_book_localized_for_italian(self):
        """Book names should be localized for Italian translation."""
        assert get_localized_book_name("Genesis", "ita1927") == "Genesi"
        assert get_localized_book_name("Matthew", "ita1927") == "Matteo"
        assert get_localized_book_name("John", "ita1927") == "Giovanni"
        assert get_localized_book_name("Psalms", "ita1927") == "Salmi"

    def test_book_localized_for_german(self):
        """Book names should be localized for German translation."""
        assert get_localized_book_name("Genesis", "schlachter") == "1. Mose"
        assert get_localized_book_name("Matthew", "schlachter") == "Matthäus"
        assert get_localized_book_name("John", "schlachter") == "Johannes"
        assert get_localized_book_name("Psalms", "schlachter") == "Psalmen"

    def test_book_localized_for_spanish(self):
        """Book names should be localized for Spanish translation."""
        assert get_localized_book_name("Genesis", "valera") == "Génesis"
        assert get_localized_book_name("Matthew", "valera") == "Mateo"
        assert get_localized_book_name("John", "valera") == "Juan"
        assert get_localized_book_name("Psalms", "valera") == "Salmos"

    def test_book_localized_for_french(self):
        """Book names should be localized for French translation."""
        assert get_localized_book_name("Genesis", "ls1910") == "Genèse"
        assert get_localized_book_name("Matthew", "ls1910") == "Matthieu"
        assert get_localized_book_name("John", "ls1910") == "Jean"
        assert get_localized_book_name("Psalms", "ls1910") == "Psaumes"

    def test_book_localized_for_portuguese(self):
        """Book names should be localized for Portuguese translation."""
        assert get_localized_book_name("Genesis", "almeida") == "Gênesis"
        assert get_localized_book_name("Matthew", "almeida") == "Mateus"
        assert get_localized_book_name("John", "almeida") == "João"
        assert get_localized_book_name("Psalms", "almeida") == "Salmos"

    def test_book_localized_for_arabic(self):
        """Book names should be localized for Arabic translation."""
        assert get_localized_book_name("Genesis", "arabicsv") == "تكوين"
        assert get_localized_book_name("Matthew", "arabicsv") == "متى"
        assert get_localized_book_name("John", "arabicsv") == "يوحنا"
        assert get_localized_book_name("Psalms", "arabicsv") == "المزامير"

    def test_unknown_book_returns_original(self):
        """Unknown book names should return the original."""
        assert get_localized_book_name("UnknownBook", "ita1927") == "UnknownBook"
        assert get_localized_book_name("UnknownBook", "schlachter") == "UnknownBook"
        assert get_localized_book_name("UnknownBook", "valera") == "UnknownBook"
        assert get_localized_book_name("UnknownBook", "arabicsv") == "UnknownBook"


# =============================================================================
# Mock Detector for Testing
# =============================================================================


class MockLanguageDetector(LanguageDetector):
    """Mock detector for testing the pluggable interface."""

    def __init__(self, fixed_language: str = "en"):
        self._fixed_language = fixed_language

    @property
    def name(self) -> str:
        return "mock"

    def detect(self, text: str) -> str:
        return self._fixed_language


class TestMockDetector:
    """Tests demonstrating the pluggable detector interface."""

    def test_mock_detector_can_be_used(self):
        """Mock detector should work with the interface."""
        original = get_detector()
        mock = MockLanguageDetector("it")
        set_detector(mock)

        # Now all detections return Italian
        assert detect_language("Hello world") == "it"
        assert detect_language("Anything") == "it"

        # Restore original
        set_detector(original)

    def test_mock_detector_for_testing_translations(self):
        """Mock detector can be used to test translation logic."""
        original = get_detector()
        mock = MockLanguageDetector("de")
        set_detector(mock)

        # Translation detection uses the mock
        assert detect_translation("Any text") == "schlachter"

        # Restore original
        set_detector(original)


# =============================================================================
# Model Override Tests
# =============================================================================


class TestGetModelOverrideForLanguage:
    """Tests for get_model_override_for_language()."""

    def test_arabic_returns_qwen_override(self):
        """Arabic should return the Qwen model override by default."""
        from unittest.mock import patch

        from config import Settings
        from utils.language import get_model_override_for_language

        mock_settings = Settings(language_model_overrides="ar=qwen/qwen-2.5-72b-instruct")
        with patch("config.get_settings", return_value=mock_settings):
            result = get_model_override_for_language("ar")
        assert result == "qwen/qwen-2.5-72b-instruct"

    def test_english_returns_none(self):
        """English should return None (use default model)."""
        from unittest.mock import patch

        from config import Settings
        from utils.language import get_model_override_for_language

        mock_settings = Settings(language_model_overrides="ar=qwen/qwen-2.5-72b-instruct")
        with patch("config.get_settings", return_value=mock_settings):
            result = get_model_override_for_language("en")
        assert result is None

    def test_french_returns_none(self):
        """French should return None when not in overrides."""
        from unittest.mock import patch

        from config import Settings
        from utils.language import get_model_override_for_language

        mock_settings = Settings(language_model_overrides="ar=qwen/qwen-2.5-72b-instruct")
        with patch("config.get_settings", return_value=mock_settings):
            result = get_model_override_for_language("fr")
        assert result is None

    def test_empty_config_returns_none(self):
        """Empty overrides string should return None."""
        from unittest.mock import patch

        from config import Settings
        from utils.language import get_model_override_for_language

        mock_settings = Settings(language_model_overrides="")
        with patch("config.get_settings", return_value=mock_settings):
            result = get_model_override_for_language("ar")
        assert result is None

    def test_multiple_overrides_parsed_correctly(self):
        """Multiple comma-separated overrides should all be resolved."""
        from unittest.mock import patch

        from config import Settings
        from utils.language import get_model_override_for_language

        mock_settings = Settings(
            language_model_overrides="ar=qwen/qwen-2.5-72b-instruct,zh=qwen/qwen-2.5-72b-instruct"
        )
        with patch("config.get_settings", return_value=mock_settings):
            assert get_model_override_for_language("ar") == "qwen/qwen-2.5-72b-instruct"
            assert get_model_override_for_language("zh") == "qwen/qwen-2.5-72b-instruct"
            assert get_model_override_for_language("en") is None
