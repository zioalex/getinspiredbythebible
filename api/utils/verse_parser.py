"""
Verse reference and prayer pattern parser.

Detects Bible verse references and famous prayer names in user messages
to enable direct lookup instead of relying solely on semantic search.
"""

import re
from dataclasses import dataclass

from utils.book_names import normalize_book_name
from utils.translation_registry import EXTRA_REVERSE_MAPPINGS, TRANSLATION_REGISTRY

# All book names in all languages (for pattern matching).
# Built dynamically from TRANSLATION_REGISTRY — adding a new translation to
# translation_registry.py automatically includes it here.
ALL_BOOK_NAMES: set[str] = set()
for _book_map in TRANSLATION_REGISTRY.values():
    if _book_map is not None:
        ALL_BOOK_NAMES.update(_book_map.keys())  # English (same keys in every map)
        ALL_BOOK_NAMES.update(_book_map.values())  # localized names
# Also include alias/variant forms (e.g. Russian genitive citation forms)
ALL_BOOK_NAMES.update(EXTRA_REVERSE_MAPPINGS.keys())

# Common abbreviations for book names
BOOK_ABBREVIATIONS = {
    # English abbreviations
    "gen": "Genesis",
    "ex": "Exodus",
    "exod": "Exodus",
    "lev": "Leviticus",
    "num": "Numbers",
    "deut": "Deuteronomy",
    "josh": "Joshua",
    "judg": "Judges",
    "ps": "Psalms",
    "psa": "Psalms",
    "psalm": "Psalms",
    "prov": "Proverbs",
    "eccl": "Ecclesiastes",
    "isa": "Isaiah",
    "jer": "Jeremiah",
    "lam": "Lamentations",
    "ezek": "Ezekiel",
    "dan": "Daniel",
    "hos": "Hosea",
    "mic": "Micah",
    "nah": "Nahum",
    "hab": "Habakkuk",
    "zeph": "Zephaniah",
    "hag": "Haggai",
    "zech": "Zechariah",
    "mal": "Malachi",
    "matt": "Matthew",
    "mt": "Matthew",
    "mk": "Mark",
    "lk": "Luke",
    "jn": "John",
    "joh": "John",
    "acts": "Acts",
    "rom": "Romans",
    "cor": "Corinthians",  # Needs number prefix handling
    "gal": "Galatians",
    "eph": "Ephesians",
    "phil": "Philippians",
    "col": "Colossians",
    "thess": "Thessalonians",  # Needs number prefix handling
    "tim": "Timothy",  # Needs number prefix handling
    "pet": "Peter",  # Needs number prefix handling
    "heb": "Hebrews",
    "jas": "James",
    "jude": "Jude",
    "rev": "Revelation",
    # Italian abbreviations (only those not already defined)
    "gv": "John",  # Giovanni
    "sal": "Psalms",  # Salmi
    "lc": "Luke",  # Luca
    "mc": "Mark",  # Marco
    "ap": "Revelation",  # Apocalisse
    "at": "Acts",  # Atti
}


@dataclass
class VerseReference:
    """Parsed verse reference."""

    book: str  # Normalized English book name
    chapter: int
    verse_start: int
    verse_end: int | None = None  # For ranges like "3:16-21"

    def __str__(self) -> str:
        if self.verse_end:
            return f"{self.book} {self.chapter}:{self.verse_start}-{self.verse_end}"
        return f"{self.book} {self.chapter}:{self.verse_start}"


@dataclass
class InlineQuote:
    """A span of quoted text in an LLM response paired with the verse reference
    it is presented as quoting (e.g. `"For God so loved…" (John 3:16)`)."""

    reference: VerseReference
    quoted_text: str  # raw text between the quotation marks
    span: tuple[int, int]  # (start, end) offsets of quoted_text in the source
    ref_span: tuple[int, int]  # (start, end) offsets of the reference token


