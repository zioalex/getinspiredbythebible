"""
Comprehensive tests for utility modules.

Covers: utils/local_only.py, utils/logging_config.py, utils/book_names.py,
utils/rate_limiter.py
"""

import asyncio
import logging
import time
from unittest.mock import MagicMock, patch

import pytest

from utils.book_names import (
    CHINESE_TO_ENGLISH,
    ENGLISH_TO_CHINESE,
    ENGLISH_TO_FRENCH,
    ENGLISH_TO_GERMAN,
    ENGLISH_TO_HINDI,
    ENGLISH_TO_ITALIAN,
    ENGLISH_TO_KOREAN,
    ENGLISH_TO_RUSSIAN,
    ENGLISH_TO_SPANISH,
    FRENCH_TO_ENGLISH,
    GERMAN_TO_ENGLISH,
    HINDI_TO_ENGLISH,
    ITALIAN_TO_ENGLISH,
    KOREAN_TO_ENGLISH,
    LOCALIZED_TO_ENGLISH,
    RUSSIAN_TO_ENGLISH,
    SPANISH_TO_ENGLISH,
    TRANSLATION_BOOK_NAMES,
    get_localized_book_name,
    normalize_book_name,
)
from utils.local_only import get_client_ip, is_local_ip
from utils.logging_config import LogContext, get_logger, setup_logging
from utils.rate_limiter import RateLimitEntry, RateLimiter
from utils.translation_registry import EXTRA_REVERSE_MAPPINGS

# =============================================================================
# Local Only Access Tests
# =============================================================================


class TestIsLocalIp:
    """Tests for is_local_ip function."""

    def test_ipv4_loopback(self):
        assert is_local_ip("127.0.0.1") is True

    def test_ipv4_loopback_other(self):
        assert is_local_ip("127.0.0.2") is True

    def test_private_class_a(self):
        assert is_local_ip("10.0.0.1") is True
        assert is_local_ip("10.255.255.255") is True

    def test_private_class_b(self):
        assert is_local_ip("172.16.0.1") is True
        assert is_local_ip("172.31.255.255") is True

    def test_private_class_c(self):
        assert is_local_ip("192.168.0.1") is True
        assert is_local_ip("192.168.1.100") is True

    def test_ipv6_loopback(self):
        assert is_local_ip("::1") is True

    def test_public_ip_v4(self):
        assert is_local_ip("8.8.8.8") is False
        assert is_local_ip("1.1.1.1") is False

    def test_invalid_ip_returns_false(self):
        assert is_local_ip("not-an-ip") is False
        assert is_local_ip("") is False
        assert is_local_ip("999.999.999.999") is False


class TestGetClientIp:
    """Tests for get_client_ip function."""

    def _make_request(self, headers=None, client_host=None):
        request = MagicMock()
        request.headers = headers or {}
        if client_host:
            request.client = MagicMock()
            request.client.host = client_host
        else:
            request.client = None
        return request

    def test_x_forwarded_for_single(self):
        request = self._make_request(
            headers={"X-Forwarded-For": "203.0.113.1"},
            client_host="10.0.0.1",
        )
        assert get_client_ip(request) == "203.0.113.1"

    def test_x_forwarded_for_multiple(self):
        """Should return the first IP (original client)."""
        request = self._make_request(
            headers={"X-Forwarded-For": "203.0.113.1, 10.0.0.1, 172.16.0.1"}
        )
        assert get_client_ip(request) == "203.0.113.1"

    def test_x_real_ip(self):
        request = self._make_request(headers={"X-Real-IP": "203.0.113.2"})
        assert get_client_ip(request) == "203.0.113.2"

    def test_x_real_ip_with_whitespace(self):
        request = self._make_request(headers={"X-Real-IP": "  203.0.113.2  "})
        assert get_client_ip(request) == "203.0.113.2"

    def test_direct_client(self):
        request = self._make_request(client_host="192.168.1.1")
        assert get_client_ip(request) == "192.168.1.1"

    def test_no_client_returns_empty(self):
        request = self._make_request()
        assert get_client_ip(request) == ""

    def test_x_forwarded_for_takes_priority(self):
        """X-Forwarded-For should take priority over X-Real-IP and direct client."""
        request = self._make_request(
            headers={
                "X-Forwarded-For": "1.2.3.4",
                "X-Real-IP": "5.6.7.8",
            },
            client_host="10.0.0.1",
        )
        assert get_client_ip(request) == "1.2.3.4"


