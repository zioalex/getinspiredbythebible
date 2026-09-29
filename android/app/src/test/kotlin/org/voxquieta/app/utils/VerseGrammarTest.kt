package org.voxquieta.app.utils

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Guards the bundled verse-grammar constants against silent drift from their canonical
 * source (BITB-113): tests/fixtures/verse_grammar.json, generated into this file by
 * scripts/generate_localized_book_map.py. Loaded from the test classpath via the same
 * sourceSets["test"].resources.srcDir("../../tests/fixtures") entry LocalizedBookToEnglishTest
 * uses.
 */
@Serializable
private data class DigitRangeFixture(val label: String, val start: String, val end: String)

@Serializable
private data class BracketPairFixture(val label: String, val open: String, val close: String)

@Serializable
private data class VerseGrammarFixture(
    val description: String,
    val connector_words: List<String>,
    val connector_repeat_max: Int,
    val chapter_verse_separators: List<String>,
    val range_separators: List<String>,
    val non_ascii_digit_ranges: List<DigitRangeFixture>,
    val cjk_bracket_pairs: List<BracketPairFixture>,
)

class VerseGrammarTest {

    private fun loadCanonicalGrammar(): VerseGrammarFixture {
        val stream =
            javaClass.classLoader?.getResourceAsStream("verse_grammar.json")
                ?: error(
                    "verse_grammar.json not found on the test classpath — check the " +
                        "sourceSets[\"test\"].resources.srcDir(\"../../tests/fixtures\") entry " +
                        "in android/app/build.gradle.kts"
                )
        val raw = stream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        return Json { ignoreUnknownKeys = true }.decodeFromString<VerseGrammarFixture>(raw)
    }

    @Test
    fun `connector words match the canonical JSON`() {
        val canonical = loadCanonicalGrammar()
        assertEquals(
            "VerseGrammar.kt's CONNECTOR_WORDS is out of sync with " +
                "tests/fixtures/verse_grammar.json — run " +
                "`python scripts/generate_localized_book_map.py` and commit the result.",
            canonical.connector_words,
            VerseGrammar.CONNECTOR_WORDS,
        )
    }

    @Test
    fun `connector repeat max matches the canonical JSON`() {
        assertEquals(
            loadCanonicalGrammar().connector_repeat_max,
            VerseGrammar.CONNECTOR_REPEAT_MAX,
        )
    }

    @Test
    fun `chapter verse separators match the canonical JSON`() {
        val canonical = loadCanonicalGrammar().chapter_verse_separators.map { it.single() }
        assertEquals(canonical, VerseGrammar.CHAPTER_VERSE_SEPARATORS)
    }

    @Test
    fun `range separators match the canonical JSON`() {
        val canonical = loadCanonicalGrammar().range_separators.map { it.single() }
        assertEquals(canonical, VerseGrammar.RANGE_SEPARATORS)
    }

    @Test
    fun `non-ASCII digit ranges match the canonical JSON`() {
        val canonical = loadCanonicalGrammar().non_ascii_digit_ranges.map {
            VerseGrammar.DigitRange(it.label, it.start.single(), it.end.single())
        }
        assertEquals(canonical, VerseGrammar.NON_ASCII_DIGIT_RANGES)
    }

    @Test
    fun `CJK bracket pairs match the canonical JSON`() {
        val canonical = loadCanonicalGrammar().cjk_bracket_pairs.map {
            VerseGrammar.BracketPair(it.label, it.open.single(), it.close.single())
        }
        assertEquals(canonical, VerseGrammar.CJK_BRACKET_PAIRS)
    }

    @Test
    fun `connector repeat max is bounded (ReDoS safety, BITB-108-114-117)`() {
        // A permanent guard against silently widening the shared upper bound back toward
        // unbounded (`*` / `+`) — see docs/BACKLOG_STORIES/BITB-108-verse-parser-phase-3-regex-grammar.md.
        assertEquals(3, VerseGrammar.CONNECTOR_REPEAT_MAX)
    }
}