@dataclass
class PrayerReference:
    """Parsed prayer/passage reference."""

    name: str  # Canonical name (e.g., "Lord's Prayer")
    reference: str  # Bible reference (e.g., "Matthew 6:9-13") - empty if not biblical
    keywords: list[str]  # Keywords for semantic search fallback
    is_biblical: bool = True  # Whether this prayer/passage is directly from the Bible
    note: str = ""  # Additional note about the prayer's origin


# Famous prayers and their Bible references
# Note: is_biblical=False indicates the prayer is NOT directly from the Bible
FAMOUS_PRAYERS = {
    # === BIBLICAL PRAYERS AND PASSAGES ===
    "lord's prayer": PrayerReference(
        name="Lord's Prayer",
        reference="Matthew 6:9-13",
        keywords=["Our Father", "hallowed be thy name", "thy kingdom come"],
        is_biblical=True,
    ),
    "our father": PrayerReference(
        name="Lord's Prayer",
        reference="Matthew 6:9-13",
        keywords=["Our Father", "hallowed be thy name", "thy kingdom come"],
        is_biblical=True,
    ),
    "padre nostro": PrayerReference(  # Italian
        name="Lord's Prayer",
        reference="Matthew 6:9-13",
        keywords=["Padre nostro", "sia santificato il tuo nome"],
        is_biblical=True,
    ),
    "vater unser": PrayerReference(  # German
        name="Lord's Prayer",
        reference="Matthew 6:9-13",
        keywords=["Vater unser", "geheiligt werde dein Name"],
        is_biblical=True,
    ),
    "prayer of jabez": PrayerReference(
        name="Prayer of Jabez",
        reference="1 Chronicles 4:10",
        keywords=["bless me indeed", "enlarge my territory"],
        is_biblical=True,
    ),
    # === NON-BIBLICAL PRAYERS ===
    "serenity prayer": PrayerReference(
        name="Serenity Prayer",
        reference="",
        keywords=["accept", "courage", "wisdom", "serenity"],
        is_biblical=False,
        note="Written by Reinhold Niebuhr in the 20th century, not from the Bible.",
    ),
    "hail mary": PrayerReference(
        name="Hail Mary",
        reference="",
        keywords=["Hail Mary", "full of grace", "blessed art thou"],
        is_biblical=False,
        note="Catholic prayer. Contains phrases from Luke 1:28,42 but the full prayer is not in the Bible.",
    ),
    "ave maria": PrayerReference(
        name="Hail Mary",
        reference="",
        keywords=["Ave Maria", "gratia plena", "benedicta tu"],
        is_biblical=False,
        note="Catholic prayer (Latin). Contains phrases from Luke 1:28,42 but the full prayer is not in the Bible.",
    ),
    "prayer of st. francis": PrayerReference(
        name="Prayer of St. Francis",
        reference="",
        keywords=["instrument of peace", "where there is hatred", "sow love"],
        is_biblical=False,
        note="20th-century prayer, not actually written by St. Francis, not from the Bible.",
    ),
    "prayer of saint francis": PrayerReference(
        name="Prayer of St. Francis",
        reference="",
        keywords=["instrument of peace", "where there is hatred", "sow love"],
        is_biblical=False,
        note="20th-century prayer, not actually written by St. Francis, not from the Bible.",
    ),
    "glory be": PrayerReference(
        name="Glory Be (Gloria Patri)",
        reference="",
        keywords=["Glory be to the Father", "as it was in the beginning"],
        is_biblical=False,
        note="Early Christian doxology (4th century), not from the Bible.",
    ),
    "gloria patri": PrayerReference(
        name="Glory Be (Gloria Patri)",
        reference="",
        keywords=["Gloria Patri", "Filio", "Spiritui Sancto"],
        is_biblical=False,
        note="Early Christian doxology (4th century), not from the Bible.",
    ),
    "act of contrition": PrayerReference(
        name="Act of Contrition",
        reference="",
        keywords=["O my God", "I am heartily sorry", "offended Thee"],
        is_biblical=False,
        note="Traditional Catholic prayer, not from the Bible.",
    ),
    "apostles' creed": PrayerReference(
        name="Apostles' Creed",
        reference="",
        keywords=["I believe in God", "almighty", "creator of heaven"],
        is_biblical=False,
        note="Early Christian creed (2nd-4th century), summarizes beliefs but is not from the Bible.",
    ),
    "nicene creed": PrayerReference(
        name="Nicene Creed",
        reference="",
        keywords=["We believe in one God", "begotten not made", "consubstantial"],
        is_biblical=False,
        note="Formulated at the Council of Nicaea (325 AD), not from the Bible.",
    ),
    # === MORE BIBLICAL PASSAGES ===
    "23rd psalm": PrayerReference(
        name="Psalm 23",
        reference="Psalms 23:1-6",
        keywords=["The Lord is my shepherd", "green pastures", "still waters"],
        is_biblical=True,
    ),
    "psalm 23": PrayerReference(
        name="Psalm 23",
        reference="Psalms 23:1-6",
        keywords=["The Lord is my shepherd", "green pastures", "still waters"],
        is_biblical=True,
    ),
    "salmo 23": PrayerReference(  # Italian
        name="Psalm 23",
        reference="Psalms 23:1-6",
        keywords=["L'Eterno è il mio pastore", "verdi paschi"],
        is_biblical=True,
    ),
    "ten commandments": PrayerReference(
        name="Ten Commandments",
        reference="Exodus 20:1-17",
        keywords=["thou shalt not", "commandments", "no other gods"],
        is_biblical=True,
    ),
    "beatitudes": PrayerReference(
        name="Beatitudes",
        reference="Matthew 5:3-12",
        keywords=["blessed are", "meek", "peacemakers"],
        is_biblical=True,
    ),
    "love chapter": PrayerReference(
        name="Love Chapter",
        reference="1 Corinthians 13:1-13",
        keywords=["love is patient", "love is kind", "greatest of these is love"],
        is_biblical=True,
    ),
    "armor of god": PrayerReference(
        name="Armor of God",
        reference="Ephesians 6:10-18",
        keywords=["armor", "belt of truth", "shield of faith", "sword of the Spirit"],
        is_biblical=True,
    ),
    "fruit of the spirit": PrayerReference(
        name="Fruit of the Spirit",
        reference="Galatians 5:22-23",
        keywords=["love", "joy", "peace", "patience", "kindness"],
        is_biblical=True,
    ),
    "great commission": PrayerReference(
        name="Great Commission",
        reference="Matthew 28:18-20",
        keywords=["go and make disciples", "baptizing", "teaching"],
        is_biblical=True,
    ),
    "magnificat": PrayerReference(
        name="Magnificat (Mary's Song)",
        reference="Luke 1:46-55",
        keywords=["My soul magnifies the Lord", "mighty has done great things"],
        is_biblical=True,
    ),
    "benedictus": PrayerReference(
        name="Benedictus (Zechariah's Song)",
        reference="Luke 1:68-79",
        keywords=["Blessed be the Lord God of Israel", "horn of salvation"],
        is_biblical=True,
    ),
    "nunc dimittis": PrayerReference(
        name="Nunc Dimittis (Simeon's Song)",
        reference="Luke 2:29-32",
        keywords=["Lord, now lettest thou", "thy servant depart in peace"],
        is_biblical=True,
    ),
}