class TestRequireLocalAccess:
    """Tests for require_local_access dependency."""

    @pytest.mark.asyncio
    async def test_allows_testclient(self):
        """TestClient should always be allowed."""
        from utils.local_only import require_local_access

        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "testclient"

        # Should not raise
        await require_local_access(request)

    @pytest.mark.asyncio
    async def test_allows_local_ip(self):
        """Local IPs should be allowed."""
        from utils.local_only import require_local_access

        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        await require_local_access(request)

    @pytest.mark.asyncio
    async def test_denies_public_ip(self):
        """Public IPs should be denied."""
        from fastapi import HTTPException

        from utils.local_only import require_local_access

        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "8.8.8.8"

        with pytest.raises(HTTPException) as exc_info:
            await require_local_access(request)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_denies_no_client_ip(self):
        """No client IP should be denied (when not in debug mode)."""
        from fastapi import HTTPException

        from utils.local_only import require_local_access

        request = MagicMock()
        request.headers = {}
        request.client = None

        with patch("utils.local_only.settings") as mock_settings:
            mock_settings.debug = False
            with pytest.raises(HTTPException) as exc_info:
                await require_local_access(request)
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_allows_empty_ip_in_debug_mode(self):
        """Empty IPs should be allowed in debug mode."""
        from utils.local_only import require_local_access

        request = MagicMock()
        request.headers = {}
        request.client = None

        with patch("utils.local_only.settings") as mock_settings:
            mock_settings.debug = True
            await require_local_access(request)


# =============================================================================
# Logging Config Tests
# =============================================================================


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_creates_handler(self):
        """setup_logging should configure root logger."""
        with patch("utils.logging_config.settings") as mock_settings:
            mock_settings.log_level = "INFO"
            setup_logging()

        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) > 0

    def test_setup_logging_debug_level(self):
        """setup_logging should support DEBUG level."""
        with patch("utils.logging_config.settings") as mock_settings:
            mock_settings.log_level = "DEBUG"
            setup_logging()

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_setup_logging_removes_duplicate_handlers(self):
        """setup_logging should not create duplicate handlers."""
        with patch("utils.logging_config.settings") as mock_settings:
            mock_settings.log_level = "INFO"
            setup_logging()
            handler_count_1 = len(logging.getLogger().handlers)
            setup_logging()
            handler_count_2 = len(logging.getLogger().handlers)

        # Should have same number of handlers after second call
        assert handler_count_1 == handler_count_2


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_logger(self):
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "bible_app.test.module"

    def test_returns_same_logger(self):
        logger1 = get_logger("test.same")
        logger2 = get_logger("test.same")
        assert logger1 is logger2


