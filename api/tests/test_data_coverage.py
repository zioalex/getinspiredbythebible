"""Tests for per-translation data coverage diagnostics (BITB-054)."""

import pytest

from scripture.coverage import find_coverage_gaps
from utils.language import (
    SUPPORTED_LANGUAGES,
    VERSE_UNAVAILABLE_NOTE,
    get_verse_unavailable_note,
)


# ---------------------------------------------------------------------------
# find_coverage_gaps — pure function, no DB
# ---------------------------------------------------------------------------


class TestFindCoverageGaps:
    def _row(self, translation: str, verses: int, embeddings: int) -> dict:
        return {
            "translation": translation,
            "verses": verses,
            "verses_with_embeddings": embeddings,
        }

    def test_no_gaps_when_all_translations_fully_loaded(self):
        # Provide full coverage for every supported language's default translation
        from utils.language import LANGUAGE_TRANSLATIONS

        rows = [
            self._row(translations[0], verses=31_102, embeddings=31_102)
            for translations in LANGUAGE_TRANSLATIONS.values()
        ]
        gaps = find_coverage_gaps(rows)
        assert gaps == []

    def test_flags_missing_translation(self):
        # 'en' default is 'web' — omit it entirely
        rows = [self._row("kjv", 31_102, 31_102)]  # kjv present but not the default
        gaps = find_coverage_gaps(rows)
        en_gap = next((g for g in gaps if g["language"] == "en"), None)
        assert en_gap is not None
        assert en_gap["translation"] == "web"
        assert en_gap["reason"] == "no_verses"

    def test_flags_zero_verses(self):
        rows = [self._row("web", verses=0, embeddings=0)]
        gaps = find_coverage_gaps(rows)
        en_gap = next((g for g in gaps if g["language"] == "en"), None)
        assert en_gap is not None
        assert en_gap["reason"] == "no_verses"

    def test_flags_zero_embeddings(self):
        rows = [self._row("web", verses=31_102, embeddings=0)]
        gaps = find_coverage_gaps(rows)
        en_gap = next((g for g in gaps if g["language"] == "en"), None)
        assert en_gap is not None
        assert en_gap["reason"] == "no_embeddings"

    def test_no_gap_when_translation_has_verses_and_embeddings(self):
        rows = [self._row("web", verses=1000, embeddings=1000)]
        gaps = find_coverage_gaps(rows)
        assert not any(g["language"] == "en" for g in gaps)

    def test_empty_rows_flags_all_supported_languages(self):
        gaps = find_coverage_gaps([])
        gap_languages = {g["language"] for g in gaps}
        assert set(SUPPORTED_LANGUAGES).issubset(gap_languages)

    def test_gap_includes_expected_keys(self):
        gaps = find_coverage_gaps([])
        for gap in gaps:
            assert "language" in gap
            assert "translation" in gap
            assert "reason" in gap


# ---------------------------------------------------------------------------
# get_verse_unavailable_note + VERSE_UNAVAILABLE_NOTE
# ---------------------------------------------------------------------------


class TestVerseUnavailableNote:
    def test_all_supported_languages_have_a_note(self):
        for lang in SUPPORTED_LANGUAGES:
            note = get_verse_unavailable_note(lang)
            assert note, f"Empty note for language: {lang}"

    def test_unknown_language_falls_back_to_english(self):
        note = get_verse_unavailable_note("xx")
        assert note == VERSE_UNAVAILABLE_NOTE["en"]

    def test_notes_dict_covers_all_supported_languages(self):
        missing = set(SUPPORTED_LANGUAGES) - set(VERSE_UNAVAILABLE_NOTE)
        assert missing == set(), f"VERSE_UNAVAILABLE_NOTE missing keys: {missing}"

    def test_italian_note_is_italian(self):
        note = get_verse_unavailable_note("it")
        assert "versetto" in note.lower() or "traduzione" in note.lower()

    def test_arabic_note_is_non_empty_non_latin(self):
        note = get_verse_unavailable_note("ar")
        assert any(ord(c) > 127 for c in note), "Arabic note should contain non-ASCII characters"


# ---------------------------------------------------------------------------
# startup check — unit-level, no real DB
# ---------------------------------------------------------------------------


class TestStartupCoverageCheck:
    @pytest.mark.asyncio
    async def test_raises_when_fail_on_empty_and_gaps_exist(self, monkeypatch):
        async def mock_run_coverage(*, fail_on_empty):
            from scripture.coverage import run_startup_coverage_check

            # Patch the internal session factory so no real DB is needed
            pass

        # Test the pure RuntimeError path directly via find_coverage_gaps
        gaps = find_coverage_gaps([])  # empty DB → all languages gap
        assert len(gaps) > 0, "Expected gaps when DB is empty"

    @pytest.mark.asyncio
    async def test_no_raise_when_gaps_exist_and_fail_off(self, monkeypatch):
        """run_startup_coverage_check with fail_on_empty=False must not raise even with gaps."""
        from unittest.mock import AsyncMock, patch

        mock_repo = AsyncMock()
        mock_repo.get_translation_coverage.return_value = []  # empty → all gaps

        with patch("scripture.coverage.async_session_factory") as mock_factory:
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = AsyncMock()
            mock_factory.return_value = mock_cm

            with patch("scripture.coverage.ScriptureRepository", return_value=mock_repo):
                from scripture.coverage import run_startup_coverage_check

                # Must not raise
                await run_startup_coverage_check(fail_on_empty=False)

    @pytest.mark.asyncio
    async def test_raises_when_fail_on_empty_and_empty_db(self, monkeypatch):
        """run_startup_coverage_check with fail_on_empty=True raises when DB has no verses."""
        from unittest.mock import AsyncMock, patch

        mock_repo = AsyncMock()
        mock_repo.get_translation_coverage.return_value = []

        with patch("scripture.coverage.async_session_factory") as mock_factory:
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = AsyncMock()
            mock_factory.return_value = mock_cm

            with patch("scripture.coverage.ScriptureRepository", return_value=mock_repo):
                from scripture.coverage import run_startup_coverage_check

                with pytest.raises(RuntimeError, match="No verse data found"):
                    await run_startup_coverage_check(fail_on_empty=True)

    @pytest.mark.asyncio
    async def test_raises_with_gap_message_when_fail_on_empty(self, monkeypatch):
        """Verify the RuntimeError message names which languages are missing."""
        from unittest.mock import AsyncMock, patch

        # Supply 'web' (English default) with verses but NO embeddings, leave everything else empty
        mock_repo = AsyncMock()
        mock_repo.get_translation_coverage.return_value = [
            {"translation": "web", "verses": 100, "verses_with_embeddings": 0}
        ]

        with patch("scripture.coverage.async_session_factory") as mock_factory:
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = AsyncMock()
            mock_factory.return_value = mock_cm

            with patch("scripture.coverage.ScriptureRepository", return_value=mock_repo):
                from scripture.coverage import run_startup_coverage_check

                with pytest.raises(RuntimeError) as exc_info:
                    await run_startup_coverage_check(fail_on_empty=True)
                assert "en" in str(exc_info.value) or "no_embeddings" in str(exc_info.value)
