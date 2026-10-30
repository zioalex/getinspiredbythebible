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
import org.voxquieta.app.data.remote.mappers.toConversationMessageDto
import org.voxquieta.app.domain.models.Message

/** BITB-254: follow-up chips are echoed back in conversation_history. */
class ConversationMessageDtoTest {

    private fun msg(role: Message.Role, followUps: List<String> = emptyList()) =
        Message(id = "1", role = role, content = "text", followUps = followUps)

    @Test
    fun `assistant message with followUps maps to dto followUps`() {
        val dto = msg(Message.Role.ASSISTANT, listOf("One?", "Two?")).toConversationMessageDto()
        assertEquals(listOf("One?", "Two?"), dto.followUps)
    }

    @Test
    fun `empty followUps map to null`() {
        assertNull(msg(Message.Role.ASSISTANT).toConversationMessageDto().followUps)
    }

    @Test
    fun `user message never carries followUps`() {
        assertNull(msg(Message.Role.USER, listOf("One?", "Two?")).toConversationMessageDto().followUps)
    }

    @Test
    fun `follow_ups serialized for assistant including CJK and RTL text`() {
        val chips = listOf("这是什么意思？", "كيف أصلي؟", "मैं कैसे प्रार्थना करूँ?")
        val body = ApiClient.json.encodeToString(
            msg(Message.Role.ASSISTANT, chips).toConversationMessageDto(),
        )
        val obj = Json.parseToJsonElement(body).jsonObject
        assertEquals("assistant", obj["role"]?.jsonPrimitive?.content)
        assertEquals(chips, obj["follow_ups"]?.jsonArray?.map { it.jsonPrimitive.content })
    }

    @Test
    fun `follow_ups key is omitted when null so old payload shape is unchanged`() {
        val body = ApiClient.json.encodeToString(
            msg(Message.Role.ASSISTANT).toConversationMessageDto(),
        )
        assertFalse(Json.parseToJsonElement(body).jsonObject.containsKey("follow_ups"))
        assertTrue(body.contains("\"role\""))
    }
}