class TestLogContext:
    """Tests for LogContext structured logging."""

    def test_info(self):
        """LogContext.info should log with context."""
        logger = MagicMock()
        ctx = LogContext(logger, user="test", session="123")
        ctx.info("Test message")
        logger.log.assert_called_once()
        args = logger.log.call_args
        assert args[0][0] == logging.INFO
        assert "Test message" in args[0][1]
        assert "user=test" in args[0][1]
        assert "session=123" in args[0][1]

    def test_error(self):
        """LogContext.error should log at ERROR level."""
        logger = MagicMock()
        ctx = LogContext(logger, request_id="abc")
        ctx.error("Something failed")
        args = logger.log.call_args
        assert args[0][0] == logging.ERROR
        assert "Something failed" in args[0][1]
        assert "request_id=abc" in args[0][1]

    def test_warning(self):
        """LogContext.warning should log at WARNING level."""
        logger = MagicMock()
        ctx = LogContext(logger)
        ctx.warning("Watch out")
        args = logger.log.call_args
        assert args[0][0] == logging.WARNING

    def test_debug(self):
        """LogContext.debug should log at DEBUG level."""
        logger = MagicMock()
        ctx = LogContext(logger)
        ctx.debug("Debug info")
        args = logger.log.call_args
        assert args[0][0] == logging.DEBUG

    def test_extra_fields_merged(self):
        """Extra fields in log calls should be merged with context."""
        logger = MagicMock()
        ctx = LogContext(logger, base="value")
        ctx.info("Message", extra_field="extra_value")
        args = logger.log.call_args
        message = args[0][1]
        assert "base=value" in message
        assert "extra_field=extra_value" in message

    def test_empty_context(self):
        """LogContext with no context should log message without separator."""
        logger = MagicMock()
        ctx = LogContext(logger)
        ctx.info("Just a message")
        args = logger.log.call_args
        assert args[0][1] == "Just a message"


# =============================================================================
# Book Names Tests
# =============================================================================


