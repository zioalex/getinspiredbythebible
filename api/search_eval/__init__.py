"""Retrieval-evaluation harness for scripture search (BITB-043).

Measures search *ranking* quality (Precision@K / Recall@K / MRR) over a curated
golden set of queries, so query expansion and the hybrid/boosting levers can be
validated and tuned. Distinct from the ``golden_set`` package, which scores
chat *response* quality.
"""

from .metrics import false_positives_at_k, mrr, precision_at_k, recall_at_k
from .models import GoldenCase
from .normalize import (
    RefMatcher,
    VerseKey,
    canonical_book,
    normalize_reference,
    parse_verse_key,
)

__all__ = [
    "GoldenCase",
    "RefMatcher",
    "VerseKey",
    "canonical_book",
    "normalize_reference",
    "parse_verse_key",
    "precision_at_k",
    "recall_at_k",
    "mrr",
    "false_positives_at_k",
]