def _build_verse_pattern() -> str:
    """Build the regex pattern for matching verse references.

    Returns the full pattern string with a capture group for the book name
    and groups for chapter, verse_start, and optional verse_end.
    """
    all_names: set[str] = set()
    all_names.update(ALL_BOOK_NAMES)
    for abbr in BOOK_ABBREVIATIONS.keys():
        all_names.add(abbr)
        all_names.add(abbr.capitalize())
        all_names.add(abbr.upper())

    sorted_names = sorted(all_names, key=len, reverse=True)
    book_alternatives = "|".join(re.escape(name) for name in sorted_names)

    cv_pattern = r"(\d+)[:\,](\d+)(?:\s*[-–]\s*(\d+))?"

    # Lookbehind allows: start of string, whitespace, CJK, Devanagari, Arabic chars,
    # or opening brackets: Chinese guillemet 《 (U+300A), Korean corner brackets
    # 「 (U+300C) and 『 (U+300E).
    # The optional closing bracket class [\u300b\u300d\u300f] after the book name
    # handles 《约翰福音》3:16 and 「요한복음」3:16 / 『시편』23:1.
    return rf"(?:^|(?<=\s)|(?<=[\u4e00-\u9fff\u3400-\u4dbf\uac00-\ud7af\u0900-\u097f\u0600-\u06ff\u300a\u300c\u300e]))({book_alternatives})[\u300b\u300d\u300f]?\s*{cv_pattern}"


