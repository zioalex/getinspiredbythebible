package org.voxquieta.app.components

import org.voxquieta.app.presentation.components.buildVerseRefRegex
import org.voxquieta.app.presentation.components.injectVerseLinks
import org.voxquieta.app.presentation.components.parseVerseLink
import org.voxquieta.app.utils.LOCALIZED_BOOK_TO_ENGLISH
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * BITB-059 AC#4 — shared cross-platform verse-reference regression corpus (Android side).
 *
 * Loads tests/fixtures/verse_reference_corpus.json (shared with the Python and web test suites
 * — see tests/fixtures/README.md) and asserts that injectVerseLinks()/parseVerseLink() resolve
 * each non-skipped case to the expected book/chapter/verseStart. The file lives outside the
 * Android module (at the repo root) and is made available to this JVM unit test via the extra
 * `sourceSets["test"].resources.srcDir("../../tests/fixtures")` entry in build.gradle.kts.
 *
 * This is a test-only regression net: it does not change ChatMessageItem.kt.
 *
 * NOTE: this file cannot be run in this environment (no Android SDK). It was written by closely
 * mirroring VerseRefLinkTest.kt's imports/usage of injectVerseLinks / parseVerseLink /
 * buildVerseRefRegex, and ChatScreen.kt's real construction of the multiWordNames /
 * cjkBookNames arguments to buildVerseRefRegex (see the comments below for why).
 */

@Serializable
private data class CorpusExpected(
    val book: String,
    val chapter: Int,
    val verseStart: Int,
    val verseEnd: Int? = null,
)

@Serializable
private data class CorpusCase(
    val id: String,
    val input: String,
    val language: String,
    val expected: CorpusExpected? = null,
    val expectNone: Boolean = false,
    val origin: String,
    val skip: List<String> = emptyList(),
    val skipReason: String = "",
)

@Serializable
private data class VerseReferenceCorpus(
    val description: String,
    @SerialName("test_cases") val testCases: List<CorpusCase>,
)

// Matches the verse:// URL embedded in an injectVerseLinks() markdown link, e.g.
// "**[John 3:16](verse://John/3/16)**" -> "verse://John/3/16". Stops before the closing ')' /
// ']' of the markdown link or any whitespace, so a trailing query string (?localizedBook=...)
// is kept but the surrounding markdown is not.
private val VERSE_URL_REGEX = Regex("""verse://[^)\]\s]+""")

class VerseCorpusParityTest {

    private fun loadCorpus(): VerseReferenceCorpus {
        val stream = javaClass.classLoader?.getResourceAsStream("verse_reference_corpus.json")
            ?: error(
                "verse_reference_corpus.json not found on the test classpath — check the " +
                    "sourceSets[\"test\"].resources.srcDir(\"../../tests/fixtures\") entry in " +
                    "android/app/build.gradle.kts"
            )
        val raw = stream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        return Json { ignoreUnknownKeys = true }.decodeFromString<VerseReferenceCorpus>(raw)
    }

    @Test
    fun `corpus cases resolve to the expected book, chapter, and verse`() {
        val corpus = loadCorpus()

        // Multi-word (non-CJK) book names from the bundled fallback map, excluding
        // number-prefixed keys. This mirrors ChatScreen.kt's `bundledMultiWord` construction
        // exactly (see its comment there): the numbered-prefix branch (Alt 1 in
        // buildVerseRefRegex) already consumes a leading "1"/"2"/"3" itself, so feeding a
        // pre-numbered key like "1 كورنثوس" into the book-name alternation would try to
        // double-consume the digit. Number-prefixed references are still matched fine — via
        // the generic book-name pattern inside Alt 1 — without needing an explicit alternation.
        val multiWordNames = LOCALIZED_BOOK_TO_ENGLISH.keys.filter { it.contains(' ') && !it.first().isDigit() }

        // CJK (Han) and Hangul book names, length >= 2, from the bundled fallback map (there is
        // no runtime API map in a unit test). Both scripts must be included, not just Han:
        // buildVerseRefRegex excludes BOTH \p{IsHan} and \p{IsHangul} from the generic
        // book-name pattern as soon as cjkBookNames is non-empty (see its kdoc), so a Korean
        // case like "요한복음" would stop matching via the generic pattern the moment any Han
        // name is supplied — it must also be present in this list to still match.
        val cjkBookNames = LOCALIZED_BOOK_TO_ENGLISH.keys.filter { key ->
            key.length >= 2 && key.all { ch ->
                val script = Character.UnicodeScript.of(ch.code)
                script == Character.UnicodeScript.HAN || script == Character.UnicodeScript.HANGUL
            }
        }

        val regex = buildVerseRefRegex(multiWordNames, cjkBookNames)
        val failures = mutableListOf<String>()

        for (case in corpus.testCases) {
            if ("android" in case.skip) {
                // Known, tracked divergence (see skipReason in the corpus JSON) — not fixed in
                // this test-only PR. Equivalent to Assume.assumeTrue(false) scoped to this case.
                continue
            }

            val result = injectVerseLinks(case.input, regex)
            val url = VERSE_URL_REGEX.find(result)?.value

            if (case.expectNone) {
                if (url != null) {
                    failures += "${case.id}: expected no verse link for '${case.input}', but got $url"
                }
                continue
            }

            val expected = case.expected
            if (expected == null) {
                failures += "${case.id}: corpus entry has no 'expected' and expectNone is not true"
                continue
            }
            if (url == null) {
                failures += "${case.id}: expected a verse link for '${case.input}', got none (result: $result)"
                continue
            }

            val link = parseVerseLink(url, null)
            if (link == null) {
                failures += "${case.id}: parseVerseLink returned null for $url"
                continue
            }

            if (!link.book.equals(expected.book, ignoreCase = true)) {
                failures += "${case.id}: book mismatch — expected '${expected.book}', got '${link.book}'"
            }
            if (link.chapter != expected.chapter) {
                failures += "${case.id}: chapter mismatch — expected ${expected.chapter}, got ${link.chapter}"
            }
            if (link.verseNumber != expected.verseStart) {
                failures += "${case.id}: verseStart mismatch — expected ${expected.verseStart}, got ${link.verseNumber}"
            }
        }

        assertTrue("Corpus mismatches:\n" + failures.joinToString("\n"), failures.isEmpty())
    }
}
