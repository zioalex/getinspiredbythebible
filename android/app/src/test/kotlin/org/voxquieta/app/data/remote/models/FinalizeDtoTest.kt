package org.voxquieta.app.data.remote.models

import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.voxquieta.app.data.remote.api.ApiClient
import org.voxquieta.app.data.remote.mappers.toDomain
import org.voxquieta.app.data.remote.mappers.toDto
import org.voxquieta.app.domain.models.FinalizeRequest
import org.voxquieta.app.domain.models.Message

/** BITB-320: wire format of `POST /api/v1/chat/finalize`. */
class FinalizeDtoTest {

    private val request = FinalizeRequest(
        message = "What is hope?",
        assistantText = "Hope is...",
        conversationHistory = listOf(
            Message(id = "1", role = Message.Role.ASSISTANT, content = "Earlier", followUps = listOf("Why?")),
        ),
        preferredTranslation = "kjv",
        language = "it",
        sessionId = "sess-1",
        messageId = "5b6c1e0e-6f0e-4c63-b0a2-2f1d6b1f8a11",
        reason = "eof",
    )

    @Test
    fun `request encodes snake_case fields and the platform despite encodeDefaults off`() {
        val body = ApiClient.json.encodeToString(request.toDto())
        val obj = Json.parseToJsonElement(body).jsonObject
        assertEquals("What is hope?", obj["message"]?.jsonPrimitive?.content)
        assertEquals("Hope is...", obj["assistant_text"]?.jsonPrimitive?.content)
        assertEquals("kjv", obj["preferred_translation"]?.jsonPrimitive?.content)
        assertEquals("it", obj["language"]?.jsonPrimitive?.content)
        assertEquals("sess-1", obj["session_id"]?.jsonPrimitive?.content)
        assertEquals("eof", obj["reason"]?.jsonPrimitive?.content)
        assertEquals("android", obj["platform"]?.jsonPrimitive?.content)
        assertEquals(1, obj["conversation_history"]?.jsonArray?.size)
        // The server uses extra="forbid": nothing outside the contract may be sent.
        val allowed = setOf(
            "message", "assistant_text", "conversation_history", "preferred_translation",
            "language", "session_id", "message_id", "reason", "platform",
        )
        assertTrue(obj.keys.all { it in allowed })
    }

    @Test
    fun `blank message id and translation are omitted`() {
        val body = ApiClient.json.encodeToString(
            request.copy(messageId = " ", preferredTranslation = "").toDto(),
        )
        val obj = Json.parseToJsonElement(body).jsonObject
        assertFalse(obj.containsKey("message_id"))
        assertFalse(obj.containsKey("preferred_translation"))
    }

    @Test
    fun `response decodes the completion fields and truncated`() {
        val dto = ApiClient.json.decodeFromString<FinalizeResponseDto>(
            """{"verses_cited":["John 3:16"],"resolved_verses":[{"book":"John","chapter":3,"verse":16,
            "text":"For God so loved","translation":"kjv"}],"corrected_message":"Fixed.",
            "corrections":[{"reference":"John 3:16","reason":"mismatch"}],"follow_ups":["Why?"],
            "truncated":true,"unknown_future_field":1}""",
        )
        val result = dto.toDomain()
        assertEquals(listOf("John 3:16"), result.versesCited)
        assertEquals("For God so loved", result.resolvedVerses.single().text)
        assertEquals("Fixed.", result.correctedMessage)
        assertEquals(listOf("Why?"), result.followUps)
        assertTrue(result.truncated)
    }

    @Test
    fun `response with only truncated false decodes with empty optional fields`() {
        val result = ApiClient.json.decodeFromString<FinalizeResponseDto>("""{"truncated":false}""").toDomain()
        assertTrue(result.versesCited.isEmpty())
        assertTrue(result.followUps.isEmpty())
        assertNull(result.correctedMessage)
        assertFalse(result.truncated)
    }
}
