"""Pydantic models for the retrieval-evaluation golden set (BITB-043).

A ``GoldenCase`` is one query annotated with the verses that *should* surface
for it (the ranking ground truth). Kept separate from the response-quality
``golden_set`` package — this harness measures retrieval, not reply quality.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, Field, field_validator

from .normalize import RefMatcher, normalize_reference


@lru_cache(maxsize=1)
def _canonical_topics() -> frozenset[str]:
    """The canonical topic-id vocabulary, imported lazily.

    ``chat.topics`` looks like a light, DB-free module on its own, but
    importing it through the ``chat`` package (``import chat.topics``)
    executes ``chat/__init__.py`` first, which pulls in ``chat.service`` ->
    FastAPI/SQLAlchemy/the provider stack -> an async engine created at
    import time (``scripture/database.py``). ``loader.py`` must stay
    importable with no DB/network access so ``--validate`` can run in CI
    with nothing but the repo, so this import is deferred to first use
    (only real validation calls pay for the heavy chain) and cached.
    """
    from chat.topics import canonical_topics

    return canonical_topics()


class GoldenCase(BaseModel):
    """One golden retrieval query with its ground-truth relevant verses."""

    id: str
    query: str
    language: str = "en"
    translation: str | None = None
    relevant_refs: list[str] = Field(min_length=1)
    irrelevant_refs: list[str] = Field(default_factory=list)
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("relevant_refs", "irrelevant_refs")
    @classmethod
    def _refs_must_parse(cls, refs: list[str]) -> list[str]:
        """Reject a case whose references cannot be normalized."""
        bad = [ref for ref in refs if normalize_reference(ref) is None]
        if bad:
            raise ValueError(f"unparseable refs: {bad}")
        return refs

    @field_validator("topics")
    @classmethod
    def _topics_must_be_canonical(cls, topics: list[str]) -> list[str]:
        """Reject a case whose topics aren't in the canonical vocabulary (BITB-103).

        An empty list is the explicit "neutral, non-thematic case" marker —
        it is not required to be non-empty here; coverage of the neutral
        subset as a whole is enforced separately by
        ``loader.validate_topic_coverage``.
        """
        if len(topics) != len(set(topics)):
            raise ValueError(f"duplicate topics: {topics}")
        if any(not t.strip() for t in topics):
            raise ValueError(f"blank topic id in: {topics}")
        canonical = _canonical_topics()
        unknown = [t for t in topics if t not in canonical]
        if unknown:
            raise ValueError(
                f"unknown topic(s) {unknown}; canonical vocabulary is "
                f"TOPIC_KEYWORDS_BY_LANGUAGE in api/chat/topics.py: {sorted(canonical)}"
            )
        return topics

    def relevant_matchers(self) -> list[RefMatcher]:
        """Return the relevance matchers for this case's ground-truth refs."""
        matchers = [normalize_reference(ref) for ref in self.relevant_refs]
        return [m for m in matchers if m is not None]

    def irrelevant_matchers(self) -> list[RefMatcher]:
        """Return matchers for verses that must NOT surface (guard cases).

        Absorbed from the BITB-043 incident guard — e.g. the Italian
        frustration query must not return Job 21:27.
        """
        matchers = [normalize_reference(ref) for ref in self.irrelevant_refs]
        return [m for m in matchers if m is not None]