class TestBookNames:
    """Tests for book name localization utilities."""

    def test_english_to_italian_count(self):
        """Should have 66 Italian book mappings."""
        assert len(ENGLISH_TO_ITALIAN) == 66

    def test_english_to_german_count(self):
        """Should have 66 German book mappings."""
        assert len(ENGLISH_TO_GERMAN) == 66

    def test_italian_reverse_mapping(self):
        """Italian reverse mapping should work."""
        assert ITALIAN_TO_ENGLISH["Genesi"] == "Genesis"
        assert ITALIAN_TO_ENGLISH["Giovanni"] == "John"

    def test_german_reverse_mapping(self):
        """German reverse mapping should work."""
        assert GERMAN_TO_ENGLISH["1. Mose"] == "Genesis"
        assert GERMAN_TO_ENGLISH["Johannes"] == "John"

    def test_english_to_spanish_count(self):
        """Should have 66 Spanish book mappings."""
        assert len(ENGLISH_TO_SPANISH) == 66

    def test_english_to_french_count(self):
        """Should have 66 French book mappings."""
        assert len(ENGLISH_TO_FRENCH) == 66

    def test_spanish_reverse_mapping(self):
        """Spanish reverse mapping should work."""
        assert SPANISH_TO_ENGLISH["Génesis"] == "Genesis"
        assert SPANISH_TO_ENGLISH["Juan"] == "John"
        assert SPANISH_TO_ENGLISH["Salmos"] == "Psalms"

    def test_french_reverse_mapping(self):
        """French reverse mapping should work."""
        assert FRENCH_TO_ENGLISH["Genèse"] == "Genesis"
        assert FRENCH_TO_ENGLISH["Jean"] == "John"
        assert FRENCH_TO_ENGLISH["Psaumes"] == "Psalms"

    def test_russian_reverse_mapping(self):
        """Russian reverse mapping should cover canonical and alias forms."""
        assert RUSSIAN_TO_ENGLISH["Бытие"] == "Genesis"
        assert RUSSIAN_TO_ENGLISH["Иоанн"] == "John"
        assert RUSSIAN_TO_ENGLISH["Псалтирь"] == "Psalms"
        # Alias forms
        assert RUSSIAN_TO_ENGLISH["Иисус Навин"] == "Joshua"
        assert RUSSIAN_TO_ENGLISH["1 Царств"] == "1 Samuel"
        assert RUSSIAN_TO_ENGLISH["3 Царств"] == "1 Kings"
        assert RUSSIAN_TO_ENGLISH["Деяния апостолов"] == "Acts"
        assert RUSSIAN_TO_ENGLISH["1 Коринфянам"] == "1 Corinthians"

    def test_chinese_reverse_mapping(self):
        """Chinese reverse mapping should cover canonical and BOM/alias forms."""
        assert CHINESE_TO_ENGLISH["创世记"] == "Genesis"
        assert CHINESE_TO_ENGLISH["约翰福音"] == "John"
        assert CHINESE_TO_ENGLISH["诗篇"] == "Psalms"
        # BOM variant
        assert CHINESE_TO_ENGLISH["\ufeff创世记"] == "Genesis"
        # Simplified alias for Revelation
        assert CHINESE_TO_ENGLISH["启示录"] == "Revelation"

    def test_korean_reverse_mapping(self):
        """Korean reverse mapping should cover canonical and no-space alias."""
        assert KOREAN_TO_ENGLISH["창세기"] == "Genesis"
        assert KOREAN_TO_ENGLISH["요한복음"] == "John"
        assert KOREAN_TO_ENGLISH["시편"] == "Psalms"
        # Alternate form for Lamentations (no space)
        assert KOREAN_TO_ENGLISH["예레미야애가"] == "Lamentations"

    def test_hindi_reverse_mapping(self):
        """Hindi reverse mapping should cover all 66 canonical forms."""
        assert HINDI_TO_ENGLISH["उत्पत्ति"] == "Genesis"
        assert HINDI_TO_ENGLISH["यूहन्ना"] == "John"
        assert HINDI_TO_ENGLISH["भजन संहिता"] == "Psalms"
        assert HINDI_TO_ENGLISH["प्रकाशितवाक्य"] == "Revelation"

    def test_hindi_forward_mapping(self):
        """Hindi forward mapping should have 66 entries."""
        assert len(ENGLISH_TO_HINDI) == 66
        assert ENGLISH_TO_HINDI["Genesis"] == "उत्पत्ति"
        assert ENGLISH_TO_HINDI["John"] == "यूहन्ना"

    def test_localized_to_english_combined(self):
        """Combined mapping should contain all supported languages."""
        assert "Genesi" in LOCALIZED_TO_ENGLISH  # Italian
        assert "1. Mose" in LOCALIZED_TO_ENGLISH  # German
        assert "Juan" in LOCALIZED_TO_ENGLISH  # Spanish
        assert "Jean" in LOCALIZED_TO_ENGLISH  # French
        assert "Бытие" in LOCALIZED_TO_ENGLISH  # Russian
        assert "创世记" in LOCALIZED_TO_ENGLISH  # Chinese
        assert "창세기" in LOCALIZED_TO_ENGLISH  # Korean
        assert "उत्पत्ति" in LOCALIZED_TO_ENGLISH  # Hindi

    def test_translation_book_names_mapping(self):
        """TRANSLATION_BOOK_NAMES should map translation codes to book maps."""
        assert TRANSLATION_BOOK_NAMES["ita1927"] is ENGLISH_TO_ITALIAN
        assert TRANSLATION_BOOK_NAMES["schlachter"] is ENGLISH_TO_GERMAN
        assert TRANSLATION_BOOK_NAMES["valera"] is ENGLISH_TO_SPANISH
        assert TRANSLATION_BOOK_NAMES["ls1910"] is ENGLISH_TO_FRENCH
        assert TRANSLATION_BOOK_NAMES["synodal"] is ENGLISH_TO_RUSSIAN
        assert TRANSLATION_BOOK_NAMES["cuv"] is ENGLISH_TO_CHINESE
        assert TRANSLATION_BOOK_NAMES["krv"] is ENGLISH_TO_KOREAN
        assert TRANSLATION_BOOK_NAMES["hindi"] is ENGLISH_TO_HINDI
        assert TRANSLATION_BOOK_NAMES["kjv"] is None
        assert TRANSLATION_BOOK_NAMES["web"] is None


