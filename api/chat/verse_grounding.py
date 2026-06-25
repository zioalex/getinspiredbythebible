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

from utils.verse_parser import (
    InlineQuote,
    ReferenceMention,
    VerseReference,
    extract_inline_quotes,
    extract_reference_mentions,
)

# Quotes scoring at or above this normalized similarity to the canonical verse
# are treated as faithful. A verbatim quote with only punctuation/casing noise
# scores ~0.95+; reconstructed-from-memory text scores well below 0.6, so 0.90
# catches fabrications while leaving margin for diacritic/whitespace artifacts.
GROUNDING_SIMILARITY_THRESHOLD = 0.90
# Below this normalized length a quote is too short to judge reliably (high
# false-positive risk), so it is left untouched.
MIN_QUOTE_LEN = 12

# --- Paraphrase detection thresholds (BITB-053) ---
# Minimum token-overlap ratio (|cand ∩ canon| / |canon|) for a sentence to be
# treated as paraphrasing the cited verse.  Calibrated across 11 languages so
# that morphologically rich languages (Italian, Russian, Arabic) still trigger
# on partial-stem overlap while pure commentary ("John 3:16 is about love")
# doesn't.  See BITB-053 for the per-language calibration table.
PARAPHRASE_SIMILARITY_THRESHOLD: float = 0.18
# Absolute minimum number of matching long tokens — prevents a single unusual
# word coincidentally pushing the ratio above threshold.
_PARAPHRASE_OVERLAP_ABS_MIN: int = 4
# Sentence must have at least this many long tokens to be a paraphrase candidate
# (short sentences like "See John 3:16." have too little signal either way).
_PARAPHRASE_MIN_CANDIDATE_WORDS: int = 4
# Only count tokens of this length or longer — filters out articles, prepositions
# ("is", "the", "di", "de") that are too common to be meaningful overlap signals.
_OVERLAP_TOKEN_MIN_LEN: int = 3

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


def _token_overlap_ratio(candidate_norm: str, canonical_norm: str) -> tuple[float, int]:
    """Asymmetric token-set overlap: what fraction of canonical long tokens appear in candidate.

    Returns (ratio, absolute_count).  Order-independent, so morphological
    divergence (verb conjugation, declension) is handled gracefully.
    """
    cand_tokens = {w for w in candidate_norm.split() if len(w) >= _OVERLAP_TOKEN_MIN_LEN}
    canon_tokens = {w for w in canonical_norm.split() if len(w) >= _OVERLAP_TOKEN_MIN_LEN}
    if not canon_tokens or not cand_tokens:
        return 0.0, 0
    overlap = cand_tokens & canon_tokens
    return len(overlap) / len(canon_tokens), len(overlap)


# Characters that indicate a sentence already contains a quotation.
# If any appear in content_text the verse is already presented quoted
# (possibly non-adjacently), so the unquoted-paraphrase path is skipped.
_QUOTE_CHARS: frozenset[str] = frozenset(
    [
        "\"",
        "'",
        "\u201c", "\u201d",
        "\u00ab", "\u00bb",
        "\u300c", "\u300d",
        "\u300e", "\u300f",
        "\u2039", "\u203a",
        "\u2018", "\u2019",
    ]
)


def _has_quotation(text: str) -> bool:
    """Return True if text contains any known quotation-mark character.

    Used by the paraphrase classifier: if the sentence already contains
    a quote char the verse text was likely already quoted (even if not
    adjacently), so we do not also trigger the paraphrase append path.
    """
    return any(c in _QUOTE_CHARS for c in text)



def _classify_paraphrase(content_text: str, canonical: str) -> bool:
    """Return True when *content_text* looks like an unquoted paraphrase of *canonical*.

    Uses token-overlap similarity rather than SequenceMatcher so that inflected
    forms in Italian / Russian / Arabic still produce meaningful signal even
    when surface forms differ from the canonical wording.
    """
    if not canonical or not content_text:
        return False
    content_norm = _normalize_for_compare(content_text)
    canonical_norm = _normalize_for_compare(canonical)
    meaningful = [w for w in content_norm.split() if len(w) >= _OVERLAP_TOKEN_MIN_LEN]
    if len(meaningful) < _PARAPHRASE_MIN_CANDIDATE_WORDS:
        return False
    ratio, abs_count = _token_overlap_ratio(content_norm, canonical_norm)
    return ratio >= PARAPHRASE_SIMILARITY_THRESHOLD and abs_count >= _PARAPHRASE_OVERLAP_ABS_MIN


