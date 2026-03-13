package com.bibleinspiration.components

import com.bibleinspiration.domain.models.Message
import com.bibleinspiration.domain.models.Verse
import com.bibleinspiration.presentation.components.referencedVerses
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
    fun `referencedVerses matches verse range reference (e-g John 3:16-17)`() {
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
}