# Compiled regex cached at module load time — avoids rebuilding the ~710-term
# alternation pattern on every call to parse_verse_reference / extract_all_references.
_VERSE_PATTERN = re.compile(_build_verse_pattern(), re.IGNORECASE)


def _match_to_verse_reference(match: re.Match) -> VerseReference | None:
    """Convert a regex match to a VerseReference, or None if book can't be normalized."""
    book_raw = match.group(1).strip()
    chapter = int(match.group(2))
    verse_start = int(match.group(3))
    verse_end = int(match.group(4)) if match.group(4) else None

    book = _normalize_book(book_raw)
    if not book:
        return None

    return VerseReference(
        book=book,
        chapter=chapter,
        verse_start=verse_start,
        verse_end=verse_end,
    )


def _normalize_arabic_text(text: str) -> str:
    """Strip Arabic tashkeel (diacritics) and tatweel (kashida) from text.

    Tashkeel marks (U+064B–U+065F, U+0670) are vowelisation marks that are
    often present in fully-vocalised Arabic text but absent in the book-name
    lookup tables.  Stripping them before regex matching ensures that
    ``يُوحَنَّا`` matches the canonical ``يوحنا``.

    Tatweel (U+0640, kashida) is a decorative letter-stretching character
    that can appear between any letters: ``يـوحـنـا``.

    Also normalizes French-style guillemets «» (U+00AB / U+00BB) to the
    CJK-style guillemets 《》 (U+300A / U+300B) so the existing bracket
    handling in the regex covers both Arabic «…» and Chinese 《…》.
    """
    # Strip tashkeel marks and tatweel
    text = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", text)
    # Normalize guillemets
    text = text.replace("\u00ab", "\u300a").replace("\u00bb", "\u300b")
    return text


def parse_verse_reference(text: str) -> VerseReference | None:
    """
    Parse the first verse reference from text.

    Supports formats:
    - "John 3:16"
    - "John 3:16-21" (range)
    - "1 Corinthians 13:4"
    - "1Cor 13:4" (abbreviated)
    - "Giovanni 3:16" (Italian)
    - "Johannes 3,16" (German with comma)
    - "约翰福音 3:16" (Chinese)
    - "요한복음 3:16" (Korean)
    - "यूहन्ना 3:16" (Hindi)
    - "يوحنا 3:16" (Arabic, with optional tashkeel)

    Args:
        text: Text that may contain a verse reference

    Returns:
        VerseReference if found, None otherwise
    """
    text = _normalize_arabic_text(text)
    match = _VERSE_PATTERN.search(text)
    if not match:
        return None
    return _match_to_verse_reference(match)


