package org.voxquieta.app.components

import org.voxquieta.app.presentation.components.parseVerseLink
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * Unit tests for [parseVerseLink] in ChatMessageItem.kt.
 *
 * Covers the URL parsing logic: well-formed verse:// URLs, malformed URLs,
 * URL-encoded book names, verse ranges, and preferred translation passthrough.
 */
class ParseVerseLinkTest {

    // ── Well-formed URLs ──────────────────────────────────────────────────────

    @Test
    fun `parseVerseLink returns correct book for simple book name`() {
        val result = parseVerseLink("verse://John/3/16", preferredTranslation = null)
        assertNotNull(result)
        assertEquals("John", result!!.book)
    }

    @Test
    fun `parseVerseLink returns correct chapter`() {
        val result = parseVerseLink("verse://John/3/16", preferredTranslation = null)
        assertNotNull(result)
        assertEquals(3, result!!.chapter)
    }

    @Test
    fun `parseVerseLink returns correct verse number`() {
        val result = parseVerseLink("verse://John/3/16", preferredTranslation = null)
        assertNotNull(result)
        assertEquals(16, result!!.verseNumber)
    }

    @Test
    fun `parseVerseLink returns null translation when preferredTranslation is null`() {
        val result = parseVerseLink("verse://John/3/16", preferredTranslation = null)
        assertNotNull(result)
        assertNull(result!!.translation)
    }

    @Test
    fun `parseVerseLink passes preferredTranslation through to result`() {
        val result = parseVerseLink("verse://John/3/16", preferredTranslation = "KJV")
        assertNotNull(result)
        assertEquals("KJV", result!!.translation)
    }

    @Test
    fun `parseVerseLink passes NIV translation through to result`() {
        val result = parseVerseLink("verse://Romans/8/28", preferredTranslation = "NIV")
        assertNotNull(result)
        assertEquals("NIV", result!!.translation)
    }

    // ── URL-encoded book names ────────────────────────────────────────────────

    @Test
    fun `parseVerseLink decodes plus-encoded space in book name`() {
        val result = parseVerseLink("verse://1+Corinthians/13/4", preferredTranslation = null)
        assertNotNull(result)
        assertEquals("1 Corinthians", result!!.book)
    }

    @Test
    fun `parseVerseLink decodes percent-encoded space in book name`() {
        val result = parseVerseLink("verse://1%20Corinthians/13/4", preferredTranslation = null)
        assertNotNull(result)
        assertEquals("1 Corinthians", result!!.book)
    }

    @Test
    fun `parseVerseLink handles Song+of+Solomon`() {
        val result = parseVerseLink("verse://Song+of+Solomon/2/1", preferredTranslation = null)
        assertNotNull(result)
        assertEquals("Song of Solomon", result!!.book)
    }

    // ── Verse range ───────────────────────────────────────────────────────────

    @Test
    fun `parseVerseLink extracts first verse number from range like 16-17`() {
        val result = parseVerseLink("verse://John/3/16-17", preferredTranslation = null)
        assertNotNull(result)
        assertEquals(16, result!!.verseNumber)
    }

    @Test
    fun `parseVerseLink extracts first verse from multi-verse range 38-39`() {
        val result = parseVerseLink("verse://Romans/8/38-39", preferredTranslation = null)
        assertNotNull(result)
        assertEquals(38, result!!.verseNumber)
    }

    // ── Missing verse segment defaults to 1 ──────────────────────────────────

    @Test
    fun `parseVerseLink defaults verse number to 1 when verse segment is absent`() {
        // URL has only scheme + book + chapter, no verse segment.
        val result = parseVerseLink("verse://Psalms/23", preferredTranslation = null)
        assertNotNull(result)
        assertEquals(1, result!!.verseNumber)
    }

    // ── Different books ───────────────────────────────────────────────────────

