"""Dataset-level tests for the retrieval-evaluation golden set (BITB-051 P2).

These tests validate the *data* in ``retrieval_golden_set.json`` — coverage,
ID uniqueness, parse-ability of every reference — and run in the blocking
``backend-tests`` CI job with no DB or embedding access needed.
"""

from __future__ import annotations

from collections import Counter

import pytest

from search_eval.loader import load_golden_set, supported_languages
from search_eval.models import GoldenCase
from search_eval.normalize import normalize_reference

SUPPORTED_LANGUAGES = sorted(supported_languages())
MIN_CASES = 55
MIN_PER_LANGUAGE = 5


@pytest.fixture(scope="module")
def golden_cases() -> list[GoldenCase]:
    return load_golden_set()


def test_minimum_case_count(golden_cases: list[GoldenCase]) -> None:
    assert (
        len(golden_cases) >= MIN_CASES
    ), f"golden set must contain ≥{MIN_CASES} cases, found {len(golden_cases)}"


def test_ids_are_unique(golden_cases: list[GoldenCase]) -> None:
    counts = Counter(c.id for c in golden_cases)
    duplicates = {id_: n for id_, n in counts.items() if n > 1}
    assert not duplicates, f"duplicate IDs: {duplicates}"


def test_all_supported_languages_covered(golden_cases: list[GoldenCase]) -> None:
    present = {c.language for c in golden_cases}
    missing = set(SUPPORTED_LANGUAGES) - present
    assert not missing, f"no golden cases for languages: {sorted(missing)}"


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_minimum_cases_per_language(golden_cases: list[GoldenCase], language: str) -> None:
    count = sum(1 for c in golden_cases if c.language == language)
    assert (
        count >= MIN_PER_LANGUAGE
    ), f"language '{language}' has only {count} cases (need ≥{MIN_PER_LANGUAGE})"


def test_every_case_has_relevant_refs(golden_cases: list[GoldenCase]) -> None:
    bad = [c.id for c in golden_cases if not c.relevant_refs]
    assert not bad, f"cases with no relevant_refs: {bad}"


def test_all_relevant_refs_parse(golden_cases: list[GoldenCase]) -> None:
    bad: list[tuple[str, str]] = []
    for case in golden_cases:
        for ref in case.relevant_refs:
            if normalize_reference(ref) is None:
                bad.append((case.id, ref))
    assert not bad, f"unparseable relevant_refs: {bad}"


def test_all_irrelevant_refs_parse(golden_cases: list[GoldenCase]) -> None:
    bad: list[tuple[str, str]] = []
    for case in golden_cases:
        for ref in case.irrelevant_refs:
            if normalize_reference(ref) is None:
                bad.append((case.id, ref))
    assert not bad, f"unparseable irrelevant_refs: {bad}"


def test_incident_guard_present(golden_cases: list[GoldenCase]) -> None:
    """The Italian frustration query must carry Job 21:27 as an irrelevant guard."""
    it_frustration = next(
        (c for c in golden_cases if c.id == "it-001"),
        None,
    )
    assert it_frustration is not None, "case 'it-001' missing from golden set"
    assert (
        "Job 21:27" in it_frustration.irrelevant_refs
    ), "it-001 must list Job 21:27 as an irrelevant_ref (incident guard)"


def test_loader_language_filter(golden_cases: list[GoldenCase]) -> None:
    en_cases = load_golden_set(language="en")
    assert all(c.language == "en" for c in en_cases)
    assert len(en_cases) >= MIN_PER_LANGUAGE


def test_loader_category_filter() -> None:
    anxiety_cases = load_golden_set(category="anxiety")
    assert all(c.category == "anxiety" for c in anxiety_cases)
    assert len(anxiety_cases) >= 1


def test_loader_tag_filter() -> None:
    tagged = load_golden_set(tags=["trust"])
    assert all("trust" in c.tags for c in tagged)
    assert len(tagged) >= 1
