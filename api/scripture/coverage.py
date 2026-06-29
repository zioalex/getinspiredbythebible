"""Per-translation data coverage diagnostics and startup gate (BITB-054).

Provides:
- find_coverage_gaps() — pure function; cross-references DB rows against the
  set of supported UI languages and flags missing or embedding-empty translations.
- run_startup_coverage_check() — called from main.py lifespan; logs the full
  per-translation table, emits a metric per gap, and optionally raises so CI
  can catch an unloaded language before it ships.
"""

from __future__ import annotations

import logging

from scripture.database import async_session_factory
from scripture.repository import ScriptureRepository
from utils.language import LANGUAGE_TRANSLATIONS, SUPPORTED_LANGUAGES
from utils.metrics import data_coverage_gaps_counter

logger = logging.getLogger(__name__)


def find_coverage_gaps(rows: list[dict]) -> list[dict]:
    """Return gap entries for supported languages whose default translation lacks data.

    Args:
        rows: Output of ScriptureRepository.get_translation_coverage() —
              a list of dicts with keys 'translation', 'verses',
              'verses_with_embeddings'.

    Returns:
        List of dicts with keys: language, translation, reason
        ('no_verses' | 'no_embeddings').
    """
    by_translation = {r["translation"]: r for r in rows}
    gaps = []
    for lang in SUPPORTED_LANGUAGES:
        default_translation = LANGUAGE_TRANSLATIONS.get(lang, [""])[0]
        if not default_translation:
            continue
        row = by_translation.get(default_translation)
        if row is None or row["verses"] == 0:
            gaps.append(
                {"language": lang, "translation": default_translation, "reason": "no_verses"}
            )
        elif row["verses_with_embeddings"] == 0:
            gaps.append(
                {
                    "language": lang,
                    "translation": default_translation,
                    "reason": "no_embeddings",
                }
            )
    return gaps


async def run_startup_coverage_check(*, fail_on_empty: bool = False) -> None:
    """Log per-translation coverage and warn loudly on gaps.

    Opens its own DB session so it can be called from the lifespan manager
    before any request session is available. Errors are caught and re-raised
    only when ``fail_on_empty=True`` (CI gate); otherwise they are logged as
    warnings so a transient DB hiccup never bounces the pod.

    Args:
        fail_on_empty: When True, raise RuntimeError if any supported language
            has a data gap (suitable for CI). Default False for production.
    """
    async with async_session_factory() as session:
        repo = ScriptureRepository(session)
        rows = await repo.get_translation_coverage()

    if not rows:
        logger.warning("Translation coverage check: no verse data found in the database")
        if fail_on_empty:
            raise RuntimeError("No verse data found — at least one translation is required")
        return

    logger.info(
        "Translation coverage",
        extra={"rows": rows},
    )

    gaps = find_coverage_gaps(rows)
    for gap in gaps:
        logger.error(
            "Translation data gap: supported language has %s",
            gap["reason"],
            extra={"language": gap["language"], "translation": gap["translation"]},
        )
        data_coverage_gaps_counter.add(
            1,
            {
                "language": gap["language"],
                "translation": gap["translation"],
                "reason": gap["reason"],
            },
        )

    if gaps and fail_on_empty:
        missing = ", ".join(f"{g['language']}({g['reason']})" for g in gaps)
        raise RuntimeError(f"Translation data gaps detected at startup: {missing}")