class TestGetLocalizedBookName:
    """Tests for get_localized_book_name function."""

    def test_italian_translation(self):
        assert get_localized_book_name("Genesis", "ita1927") == "Genesi"
        assert get_localized_book_name("John", "ita1927") == "Giovanni"

    def test_german_translation(self):
        assert get_localized_book_name("Genesis", "schlachter") == "1. Mose"
        assert get_localized_book_name("John", "schlachter") == "Johannes"

    def test_spanish_translation(self):
        assert get_localized_book_name("Genesis", "valera") == "Génesis"
        assert get_localized_book_name("John", "valera") == "Juan"
        assert get_localized_book_name("Psalms", "valera") == "Salmos"
        assert get_localized_book_name("2 Corinthians", "valera") == "2 Corintios"

    def test_french_translation(self):
        assert get_localized_book_name("Genesis", "ls1910") == "Genèse"
        assert get_localized_book_name("John", "ls1910") == "Jean"
        assert get_localized_book_name("Psalms", "ls1910") == "Psaumes"
        assert get_localized_book_name("2 Corinthians", "ls1910") == "2 Corinthiens"

    def test_russian_translation(self):
        assert get_localized_book_name("Genesis", "synodal") == "Бытие"
        assert get_localized_book_name("John", "synodal") == "Иоанн"
        assert get_localized_book_name("Psalms", "synodal") == "Псалтирь"
        assert get_localized_book_name("1 Corinthians", "synodal") == "1-е Коринфянам"
        assert get_localized_book_name("Revelation", "synodal") == "Откровение"

    def test_chinese_translation(self):
        assert get_localized_book_name("Genesis", "cuv") == "创世记"
        assert get_localized_book_name("John", "cuv") == "约翰福音"
        assert get_localized_book_name("Psalms", "cuv") == "诗篇"
        assert get_localized_book_name("Revelation", "cuv") == "啟示錄"

    def test_korean_translation(self):
        assert get_localized_book_name("Genesis", "krv") == "창세기"
        assert get_localized_book_name("John", "krv") == "요한복음"
        assert get_localized_book_name("Psalms", "krv") == "시편"
        assert get_localized_book_name("Lamentations", "krv") == "예레미야 애가"

    def test_hindi_translation(self):
        assert get_localized_book_name("Genesis", "hindi") == "उत्पत्ति"
        assert get_localized_book_name("John", "hindi") == "यूहन्ना"
        assert get_localized_book_name("Psalms", "hindi") == "भजन संहिता"
        assert get_localized_book_name("Revelation", "hindi") == "प्रकाशितवाक्य"

    def test_english_translations_return_english(self):
        assert get_localized_book_name("Genesis", "kjv") == "Genesis"
        assert get_localized_book_name("Genesis", "web") == "Genesis"

    def test_none_translation_returns_english(self):
        assert get_localized_book_name("Genesis", None) == "Genesis"

    def test_unknown_translation_returns_english(self):
        assert get_localized_book_name("Genesis", "unknown_translation") == "Genesis"

    def test_unknown_book_returns_original(self):
        assert get_localized_book_name("FakeBook", "ita1927") == "FakeBook"
        assert get_localized_book_name("FakeBook", "valera") == "FakeBook"


