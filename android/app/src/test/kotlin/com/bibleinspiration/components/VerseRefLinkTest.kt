package com.bibleinspiration.components

import com.bibleinspiration.presentation.components.handleVerseLink
import com.bibleinspiration.presentation.components.injectVerseLinks
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class VerseRefLinkTest {

    // ── injectVerseLinks ──────────────────────────────────────────────────────

    @Test
    fun `injectVerseLinks wraps simple verse reference`() {
        val input = "As Jesus said in John 3:16, God so loved the world."
        val result = injectVerseLinks(input)
        assertTrue("should contain markdown link", result.contains("[John 3:16](verse://John/3/16)"))
        assertTrue("should not contain bare ref", !result.contains("in John 3:16,"))
    }

    @Test
    fun `injectVerseLinks wraps numbered book reference`() {
        val input = "See 1 Corinthians 13:4 for love."
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[1 Corinthians 13:4]"))
        assertTrue(result.contains("verse://1+Corinthians/13/4") || result.contains("verse://1%20Corinthians/13/4"))
    }

    @Test
    fun `injectVerseLinks wraps verse range reference`() {
        val input = "Romans 8:38-39 tells us nothing can separate us."
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Romans 8:38-39]"))
    }

    @Test
    fun `injectVerseLinks leaves plain text unchanged when no verse refs present`() {
        val input = "God is love."
        val result = injectVerseLinks(input)
        assertEquals(input, result)
    }

    @Test
    fun `injectVerseLinks does not double-link already linked verse refs`() {
        val input = "[John 3:16](verse://John/3/16)"
        val result = injectVerseLinks(input)
        // Should remain unchanged — the negative look-behind prevents re-wrapping
        assertEquals(input, result)
    }

    @Test
    fun `injectVerseLinks wraps multiple verse references in one message`() {
        val input = "John 3:16 and Romans 5:8 are key verses."
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[John 3:16]"))
        assertTrue(result.contains("[Romans 5:8]"))
    }

    // ── handleVerseLink ───────────────────────────────────────────────────────

    @Test
    fun `handleVerseLink calls onLoadChapter with correct book and chapter`() {
        var calledBook: String? = null
        var calledChapter: Int? = null
        var calledTranslation: String? = null

        handleVerseLink(
            url = "verse://John/3/16",
            preferredTranslation = null,
        ) { book, chapter, translation ->
            calledBook = book
            calledChapter = chapter
            calledTranslation = translation
        }

        assertEquals("John", calledBook)
        assertEquals(3, calledChapter)
        assertEquals(null, calledTranslation)
    }

    @Test
    fun `handleVerseLink passes preferredTranslation`() {
        var calledTranslation: String? = "not-set"

        handleVerseLink(
            url = "verse://Romans/5/8",
            preferredTranslation = "KJV",
        ) { _, _, translation ->
            calledTranslation = translation
        }

        assertEquals("KJV", calledTranslation)
    }

    @Test
    fun `handleVerseLink ignores non-verse urls`() {
        var called = false

        handleVerseLink(
            url = "https://example.com",
            preferredTranslation = null,
        ) { _, _, _ -> called = true }

        assertTrue("should not call onLoadChapter for non-verse URL", !called)
    }

    @Test
    fun `handleVerseLink ignores malformed verse url`() {
        var called = false

        handleVerseLink(
            url = "verse://OnlyOneSegment",
            preferredTranslation = null,
        ) { _, _, _ -> called = true }

        assertTrue("should not call onLoadChapter for malformed URL", !called)
    }

    @Test
    fun `handleVerseLink decodes URL-encoded book name`() {
        var calledBook: String? = null

        // 1+Corinthians or 1%20Corinthians — both should decode to "1 Corinthians"
        handleVerseLink(
            url = "verse://1+Corinthians/13/4",
            preferredTranslation = null,
        ) { book, _, _ ->
            calledBook = book
        }

        assertEquals("1 Corinthians", calledBook)
    }
}
