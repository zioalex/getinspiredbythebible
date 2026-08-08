"""Tests for scripts/populate_verse_topics.py (BITB-044).

Pure/mocked tests only — target selection, CLI defaults, and the batching/
ON-CONFLICT shape of the insert helper. The script's actual database
behavior (idempotency, --replace, real KJV/Luther-1912 text tagging) was
verified by hand against a live Postgres instance during development; see
docs/HOW-TO-POPULATE-VERSE-TOPICS.md for how to reproduce that.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "populate_verse_topics.py"


@pytest.fixture(scope="module")
def populate_module():
    spec = importlib.util.spec_from_file_location("populate_verse_topics", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SUPPORTED = frozenset({"en", "it", "de", "es", "fr", "pt", "ar"})

TRANSLATIONS = [
    {"code": "kjv", "language_code": "en"},
    {"code": "web", "language_code": "en"},
    {"code": "luther1912", "language_code": "de"},
    {"code": "cuv", "language_code": "zh"},
    {"code": "hindi", "language_code": "hi"},
]


class TestSelectTargets:
    def test_default_selects_all_supported_languages(self, populate_module):
        targets = populate_module.select_targets(TRANSLATIONS, None, SUPPORTED)
        assert {t.code for t in targets} == {"kjv", "web", "luther1912"}

    def test_unsupported_languages_excluded(self, populate_module):
        targets = populate_module.select_targets(TRANSLATIONS, None, SUPPORTED)
        assert "cuv" not in {t.code for t in targets}
        assert "hindi" not in {t.code for t in targets}

    def test_explicit_translation_filter_honored(self, populate_module):
        targets = populate_module.select_targets(TRANSLATIONS, ["kjv"], SUPPORTED)
        assert [t.code for t in targets] == ["kjv"]

    def test_explicit_filter_still_excludes_unsupported_language(self, populate_module):
        """Requesting an unsupported-language translation by name must not
        override the language check — there's no vocabulary to tag it with."""
        targets = populate_module.select_targets(TRANSLATIONS, ["cuv"], SUPPORTED)
        assert targets == []

    def test_empty_translations_list(self, populate_module):
        assert populate_module.select_targets([], None, SUPPORTED) == []

    def test_language_code_carried_onto_target(self, populate_module):
        targets = populate_module.select_targets(TRANSLATIONS, ["luther1912"], SUPPORTED)
        assert targets[0].language_code == "de"


class TestArgParsing:
    def test_defaults(self, populate_module):
        args = populate_module._build_parser().parse_args([])
        assert args.dry_run is False
        assert args.replace is False
        assert args.verbose is False
        assert args.translation is None
        assert args.limit is None
        assert args.batch_size == populate_module.DEFAULT_BATCH_SIZE

    def test_translation_is_repeatable(self, populate_module):
        args = populate_module._build_parser().parse_args(
            ["--translation", "kjv", "--translation", "web"]
        )
        assert args.translation == ["kjv", "web"]

    def test_flags_and_options(self, populate_module):
        args = populate_module._build_parser().parse_args(
            ["--dry-run", "--replace", "-v", "--limit", "10", "--batch-size", "100"]
        )
        assert args.dry_run is True
        assert args.replace is True
        assert args.verbose is True
        assert args.limit == 10
        assert args.batch_size == 100


class _FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeConnection:
    def __init__(self):
        self.executemany_calls: list[tuple[str, list]] = []

    def transaction(self):
        return _FakeTransaction()

    async def executemany(self, query, args):
        self.executemany_calls.append((query, list(args)))


class TestInsertPairs:
    async def test_uses_on_conflict_do_nothing(self, populate_module):
        conn = _FakeConnection()
        await populate_module.insert_pairs(conn, [(1, 1), (2, 1)], batch_size=10)
        assert len(conn.executemany_calls) == 1
        query, _ = conn.executemany_calls[0]
        assert "ON CONFLICT" in query
        assert "DO NOTHING" in query

    async def test_batches_by_batch_size(self, populate_module):
        conn = _FakeConnection()
        pairs = [(i, 1) for i in range(5)]
        await populate_module.insert_pairs(conn, pairs, batch_size=2)
        assert len(conn.executemany_calls) == 3  # 2 + 2 + 1
        batch_sizes = [len(batch) for _, batch in conn.executemany_calls]
        assert batch_sizes == [2, 2, 1]

    async def test_all_pairs_are_written_exactly_once(self, populate_module):
        conn = _FakeConnection()
        pairs = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]
        await populate_module.insert_pairs(conn, pairs, batch_size=2)
        written = [row for _, batch in conn.executemany_calls for row in batch]
        assert sorted(written) == sorted(pairs)

    async def test_empty_pairs_makes_no_calls(self, populate_module):
        conn = _FakeConnection()
        await populate_module.insert_pairs(conn, [], batch_size=10)
        assert conn.executemany_calls == []