class TestNormalizeBookName:
    """Tests for normalize_book_name function."""

    def test_english_name_unchanged(self):
        assert normalize_book_name("Genesis") == "Genesis"
        assert normalize_book_name("John") == "John"

    def test_italian_to_english(self):
        assert normalize_book_name("Genesi") == "Genesis"
        assert normalize_book_name("Giovanni") == "John"
        assert normalize_book_name("Salmi") == "Psalms"

    def test_german_to_english(self):
        assert normalize_book_name("1. Mose") == "Genesis"
        assert normalize_book_name("Johannes") == "John"
        assert normalize_book_name("Psalmen") == "Psalms"

    def test_spanish_to_english(self):
        assert normalize_book_name("Génesis") == "Genesis"
        assert normalize_book_name("Juan") == "John"
        assert normalize_book_name("Salmos") == "Psalms"
        assert normalize_book_name("2 Corintios") == "2 Corinthians"

    def test_french_to_english(self):
        assert normalize_book_name("Genèse") == "Genesis"
        assert normalize_book_name("Jean") == "John"
        assert normalize_book_name("Psaumes") == "Psalms"
        assert normalize_book_name("2 Corinthiens") == "2 Corinthians"

    def test_russian_to_english(self):
        """normalize_book_name should handle Russian canonical and alias forms."""
        assert normalize_book_name("Бытие") == "Genesis"
        assert normalize_book_name("Иоанн") == "John"
        assert normalize_book_name("Псалтирь") == "Psalms"
        assert normalize_book_name("1-е Коринфянам") == "1 Corinthians"
        # Alias forms
        assert normalize_book_name("Иисус Навин") == "Joshua"
        assert normalize_book_name("1 Царств") == "1 Samuel"
        assert normalize_book_name("3 Царств") == "1 Kings"
        assert normalize_book_name("Деяния апостолов") == "Acts"
        assert normalize_book_name("Откровение") == "Revelation"

    def test_chinese_to_english(self):
        """normalize_book_name should handle Chinese canonical and alias forms."""
        assert normalize_book_name("创世记") == "Genesis"
        assert normalize_book_name("约翰福音") == "John"
        assert normalize_book_name("诗篇") == "Psalms"
        assert normalize_book_name("哥林多前书") == "1 Corinthians"
        assert normalize_book_name("啟示錄") == "Revelation"
        # BOM variant
        assert normalize_book_name("\ufeff创世记") == "Genesis"
        # Simplified alias
        assert normalize_book_name("启示录") == "Revelation"

    def test_korean_to_english(self):
        """normalize_book_name should handle Korean canonical and alias forms."""
        assert normalize_book_name("창세기") == "Genesis"
        assert normalize_book_name("요한복음") == "John"
        assert normalize_book_name("시편") == "Psalms"
        assert normalize_book_name("고린도전서") == "1 Corinthians"
        assert normalize_book_name("요한계시록") == "Revelation"
        # Alternate Lamentations form (no space)
        assert normalize_book_name("예레미야애가") == "Lamentations"

    def test_hindi_to_english(self):
        """normalize_book_name should handle Hindi canonical forms."""
        assert normalize_book_name("उत्पत्ति") == "Genesis"
        assert normalize_book_name("यूहन्ना") == "John"
        assert normalize_book_name("भजन संहिता") == "Psalms"
        assert normalize_book_name("प्रकाशितवाक्य") == "Revelation"

    def test_unknown_name_returned_as_is(self):
        assert normalize_book_name("UnknownBook") == "UnknownBook"

    def test_russian_genitive_to_english(self):
        """Russian genitive citation forms should normalize to English book names."""
        assert normalize_book_name("Иоанна") == "John"
        assert normalize_book_name("Матфея") == "Matthew"
        assert normalize_book_name("Луки") == "Luke"
        assert normalize_book_name("Псалтири") == "Psalms"
        assert normalize_book_name("Бытия") == "Genesis"

    def test_russian_genitive_additional(self):
        """Additional Russian genitive forms should normalize correctly."""
        assert normalize_book_name("Марка") == "Mark"
        assert normalize_book_name("Деяний") == "Acts"
        assert normalize_book_name("Откровения") == "Revelation"
        assert normalize_book_name("Притч") == "Proverbs"
        assert normalize_book_name("Екклесиаста") == "Ecclesiastes"
        assert normalize_book_name("Исаии") == "Isaiah"
        assert normalize_book_name("Иеремии") == "Jeremiah"
        assert normalize_book_name("Исхода") == "Exodus"
        assert normalize_book_name("Левита") == "Leviticus"
        assert normalize_book_name("Числ") == "Numbers"
        assert normalize_book_name("Второзакония") == "Deuteronomy"
        assert normalize_book_name("Руфи") == "Ruth"
        assert normalize_book_name("Иакова") == "James"