    @Test
    fun `parseVerseLink handles Genesis 1 1`() {
        val result = parseVerseLink("verse://Genesis/1/1", preferredTranslation = null)
        assertNotNull(result)
        assertEquals("Genesis", result!!.book)
        assertEquals(1, result.chapter)
        assertEquals(1, result.verseNumber)
    }

    @Test
    fun `parseVerseLink handles Revelation 22 21`() {
        val result = parseVerseLink("verse://Revelation/22/21", preferredTranslation = null)
        assertNotNull(result)
        assertEquals("Revelation", result!!.book)
        assertEquals(22, result.chapter)
        assertEquals(21, result.verseNumber)
    }

    @Test
    fun `parseVerseLink handles 2+Timothy`() {
        val result = parseVerseLink("verse://2+Timothy/3/16", preferredTranslation = null)
        assertNotNull(result)
        assertEquals("2 Timothy", result!!.book)
        assertEquals(3, result.chapter)
        assertEquals(16, result.verseNumber)
    }

    // ── Malformed / invalid URLs ──────────────────────────────────────────────

    @Test
    fun `parseVerseLink returns null for non-verse scheme`() {
        assertNull(parseVerseLink("https://example.com/john/3/16", preferredTranslation = null))
    }

    @Test
    fun `parseVerseLink returns null for http URL`() {
        assertNull(parseVerseLink("http://bible.com", preferredTranslation = null))
    }

    @Test
    fun `parseVerseLink returns null for empty string`() {
        assertNull(parseVerseLink("", preferredTranslation = null))
    }

    @Test
    fun `parseVerseLink returns null for verse scheme with only one path segment`() {
        // verse://OnlyBook — no chapter, so the parse should fail
        assertNull(parseVerseLink("verse://OnlyOneSegment", preferredTranslation = null))
    }

    @Test
    fun `parseVerseLink returns null when chapter is not an integer`() {
        assertNull(parseVerseLink("verse://John/three/16", preferredTranslation = null))
    }

    @Test
    fun `parseVerseLink returns null for bare verse scheme with no path`() {
        assertNull(parseVerseLink("verse://", preferredTranslation = null))
    }

    // ── Localized book name query param ───────────────────────────────────────

    @Test
    fun `parseVerseLink returns null localizedBook when query param absent`() {
        val result = parseVerseLink("verse://John/3/16", preferredTranslation = null)
        assertNotNull(result)
        assertNull(result!!.localizedBook)
    }

    @Test
    fun `parseVerseLink extracts localizedBook from query param`() {
        val result = parseVerseLink("verse://Exodus/30/22?localizedBook=Esodo", preferredTranslation = null)
        assertNotNull(result)
        assertEquals("Exodus", result!!.book)
        assertEquals(30, result.chapter)
        assertEquals(22, result.verseNumber)
        assertEquals("Esodo", result.localizedBook)
    }

    @Test
    fun `parseVerseLink decodes URL-encoded localizedBook with space`() {
        val result = parseVerseLink("verse://1+Corinthians/13/4?localizedBook=1+Corinzi", preferredTranslation = null)
        assertNotNull(result)
        assertEquals("1 Corinthians", result!!.book)
        assertEquals("1 Corinzi", result.localizedBook)
    }

    @Test
    fun `parseVerseLink decodes URL-encoded localizedBook with special char`() {
        val result = parseVerseLink(
            "verse://2+Kings/5/14?localizedBook=2.+K%C3%B6nige",
            preferredTranslation = null,
        )
        assertNotNull(result)
        assertEquals("2 Kings", result!!.book)
        assertEquals("2. Könige", result.localizedBook)
    }

    @Test
    fun `parseVerseLink chapter-only URL with localizedBook query param parses correctly`() {
        val result = parseVerseLink("verse://Psalms/23?localizedBook=Salmi", preferredTranslation = null)
        assertNotNull(result)
        assertEquals("Psalms", result!!.book)
        assertEquals(23, result.chapter)
        assertEquals(1, result.verseNumber)
        assertEquals("Salmi", result.localizedBook)
    }
}
