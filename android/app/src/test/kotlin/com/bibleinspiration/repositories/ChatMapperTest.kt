package com.bibleinspiration.repositories

import com.bibleinspiration.data.remote.mappers.toDomain
import com.bibleinspiration.data.remote.mappers.toDto
import com.bibleinspiration.data.remote.models.ChatResponseDto
import com.bibleinspiration.data.remote.models.StreamChunkDto
import com.bibleinspiration.data.remote.models.VerseDto
import com.bibleinspiration.domain.models.ChatRequest
import com.bibleinspiration.domain.models.Message
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ChatMapperTest {

    @Test
    fun `ChatRequest toDto maps message and conversationHistory`() {
        val request = ChatRequest(
            message = "Hello",
            conversationHistory = listOf(
                Message(id = "1", role = Message.Role.USER, content = "Hi"),
            ),
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
        )
        val dto = request.toDto()

        assertEquals("KJV", dto.preferredTranslation)
    }

    @Test
    fun `ChatRequest toDto maps null preferred translation when not set`() {
        val request = ChatRequest(
            message = "Hello",
            preferredTranslation = null,
        )
        val dto = request.toDto()

        assertNull(dto.preferredTranslation)
    }

    @Test
    fun `ChatRequest toDto converts blank preferred translation to null`() {
        val request = ChatRequest(
            message = "Hello",
            preferredTranslation = "",
        )
        val dto = request.toDto()

        assertNull(dto.preferredTranslation)
    }

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
}
