"""BITB-059 AC#4 — shared cross-platform verse-reference regression corpus (Python side).

Loads ``tests/fixtures/verse_reference_corpus.json`` (shared with the web and Android test
suites — see ``tests/fixtures/README.md``) and asserts that ``parse_verse_reference`` produces
the expected book/chapter/verse_start/verse_end for every non-skipped case.

This is a test-only regression net: it does not change ``api/utils/verse_parser.py``.
"""

import json
from pathlib import Path

import pytest

from utils.verse_parser import parse_verse_reference

_CORPUS_PATH = Path(__file__).resolve().parents[2] / "tests/fixtures/verse_reference_corpus.json"

with open(_CORPUS_PATH, encoding="utf-8") as f:
    _CORPUS = json.load(f)

_TEST_CASES = _CORPUS["test_cases"]


@pytest.mark.parametrize("case", _TEST_CASES, ids=[c["id"] for c in _TEST_CASES])
def test_corpus_case(case):
    if "python" in case["skip"]:
        pytest.skip(case["skipReason"] or "skipped for python")

    result = parse_verse_reference(case["input"])

    if case.get("expectNone"):
        assert (
            result is None
        ), f"{case['id']!r}: expected no reference for {case['input']!r}, got {result}"
        return

    expected = case["expected"]
    assert (
        result is not None
    ), f"{case['id']!r}: expected a reference for {case['input']!r}, got None"
    assert (
        result.book.lower() == expected["book"]
    ), f"{case['id']!r}: book mismatch — expected {expected['book']!r}, got {result.book!r}"
    assert (
        result.chapter == expected["chapter"]
    ), f"{case['id']!r}: chapter mismatch — expected {expected['chapter']!r}, got {result.chapter!r}"
    assert result.verse_start == expected["verseStart"], (
        f"{case['id']!r}: verse_start mismatch — "
        f"expected {expected['verseStart']!r}, got {result.verse_start!r}"
    )
    if expected["verseEnd"] is not None:
        assert result.verse_end == expected["verseEnd"], (
            f"{case['id']!r}: verse_end mismatch — "
            f"expected {expected['verseEnd']!r}, got {result.verse_end!r}"
        )
    else:
        assert (
            not result.verse_end
        ), f"{case['id']!r}: expected no verse range, got verse_end={result.verse_end!r}"
