package com.bibleinspiration.repositories

import com.bibleinspiration.data.remote.mappers.toDomain
import com.bibleinspiration.data.remote.mappers.toDto
import com.bibleinspiration.data.remote.models.ChatResponseDto
import com.bibleinspiration.data.remote.models.ScriptureContextDto
import com.bibleinspiration.data.remote.models.ScriptureVerseDto
import com.bibleinspiration.data.remote.models.StreamChunkDto
import com.bibleinspiration.data.remote.models.VerseDto
import com.bibleinspiration.domain.models.ChatRequest
import com.bibleinspiration.domain.models.Message
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ChatMapperTest {

    @Test
    fun `ChatRequest toDto maps message and conversationHistory`() {
        val request = ChatRequest(
            message = "Hello",
            conversationHistory = listOf(
                Message(id = "1", role = Message.Role.USER, content = "Hi"),
            ),
            sessionId = "test-session-id",
        )
        val dto = request.toDto()

        assertEquals("Hello", dto.message)
        assertEquals(1, dto.conversationHistory.size)
        assertEquals("user", dto.conversationHistory[0].role)
        assertEquals("Hi", dto.conversationHistory[0].content)
    }

    @Test
    fun `ChatRequest toDto maps preferred translation when set`() {
        val request = ChatRequest(
            message = "Hello",
            preferredTranslation = "KJV",
            sessionId = "test-session-id",
        )
        val dto = request.toDto()

        assertEquals("KJV", dto.preferredTranslation)
    }

    @Test
    fun `ChatRequest toDto maps null preferred translation when not set`() {
        val request = ChatRequest(
            message = "Hello",
            preferredTranslation = null,
            sessionId = "test-session-id",
        )
        val dto = request.toDto()

        assertNull(dto.preferredTranslation)
    }

    @Test
    fun `ChatRequest toDto converts blank preferred translation to null`() {
        val request = ChatRequest(
            message = "Hello",
            preferredTranslation = "",
            sessionId = "test-session-id",
        )
        val dto = request.toDto()

        assertNull(dto.preferredTranslation)
    }

    // ── GAP-001 tests ─────────────────────────────────────────────────────────

    @Test
    fun `ChatRequestDto includes include_search true by default`() {
        val dto = com.bibleinspiration.data.remote.models.ChatRequestDto(
            message = "hi",
            sessionId = "test-uuid",
        )
        assertTrue(dto.includeSearch)
    }

    @Test
    fun `ChatRequest toDto maps session_id correctly`() {
        val request = ChatRequest(
            message = "hi",
            sessionId = "my-session-id",
        )
        val dto = request.toDto()

        assertEquals("my-session-id", dto.sessionId)
        assertTrue(dto.includeSearch)
    }

    @Test
    fun `ChatRequest toDto always sets includeSearch to true`() {
        val request = ChatRequest(
            message = "Hello",
            sessionId = "any-uuid",
        )
        val dto = request.toDto()

        assertTrue(dto.includeSearch)
    }

    // ── Existing domain mapper tests ──────────────────────────────────────────

    @Test
    fun `ChatResponseDto toDomain maps verses`() {
        val dto = ChatResponseDto(
            message = "God loves you",
            verses = listOf(
                VerseDto(book = "John", chapter = 3, verse = 16, text = "For God so loved...", translation = "kjv", relevanceScore = 0.9f),
            ),
        )
        val domain = dto.toDomain()

        assertEquals("God loves you", domain.message)
        assertEquals(1, domain.verses.size)
        assertEquals("John 3:16", domain.verses[0].reference)
        assertEquals(0.9f, domain.verses[0].relevanceScore)
    }

    @Test
    fun `StreamChunkDto toDomain maps done flag`() {
        val dto = StreamChunkDto(content = "partial", done = false)
        val domain = dto.toDomain()

        assertEquals("partial", domain.content)
        assertEquals(false, domain.done)
    }

    @Test
    fun `VerseDto toDomain builds reference correctly`() {
        val dto = VerseDto(book = "Genesis", chapter = 1, verse = 1, text = "In the beginning...", translation = "kjv")
        val verse = dto.toDomain()

        assertEquals("Genesis 1:1", verse.reference)
    }

    // ── GAP-002: metadata chunk mapper tests ─────────────────────────────────

    @Test
    fun `StreamChunkDto toDomain maps metadata type fields`() {
        val dto = StreamChunkDto(
            type = "metadata",
            messageId = "abc-123",
            model = "gpt-4o",
        )
        val domain = dto.toDomain()

        assertEquals("metadata", domain.type)
        assertEquals("abc-123", domain.messageId)
        assertEquals("gpt-4o", domain.model)
        assertNull(domain.scriptureContext)
    }

    @Test
    fun `StreamChunkDto toDomain maps scripture_context with verses`() {
        val dto = StreamChunkDto(
            type = "metadata",
            messageId = "msg-1",
            model = "claude-3-5-sonnet",
            scriptureContext = ScriptureContextDto(
                query = "love",
                verses = listOf(
                    ScriptureVerseDto(
                        book = "John",
                        chapter = 3,
                        verse = 16,
                        text = "For God so loved the world...",
                        translation = "NIV",
                        reference = "John 3:16",
                        similarity = 0.95f,
                    ),
                ),
            ),
        )
        val domain = dto.toDomain()

        assertEquals("metadata", domain.type)
        assertEquals("msg-1", domain.messageId)
        assertEquals("claude-3-5-sonnet", domain.model)

        val ctx = domain.scriptureContext!!
        assertEquals("love", ctx.query)
        assertEquals(1, ctx.verses.size)

        val verse = ctx.verses[0]
        assertEquals("John", verse.book)
        assertEquals(3, verse.chapter)
        assertEquals(16, verse.verse)
        assertEquals("For God so loved the world...", verse.text)
        assertEquals("NIV", verse.translation)
        assertEquals("John 3:16", verse.reference)
        assertEquals(0.95f, verse.similarity)
    }

    @Test
    fun `StreamChunkDto toDomain maps content chunk type`() {
        val dto = StreamChunkDto(
            type = "content",
            content = "Hello, world!",
        )
        val domain = dto.toDomain()

        assertEquals("content", domain.type)
        assertEquals("Hello, world!", domain.content)
        assertNull(domain.scriptureContext)
        assertNull(domain.messageId)
        assertNull(domain.model)
    }

    @Test
    fun `StreamChunkDto toDomain maps null type for legacy chunks`() {
        val dto = StreamChunkDto(
            content = "legacy content",
            done = true,
        )
        val domain = dto.toDomain()

        assertNull(domain.type)
        assertEquals("legacy content", domain.content)
        assertTrue(domain.done)
    }

    @Test
    fun `ScriptureContextDto toDomain with empty verses returns empty list`() {
        val dto = ScriptureContextDto(query = "hope", verses = emptyList())
        val domain = dto.toDomain()

        assertEquals("hope", domain.query)
        assertTrue(domain.verses.isEmpty())
    }

    @Test
    fun `ScriptureVerseDto toDomain maps all fields`() {
        val dto = ScriptureVerseDto(
            book = "Psalms",
            chapter = 23,
            verse = 1,
            text = "The Lord is my shepherd",
            translation = "KJV",
            reference = "Psalms 23:1",
            similarity = 0.88f,
        )
        val domain = dto.toDomain()

        assertEquals("Psalms", domain.book)
        assertEquals(23, domain.chapter)
        assertEquals(1, domain.verse)
        assertEquals("The Lord is my shepherd", domain.text)
        assertEquals("KJV", domain.translation)
        assertEquals("Psalms 23:1", domain.reference)
        assertEquals(0.88f, domain.similarity)
    }
}


