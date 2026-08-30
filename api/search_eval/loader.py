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

from pydantic import ValidationError

from .models import GoldenCase

_DATA_FILE = Path(__file__).parent / "data" / "retrieval_golden_set.json"

_SUPPORTED_LANGUAGES = frozenset({"en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"})

# Languages the keyword-based topic tagger (api/chat/topics.py) supports.
# Duplicated here (rather than imported) so this module — which must stay
# importable with no DB/network access — doesn't pay for chat.topics's
# heavy transitive import chain just to read a language list; models.py's
# _canonical_topics() already documents and defers that cost where it's
# unavoidable (validating a topic id).
_TOPIC_TAGGER_LANGUAGES = frozenset({"en", "it", "de", "es", "fr", "pt", "ar"})

# BITB-103: every canonical topic must have at least this many golden-set
# cases carrying it in `topics`, and at least this many where the keyword
# tagger actually detects it too (a label the tagger never produces cannot
# exercise topic boosting regardless of how many cases claim it).
MIN_CASES_PER_TOPIC = 3
MIN_TAGGABLE_CASES_PER_TOPIC = 2
# Floor for the neutral (non-thematic) control subset. 10 cases are
# authored; the floor is lower so removing one case doesn't instantly
# redden CI.
MIN_NEUTRAL_CASES = 6


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
        ValueError: If any case fails Pydantic validation (e.g. bad ref),
            or is missing the ``topics`` key entirely (BITB-103 — a case
            authored without an explicit topics/neutral declaration must
            not silently join the neutral control group).
    """
    src = path or _DATA_FILE
    raw: list[dict] = json.loads(src.read_text(encoding="utf-8"))

    missing_topics = [item.get("id", "<no id>") for item in raw if "topics" not in item]
    if missing_topics:
        raise ValueError(
            f"cases missing the required 'topics' key (use [] for a neutral "
            f"case): {missing_topics}"
        )

    cases = []
    for item in raw:
        try:
            cases.append(GoldenCase.model_validate(item))
        except ValidationError as exc:
            raise ValueError(f"{item.get('id', '<no id>')}: {exc}") from exc

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


def topic_coverage(cases: list[GoldenCase]) -> dict[str, int]:
    """Return {canonical topic id: labelled case count}, zeros included.

    "Labelled" means the case's ``topics`` field names this topic — this is
    the ground-truth authoring signal, independent of whether the keyword
    tagger would actually detect it in the query text (see
    ``topic_tagger_coverage`` for that).
    """
    from chat.topics import canonical_topics

    counts = dict.fromkeys(sorted(canonical_topics()), 0)
    for case in cases:
        for topic in case.topics:
            counts[topic] = counts.get(topic, 0) + 1
    return counts


def topic_tagger_coverage(cases: list[GoldenCase]) -> dict[str, int]:
    """Return {canonical topic id: taggable case count}, zeros included.

    A case counts toward a topic here only if BOTH hold: the case's
    ``topics`` field claims that topic (it's the real ground truth, not an
    accident), AND the case's language is one the keyword tagger supports
    AND the tagger's ``detect_topics()`` actually returns that topic for the
    query text. This is the metric that closes BITB-103's core gap: a topic
    can rack up plenty of *labelled* cases (e.g. via a `tags` match) while
    the production tagger never once produces it — leaving it exactly as
    unmeasurable as a topic with zero cases at all.
    """
    from chat.topics import canonical_topics, detect_topics

    counts = dict.fromkeys(sorted(canonical_topics()), 0)
    for case in cases:
        if case.language not in _TOPIC_TAGGER_LANGUAGES:
            continue
        detected = set(detect_topics(case.query))
        for topic in case.topics:
            if topic in detected:
                counts[topic] = counts.get(topic, 0) + 1
    return counts


def neutral_cases(cases: list[GoldenCase]) -> list[GoldenCase]:
    """Return the cases with no topic at all — the non-thematic control group."""
    return [case for case in cases if not case.topics]


def validate_topic_coverage(cases: list[GoldenCase]) -> list[str]:
    """Check the BITB-103 coverage rules; return a list of failure messages.

    Does not raise — callers (the CLI, the test suite) accumulate these
    alongside their other structural checks, matching how
    ``scripts/run_search_eval.py``'s ``_cmd_validate`` already reports
    every failure in one pass rather than stopping at the first.
    """
    failures: list[str] = []

    labelled = topic_coverage(cases)
    for topic, count in labelled.items():
        if count < MIN_CASES_PER_TOPIC:
            failures.append(
                f"topic '{topic}' has only {count} labelled case(s), "
                f"need >= {MIN_CASES_PER_TOPIC}"
            )

    taggable = topic_tagger_coverage(cases)
    for topic, count in taggable.items():
        if count < MIN_TAGGABLE_CASES_PER_TOPIC:
            failures.append(
                f"topic '{topic}' has only {count} case(s) the keyword tagger "
                f"actually detects (labelled: {labelled.get(topic, 0)}), "
                f"need >= {MIN_TAGGABLE_CASES_PER_TOPIC} — a topic the tagger "
                f"never produces cannot exercise topic boosting"
            )

    neutral = neutral_cases(cases)
    if len(neutral) < MIN_NEUTRAL_CASES:
        failures.append(
            f"only {len(neutral)} neutral (topics: []) case(s), "
            f"need >= {MIN_NEUTRAL_CASES} to detect a topic-boosting regression"
        )

    return failures
