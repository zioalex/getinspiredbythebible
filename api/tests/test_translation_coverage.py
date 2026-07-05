"""Tests for translation data-coverage diagnostics (BITB-054).

Covers:
- scripture/coverage.py: find_unusable_languages, check_translation_coverage
- main.py: _check_translation_coverage_at_startup (the extracted startup guard)
- routes/admin.py: GET /api/v1/admin/translation-coverage
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from main import app
from scripture import get_db_session
from scripture.coverage import UnusableLanguage, check_translation_coverage, find_unusable_languages
from utils.language import SUPPORTED_LANGUAGES

client = TestClient(app)

ENDPOINT = "/api/v1/admin/translation-coverage"
SECRET = "probe-secret"  # pragma: allowlist secret
HEADERS = {"X-Monitor-Probe-Secret": SECRET}


# ==================== find_unusable_languages (pure function) ====================


class TestFindUnusableLanguages:
    def test_fully_loaded_translation_is_usable(self):
        coverage = [{"translation": "kjv", "total_verses": 31102, "verses_with_embeddings": 31102}]
        unusable = find_unusable_languages(coverage)
        assert not any(u.translation == "kjv" for u in unusable)

    def test_zero_verses_flagged_no_verses(self):
        """A translation present with 0 rows, or entirely absent from coverage,
        must be flagged 'no_verses'."""
        coverage = [{"translation": "ita1927", "total_verses": 0, "verses_with_embeddings": 0}]
        unusable = find_unusable_languages(coverage)
        it = next(u for u in unusable if u.language == "it")
        assert it.problem == "no_verses"
        assert it.translation == "ita1927"

    def test_missing_translation_entirely_flagged_no_verses(self):
        """A translation that never appears in coverage (table has zero rows for
        it) must be treated the same as a translation with 0 verses."""
        coverage = [
            row
            for row in _full_coverage()
            if row["translation"] != "ita1927"  # simulate Italian never loaded
        ]
        unusable = find_unusable_languages(coverage)
        it = next(u for u in unusable if u.language == "it")
        assert it.problem == "no_verses"

    def test_zero_embeddings_flagged_no_embeddings(self):
        coverage = _full_coverage()
        # Zero out embeddings for German only.
        for row in coverage:
            if row["translation"] == "schlachter":
                row["verses_with_embeddings"] = 0
        unusable = find_unusable_languages(coverage)
        de = next(u for u in unusable if u.language == "de")
        assert de.problem == "no_embeddings"
        assert de.translation == "schlachter"

    def test_all_languages_usable_returns_empty(self):
        unusable = find_unusable_languages(_full_coverage())
        assert unusable == []

    def test_only_supported_languages_considered(self):
        """A translation-less/unmapped coverage row should not create a phantom
        unusable-language entry; only SUPPORTED_LANGUAGES are checked."""
        coverage = _full_coverage() + [
            {"translation": "unmapped_code", "total_verses": 100, "verses_with_embeddings": 100}
        ]
        unusable = find_unusable_languages(coverage)
        assert unusable == []


def _full_coverage() -> list[dict]:
    """Coverage rows where every supported language's translation is fully loaded."""
    from utils.language import LANGUAGE_TO_TRANSLATION

    return [
        {"translation": translation, "total_verses": 1000, "verses_with_embeddings": 1000}
        for translation in LANGUAGE_TO_TRANSLATION.values()
    ]


# ==================== check_translation_coverage (DB-backed) ====================


class TestCheckTranslationCoverage:
    @pytest.mark.asyncio
    async def test_combines_repository_and_classification(self):
        session = AsyncMock()
        mock_result = MagicMock()
        # "web" (not "kjv") is English's default translation per LANGUAGE_TO_TRANSLATION.
        mock_result.all.return_value = [("web", 31102, 31102)]
        session.execute = AsyncMock(return_value=mock_result)

        coverage, unusable = await check_translation_coverage(session)

        assert coverage == [
            {"translation": "web", "total_verses": 31102, "verses_with_embeddings": 31102}
        ]
        # Every supported language other than English (web) has no data at all.
        assert len(unusable) == len(SUPPORTED_LANGUAGES) - 1
        assert all(isinstance(u, UnusableLanguage) for u in unusable)
        assert not any(u.language == "en" for u in unusable)


