package org.voxquieta.app.components

import org.voxquieta.app.domain.models.Message
import org.voxquieta.app.domain.models.Verse
import org.voxquieta.app.presentation.components.referencedVerses
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.UUID

class VersesPanelTest {

    private fun assistantMsg(content: String) = Message(
        id = UUID.randomUUID().toString(),
        role = Message.Role.ASSISTANT,
        content = content,
    )

    private fun userMsg(content: String) = Message(
        id = UUID.randomUUID().toString(),
        role = Message.Role.USER,
        content = content,
    )

    private fun verse(book: String, chapter: Int, verseNum: Int, translation: String = "kjv") =
        Verse(book = book, chapter = chapter, verse = verseNum, text = "text", translation = translation)

    // ─────────────────────────────────────────────────────────────────────────

    @Test
    fun `referencedVerses returns verse explicitly cited in assistant message`() {
        val john316 = verse("John", 3, 16)
        val messages = listOf(assistantMsg("See John 3:16 for more context."))

        val result = referencedVerses(listOf(john316), messages)

        assertEquals(1, result.size)
        assertEquals(john316, result[0])
    }

    @Test
    fun `referencedVerses excludes verse not cited in any message`() {
        val john316 = verse("John", 3, 16)
        val psalms23 = verse("Psalms", 23, 1)
        val messages = listOf(assistantMsg("See John 3:16 for hope."))

        val result = referencedVerses(listOf(john316, psalms23), messages)

        assertEquals(1, result.size)
        assertEquals(john316, result[0])
    }

    @Test
    fun `referencedVerses returns empty list when allVerses is empty`() {
        val messages = listOf(assistantMsg("John 3:16 is a great verse."))

        val result = referencedVerses(emptyList(), messages)

        assertTrue(result.isEmpty())
    }

    @Test
    fun `referencedVerses returns empty list when messages list is empty`() {
        val john316 = verse("John", 3, 16)

        val result = referencedVerses(listOf(john316), emptyList())

        assertTrue(result.isEmpty())
    }

    @Test
    fun `referencedVerses returns all verses when all are cited`() {
        val john316 = verse("John", 3, 16)
        val psalms23 = verse("Psalms", 23, 1)
        val genesis11 = verse("Genesis", 1, 1)
        val messages = listOf(
            assistantMsg("As written in John 3:16 and Psalms 23:1, also Genesis 1:1."),
        )

        val result = referencedVerses(listOf(john316, psalms23, genesis11), messages)

        assertEquals(3, result.size)
    }

    @Test
    fun `referencedVerses ignores user messages for citation matching`() {
        val john316 = verse("John", 3, 16)
        // Cite the verse only in a user message — should NOT count as referenced
        val messages = listOf(
            userMsg("Can you explain John 3:16?"),
            assistantMsg("It speaks about God's love for humanity."),
        )

        val result = referencedVerses(listOf(john316), messages)

        assertTrue(result.isEmpty())
    }

    @Test
    fun `referencedVerses aggregates citations across multiple assistant messages`() {
        val john316 = verse("John", 3, 16)
        val psalms23 = verse("Psalms", 23, 1)
        val messages = listOf(
            assistantMsg("First, consider John 3:16."),
            assistantMsg("Also, Psalms 23:1 brings comfort."),
        )

        val result = referencedVerses(listOf(john316, psalms23), messages)

        assertEquals(2, result.size)
    }

    @Test
    fun `referencedVerses matches verse range reference eg John 3 16-17`() {
        val john316 = verse("John", 3, 16)
        // The regex captures "John 3:16-17"; baseRef "John 3:16" should match via startsWith
        val messages = listOf(assistantMsg("Read John 3:16-17 carefully."))

        val result = referencedVerses(listOf(john316), messages)

        assertEquals(1, result.size)
        assertEquals(john316, result[0])
    }

    @Test
    fun `referencedVerses handles book names with numeric prefix`() {
        val firstCor13 = verse("1 Corinthians", 13, 4)
        val messages = listOf(assistantMsg("Love is patient — see 1 Corinthians 13:4."))

        val result = referencedVerses(listOf(firstCor13), messages)

        assertEquals(1, result.size)
        assertEquals(firstCor13, result[0])
    }

