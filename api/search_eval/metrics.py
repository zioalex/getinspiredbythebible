"""Pure ranking metrics for the retrieval-evaluation harness (BITB-043).

Given a ranked list of retrieved verses and a set of relevance matchers (the
ground truth for one query), compute Precision@K, Recall@K, and MRR. All
functions are pure and DB-free so they run in the standard (blocking) CI test
job with no infrastructure.
"""

from __future__ import annotations

from .normalize import RefMatcher, VerseKey


def _is_hit(retrieved: VerseKey, relevant: list[RefMatcher]) -> bool:
    """True if a retrieved verse satisfies any relevance matcher."""
    return any(matcher.matches(retrieved) for matcher in relevant)


def precision_at_k(retrieved: list[VerseKey], relevant: list[RefMatcher], k: int) -> float:
    """Fraction of the top-k retrieved verses that are relevant.

    Denominator is always ``k`` (standard Precision@K), so a short or empty
    result list lowers precision rather than inflating it.
    """
    if k <= 0:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for verse in top_k if _is_hit(verse, relevant))
    return hits / k


def recall_at_k(retrieved: list[VerseKey], relevant: list[RefMatcher], k: int) -> float:
    """Fraction of relevance matchers covered by the top-k retrieved verses.

    Matcher-coverage (not verse count), so a verse range or a chapter-only
    reference counts as a single relevant item.
    """
    if not relevant:
        return 0.0
    top_k = retrieved[:k]
    covered = sum(1 for matcher in relevant if any(matcher.matches(v) for v in top_k))
    return covered / len(relevant)


def mrr(retrieved: list[VerseKey], relevant: list[RefMatcher]) -> float:
    """Reciprocal rank of the first relevant retrieved verse (0.0 if none)."""
    for rank, verse in enumerate(retrieved, start=1):
        if _is_hit(verse, relevant):
            return 1.0 / rank
    return 0.0
