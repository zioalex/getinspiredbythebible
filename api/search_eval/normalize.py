"""Reference normalization for the retrieval-evaluation harness (BITB-043).

Turns Bible references — both golden-set ground truth and retrieved results —
into canonical, comparable keys so ranking metrics can match them robustly
across:

- book-name spelling/locale variants (e.g. "Psalm" vs "Psalms", localized names),
- verse ranges ("Philippians 4:6-7" matches verse 6 or 7),
- chapter-only references ("Psalm 23" matches any verse in Psalms 23).

Reuses ``utils.book_names.normalize_book_name`` (localized -> English) and adds a
small table of English spelling variants it does not cover.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import NamedTuple

from utils.book_names import normalize_book_name

# Non-English book names are NOT handled here — they are resolved upstream by
# ``normalize_book_name`` (see ``canonical_book``), which maps all 11 supported
# languages (it/de/es/fr/pt/ar/ru/zh/ko/hi/en) to English via ``LOCALIZED_TO_ENGLISH``.
# This table only patches *English* spelling variants that the upstream map does not
# carry (the canonical target is English). It is intentionally English-only because
# golden-set ``relevant_refs`` and retrieved ``VerseResult.reference`` are both
# English-canonical, so localized strings rarely reach this function. (Gaps in the
# upstream localized coverage — e.g. Italian "Salmo" singular — are tracked in BITB-052.)
# Keys are lower-cased for case-insensitive lookup.
_EXTRA_BOOK_ALIASES: dict[str, str] = {
    "psalm": "Psalms",
    "song of songs": "Song of Solomon",
    "canticles": "Song of Solomon",
    "revelations": "Revelation",
}

# "<book> <chapter>[:<verse>[-<verse>]]" — book may contain spaces and digits
# (e.g. "1 Corinthians 13:4-7", "Song of Solomon 2:1", "Psalm 23").
_REF_RE = re.compile(
    r"^\s*(?P<book>.+?)\s+(?P<chapter>\d+)" r"(?::(?P<start>\d+)(?:\s*-\s*(?P<end>\d+))?)?\s*$"
)


class VerseKey(NamedTuple):
    """A single concrete verse: canonical English book, chapter, verse."""

    book: str
    chapter: int
    verse: int


@dataclass(frozen=True)
class RefMatcher:
    """A relevance matcher for one ground-truth reference.

    ``verses`` is a frozenset of acceptable verse numbers (an exact verse or an
    expanded range), or ``None`` for a chapter-only reference (any verse in the
    chapter is relevant).
    """

    book: str
    chapter: int
    verses: frozenset[int] | None

    def matches(self, key: VerseKey) -> bool:
        """Return True if ``key`` falls within this matcher."""
        if key.book != self.book or key.chapter != self.chapter:
            return False
        return self.verses is None or key.verse in self.verses


def canonical_book(book: str) -> str:
    """Canonicalize a book name to its standard English form.

    Applies ``normalize_book_name`` (handles localized names and Psalm->Psalms),
    then a small English spelling-variant alias table.
    """
    raw = book.strip()
    name = normalize_book_name(raw)
    return _EXTRA_BOOK_ALIASES.get(name.lower(), _EXTRA_BOOK_ALIASES.get(raw.lower(), name))


def normalize_reference(ref: str) -> RefMatcher | None:
    """Parse a reference string into a :class:`RefMatcher`.

    Returns ``None`` if the string cannot be parsed. Handles exact verses,
    inclusive ranges, and chapter-only references.
    """
    match = _REF_RE.match(ref or "")
    if not match:
        return None

    book = canonical_book(match.group("book"))
    chapter = int(match.group("chapter"))

    start = match.group("start")
    if start is None:
        return RefMatcher(book, chapter, None)  # chapter-only

    start_v = int(start)
    end = match.group("end")
    end_v = int(end) if end is not None else start_v
    if end_v < start_v:
        start_v, end_v = end_v, start_v
    return RefMatcher(book, chapter, frozenset(range(start_v, end_v + 1)))


def parse_verse_key(reference: str) -> VerseKey | None:
    """Parse a single retrieved verse reference (e.g. "John 3:16") to a VerseKey.

    Retrieved references always carry a verse; if a range is given, the start
    verse is used. Returns ``None`` for chapter-only or unparseable input.
    """
    match = _REF_RE.match(reference or "")
    if not match or match.group("start") is None:
        return None
    return VerseKey(
        canonical_book(match.group("book")),
        int(match.group("chapter")),
        int(match.group("start")),
    )