class TestRussianGenitiveMappings:
    """Tests that Russian genitive citation forms are in EXTRA_REVERSE_MAPPINGS."""

    # The 18 unambiguous genitive forms that were added to EXTRA_REVERSE_MAPPINGS
    GENITIVE_FORMS = {
        "Иоанна": "John",
        "Матфея": "Matthew",
        "Луки": "Luke",
        "Марка": "Mark",
        "Деяний": "Acts",
        "Откровения": "Revelation",
        "Бытия": "Genesis",
        "Псалтири": "Psalms",
        "Притч": "Proverbs",
        "Екклесиаста": "Ecclesiastes",
        "Исаии": "Isaiah",
        "Иеремии": "Jeremiah",
        "Исхода": "Exodus",
        "Левита": "Leviticus",
        "Числ": "Numbers",
        "Второзакония": "Deuteronomy",
        "Руфи": "Ruth",
        "Иакова": "James",
    }

    def test_genitive_forms_in_extra_reverse_mappings(self):
        """All Russian genitive forms should be present in EXTRA_REVERSE_MAPPINGS."""
        for genitive, english in self.GENITIVE_FORMS.items():
            assert (
                genitive in EXTRA_REVERSE_MAPPINGS
            ), f"Russian genitive '{genitive}' missing from EXTRA_REVERSE_MAPPINGS"
            assert EXTRA_REVERSE_MAPPINGS[genitive] == english

    def test_all_values_are_valid_english_book_names(self):
        """All values in the Russian genitive mapping should be valid English book names."""
        for genitive, english in self.GENITIVE_FORMS.items():
            assert (
                english in ENGLISH_TO_ITALIAN
            ), f"'{english}' (from Russian '{genitive}') is not a valid English book name"

    def test_genitive_forms_in_localized_to_english(self):
        """All Russian genitive forms should appear in the combined LOCALIZED_TO_ENGLISH map."""
        for genitive, english in self.GENITIVE_FORMS.items():
            assert (
                genitive in LOCALIZED_TO_ENGLISH
            ), f"Russian genitive '{genitive}' missing from LOCALIZED_TO_ENGLISH"
            assert LOCALIZED_TO_ENGLISH[genitive] == english

    def test_ambiguous_forms_not_present(self):
        """Ambiguous forms that map to multiple books should NOT be in the unambiguous set."""
        # "Петра" could be 1 Peter or 2 Peter — must not be in GENITIVE_FORMS
        assert "Петра" not in self.GENITIVE_FORMS
        # "Коринфянам" could be 1 or 2 Corinthians — must not be in GENITIVE_FORMS
        assert "Коринфянам" not in self.GENITIVE_FORMS
        # "Фессалоникийцам" could be 1 or 2 Thessalonians — must not be in GENITIVE_FORMS
        assert "Фессалоникийцам" not in self.GENITIVE_FORMS


# =============================================================================
# Rate Limiter Tests
# =============================================================================


class TestRateLimitEntry:
    """Tests for RateLimitEntry dataclass."""

    def test_default_values(self):
        entry = RateLimitEntry()
        assert entry.timestamps == []
        assert entry.total_requests == 0


