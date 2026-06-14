"""Pydantic models for the retrieval-evaluation golden set (BITB-043).

A ``GoldenCase`` is one query annotated with the verses that *should* surface
for it (the ranking ground truth). Kept separate from the response-quality
``golden_set`` package — this harness measures retrieval, not reply quality.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from .normalize import RefMatcher, normalize_reference


class GoldenCase(BaseModel):
    """One golden retrieval query with its ground-truth relevant verses."""

    id: str
    query: str
    language: str = "en"
    translation: str | None = None
    relevant_refs: list[str] = Field(min_length=1)
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("relevant_refs")
    @classmethod
    def _refs_must_parse(cls, refs: list[str]) -> list[str]:
        """Reject a case whose relevant references cannot be normalized."""
        bad = [ref for ref in refs if normalize_reference(ref) is None]
        if bad:
            raise ValueError(f"unparseable relevant_refs: {bad}")
        return refs

    def relevant_matchers(self) -> list[RefMatcher]:
        """Return the relevance matchers for this case's ground-truth refs."""
        matchers = [normalize_reference(ref) for ref in self.relevant_refs]
        return [m for m in matchers if m is not None]
