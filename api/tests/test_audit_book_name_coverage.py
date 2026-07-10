"""Tests for scripts/audit_book_name_coverage.py (BITB-052 coverage audit)."""

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "audit_book_name_coverage.py"


@pytest.fixture(scope="module")
def audit_module():
    spec = importlib.util.spec_from_file_location("audit_book_name_coverage", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def registry(audit_module):
    return audit_module._load_registry()


class TestGenerateReport:
    def test_includes_all_non_english_languages(self, audit_module, registry):
        report = audit_module.generate_report(registry)
        for language in [
            "Italian",
            "German",
            "Spanish",
            "French",
            "Portuguese",
            "Arabic",
            "Russian",
            "Chinese",
            "Korean",
            "Hindi",
        ]:
            assert f"### {language}" in report

    def test_every_book_appears_per_language(self, audit_module, registry):
        report = audit_module.generate_report(registry)
        books = list(registry.ENGLISH_TO_ITALIAN.keys())
        assert len(books) == 66
        for book in books:
            # Each book must appear at least once per language section as a table row.
            assert report.count(f"| {book} |") == 11  # 11 languages incl. English

    def test_summary_table_present(self, audit_module, registry):
        report = audit_module.generate_report(registry)
        assert "## Summary" in report
        assert "Books with ≥1 alias" in report


class TestFoldCollisionCheck:
    def test_no_collisions_in_current_registry(self, audit_module, registry):
        assert audit_module.check_fold_collisions(registry) == []

    def test_detects_synthetic_collision(self, audit_module):
        """Sanity check the detector itself: two different English books
        whose aliases fold to the same key must be flagged."""

        class FakeRegistry:
            ENGLISH_TO_ITALIAN = {"Genesis": "Genesi", "Exodus": "Esodo"}
            ENGLISH_TO_GERMAN = {"Genesis": "Genesis", "Exodus": "Exodus"}
            ENGLISH_TO_SPANISH = {}
            ENGLISH_TO_FRENCH = {}
            ENGLISH_TO_PORTUGUESE = {}
            ENGLISH_TO_ARABIC = {}
            ENGLISH_TO_RUSSIAN = {}
            ENGLISH_TO_CHINESE = {}
            ENGLISH_TO_KOREAN = {}
            ENGLISH_TO_HINDI = {}
            ITALIAN_ALIASES = {}
            GERMAN_ALIASES = {"gen": "Genesis", "GEN": "Exodus"}  # deliberate collision
            FRENCH_ALIASES = {}
            ARABIC_CITATION_FORMS = {}
            RUSSIAN_CITATION_FORMS = {}
            RUSSIAN_ALIASES = {}
            CHINESE_ALIASES = {}
            KOREAN_ALIASES = {}
            HINDI_ALIASES = {}
            ENGLISH_ALIASES = {}

        collisions = audit_module.check_fold_collisions(FakeRegistry())
        assert len(collisions) == 1
        assert "gen" in collisions[0] or "GEN" in collisions[0].lower()
