package org.voxquieta.app.repositories

import org.voxquieta.app.data.remote.mappers.toDomain
import org.voxquieta.app.data.remote.mappers.toDto
import org.voxquieta.app.data.remote.models.ChatResponseDto
import org.voxquieta.app.data.remote.models.StreamChunkDto
import org.voxquieta.app.data.remote.models.VerseDto
import org.voxquieta.app.domain.models.ChatRequest
import org.voxquieta.app.domain.models.Message
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
        val dto = org.voxquieta.app.data.remote.models.ChatRequestDto(
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

    @Test
    fun `ChatRequest toDto maps language when set`() {
        val request = ChatRequest(
            message = "Ciao",
            sessionId = "any-uuid",
            language = "it",
        )
        val dto = request.toDto()

        assertEquals("it", dto.language)
    }

    @Test
    fun `ChatRequest toDto maps null language when not set`() {
        val request = ChatRequest(
            message = "Hello",
            sessionId = "any-uuid",
        )
        val dto = request.toDto()

        assertNull(dto.language)
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

    // ── GAP-002 tests ─────────────────────────────────────────────────────────

    @Test
    fun `StreamChunkDto toDomain maps messageId and model fields`() {
        val dto = StreamChunkDto(
            type = "metadata",
            content = "",
            done = false,
            messageId = "msg-uuid-001",
            model = "llama3.2",
        )
        val domain = dto.toDomain()

        assertEquals("msg-uuid-001", domain.messageId)
        assertEquals("llama3.2", domain.model)
        assertEquals("", domain.content)
    }

    @Test
    fun `StreamChunkDto toDomain defaults messageId and model to empty string`() {
        val dto = StreamChunkDto(content = "hello", done = false)
        val domain = dto.toDomain()

        assertEquals("", domain.messageId)
        assertEquals("", domain.model)
    }

    @Test
    fun `VerseDto toDomain builds reference correctly`() {
        val dto = VerseDto(book = "Genesis", chapter = 1, verse = 1, text = "In the beginning...", translation = "kjv")
        val verse = dto.toDomain()

        assertEquals("Genesis 1:1", verse.reference)
    }

    @Test
    fun `VerseDto with localizedBook toDomain uses localizedBook in reference`() {
        val dto = VerseDto(book = "John", chapter = 3, verse = 16, text = "For God so loved...", translation = "synodal", localizedBook = "Иоанна")
        val verse = dto.toDomain()

        assertEquals("Иоанна 3:16", verse.reference)
        assertEquals("Иоанна", verse.localizedBook)
    }

    @Test
    fun `VerseDto without localizedBook toDomain falls back to book in reference`() {
        val dto = VerseDto(book = "John", chapter = 3, verse = 16, text = "For God so loved...", translation = "kjv", localizedBook = null)
        val verse = dto.toDomain()

        assertEquals("John 3:16", verse.reference)
        assertNull(verse.localizedBook)
    }
}