class TestRateLimiter:
    """Tests for the RateLimiter class."""

    @pytest.mark.asyncio
    async def test_allows_first_request(self):
        limiter = RateLimiter(requests_per_minute=5)
        allowed, reason = await limiter.check_rate_limit("1.2.3.4")
        assert allowed is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_ip_rate_limit_exceeded(self):
        """Should block after exceeding IP rate limit."""
        limiter = RateLimiter(requests_per_minute=3)

        for _ in range(3):
            allowed, _ = await limiter.check_rate_limit("1.2.3.4")
            assert allowed is True

        allowed, reason = await limiter.check_rate_limit("1.2.3.4")
        assert allowed is False
        assert "IP rate limit" in reason

    @pytest.mark.asyncio
    async def test_different_ips_independent(self):
        """Different IPs should have independent limits."""
        limiter = RateLimiter(requests_per_minute=2)

        # Fill up first IP
        await limiter.check_rate_limit("1.1.1.1")
        await limiter.check_rate_limit("1.1.1.1")

        # Second IP should still work
        allowed, _ = await limiter.check_rate_limit("2.2.2.2")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_session_rate_limit(self):
        """Should block after exceeding session rate limit."""
        limiter = RateLimiter(
            requests_per_minute=100,
            session_requests_per_minute=2,
        )

        await limiter.check_rate_limit("1.2.3.4", session_id="session1")
        await limiter.check_rate_limit("1.2.3.4", session_id="session1")

        allowed, reason = await limiter.check_rate_limit("1.2.3.4", session_id="session1")
        assert allowed is False
        assert "Session rate limit" in reason

    @pytest.mark.asyncio
    async def test_session_lifetime_limit(self):
        """Should block after exceeding session lifetime limit."""
        limiter = RateLimiter(
            requests_per_minute=1000,
            session_requests_per_minute=1000,
            session_max_requests=3,
            window_seconds=1,
        )

        for _ in range(3):
            allowed, _ = await limiter.check_rate_limit("1.2.3.4", session_id="session1")
            assert allowed is True

        allowed, reason = await limiter.check_rate_limit("1.2.3.4", session_id="session1")
        assert allowed is False
        assert "Session lifetime limit" in reason

    @pytest.mark.asyncio
    async def test_window_expiry(self):
        """Requests should expire after the window."""
        limiter = RateLimiter(
            requests_per_minute=2,
            window_seconds=1,
        )

        await limiter.check_rate_limit("1.2.3.4")
        await limiter.check_rate_limit("1.2.3.4")

        # Should be blocked
        allowed, _ = await limiter.check_rate_limit("1.2.3.4")
        assert allowed is False

        # Wait for window to expire
        await asyncio.sleep(1.1)

        # Should be allowed again
        allowed, _ = await limiter.check_rate_limit("1.2.3.4")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_cleanup_runs_periodically(self):
        """Cleanup should remove expired entries."""
        limiter = RateLimiter(
            requests_per_minute=100,
            window_seconds=1,
            cleanup_interval_seconds=0,  # Cleanup on every request
        )

        # Add some entries
        await limiter.check_rate_limit("1.1.1.1")
        await limiter.check_rate_limit("2.2.2.2")

        assert len(limiter._ip_limits) == 2

        # Force entries to expire
        limiter._last_cleanup = 0
        for entry in limiter._ip_limits.values():
            entry.timestamps = [time.time() - 100]

        # Next request triggers cleanup
        await limiter.check_rate_limit("3.3.3.3")

        # Old entries should be cleaned
        assert "1.1.1.1" not in limiter._ip_limits
        assert "2.2.2.2" not in limiter._ip_limits

    @pytest.mark.asyncio
    async def test_cleanup_keeps_active_sessions(self):
        """Cleanup should keep sessions that hit lifetime limit."""
        limiter = RateLimiter(
            requests_per_minute=100,
            session_requests_per_minute=100,
            session_max_requests=2,
            window_seconds=1,
            cleanup_interval_seconds=0,
        )

        # Create session that hits lifetime limit
        await limiter.check_rate_limit("1.2.3.4", session_id="maxed-session")
        await limiter.check_rate_limit("1.2.3.4", session_id="maxed-session")

        # Force timestamps to expire but keep total_requests
        limiter._last_cleanup = 0
        entry = limiter._session_limits["maxed-session"]
        entry.timestamps = [time.time() - 100]

        # Trigger cleanup
        await limiter.check_rate_limit("5.5.5.5")

        # Maxed session should be kept (lifetime limit reached)
        assert "maxed-session" in limiter._session_limits

    def test_get_stats(self):
        """get_stats should return current statistics."""
        limiter = RateLimiter(
            requests_per_minute=20,
            session_requests_per_minute=10,
            session_max_requests=100,
            window_seconds=60,
        )

        stats = limiter.get_stats()
        assert stats["tracked_ips"] == 0
        assert stats["tracked_sessions"] == 0
        assert stats["config"]["requests_per_minute"] == 20
        assert stats["config"]["session_requests_per_minute"] == 10
        assert stats["config"]["session_max_requests"] == 100
        assert stats["config"]["window_seconds"] == 60
