"""Golden-set loader for the retrieval-evaluation harness (BITB-051).

Reads ``data/retrieval_golden_set.json``, validates every case through the
``GoldenCase`` Pydantic model (which rejects unparseable refs), and exposes
thin filter helpers for language, category, and tag slicing.

No DB or embedding access — this module is pure I/O and validation so it can
run in CI without any secrets.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import GoldenCase

_DATA_FILE = Path(__file__).parent / "data" / "retrieval_golden_set.json"

_SUPPORTED_LANGUAGES = frozenset({"en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"})


def load_golden_set(
    path: Path | None = None,
    *,
    language: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
) -> list[GoldenCase]:
    """Load and validate the retrieval golden set.

    Args:
        path: Override the default JSON file location (useful in tests).
        language: If given, return only cases for that ISO-639-1 language code.
        category: If given, return only cases with this category.
        tags: If given, return only cases that carry ALL of the listed tags.

    Returns:
        A list of validated ``GoldenCase`` objects.

    Raises:
        FileNotFoundError: If the golden-set JSON file is missing.
        ValueError: If any case fails Pydantic validation (e.g. bad ref).
    """
    src = path or _DATA_FILE
    raw: list[dict] = json.loads(src.read_text(encoding="utf-8"))
    cases = [GoldenCase.model_validate(item) for item in raw]

    if language is not None:
        cases = [c for c in cases if c.language == language]
    if category is not None:
        cases = [c for c in cases if c.category == category]
    if tags is not None:
        tag_set = set(tags)
        cases = [c for c in cases if tag_set.issubset(set(c.tags))]

    return cases


def supported_languages() -> frozenset[str]:
    """Return the set of language codes the app officially supports."""
    return _SUPPORTED_LANGUAGES


def coverage_summary(cases: list[GoldenCase]) -> dict[str, int]:
    """Return a {language: count} dict for the given case list."""
    summary: dict[str, int] = {}
    for case in cases:
        summary[case.language] = summary.get(case.language, 0) + 1
    return summary
