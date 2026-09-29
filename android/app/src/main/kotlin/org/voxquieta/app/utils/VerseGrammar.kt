package org.voxquieta.app.utils

/**
 * Literal separator/range/connector grammar fragments shared by the verse-reference
 * parsers (BITB-113).
 *
 * Canonical source: tests/fixtures/verse_grammar.json. The web copy
 * (frontend/src/lib/verseGrammar.generated.ts) is generated from the same file. The
 * backend (api/utils/verse_parser.py) is a separate master for its own separator/range
 * characters, held contradiction-free by api/tests/test_verse_grammar_parity.py — Python
 * has no compositional connector-word grammar to unify (see that test's docstring) and its
 * `\d` is already Unicode-aware, so it does not need the connector words or non-ASCII
 * digit ranges below.
 *
 * ChatMessageItem.kt composes these into its own regex fragments — this object exposes
 * plain constants only, never a compiled Regex.
 *
 * [CONNECTOR_REPEAT_MAX] is the shared UPPER bound only (the ReDoS-safety cap from
 * BITB-108/114/117: an unbounded connector-repeat quantifier let adversarial input drive
 * superlinear regex backtracking). The *lower* bound on the connector-repeat quantifier is
 * NOT generated here and legitimately differs between ChatMessageItem.kt's BOOK_NAME
 * (minimum 0 — one pattern shared by single- and multi-word books) and versePatterns.ts
 * (minimum 1 in its dedicated "word CONNECTOR word" fallback branch — single-word books
 * are matched by a separate branch there). See
 * docs/BACKLOG_STORIES/BITB-113-verse-parser-grammar-unification.md for the full
 * investigation of that discrepancy.
 *
 * @generated from tests/fixtures/verse_grammar.json by
 * scripts/generate_localized_book_map.py — DO NOT EDIT individual entries by hand. Edit
 * the JSON and re-run the generator; VerseGrammarTest checks content equivalence against
 * the JSON so drift fails CI.
 */
internal object VerseGrammar {
    /** Connector words joined between two book-name words (e.g. "of" in "Song of Solomon"). */
    val CONNECTOR_WORDS: List<String> = listOf(
        "of",
        "dei",
        "des",
        "der",
        "van",
        "de",
        "af",
        "dos",
        "da",
        "del",
        "के",
        "ال",
    )

    /** Upper bound for repeated connector-word groups (ReDoS-safety bound, BITB-108/114/117). */
    const val CONNECTOR_REPEAT_MAX: Int = 3

    /** Chapter/verse separator characters (colon, comma). */
    val CHAPTER_VERSE_SEPARATORS: List<Char> = listOf(':', ',')

    /** Verse-range separator characters (hyphen, en dash). */
    val RANGE_SEPARATORS: List<Char> = listOf('-', '–')

    /** Non-ASCII digit range: [start, end] Unicode codepoints, with a language label. */
    data class DigitRange(val label: String, val start: Char, val end: Char)

    /** Non-ASCII digit ranges the chapter/verse number class must also match. */
    val NON_ASCII_DIGIT_RANGES: List<DigitRange> = listOf(
        DigitRange("Devanagari (Hindi)", '०', '९'),
        DigitRange("Eastern Arabic-Indic", '٠', '٩'),
    )

    /** CJK/Korean bracket pair that may wrap a book name in a citation, with a label. */
    data class BracketPair(val label: String, val open: Char, val close: Char)

    /** CJK/Korean bracket pairs that may wrap a book name in a citation. */
    val CJK_BRACKET_PAIRS: List<BracketPair> = listOf(
        BracketPair("Chinese guillemets", '《', '》'),
        BracketPair("Korean corner brackets", '「', '」'),
        BracketPair("Korean white corner brackets", '『', '』'),
    )
}
