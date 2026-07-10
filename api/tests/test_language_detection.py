"""
Tests for the language detection and translation mapping utilities.
"""

from utils.language import (
    DEFAULT_TRANSLATION,
    ENGLISH_TO_ARABIC_BOOKS,
    ENGLISH_TO_CHINESE_BOOKS,
    ENGLISH_TO_FRENCH_BOOKS,
    ENGLISH_TO_GERMAN_BOOKS,
    ENGLISH_TO_HINDI_BOOKS,
    ENGLISH_TO_ITALIAN_BOOKS,
    ENGLISH_TO_KOREAN_BOOKS,
    ENGLISH_TO_PORTUGUESE_BOOKS,
    ENGLISH_TO_RUSSIAN_BOOKS,
    ENGLISH_TO_SPANISH_BOOKS,
    LANGUAGE_TO_TRANSLATION,
    LANGUAGE_TRANSLATIONS,
    TRANSLATION_INFO,
    detect_language,
    detect_language_confident,
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
            "Mi sento molto ansioso per il mio futuro",
            "Cosa dice la Bibbia sul perdono e la grazia?",
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

    def test_detect_russian(self):
        """Test detection of Russian text."""
        texts = [
            "Привет, мне нужна помощь с моей жизнью",
            "Я беспокоюсь о своём будущем",
            "Что Библия говорит о прощении и благодати?",
        ]
        for text in texts:
            assert detect_language(text) == "ru"

    def test_detect_chinese(self):
        """Test detection of Chinese text."""
        texts = [
            "你好，我需要生活方面的帮助",
            "我对未来感到焦虑和不安",
            "圣经对宽恕有什么看法？",
        ]
        for text in texts:
            assert detect_language(text) == "zh"

    def test_detect_hindi(self):
        """Test detection of Hindi text."""
        texts = [
            "नमस्ते, मुझे अपने जीवन में मदद चाहिए",
            "मैं अपने भविष्य को लेकर चिंतित हूं",
            "बाइबिल क्षमा के बारे में क्या कहती है?",
        ]
        for text in texts:
            assert detect_language(text) == "hi"

    def test_detect_korean(self):
        """Test detection of Korean text."""
        texts = [
            "안녕하세요, 제 삶에 대한 도움이 필요합니다",
            "저는 미래에 대해 불안합니다",
            "성경은 용서에 대해 무엇을 말하나요?",
        ]
        for text in texts:
            assert detect_language(text) == "ko"


class TestTranslationMapping:
    """Tests for translation mapping."""

    def test_get_translation_for_english(self):
        """Test English maps to WEB (default)."""
        assert get_translation_for_language("en") == "web"

    def test_get_translation_for_italian(self):
        """Test Italian maps to Riveduta 1927."""
        assert get_translation_for_language("it") == "ita1927"

    def test_get_translation_for_german(self):
        """Test German maps to Schlachter 1951 (default until Luther 1912 is seeded)."""
        assert get_translation_for_language("de") == "schlachter"

    def test_get_translation_for_spanish(self):
        """Test Spanish maps to Reina Valera."""
        assert get_translation_for_language("es") == "valera"

    def test_get_translation_for_french(self):
        """Test French maps to Louis Segond."""
        assert get_translation_for_language("fr") == "ls1910"

    def test_get_translation_for_portuguese(self):
        """Test Portuguese maps to Almeida."""
        assert get_translation_for_language("pt") == "almeida"

    def test_get_translation_for_arabic(self):
        """Test Arabic maps to Smith & Van Dyke."""
        assert get_translation_for_language("ar") == "arabicsv"

    def test_get_translation_for_unknown_language(self):
        """Test unknown language defaults to WEB."""
        assert get_translation_for_language("xx") == DEFAULT_TRANSLATION

    def test_get_translation_for_russian(self):
        """Test Russian maps to Synodal."""
        assert get_translation_for_language("ru") == "synodal"

    def test_get_translation_for_chinese(self):
        """Test Chinese maps to CUV."""
        assert get_translation_for_language("zh") == "cuv"

    def test_get_translation_for_hindi(self):
        """Test Hindi maps to IRV Hindi."""
        assert get_translation_for_language("hi") == "hindi"

    def test_get_translation_for_korean(self):
        """Test Korean maps to Korean Revised Version."""
        assert get_translation_for_language("ko") == "krv"

    def test_detect_translation_english(self):
        """Test full detection pipeline for English."""
        assert detect_translation("I need encouragement today") == "web"

    def test_detect_translation_italian(self):
        """Test full detection pipeline for Italian."""
        assert detect_translation("Ho bisogno di incoraggiamento oggi") == "ita1927"

    def test_detect_translation_german(self):
        """Test full detection pipeline for German."""
        assert detect_translation("Ich brauche heute Ermutigung") == "schlachter"

    def test_detect_translation_russian(self):
        """Test full detection pipeline for Russian."""
        assert detect_translation("Мне нужно ободрение сегодня") == "synodal"

    def test_detect_translation_chinese(self):
        """Test full detection pipeline for Chinese."""
        assert detect_translation("我今天需要鼓励和支持") == "cuv"

    def test_detect_translation_hindi(self):
        """Test full detection pipeline for Hindi."""
        assert detect_translation("मुझे आज प्रोत्साहन चाहिए") == "hindi"

    def test_detect_translation_korean(self):
        """Test full detection pipeline for Korean."""
        assert detect_translation("나는 오늘 격려가 필요합니다") == "krv"


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

    def test_all_66_books_have_russian_translation(self):
        """Test all 66 Bible books have Russian translations."""
        assert len(ENGLISH_TO_RUSSIAN_BOOKS) == 66

    def test_all_66_books_have_chinese_translation(self):
        """Test all 66 Bible books have Chinese translations."""
        assert len(ENGLISH_TO_CHINESE_BOOKS) == 66

    def test_all_66_books_have_hindi_translation(self):
        """Test all 66 Bible books have Hindi translations."""
        assert len(ENGLISH_TO_HINDI_BOOKS) == 66

    def test_all_66_books_have_korean_translation(self):
        """Test all 66 Bible books have Korean translations."""
        assert len(ENGLISH_TO_KOREAN_BOOKS) == 66

    # ── Exodus/Esodo spot-check (primary BITB-040 regression guard) ──────────

    def test_localize_exodus_italian(self):
        assert get_localized_book_name("Exodus", "ita1927") == "Esodo"

    def test_localize_exodus_german(self):
        assert get_localized_book_name("Exodus", "schlachter") == "2. Mose"

    def test_localize_exodus_russian(self):
        assert get_localized_book_name("Exodus", "synodal") == "Исход"

    def test_localize_exodus_chinese(self):
        assert get_localized_book_name("Exodus", "cuv") == "出埃及记"

    # ── Spot-checks for translations not yet individually tested ────────────

    def test_localize_genesis_spanish(self):
        assert get_localized_book_name("Genesis", "valera") == "Génesis"

    def test_localize_john_spanish(self):
        assert get_localized_book_name("John", "valera") == "Juan"

    def test_localize_revelation_spanish(self):
        assert get_localized_book_name("Revelation", "valera") == "Apocalipsis"

    def test_localize_genesis_french(self):
        assert get_localized_book_name("Genesis", "ls1910") == "Genèse"

    def test_localize_john_french(self):
        assert get_localized_book_name("John", "ls1910") == "Jean"

    def test_localize_psalms_french(self):
        assert get_localized_book_name("Psalms", "ls1910") == "Psaumes"

    def test_localize_genesis_portuguese(self):
        assert get_localized_book_name("Genesis", "almeida") == "Gênesis"

    def test_localize_john_portuguese(self):
        assert get_localized_book_name("John", "almeida") == "João"

    def test_localize_genesis_arabic(self):
        assert get_localized_book_name("Genesis", "arabicsv") == "تكوين"

    def test_localize_john_arabic(self):
        assert get_localized_book_name("John", "arabicsv") == "يوحنا"

    # ── Map size checks for all 10 translations ──────────────────────────────

    def test_all_66_books_have_spanish_translation(self):
        assert len(ENGLISH_TO_SPANISH_BOOKS) == 66

    def test_all_66_books_have_french_translation(self):
        assert len(ENGLISH_TO_FRENCH_BOOKS) == 66

    def test_all_66_books_have_portuguese_translation(self):
        assert len(ENGLISH_TO_PORTUGUESE_BOOKS) == 66

    def test_all_66_books_have_arabic_translation(self):
        assert len(ENGLISH_TO_ARABIC_BOOKS) == 66

    def test_localize_genesis_russian(self):
        """Test Genesis localizes to Russian."""
        assert get_localized_book_name("Genesis", "synodal") == "Бытие"

    def test_localize_genesis_chinese(self):
        """Test Genesis localizes to Chinese."""
        assert get_localized_book_name("Genesis", "cuv") == "创世记"

    def test_localize_genesis_hindi(self):
        """Test Genesis localizes to Hindi."""
        assert get_localized_book_name("Genesis", "hindi") == "उत्पत्ति"

    def test_localize_genesis_korean(self):
        """Test Genesis localizes to Korean."""
        assert get_localized_book_name("Genesis", "krv") == "창세기"

    def test_localize_john_russian(self):
        """Test John localizes to Russian."""
        assert get_localized_book_name("John", "synodal") == "Иоанн"

    def test_localize_revelation_chinese(self):
        """Test Revelation localizes to Chinese."""
        assert get_localized_book_name("Revelation", "cuv") == "启示录"

    def test_localize_psalms_hindi(self):
        """Test Psalms localizes to Hindi."""
        assert get_localized_book_name("Psalms", "hindi") == "भजन संहिता"

    def test_localize_revelation_korean(self):
        """Test Revelation localizes to Korean."""
        assert get_localized_book_name("Revelation", "krv") == "요한계시록"


class TestLanguageToTranslationMapping:
    """Tests for the language to translation mapping."""

    def test_all_supported_languages_have_mappings(self):
        """Test all supported languages have translation mappings."""
        supported = ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"]
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

    def test_german_returns_two(self):
        """Test German has two translations with Schlachter as default (until Luther is seeded)."""
        result = get_translations_for_language("de")
        assert len(result) == 2
        assert result[0]["code"] == "schlachter"
        assert result[1]["code"] == "luther1912"

    def test_unknown_language_returns_empty(self):
        """Test unknown language returns empty list."""
        result = get_translations_for_language("xx")
        assert result == []

    def test_russian_returns_one(self):
        """Test Russian has one translation."""
        result = get_translations_for_language("ru")
        assert len(result) == 1
        assert result[0]["code"] == "synodal"

    def test_chinese_returns_one(self):
        """Test Chinese has one translation."""
        result = get_translations_for_language("zh")
        assert len(result) == 1
        assert result[0]["code"] == "cuv"

    def test_hindi_returns_one(self):
        """Test Hindi has one translation."""
        result = get_translations_for_language("hi")
        assert len(result) == 1
        assert result[0]["code"] == "hindi"

    def test_korean_returns_one(self):
        """Test Korean has one translation."""
        result = get_translations_for_language("ko")
        assert len(result) == 1
        assert result[0]["code"] == "krv"


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


class TestDetectLanguageConfident:
    """Tests for detect_language_confident — high-confidence detection only."""

    def test_long_italian_returns_it(self):
        """Long Italian text should be detected with high confidence."""
        result = detect_language_confident("Cosa dice la Bibbia sull'amore e la speranza in Dio?")
        assert result == "it"

    def test_short_text_returns_none(self):
        """Text shorter than min_text_length should return None."""
        assert detect_language_confident("Ciao") is None

    def test_empty_returns_none(self):
        """Empty string should return None."""
        assert detect_language_confident("") is None

    def test_long_english_returns_en(self):
        """Long English text should be detected with high confidence."""
        result = detect_language_confident("What does the Bible say about love and hope in God?")
        assert result == "en"

    def test_long_german_returns_de(self):
        """Long German text should be detected with high confidence."""
        result = detect_language_confident("Was sagt die Bibel über Liebe und Hoffnung in Gott?")
        assert result == "de"
