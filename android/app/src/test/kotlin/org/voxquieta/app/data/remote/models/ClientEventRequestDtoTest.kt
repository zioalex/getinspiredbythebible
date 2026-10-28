package org.voxquieta.app.data.remote.models

import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Test
import org.voxquieta.app.data.remote.api.ApiClient

class ClientEventRequestDtoTest {

    @Test
    fun `app Json encodes platform browser and os despite encodeDefaults being off`() {
        val body = ApiClient.json.encodeToString(ClientEventRequestDto(event = "tts_started", locale = "it"))
        val obj = Json.parseToJsonElement(body).jsonObject
        assertEquals("tts_started", obj["event"]?.jsonPrimitive?.content)
        assertEquals("it", obj["locale"]?.jsonPrimitive?.content)
        assertEquals("android", obj["platform"]?.jsonPrimitive?.content)
        assertEquals("app", obj["browser"]?.jsonPrimitive?.content)
        assertEquals("android", obj["os"]?.jsonPrimitive?.content)
    }
}
