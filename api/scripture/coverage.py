"""Translation data-coverage diagnostics (BITB-054).

When a supported UI language's backing translation is missing entirely, or is
loaded but has no embeddings, two things happen silently: semantic search
returns nothing (the model free-generates the verse from memory), and
post-generation grounding classifies the citation ``unresolved`` with no
canonical text to fall back on. This module makes that condition observable —
reused by both the admin diagnostic endpoint (``routes/admin.py``) and the
startup guard (``main.py``) — instead of requiring a manual ``psql`` session
(see the diagnostic SQL in ``NEXT_STEPS.md``).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from utils import translation_readiness
from utils.language import LANGUAGE_TO_TRANSLATION, SUPPORTED_LANGUAGES

from .repository import ScriptureRepository


@dataclass(frozen=True)
class UnusableLanguage:
    """A supported UI language whose backing translation has no usable data."""

    language: str
    translation: str
    problem: str  # "no_verses" | "no_embeddings"


def find_unusable_languages(coverage: list[dict]) -> list[UnusableLanguage]:
    """Return supported languages whose backing translation is unusable.

    A language is unusable when its default translation (``LANGUAGE_TO_TRANSLATION``)
    either has no rows at all in ``coverage`` (never loaded / zero verses) or has
    verses but zero embeddings (semantic search can never surface it).

    Args:
        coverage: Rows as returned by ``ScriptureRepository.get_translation_coverage()``
            — ``{"translation", "total_verses", "verses_with_embeddings"}``.

    Returns:
        One ``UnusableLanguage`` per affected supported language, in
        ``SUPPORTED_LANGUAGES`` order.
    """
    by_translation = {row["translation"]: row for row in coverage}
    unusable: list[UnusableLanguage] = []
    for language in SUPPORTED_LANGUAGES:
        translation = LANGUAGE_TO_TRANSLATION.get(language)
        if translation is None:
            # No mapping at all — treat the same as a missing translation.
            unusable.append(UnusableLanguage(language, "unknown", "no_verses"))
            continue
        row = by_translation.get(translation)
        if row is None or row["total_verses"] == 0:
            unusable.append(UnusableLanguage(language, translation, "no_verses"))
        elif row["verses_with_embeddings"] == 0:
            unusable.append(UnusableLanguage(language, translation, "no_embeddings"))
    return unusable


async def check_translation_coverage(
    session: AsyncSession,
) -> tuple[list[dict], list[UnusableLanguage]]:
    """Fetch per-translation coverage and classify unusable supported languages.

    Shared by the admin diagnostic endpoint and the startup guard so both
    surfaces report exactly the same thing.
    """
    repo = ScriptureRepository(session)
    coverage = await repo.get_translation_coverage()
    unusable = find_unusable_languages(coverage)
    return coverage, unusable


async def refresh_ready_translations(session: AsyncSession) -> None:
    """Refresh the cached "ready translations" set from live DB coverage.

    Feeds ``utils.translation_readiness`` so default resolution
    (``utils.language.get_translation_for_language``) can skip a language default
    whose verses/embeddings are not loaded yet and fall back to the next ready
    translation. Best-effort: callers should swallow exceptions so a
    cold/unreachable DB never blocks startup or a request.
    """
    repo = ScriptureRepository(session)
    coverage = await repo.get_translation_coverage()
    translation_readiness.set_ready_translations(translation_readiness.compute_ready(coverage))