    @Test
    fun `referencedVerses does not return duplicates when same verse cited twice in one message`() {
        val john316 = verse("John", 3, 16)
        // Cited twice in a single message; the verse object is in the list once
        val messages = listOf(assistantMsg("John 3:16 is important. Again, John 3:16."))

        val result = referencedVerses(listOf(john316), messages)

        assertEquals(1, result.size)
    }

    // ── Multi-word book names ────────────────────────────────────────────────

    @Test
    fun `referencedVerses matches multi-word book Song of Solomon`() {
        val song21 = verse("Song of Solomon", 2, 1)
        val messages = listOf(assistantMsg("Song of Solomon 2:1 speaks of love."))

        val result = referencedVerses(listOf(song21), messages)

        assertEquals(1, result.size)
        assertEquals(song21, result[0])
    }

    @Test
    fun `referencedVerses matches Song of Solomon with verse range`() {
        val song21 = verse("Song of Solomon", 2, 1)
        val messages = listOf(assistantMsg("Read Song of Solomon 2:1-5 for the wedding."))

        val result = referencedVerses(listOf(song21), messages)

        assertEquals(1, result.size)
    }

    // ── Non-Latin book names ─────────────────────────────────────────────────
    // NOTE: referencedVerses compares the regex-extracted book name (from the message)
    // against Verse.book (the backend's English name). Cross-language matching
    // (e.g. "Johannes" vs "John") is not supported — those tests are intentionally
    // omitted. These tests verify that the regex correctly extracts the citation
    // from non-Latin text, using the SAME book name in both the message and the verse.

    @Test
    fun `referencedVerses matches same-language citation with Unicode book name`() {
        // When the verse.book matches the localized name in the message, it works.
        val verse = verse("Иоанн", 3, 16)
        val messages = listOf(assistantMsg("читайте Иоанн 3:16 для вдохновения."))

        val result = referencedVerses(listOf(verse), messages)

        assertEquals(1, result.size)
        assertEquals(verse, result[0])
    }

    @Test
    fun `referencedVerses matches CJK book name when verse book matches`() {
        val verse = verse("约翰福音", 3, 16)
        val messages = listOf(assistantMsg("约翰福音 3:16是著名的经文。"))

        val result = referencedVerses(listOf(verse), messages)

        assertEquals(1, result.size)
    }

    @Test
    fun `referencedVerses matches Korean book name when verse book matches`() {
        val verse = verse("요한복음", 3, 16)
        val messages = listOf(assistantMsg("요한복음 3:16은 유명한 구절입니다."))

        val result = referencedVerses(listOf(verse), messages)

        assertEquals(1, result.size)
    }

    @Test
    fun `referencedVerses matches German book with umlaut when verse book matches`() {
        val rom828 = verse("Römer", 8, 28)
        val messages = listOf(assistantMsg("Römer 8:28 ist ein wichtiger Vers."))

        val result = referencedVerses(listOf(rom828), messages)

        assertEquals(1, result.size)
    }

    @Test
    fun `referencedVerses matches German numbered book 1 Mose with period`() {
        val gen11 = verse("1. Mose", 1, 1)
        val messages = listOf(assistantMsg("am Anfang steht 1. Mose 1:1."))

        val result = referencedVerses(listOf(gen11), messages)

        assertEquals(1, result.size)
    }

    // ── Edge cases ──────────────────────────────────────────────────────────

    @Test
    fun `referencedVerses does not match chapter-verse without book name`() {
        val john316 = verse("John", 3, 16)
        val messages = listOf(assistantMsg("Verse 3:16 is well known."))

        val result = referencedVerses(listOf(john316), messages)

        // "Verse 3:16" should NOT match — no valid book name before "3:16"
        assertTrue(result.isEmpty())
    }

    @Test
    fun `referencedVerses matches mixed-language message with same-lang verse names`() {
        val john316 = verse("John", 3, 16)
        val rom828 = verse("Römer", 8, 28)
        // Message mixes English and German; verse names match the respective language
        val messages = listOf(assistantMsg("John 3:16 und Römer 8:28 sind wichtige Verse."))

        val result = referencedVerses(listOf(john316, rom828), messages)

        assertEquals(2, result.size)
    }
}
