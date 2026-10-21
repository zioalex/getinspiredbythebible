package org.voxquieta.app.utils

/**
 * ASCII normalisation helpers for verse references (BITB-179).
 *
 * Both helpers are driven by [VerseGrammar] (generated from tests/fixtures/verse_grammar.json),
 * so a new digit range or range separator in the JSON needs no further code here.
 *
 * Use these wherever a matched reference is turned into data (a `verse://` URL, an `Int`, a
 * speech template). The text shown to the user is left exactly as written.
 */

/**
 * Maps every digit in [VerseGrammar.NON_ASCII_DIGIT_RANGES] (Devanagari, Eastern Arabic,
 * fullwidth, ...) to its ASCII digit. Other characters are returned unchanged.
 */
internal fun normalizeVerseDigits(s: String): String = buildString(s.length) {
    for (ch in s) {
        val range = VerseGrammar.NON_ASCII_DIGIT_RANGES.firstOrNull { ch in it.start..it.end }
        append(if (range != null) '0' + (ch - range.start) else ch)
    }
}

/** Replaces every [VerseGrammar.RANGE_SEPARATORS] character (en dash, tildes, ...) with `-`. */
internal fun normalizeRangeSeparators(s: String): String = buildString(s.length) {
    for (ch in s) {
        append(if (ch in VerseGrammar.RANGE_SEPARATORS) '-' else ch)
    }
}