def extract_all_references(text: str) -> list[VerseReference]:
    """
    Extract ALL verse references from text.

    Unlike parse_verse_reference() which returns only the first match,
    this function finds every verse reference in the text. Designed for
    parsing AI responses that may cite multiple verses.

    Args:
        text: Text that may contain multiple verse references

    Returns:
        List of all VerseReference objects found (deduplicated)
    """
    text = _normalize_arabic_text(text)
    results: list[VerseReference] = []
    seen: set[str] = set()

    for match in _VERSE_PATTERN.finditer(text):
        ref = _match_to_verse_reference(match)
        if ref:
            key = str(ref)
            if key not in seen:
                seen.add(key)
                results.append(ref)

    return results


def parse_structured_citations(text: str) -> list[VerseReference]:
    """
    Parse the LLM's structured verse citation HTML comment.

    Looks for a comment like: <!-- VERSES: John 3:16; Romans 8:28 -->
    and parses each semicolon-separated reference.

    Args:
        text: Full LLM response text

    Returns:
        List of VerseReference objects from the structured citation
    """
    match = re.search(r"<!--\s*VERSES:\s*(.+?)\s*-->", text)
    if not match:
        return []

    results: list[VerseReference] = []
    seen: set[str] = set()

    for ref_text in match.group(1).split(";"):
        ref_text = ref_text.strip()
        if not ref_text:
            continue
        ref = parse_verse_reference(ref_text)
        if ref:
            key = str(ref)
            if key not in seen:
                seen.add(key)
                results.append(ref)

    return results


# Quote-mark pairs used across the 11 supported UI languages, as (open, close).
# Chinese book-title guillemets 《》 are intentionally excluded: they wrap book
# names inside references (《约翰福音》3:16), not verse quotations, and would
# otherwise be misread as quoted verse text.
_QUOTE_PAIRS: list[tuple[str, str]] = [
    ('"', '"'),
    ("“", "”"),  # “ ”
    ("„", "“"),  # „ … “  (German)
    ("«", "»"),  # « »   (French / Italian)
    ("「", "」"),  # 「 」  (CJK corner)
    ("『", "』"),  # 『 』  (CJK white corner)
    ("‘", "’"),  # ‘ ’
]

# Each pair captures its inner span on a single line (no newline), length-bounded
# so a stray opening mark can't swallow the rest of the message.
_QUOTE_PATTERNS: list[re.Pattern] = [
    re.compile(re.escape(o) + r"([^\n]{1,600}?)" + re.escape(c)) for o, c in _QUOTE_PAIRS
]

# Characters allowed to sit between a quotation and its adjacent reference
# (e.g. `… ." (John 3:16)` or `John 3:16: "…`). Any other character (a letter)
# means the quote and reference belong to different clauses.
_ADJACENCY_SEPARATORS = set(" \t\n ()[]—–-,.:;")
_ADJACENCY_WINDOW = 50
# Map brackets to spaces before running _VERSE_PATTERN so its whitespace
# lookbehind matches a reference written as "(John 3:16)"; same length keeps
# offsets aligned with the original text.
_BRACKET_TO_SPACE = str.maketrans("()[]", "    ")
# A reference may introduce a quotation with a short connector — `John 3:16 says:`,
# `Giovanni 3:16 dice,` — so a gap of a few words ending in a colon/comma also
# counts as adjacent. Anything richer (sentence punctuation, more text) does not,
# which keeps a nearby non-verse quotation from being misattributed.
_QUOTE_INTRO_GAP = re.compile(r"^[\w\s]{0,20}[:,]\s*$")


def _gap_is_adjacent(gap: str) -> bool:
    """True when only separators / a short quote-introducing connector separate a
    reference from a quotation."""
    return all(ch in _ADJACENCY_SEPARATORS for ch in gap) or bool(_QUOTE_INTRO_GAP.match(gap))


