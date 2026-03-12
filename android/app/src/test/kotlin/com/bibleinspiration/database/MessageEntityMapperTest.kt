package com.bibleinspiration.database

import com.bibleinspiration.data.local.MessageEntity
import com.bibleinspiration.data.local.mappers.toDomain
import com.bibleinspiration.data.local.mappers.toEntity
import com.bibleinspiration.domain.models.Message
import com.bibleinspiration.domain.models.Verse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class MessageEntityMapperTest {

    private val conversationId = "conv-123"

    // ── toEntity ──────────────────────────────────────────────────────────────

    @Test
    fun `user Message toEntity maps role as lowercase string`() {
        val message = Message(id = "m1", role = Message.Role.USER, content = "Hello")
        val entity = message.toEntity(conversationId)

        assertEquals("user", entity.role)
        assertEquals(conversationId, entity.conversationId)
        assertEquals("m1", entity.id)
        assertEquals("Hello", entity.content)
    }

    @Test
    fun `assistant Message toEntity maps role as lowercase string`() {
        val message = Message(id = "m2", role = Message.Role.ASSISTANT, content = "Peace be with you")
        val entity = message.toEntity(conversationId)

        assertEquals("assistant", entity.role)
    }

    @Test
    fun `Message with empty verses produces empty JSON array`() {
        val message = Message(id = "m3", role = Message.Role.USER, content = "Hi")
        val entity = message.toEntity(conversationId)

        assertEquals("[]", entity.versesJson)
    }

    @Test
    fun `Message with verses serialises to non-empty JSON`() {
        val verse = Verse(book = "John", chapter = 3, verse = 16, text = "For God so loved...")
        val message = Message(id = "m4", role = Message.Role.ASSISTANT, content = "See John", verses = listOf(verse))
        val entity = message.toEntity(conversationId)

        // Should contain the book field value in JSON
        assert(entity.versesJson.contains("John")) { "versesJson should contain 'John'" }
        assert(entity.versesJson.contains("16")) { "versesJson should contain the verse number" }
    }

    // ── toDomain ─────────────────────────────────────────────────────────────

    @Test
    fun `MessageEntity with 'user' role maps to USER`() {
        val message = Message(id = "m5", role = Message.Role.USER, content = "Test")
        val entity = message.toEntity(conversationId)
        val domain = entity.toDomain()

        assertEquals(Message.Role.USER, domain.role)
    }

    @Test
    fun `MessageEntity with 'assistant' role maps to ASSISTANT`() {
        val message = Message(id = "m6", role = Message.Role.ASSISTANT, content = "Answer")
        val entity = message.toEntity(conversationId)
        val domain = entity.toDomain()

        assertEquals(Message.Role.ASSISTANT, domain.role)
    }

    @Test
    fun `isStreaming is always false when loaded from entity`() {
        val message = Message(id = "m7", role = Message.Role.ASSISTANT, content = "Done", isStreaming = true)
        val entity = message.toEntity(conversationId)
        val domain = entity.toDomain()

        assertFalse(domain.isStreaming)
    }

    // ── round-trip ───────────────────────────────────────────────────────────

    @Test
    fun `round-trip preserves content and id`() {
        val original = Message(id = "m8", role = Message.Role.USER, content = "Round-trip test")
        val domain = original.toEntity(conversationId).toDomain()

        assertEquals(original.id, domain.id)
        assertEquals(original.content, domain.content)
        assertEquals(original.role, domain.role)
    }

    @Test
    fun `round-trip preserves all verse fields`() {
        val verse = Verse(
            book = "Genesis",
            chapter = 1,
            verse = 1,
            text = "In the beginning...",
            translation = "kjv",
            relevanceScore = 0.95f,
        )
        val original = Message(
            id = "m9",
            role = Message.Role.ASSISTANT,
            content = "Creation",
            verses = listOf(verse),
        )

        val roundTripped = original.toEntity(conversationId).toDomain()

        assertEquals(1, roundTripped.verses.size)
        val rv = roundTripped.verses[0]
        assertEquals("Genesis", rv.book)
        assertEquals(1, rv.chapter)
        assertEquals(1, rv.verse)
        assertEquals("In the beginning...", rv.text)
        assertEquals("kjv", rv.translation)
        assertEquals(0.95f, rv.relevanceScore)
    }

    @Test
    fun `round-trip preserves multiple verses`() {
        val verses = listOf(
            Verse(book = "John", chapter = 3, verse = 16, text = "For God so loved..."),
            Verse(book = "Romans", chapter = 8, verse = 28, text = "All things work..."),
            Verse(book = "Psalm", chapter = 23, verse = 1, text = "The Lord is my shepherd..."),
        )
        val original = Message(
            id = "m10",
            role = Message.Role.ASSISTANT,
            content = "Multiple verses",
            verses = verses,
        )

        val roundTripped = original.toEntity(conversationId).toDomain()

        assertEquals(3, roundTripped.verses.size)
        assertEquals("John", roundTripped.verses[0].book)
        assertEquals("Romans", roundTripped.verses[1].book)
        assertEquals("Psalm", roundTripped.verses[2].book)
    }

    // ── Crash-safety: malformed versesJson ───────────────────────────────────

    @Test
    fun `toDomain returns empty verses for empty versesJson instead of crashing`() {
        val entity = MessageEntity(
            id = "m11",
            conversationId = conversationId,
            role = "assistant",
            content = "Stored message",
            versesJson = "",   // empty string — would previously throw JsonDecodingException
            createdAt = 1000L,
        )

        val domain = entity.toDomain()

        assertTrue("Expected empty verses list", domain.verses.isEmpty())
        assertEquals("m11", domain.id)
        assertEquals("Stored message", domain.content)
    }

    @Test
    fun `toDomain returns empty verses for malformed versesJson instead of crashing`() {
        val entity = MessageEntity(
            id = "m12",
            conversationId = conversationId,
            role = "user",
            content = "Old message",
            versesJson = "NOT_VALID_JSON{{",  // corrupted — would previously crash
            createdAt = 2000L,
        )

        val domain = entity.toDomain()

        assertTrue("Expected empty verses list for corrupted JSON", domain.verses.isEmpty())
        assertEquals("m12", domain.id)
    }

    @Test
    fun `toDomain returns empty verses for null-equivalent versesJson instead of crashing`() {
        val entity = MessageEntity(
            id = "m13",
            conversationId = conversationId,
            role = "assistant",
            content = "Legacy message",
            versesJson = "null",  // some serializers write "null" as the literal string
            createdAt = 3000L,
        )

        val domain = entity.toDomain()

        assertTrue("Expected empty verses list for 'null' string JSON", domain.verses.isEmpty())
    }
}
