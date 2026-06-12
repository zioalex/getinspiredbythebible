"""BITB-043: Search/retrieval golden-set evaluation harness.

Mock-based tests validate the scorer itself (no DB, always run in CI).
The @pytest.mark.slow integration test is opt-in via RUN_DB_TESTS=1 and
skipped in CI by default.
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "search_golden_set.json"
RUN_DB = os.getenv("RUN_DB_TESTS") == "1"


# ---------- helpers ----------


def _load_golden():
    return json.loads(FIXTURE.read_text())


def _ref_key(book: str, chapter: int, verse: int) -> tuple:
    return (book.lower(), int(chapter), int(verse))


def _verse_result_key(vr) -> tuple:
    return (vr.book.lower(), int(vr.chapter), int(vr.verse))


# ---------- pure scoring functions ----------


def precision_at_k(ranked_keys: list, relevant_keys: set, k: int) -> float:
    top = ranked_keys[:k]
    if not top:
        return 0.0
    return sum(1 for r in top if r in relevant_keys) / len(top)


def recall_at_k(ranked_keys: list, relevant_keys: set, k: int) -> float:
    if not relevant_keys:
        return 0.0
    hits = len(set(ranked_keys[:k]) & relevant_keys)
    return hits / len(relevant_keys)


def mrr(ranked_keys: list, relevant_keys: set) -> float:
    for i, key in enumerate(ranked_keys, start=1):
        if key in relevant_keys:
            return 1.0 / i
    return 0.0


# ---------- unit tests: scorer logic (no DB) ----------


class TestScorerLogic:
    """Verify precision/recall/MRR functions with hand-built ranked lists."""

    def _mk_ranked(self, *tuples):
        return [_ref_key(*t) for t in tuples]

    def test_perfect_precision_at_1(self):
        ranked = self._mk_ranked(("Mark", 4, 39))
        relevant = {_ref_key("Mark", 4, 39)}
        assert precision_at_k(ranked, relevant, 1) == 1.0

    def test_zero_precision_when_no_hit(self):
        ranked = self._mk_ranked(("John", 1, 1), ("John", 1, 2))
        relevant = {_ref_key("Mark", 4, 39)}
        assert precision_at_k(ranked, relevant, 5) == 0.0

    def test_partial_precision(self):
        ranked = self._mk_ranked(("John", 3, 16), ("Mark", 4, 39), ("Psalms", 23, 1))
        relevant = {_ref_key("John", 3, 16), _ref_key("Psalms", 23, 1)}
        # top-3: 2 hits out of 3
        assert precision_at_k(ranked, relevant, 3) == pytest.approx(2 / 3)

    def test_recall_all_relevant_in_top_k(self):
        ranked = self._mk_ranked(("Mark", 4, 39), ("Psalms", 23, 1))
        relevant = {_ref_key("Mark", 4, 39), _ref_key("Psalms", 23, 1)}
        assert recall_at_k(ranked, relevant, 5) == 1.0

    def test_recall_partial(self):
        ranked = self._mk_ranked(("Mark", 4, 39))
        relevant = {_ref_key("Mark", 4, 39), _ref_key("Psalms", 23, 1)}
        assert recall_at_k(ranked, relevant, 5) == pytest.approx(0.5)

    def test_recall_zero_when_no_relevant(self):
        ranked = self._mk_ranked(("Mark", 4, 39))
        assert recall_at_k(ranked, set(), 5) == 0.0

    def test_mrr_first_hit_at_rank_1(self):
        ranked = self._mk_ranked(("Mark", 4, 39), ("John", 3, 16))
        relevant = {_ref_key("Mark", 4, 39)}
        assert mrr(ranked, relevant) == 1.0

    def test_mrr_first_hit_at_rank_2(self):
        ranked = self._mk_ranked(("John", 3, 16), ("Mark", 4, 39))
        relevant = {_ref_key("Mark", 4, 39)}
        assert mrr(ranked, relevant) == pytest.approx(0.5)

    def test_mrr_no_hit(self):
        ranked = self._mk_ranked(("John", 1, 1))
        relevant = {_ref_key("Mark", 4, 39)}
        assert mrr(ranked, relevant) == 0.0

    def test_empty_ranked_list(self):
        relevant = {_ref_key("Mark", 4, 39)}
        assert precision_at_k([], relevant, 5) == 0.0
        assert recall_at_k([], relevant, 5) == 0.0
        assert mrr([], relevant) == 0.0


# ---------- fixture integrity tests ----------


class TestGoldenSetFixture:
    """Verify the fixture file is well-formed and covers required cases."""

    def test_fixture_loads(self):
        data = _load_golden()
        assert "cases" in data
        assert len(data["cases"]) >= 10

    def test_all_cases_have_unique_ids(self):
        cases = _load_golden()["cases"]
        ids = [c["id"] for c in cases]
        assert len(ids) == len(set(ids)), "Duplicate case IDs found"

    def test_all_cases_have_relevant_references(self):
        for case in _load_golden()["cases"]:
            assert case.get("relevant_references"), (
                f"Case '{case['id']}' missing relevant_references"
            )
            for ref in case["relevant_references"]:
                assert {"book", "chapter", "verse"} <= set(ref.keys()), (
                    f"Case '{case['id']}' ref missing required fields: {ref}"
                )

    def test_regression_case_present(self):
        ids = {c["id"] for c in _load_golden()["cases"]}
        assert "peace-be-still-en" in ids, "Regression case 'peace-be-still-en' must be present"

    def test_incident_case_present(self):
        ids = {c["id"] for c in _load_golden()["cases"]}
        assert "italian-frustration-incident" in ids, "Incident case must be present"

    def test_multilingual_coverage(self):
        languages = {c["language"] for c in _load_golden()["cases"]}
        assert len(languages) >= 4, (
            f"Expected >= 4 languages, got {languages}"
        )
        for lang in ("en", "it", "de", "es"):
            assert lang in languages, f"Language '{lang}' missing from golden set"

    def test_incident_case_has_irrelevant_guard(self):
        cases = {c["id"]: c for c in _load_golden()["cases"]}
        incident = cases["italian-frustration-incident"]
        assert incident.get("irrelevant_references"), (
            "Incident case must list irrelevant references for regression guard"
        )
        # Job 21:27 must be guarded
        job_ref = _ref_key("Job", 21, 27)
        irrelevant_keys = {
            _ref_key(r["book"], r["chapter"], r["verse"])
            for r in incident["irrelevant_references"]
        }
        assert job_ref in irrelevant_keys, "Job 21:27 must be in irrelevant_references"


# ---------- mock plumbing test ----------


class TestScorerWithMockResults:
    """Verify the scorer integrates correctly with VerseResult-shaped objects."""

    def _make_verse_result(self, book, chapter, verse, similarity=0.9):
        vr = MagicMock()
        vr.book = book
        vr.chapter = chapter
        vr.verse = verse
        vr.similarity = similarity
        return vr

    def test_scorer_with_verse_result_objects(self):
        """Ranked list of VerseResult-shaped mocks feeds correctly into scorer."""
        results = [
            self._make_verse_result("Mark", 4, 39, 0.95),
            self._make_verse_result("John", 3, 16, 0.80),
            self._make_verse_result("Psalms", 23, 1, 0.72),
        ]
        ranked_keys = [_verse_result_key(v) for v in results]
        relevant = {_ref_key("Mark", 4, 39)}

        assert precision_at_k(ranked_keys, relevant, 1) == 1.0
        assert mrr(ranked_keys, relevant) == 1.0
        assert recall_at_k(ranked_keys, relevant, 3) == 1.0

    def test_incident_guard_with_mock_results(self):
        """Job 21:27 in top results triggers zero MRR for relevant references."""
        # Simulate the bad-search scenario: Job 21:27 ranked first
        results = [
            self._make_verse_result("Job", 21, 27, 0.95),   # irrelevant (bad)
            self._make_verse_result("James", 1, 19, 0.70),  # relevant
        ]
        ranked_keys = [_verse_result_key(v) for v in results]
        relevant = {
            _ref_key("James", 1, 19),
            _ref_key("Proverbs", 14, 29),
            _ref_key("Ephesians", 4, 26),
        }
        irrelevant = {_ref_key("Job", 21, 27)}

        # MRR is poor because first hit is at rank 2
        assert mrr(ranked_keys, relevant) == pytest.approx(0.5)
        # Job appears in top-1 (incident guard)
        assert ranked_keys[0] in irrelevant


# ---------- real-DB integration tests (opt-in, CI skipped) ----------


@pytest.mark.slow
@pytest.mark.skipif(not RUN_DB, reason="DB integration: set RUN_DB_TESTS=1 to run")
@pytest.mark.asyncio
async def test_hybrid_search_regression_case():
    """
    Verify hybrid search surfaces Mark 4:39 in top-3 for 'peace be still' (KJV).
    Opt-in: set RUN_DB_TESTS=1.  Requires DATABASE_URL and EMBEDDING_PROVIDER
    environment variables pointing at a seeded database.
    """
    import os

    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    db_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from embeddings.provider import create_embedding_provider

    from config import settings as app_settings
    from scripture.search import ScriptureSearchService

    embedding_provider = create_embedding_provider(app_settings)

    async with async_session() as session:
        search_service = ScriptureSearchService(session, embedding_provider)
        results = await search_service.search_hybrid(
            query="peace be still",
            max_verses=10,
            max_passages=0,
            similarity_threshold=0.3,
            translation="kjv",
            semantic_weight=app_settings.hybrid_search_semantic_weight,
            keyword_weight=app_settings.hybrid_search_keyword_weight,
        )

    ranked_keys = [_verse_result_key(v) for v in results.verses]
    relevant = {_ref_key("Mark", 4, 39)}
    hit_rank = next((i + 1 for i, k in enumerate(ranked_keys) if k in relevant), None)
    assert hit_rank is not None, (
        f"Mark 4:39 not found in results. Top-10: "
        f"{[f'{v.book} {v.chapter}:{v.verse}' for v in results.verses[:10]]}"
    )
    assert hit_rank <= 3, (
        f"Mark 4:39 at rank {hit_rank}, expected <= 3. "
        f"Top-3: {[f'{v.book} {v.chapter}:{v.verse}' for v in results.verses[:3]]}"
    )
