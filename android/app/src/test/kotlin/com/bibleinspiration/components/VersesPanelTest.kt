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

    @Test
    fun `referencedVerses matches Russian Плач Иеремии`() {
        val lam33 = verse("Lamentations", 3, 3)
        // Russian: "Плач Иеремии" = Lamentations
        val messages = listOf(assistantMsg("В Плач Иеремии 3:3 написано о страдании."))

        val result = referencedVerses(listOf(lam33), messages)

        assertEquals(1, result.size)
        assertEquals(lam33, result[0])
    }

    @Test
    fun `referencedVerses matches Russian numbered book 1 Коринфянам`() {
        val cor134 = verse("1 Corinthians", 13, 4)
        val messages = listOf(assistantMsg("1 Коринфянам 13:4 говорит о любви."))

        val result = referencedVerses(listOf(cor134), messages)

        assertEquals(1, result.size)
    }

    @Test
    fun `referencedVerses matches Russian Откровение`() {
        val rev214 = verse("Revelation", 21, 4)
        val messages = listOf(assistantMsg("Откровение 21:4 говорит о новом небе."))

        val result = referencedVerses(listOf(rev214), messages)

        assertEquals(1, result.size)
    }

    @Test
    fun `referencedVerses matches Chinese 约翰福音`() {
        val john316 = verse("John", 3, 16)
        val messages = listOf(assistantMsg("约翰福音 3:16是著名的经文。"))

        val result = referencedVerses(listOf(john316), messages)

        assertEquals(1, result.size)
        assertEquals(john316, result[0])
    }

    @Test
    fun `referencedVerses matches Chinese 诗篇`() {
        val psalms231 = verse("Psalms", 23, 1)
        val messages = listOf(assistantMsg("诗篇 23:1是安慰的经文。"))

        val result = referencedVerses(listOf(psalms231), messages)

        assertEquals(1, result.size)
        assertEquals(psalms231, result[0])
    }

    @Test
    fun `referencedVerses matches Chinese 耶利米哀歌`() {
        val lam33 = verse("Lamentations", 3, 3)
        val messages = listOf(assistantMsg("耶利米哀歌 3:3讲述苦难。"))

        val result = referencedVerses(listOf(lam33), messages)

        assertEquals(1, result.size)
    }

    @Test
    fun `referencedVerses matches Korean 요한복음`() {
        val john316 = verse("John", 3, 16)
        val messages = listOf(assistantMsg("요한복음 3:16은 유명한 구절입니다."))

        val result = referencedVerses(listOf(john316), messages)

        assertEquals(1, result.size)
        assertEquals(john316, result[0])
    }

    @Test
    fun `referencedVerses matches Korean 시편`() {
        val psalms231 = verse("Psalms", 23, 1)
        val messages = listOf(assistantMsg("시편 23:1은 위로의 구절입니다."))

        val result = referencedVerses(listOf(psalms231), messages)

        assertEquals(1, result.size)
    }

    // ── German book names ────────────────────────────────────────────────────

    @Test
    fun `referencedVerses matches German Johannes`() {
        val john316 = verse("John", 3, 16)
        val messages = listOf(assistantMsg("Lies Johannes 3:16 für Ermutigung."))

        val result = referencedVerses(listOf(john316), messages)

        assertEquals(1, result.size)
    }

    @Test
    fun `referencedVerses matches German Römer with umlaut`() {
        val rom828 = verse("Romans", 8, 28)
        val messages = listOf(assistantMsg("Römer 8:28 ist ein wichtiger Vers."))

        val result = referencedVerses(listOf(rom828), messages)

        assertEquals(1, result.size)
    }

    @Test
    fun `referencedVerses matches German numbered book 1 Mose`() {
        val gen11 = verse("Genesis", 1, 1)
        val messages = listOf(assistantMsg("Am Anfang steht 1. Mose 1:1."))

        val result = referencedVerses(listOf(gen11), messages)

        assertEquals(1, result.size)
    }

    // ── Italian book names ───────────────────────────────────────────────────

    @Test
    fun `referencedVerses matches Italian Giovanni`() {
        val john316 = verse("John", 3, 16)
        val messages = listOf(assistantMsg("Leggi Giovanni 3:16 per incoraggiamento."))

        val result = referencedVerses(listOf(john316), messages)

        assertEquals(1, result.size)
    }

    @Test
    fun `referencedVerses matches Italian Genesi with accent`() {
        val gen11 = verse("Genesis", 1, 1)
        val messages = listOf(assistantMsg("Considera Genesi 1:1."))

        val result = referencedVerses(listOf(gen11), messages)

        assertEquals(1, result.size)
    }

    // ── Spanish book names ───────────────────────────────────────────────────

    @Test
    fun `referencedVerses matches Spanish Juan`() {
        val john316 = verse("John", 3, 16)
        val messages = listOf(assistantMsg("Lee Juan 3:16 para aliento."))

        val result = referencedVerses(listOf(john316), messages)

        assertEquals(1, result.size)
    }

    @Test
    fun `referencedVerses matches Spanish Génesis with accent`() {
        val gen11 = verse("Genesis", 1, 1)
        val messages = listOf(assistantMsg("Génesis 1:1 es el comienzo."))

        val result = referencedVerses(listOf(gen11), messages)

        assertEquals(1, result.size)
    }

    // ── French book names ───────────────────────────────────────────────────

    @Test
    fun `referencedVerses matches French Jean`() {
        val john316 = verse("John", 3, 16)
        val messages = listOf(assistantMsg("Lis Jean 3:16 pour encouragement."))

        val result = referencedVerses(listOf(john316), messages)

        assertEquals(1, result.size)
    }

    @Test
    fun `referencedVerses matches French Genèse with accent`() {
        val gen11 = verse("Genesis", 1, 1)
        val messages = listOf(assistantMsg("Genèse 1:1 est le commencement."))

        val result = referencedVerses(listOf(gen11), messages)

        assertEquals(1, result.size)
    }

    // ── Portuguese book names ──────────────────────────────────────────────

    @Test
    fun `referencedVerses matches Portuguese João with tilde`() {
        val john316 = verse("John", 3, 16)
        val messages = listOf(assistantMsg("Lê João 3:16 para ânimo."))

        val result = referencedVerses(listOf(john316), messages)

        assertEquals(1, result.size)
    }

    @Test
    fun `referencedVerses matches Portuguese Salmos`() {
        val psalms231 = verse("Psalms", 23, 1)
        val messages = listOf(assistantMsg("Salmos 23:1 é reconfortante."))

        val result = referencedVerses(listOf(psalms231), messages)

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
    fun `referencedVerses matches mixed-language message`() {
        val john316 = verse("John", 3, 16)
        val rom828 = verse("Romans", 8, 28)
        // Message mixes English and German
        val messages = listOf(assistantMsg("John 3:16 und Römer 8:28 sind wichtige Verse."))

        val result = referencedVerses(listOf(john316, rom828), messages)

        assertEquals(2, result.size)
    }
}