def _find_adjacent_reference(
    text: str, open_pos: int, close_end: int
) -> tuple[VerseReference, tuple[int, int]] | None:
    """Find a verse reference immediately before or after a quotation.

    Returns (reference, (ref_start, ref_end)) using absolute offsets into ``text``,
    or None when no reference sits directly beside the quote.
    """
    # After the quote: `"…" (John 3:16)`
    after = text[close_end : close_end + _ADJACENCY_WINDOW]
    m = _VERSE_PATTERN.search(after.translate(_BRACKET_TO_SPACE))
    if m and all(ch in _ADJACENCY_SEPARATORS for ch in after[: m.start()]):
        ref = _match_to_verse_reference(m)
        if ref:
            return ref, (close_end + m.start(), close_end + m.end())

    # Before the quote: `John 3:16: "…"` — take the reference closest to the quote.
    start = max(0, open_pos - _ADJACENCY_WINDOW)
    before = text[start:open_pos]
    last = None
    for mm in _VERSE_PATTERN.finditer(before.translate(_BRACKET_TO_SPACE)):
        last = mm
    if last and _gap_is_adjacent(before[last.end() :]):
        ref = _match_to_verse_reference(last)
        if ref:
            return ref, (start + last.start(), start + last.end())
    return None


def extract_inline_quotes(text: str) -> list[InlineQuote]:
    """Find verse text quoted inline next to a parsed reference.

    Detects both orderings — `"…quoted…" (John 3:16)` and `John 3:16: "…quoted…"`
    — across the quotation styles used by the supported languages. Only quotes
    sitting immediately beside a resolvable reference (separated by punctuation /
    whitespace, not other words) are returned, so ordinary quoted phrases are
    ignored. Offsets are reported against ``text`` unchanged so callers can
    substitute corrected text safely.

    Limitations: paraphrases without quotation marks are not detected (the prompt
    rules cover those); a quote is associated with the single nearest reference;
    unbalanced quotation marks are skipped.
    """
    quotes: list[InlineQuote] = []
    seen_spans: set[tuple[int, int]] = set()
    for pattern in _QUOTE_PATTERNS:
        for m in pattern.finditer(text):
            span = (m.start(1), m.end(1))
            if span in seen_spans:
                continue
            found = _find_adjacent_reference(text, m.start(), m.end())
            if not found:
                continue
            ref, ref_span = found
            seen_spans.add(span)
            quotes.append(
                InlineQuote(
                    reference=ref,
                    quoted_text=m.group(1),
                    span=span,
                    ref_span=ref_span,
                )
            )
    quotes.sort(key=lambda q: q.span[0])
    return quotes


def _check_direct_match(book_raw_lower: str) -> str | None:
    """Check if book name matches a known book directly."""
    for known_book in ALL_BOOK_NAMES:
        if known_book.lower() == book_raw_lower:
            return normalize_book_name(known_book)
    return None


def _extract_number_prefix(book_raw: str) -> tuple[str, str]:
    """Extract number prefix from book name like '1 John' or 'I John'."""
    num_match = re.match(r"^([1-3I])\s*", book_raw)
    if num_match:
        prefix = num_match.group(1)
        number = "1" if prefix in ("1", "I") else "2" if prefix == "2" else "3"
        return number, book_raw[num_match.end() :].strip()
    return "", book_raw


def _expand_abbreviation(book_lower: str, number_prefix: str) -> str | None:
    """Expand a book abbreviation to full name."""
    if book_lower not in BOOK_ABBREVIATIONS:
        return None

    expanded = BOOK_ABBREVIATIONS[book_lower]
    # Books that ONLY exist with number prefix
    books_requiring_prefix = ("Corinthians", "Thessalonians", "Timothy", "Peter")

    if expanded in books_requiring_prefix and not number_prefix:
        return None  # Need number prefix for these books

    return f"{number_prefix} {expanded}" if number_prefix else expanded


