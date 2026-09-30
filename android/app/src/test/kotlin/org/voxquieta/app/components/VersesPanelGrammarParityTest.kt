package org.voxquieta.app.components

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.voxquieta.app.domain.models.Message
import org.voxquieta.app.domain.models.Verse
import org.voxquieta.app.presentation.components.injectVerseLinks
import org.voxquieta.app.presentation.components.parseVerseLink
import org.voxquieta.app.presentation.components.referencedVerses
import org.voxquieta.app.utils.VerseGrammar

/**
 * BITB-164 — the Cited-tab fallback ([referencedVerses]) now reuses the shared
 * DEFAULT_VERSE_REF_REGEX (composed from VerseGrammar.kt). This test is data-driven from
 * [VerseGrammar] so a grammar addition is automatically exercised against the Cited tab, and
 * asserts that [referencedVerses] and [injectVerseLinks] agree on every generated input.
 */
class VersesPanelGrammarParityTest {

    private val john316 = Verse(book = "John", chapter = 3, verse = 16, text = "")

    private fun assistant(text: String) =
        Message(id = "m", role = Message.Role.ASSISTANT, content = text)

    private fun cited(text: String, verses: List<Verse>, map: Map<String, String> = emptyMap()) =
        referencedVerses(verses, listOf(assistant(text)), map)

    // Compare the parsed link, not the raw URL: injectVerseLinks keeps the source digits
    // (e.g. "verse://John/३/१६") and may emit the bundled map's lowercase canonical
    // ("verse://john/3/16"); toIntOrNull handles the non-ASCII digits. The verse segment is
    // read here (split on every range separator) rather than via parseVerseLink.verseNumber,
    // which splits on '-' only and so falls back to verse 1 for an en-dash range.
    private fun linked(text: String, map: Map<String, String> = emptyMap()): Boolean {
        val url = Regex("""verse://[^)\]\s]+""").find(injectVerseLinks(text, localizedToEnglish = map))?.value
            ?: return false
        val link = parseVerseLink(url, null) ?: return false
        val verseSegment = url.removePrefix("verse://").substringBefore('?').split("/").getOrNull(2)
        val verseStart = verseSegment
            ?.split(*VerseGrammar.RANGE_SEPARATORS.toCharArray())?.first()?.toIntOrNull()
        return link.book.equals("John", ignoreCase = true) && link.chapter == 3 && verseStart == 16
    }

    private fun assertBothAgree(text: String, map: Map<String, String> = emptyMap()) {
        assertEquals("referencedVerses for '$text'", listOf(john316), cited(text, listOf(john316), map))
        assertTrue("injectVerseLinks for '$text'", linked(text, map))
    }

    @Test
    fun `every chapter-verse separator crossed with every range separator is recognised`() {
        for (sep in VerseGrammar.CHAPTER_VERSE_SEPARATORS) {
            for (range in VerseGrammar.RANGE_SEPARATORS) {
                assertBothAgree("See John 3${sep}16${range}18 today")
            }
            assertBothAgree("See John 3${sep}16 today")
        }
    }

    @Test
    fun `every non-ASCII digit range is recognised as chapter and verse digits`() {
        for (r in VerseGrammar.NON_ASCII_DIGIT_RANGES) {
            // chapter "3" = start+3; verse "16" = start+1, start+6 (all ranges are 10 wide, 0-9).
            val chapter = (r.start + 3).toString()
            val verse = (r.start + 1).toString() + (r.start + 6).toString()
            assertBothAgree("John $chapter:$verse")
        }
    }

    @Test
    fun `every connector word is allowed inside a multi-word book name`() {
        for (w in VerseGrammar.CONNECTOR_WORDS) {
            val bookName = "Xyl $w Zor"
            val text = "Xyl $w Zor 3:16"
            // Runtime map teaches both scanners that the synthetic name is John.
            val map = mapOf(bookName to "John")
            assertBothAgree(text, map)
        }
    }

    @Test
    fun `every CJK bracket pair may wrap the book name`() {
        for (pair in VerseGrammar.CJK_BRACKET_PAIRS) {
            assertBothAgree("${pair.open}约翰福音${pair.close}3:16")
        }
    }

    @Test
    fun `chapter-only references are not citations`() {
        assertTrue(cited("Read John 3 tonight", listOf(john316)).isEmpty())
    }
}