def ground_response(
    text: str,
    resolved_verses: list,
    context_refs: set[tuple[str, int, int]],
    *,
    strip_unresolved: bool = False,
    ground_paraphrases: bool = True,
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
        ground_paraphrases: When True (default), also detect unquoted
            paraphrases and append the canonical verse text after the reference
            so the user sees the real wording (BITB-053).

    Returns:
        (corrected_text, corrections). ``corrected_text`` is ``text`` unchanged
        when nothing needed fixing.
    """
    quotes = extract_inline_quotes(text)

    canonical_by_key: dict[tuple[str, int, int], str] = {}
    for v in resolved_verses:
        canonical_by_key[(v.book.lower(), v.chapter, v.verse)] = v.text

    corrections: list[Correction] = []
    # (start, end, replacement) edits, applied right-to-left so offsets stay valid.
    edits: list[tuple[int, int, str]] = []

    # --- Pass 1: quoted-verse grounding (existing behaviour) ---
    # Track which (book, chapter, verse_start) keys are already handled so the
    # paraphrase pass doesn't double-process the same reference.
    handled_ref_keys: set[tuple[str, int, int]] = set()
    for q in quotes:
        canonical = _canonical_text(q.reference, canonical_by_key)
        in_context = any(k in context_refs for k in _ref_keys(q.reference))
        reason = _classify(q.quoted_text, canonical, in_context)
        if reason is None:
            # Quote is faithful — still mark as handled so paraphrase pass skips it.
            handled_ref_keys.add((q.reference.book.lower(), q.reference.chapter, q.reference.verse_start))
            continue
        if reason == "unresolved":
            corrected = None
            if strip_unresolved:
                edits.append(_strip_edit(text, q))
        else:
            corrected = canonical
            edits.append((q.span[0], q.span[1], canonical))
        handled_ref_keys.add((q.reference.book.lower(), q.reference.chapter, q.reference.verse_start))
        corrections.append(
            Correction(
                reference=str(q.reference),
                reason=reason,
                original_quote=q.quoted_text,
                corrected_quote=corrected,
            )
        )

    # --- Pass 2: unquoted / paraphrased citation grounding (BITB-053) ---
    if ground_paraphrases and canonical_by_key:
        for mention in extract_reference_mentions(text):
            ref_key = (
                mention.reference.book.lower(),
                mention.reference.chapter,
                mention.reference.verse_start,
            )
            # Skip if the quoted-verse pass already handled this reference.
            if ref_key in handled_ref_keys:
                continue
            canonical = _canonical_text(mention.reference, canonical_by_key)
            if not canonical:
                continue  # verse not in resolved set — nothing to append
            # Idempotency guard: skip if canonical text is already present in the sentence.
            canonical_norm = _normalize_for_compare(canonical)
            sentence_norm = _normalize_for_compare(mention.sentence)
            if canonical_norm in sentence_norm:
                continue
            # If the sentence already contains any quote character the verse was
            # likely presented quoted (even if not adjacently detected by pass-1).
            # Skip so we don't also append via the paraphrase path.
            if _has_quotation(mention.content_text):
                continue
            if not _classify_paraphrase(mention.content_text, canonical):
                continue
            # Append the canonical verse in quotes immediately after the reference.
            insert_pos = mention.ref_span[1]
            edits.append((insert_pos, insert_pos, f' ("{canonical}")'))
            handled_ref_keys.add(ref_key)
            corrections.append(
                Correction(
                    reference=str(mention.reference),
                    reason="paraphrased",
                    original_quote=mention.content_text,
                    corrected_quote=canonical,
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