# ==================== Admin diagnostic endpoint ====================


def setup_module():
    app.dependency_overrides[get_db_session] = lambda: MagicMock()


def teardown_module():
    app.dependency_overrides.pop(get_db_session, None)


class TestTranslationCoverageEndpoint:
    def test_missing_header_returns_401(self):
        with patch.object(settings, "monitor_probe_secret", SECRET):
            resp = client.get(ENDPOINT)
        assert resp.status_code == 401

    def test_wrong_header_returns_401(self):
        with patch.object(settings, "monitor_probe_secret", SECRET):
            resp = client.get(ENDPOINT, headers={"X-Monitor-Probe-Secret": "nope"})
        assert resp.status_code == 401

    def test_unset_secret_fails_closed(self):
        with patch.object(settings, "monitor_probe_secret", None):
            resp = client.get(ENDPOINT, headers=HEADERS)
        assert resp.status_code == 401

    def test_authorized_request_returns_coverage_and_unusable_languages(self):
        coverage = [{"translation": "kjv", "total_verses": 31102, "verses_with_embeddings": 31102}]
        unusable = [UnusableLanguage(language="it", translation="ita1927", problem="no_verses")]
        with (
            patch.object(settings, "monitor_probe_secret", SECRET),
            patch(
                "routes.admin.check_translation_coverage",
                AsyncMock(return_value=(coverage, unusable)),
            ),
        ):
            resp = client.get(ENDPOINT, headers=HEADERS)

        assert resp.status_code == 200
        body = resp.json()
        assert body["coverage"] == coverage
        assert body["unusable_languages"] == [
            {"language": "it", "translation": "ita1927", "problem": "no_verses"}
        ]

    def test_flags_empty_language(self):
        """An empty/missing language must show up in unusable_languages."""
        coverage = [{"translation": "web", "total_verses": 31102, "verses_with_embeddings": 31102}]
        unusable = find_unusable_languages(coverage)
        with (
            patch.object(settings, "monitor_probe_secret", SECRET),
            patch(
                "routes.admin.check_translation_coverage",
                AsyncMock(return_value=(coverage, unusable)),
            ),
        ):
            resp = client.get(ENDPOINT, headers=HEADERS)

        body = resp.json()
        languages_flagged = {u["language"] for u in body["unusable_languages"]}
        assert "it" in languages_flagged
        assert "en" not in languages_flagged


# ==================== Startup guard ====================


class TestStartupCoverageGuard:
    """The startup guard (main.py::_check_translation_coverage_at_startup) is a thin
    wrapper around check_translation_coverage — exercised here without booting the
    full FastAPI lifespan."""

    @pytest.mark.asyncio
    async def test_logs_warning_and_increments_metric_for_unusable_language(self):
        from main import _check_translation_coverage_at_startup

        unusable = [UnusableLanguage(language="it", translation="ita1927", problem="no_verses")]

        @asynccontextmanager
        async def _fake_session_factory():
            yield MagicMock()

        with (
            patch(
                "main.check_translation_coverage",
                AsyncMock(return_value=([], unusable)),
            ),
            patch("scripture.database.async_session_factory", _fake_session_factory),
            patch("main.translation_data_missing_counter") as mock_counter,
        ):
            await _check_translation_coverage_at_startup()

        mock_counter.add.assert_called_once_with(
            1, {"language": "it", "translation": "ita1927", "problem": "no_verses"}
        )

    @pytest.mark.asyncio
    async def test_never_raises_on_failure(self):
        """Best-effort: a failure in the coverage check must never block startup."""
        from main import _check_translation_coverage_at_startup

        with patch("main.check_translation_coverage", AsyncMock(side_effect=Exception("db down"))):
            # Must not raise.
            await _check_translation_coverage_at_startup()
