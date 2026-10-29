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
    fun `StreamChunkDto toDomain maps resolved_verses to domain verses`() {
        val dto = StreamChunkDto(
            type = "completion",
            versesCited = listOf("John 14:27"),
            resolvedVerses = listOf(
                VerseDto(book = "John", chapter = 14, verse = 27, text = "Peace I leave with you...", translation = "kjv"),
            ),
        )
        val domain = dto.toDomain()

        assertEquals(1, domain.resolvedVerses.size)
        assertEquals("John", domain.resolvedVerses[0].book)
        assertEquals(27, domain.resolvedVerses[0].verse)
    }

    @Test
    fun `StreamChunkDto toDomain defaults resolved_verses to empty list`() {
        val dto = StreamChunkDto(content = "hi", done = false)
        val domain = dto.toDomain()

        assertTrue(domain.resolvedVerses.isEmpty())
    }

    // ── BITB-149 tests ────────────────────────────────────────────────────────

    @Test
    fun `StreamChunkDto toDomain maps follow_ups to domain followUps`() {
        val dto = StreamChunkDto(
            type = "completion",
            followUps = listOf("x", "y"),
        )
        val domain = dto.toDomain()

        assertEquals(listOf("x", "y"), domain.followUps)
    }

    @Test
    fun `StreamChunkDto toDomain defaults followUps to empty list`() {
        val dto = StreamChunkDto(content = "hi", done = false)
        val domain = dto.toDomain()

        assertTrue(domain.followUps.isEmpty())
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

    // ── BITB-251: region + crisis card contract ──────────────────────────────

    @Test
    fun `ChatRequest toDto maps a 2-letter region upper-cased and the override flag`() {
        val dto = ChatRequest(message = "hi", sessionId = "s", region = "ch", regionOverride = true).toDto()

        assertEquals("CH", dto.region)
        assertTrue(dto.regionOverride)
        assertTrue(dto.supportsCrisisCard)
    }

    @Test
    fun `ChatRequest toDto drops an invalid region`() {
        assertNull(ChatRequest(message = "hi", sessionId = "s", region = "").toDto().region)
        assertNull(ChatRequest(message = "hi", sessionId = "s", region = "USA").toDto().region)
        assertNull(ChatRequest(message = "hi", sessionId = "s", region = "1A").toDto().region)
    }

    @Test
    fun `request JSON always carries supports_crisis_card and region_override`() {
        val json = org.voxquieta.app.data.remote.api.ApiClient.json
        val body = json.encodeToString(
            org.voxquieta.app.data.remote.models.ChatRequestDto.serializer(),
            ChatRequest(message = "hi", sessionId = "s").toDto(),
        )

        assertTrue(body, body.contains("\"supports_crisis_card\":true"))
        assertTrue(body, body.contains("\"region_override\":false"))
        assertTrue("region is omitted when unknown: $body", !body.contains("\"region\":"))
    }

    @Test
    fun `request JSON carries the picked region with region_override true`() {
        val json = org.voxquieta.app.data.remote.api.ApiClient.json
        val body = json.encodeToString(
            org.voxquieta.app.data.remote.models.ChatRequestDto.serializer(),
            ChatRequest(message = "hi", sessionId = "s", region = "AT", regionOverride = true).toDto(),
        )

        assertTrue(body, body.contains("\"region\":\"AT\""))
        assertTrue(body, body.contains("\"region_override\":true"))
    }

    @Test
    fun `StreamChunkDto maps crisis resources to the domain model`() {
        val dto = StreamChunkDto(
            type = "crisis_resources",
            crisisResources = org.voxquieta.app.data.remote.models.CrisisResourcesDto(
                kind = "threat_to_others",
                country = "US",
                emergency = org.voxquieta.app.data.remote.models.CrisisEmergencyDto("911"),
                lines = listOf(org.voxquieta.app.data.remote.models.CrisisLineDto(name = "988", phone = "988")),
                availableCountries = listOf("US", "CA"),
            ),
        )

        val card = dto.toDomain().crisisResources!!

        assertEquals("threat_to_others", card.kind)
        assertEquals("911", card.emergencyNumber)
        assertEquals("988", card.lines.single().phone)
        assertEquals(listOf("US", "CA"), card.availableCountries)
    }

    @Test
    fun `ChatResponseDto maps a null crisis_resources to null`() {
        assertNull(ChatResponseDto(message = "x").toDomain().crisisResources)
    }
}