def _find_book_match(book_lower: str, number_prefix: str) -> str | None:
    """Find a book by direct or partial match."""
    # Try direct match
    for known_book in ALL_BOOK_NAMES:
        if known_book.lower() == book_lower:
            english_name = normalize_book_name(known_book)
            return f"{number_prefix} {english_name}" if number_prefix else english_name

    # Try partial match for abbreviated forms
    if len(book_lower) >= 3:
        for known_book in ALL_BOOK_NAMES:
            if known_book.lower().startswith(book_lower):
                english_name = normalize_book_name(known_book)
                return f"{number_prefix} {english_name}" if number_prefix else english_name

    return None


def _normalize_book(book_raw: str) -> str | None:
    """
    Normalize a book name to standard English.

    Handles abbreviations, numbered books, and localized names.
    """
    book_raw = book_raw.strip()

    # First, check if the FULL book name (including number) matches directly
    result = _check_direct_match(book_raw.lower())
    if result:
        return result

    # Extract number prefix (e.g., "1" from "1 John")
    number_prefix, book_name = _extract_number_prefix(book_raw)
    book_lower = book_name.lower()

    # Check abbreviations
    result = _expand_abbreviation(book_lower, number_prefix)
    if result:
        return result

    # Try direct/partial match
    return _find_book_match(book_lower, number_prefix)


def find_prayer_reference(text: str) -> PrayerReference | None:
    """
    Find a reference to a famous prayer or passage in text.

    Args:
        text: User message to search

    Returns:
        PrayerReference if found, None otherwise
    """
    text_lower = text.lower()

    for pattern, prayer in FAMOUS_PRAYERS.items():
        if pattern in text_lower:
            return prayer

    return None


def extract_references(text: str) -> tuple[list[VerseReference], PrayerReference | None]:
    """
    Extract all verse references and prayer references from text.

    Args:
        text: User message to parse

    Returns:
        Tuple of (list of verse references, optional prayer reference)
    """
    verses: list[VerseReference] = []

    # Find all verse references
    verse_ref = parse_verse_reference(text)
    if verse_ref:
        verses.append(verse_ref)

    # Find prayer reference
    prayer = find_prayer_reference(text)

    # If prayer has a reference, parse it as a verse reference too
    if prayer and prayer.reference:
        prayer_verse = parse_verse_reference(prayer.reference)
        if prayer_verse and prayer_verse not in verses:
            verses.append(prayer_verse)

    return verses, prayer


def is_verse_lookup_request(text: str) -> bool:
    """
    Determine if the user is asking about a specific verse or prayer.

    Looks for patterns like:
    - "What does John 3:16 say?"
    - "Explain Romans 8:28"
    - "Tell me about the Lord's Prayer"
    - "What is the meaning of Psalm 23?"

    Args:
        text: User message

    Returns:
        True if this appears to be a verse/prayer lookup request
    """
    verses, prayer = extract_references(text)

    if verses or prayer:
        # Check for lookup-indicating words
        lookup_patterns = [
            r"\bwhat\s+(?:does|is|did|do)\b",
            r"\bexplain\b",
            r"\btell\s+me\s+about\b",
            r"\bmeaning\s+of\b",
            r"\bunderstand\b",
            r"\binterpret\b",
            r"\bwhat\s+.*\s+mean\b",
            r"\bhelp\s+.*\s+understand\b",
            r"\bread\s+me\b",
            r"\brecite\b",
            r"\bshow\s+me\b",
            r"\bfind\b",
            r"\blook\s+up\b",
            r"\bcosa\s+dice\b",  # Italian: "what does ... say"
            r"\bspiegami\b",  # Italian: "explain to me"
            r"\bwas\s+sagt\b",  # German: "what does ... say"
            r"\berkläre\b",  # German: "explain"
        ]

        text_lower = text.lower()
        for pattern in lookup_patterns:
            if re.search(pattern, text_lower):
                return True

        # Even without lookup words, if they just mention a specific verse, likely a lookup
        return len(verses) > 0

    return False
