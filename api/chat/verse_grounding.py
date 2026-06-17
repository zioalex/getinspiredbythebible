"""Post-generation scripture grounding.

The LLM is given verified verse text in the "Scripture Context" block, but it
sometimes volunteers a verse that was never retrieved and reconstructs its
wording from memory — producing a citation whose quoted text does not match the
real verse (e.g. Italian Isaiah 41:10 rendered with the non-word "io ti
fortirò"). Prompt rules alone (BITB-038) don't fully prevent this.

This module adds a mechanical safety net: after generation, every inline-quoted
verse is compared against the canonical text already resolved from the database,
and a fabricated or mismatched quote is rewritten to the canonical wording (the
reference and surrounding prose are preserved). It is a pure function — all DB
access happens upstream in the caller — so it is fast and trivially testable.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass

from utils.verse_parser import InlineQuote, VerseReference, extract_inline_quotes

# Quotes scoring at or above this normalized similarity to the canonical verse
# are treated as faithful. A verbatim quote with only punctuation/casing noise
# scores ~0.95+; reconstructed-from-memory text scores well below 0.6, so 0.90
# catches fabrications while leaving margin for diacritic/whitespace artifacts.
GROUNDING_SIMILARITY_THRESHOLD = 0.90
# Below this normalized length a quote is too short to judge reliably (high
# false-positive risk), so it is left untouched.
MIN_QUOTE_LEN = 12

_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WS_RE = re.compile(r"\s+")
_ELLIPSIS_RE = re.compile(r"(\.{3,}|…)")


def _normalize_for_compare(s: str) -> str:
    """Normalize verse text for similarity comparison.

    Unicode-normalize (NFKC), casefold, drop ellipsis truncation markers, strip
    punctuation/quote marks, and collapse all whitespace (including newlines, so
    flattened poetry doesn't read as a mismatch).
    """
    s = unicodedata.normalize("NFKC", s)
    s = _ELLIPSIS_RE.sub(" ", s)
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s)
    return s.casefold().strip()


@dataclass
class Correction:
    """A detected scripture-fidelity issue and what was done about it."""

    reference: str
    reason: str  # "fabricated" | "mismatched" | "unresolved"
    original_quote: str
    corrected_quote: str | None  # None when no canonical text was available


def _ref_keys(ref: VerseReference) -> list[tuple[str, int, int]]:
    """Canonical (book, chapter, verse) keys a reference covers, expanding ranges."""
    if ref.verse_end and ref.verse_end > ref.verse_start:
        return [
            (ref.book.lower(), ref.chapter, v) for v in range(ref.verse_start, ref.verse_end + 1)
        ]
    return [(ref.book.lower(), ref.chapter, ref.verse_start)]


def _canonical_text(ref: VerseReference, canonical_by_key: dict[tuple[str, int, int], str]) -> str:
    """Concatenate the canonical text for a reference (joined for ranges)."""
    parts = [canonical_by_key[k] for k in _ref_keys(ref) if k in canonical_by_key]
    return " ".join(p for p in parts if p).strip()


def _classify(quoted: str, canonical: str, in_context: bool) -> str | None:
    """Return a correction reason, or None when the quote is acceptable.

    A partial quote that is a substring of the canonical text is always
    acceptable — the model may legitimately quote only part of a verse.
    """
    if not canonical:
        return "unresolved"
    nq = _normalize_for_compare(quoted)
    if len(nq) < MIN_QUOTE_LEN:
        return None
    nc = _normalize_for_compare(canonical)
    if nq in nc:
        return None
    if difflib.SequenceMatcher(None, nq, nc).ratio() >= GROUNDING_SIMILARITY_THRESHOLD:
        return None
    return "mismatched" if in_context else "fabricated"


def ground_response(
    text: str,
    resolved_verses: list,
    context_refs: set[tuple[str, int, int]],
    *,
    strip_unresolved: bool = False,
) -> tuple[str, list[Correction]]:
    """Correct fabricated/mismatched inline verse quotes in ``text``.

    Args:
        text: The full LLM response.
        resolved_verses: VerseResult objects already resolved from the DB for the
            cited references (reused — this function makes no DB calls).
        context_refs: (book, chapter, verse) keys that were in the Scripture
            Context, used to label a low-similarity quote ``fabricated`` (not
            provided) vs ``mismatched`` (provided but re-worded).
        strip_unresolved: When a reference resolves to no DB text, remove the
            invented quotation instead of only reporting it.

    Returns:
        (corrected_text, corrections). ``corrected_text`` is ``text`` unchanged
        when nothing needed fixing.
    """
    quotes = extract_inline_quotes(text)
    if not quotes:
        return text, []

    canonical_by_key: dict[tuple[str, int, int], str] = {}
    for v in resolved_verses:
        canonical_by_key[(v.book.lower(), v.chapter, v.verse)] = v.text

    corrections: list[Correction] = []
    # (start, end, replacement) edits, applied right-to-left so offsets stay valid.
    edits: list[tuple[int, int, str]] = []
    for q in quotes:
        canonical = _canonical_text(q.reference, canonical_by_key)
        in_context = any(k in context_refs for k in _ref_keys(q.reference))
        reason = _classify(q.quoted_text, canonical, in_context)
        if reason is None:
            continue
        if reason == "unresolved":
            corrected = None
            if strip_unresolved:
                edits.append(_strip_edit(text, q))
        else:
            corrected = canonical
            edits.append((q.span[0], q.span[1], canonical))
        corrections.append(
            Correction(
                reference=str(q.reference),
                reason=reason,
                original_quote=q.quoted_text,
                corrected_quote=corrected,
            )
        )

    if not edits:
        return text, corrections

    corrected_text = text
    for start, end, replacement in sorted(edits, key=lambda e: e[0], reverse=True):
        corrected_text = corrected_text[:start] + replacement + corrected_text[end:]
    return corrected_text, corrections


def _strip_edit(text: str, quote: InlineQuote) -> tuple[int, int, str]:
    """Edit that removes an invented quotation along with its surrounding marks,
    leaving the reference and prose intact."""
    start = quote.span[0]
    end = quote.span[1]
    # Drop the opening/closing quotation marks that bracket the span.
    if start > 0:
        start -= 1
    if end < len(text):
        end += 1
    return start, end, ""
