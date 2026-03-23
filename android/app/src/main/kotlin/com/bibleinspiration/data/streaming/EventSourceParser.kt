package com.bibleinspiration.data.streaming

import com.bibleinspiration.data.remote.models.StreamChunkDto
import com.bibleinspiration.data.remote.models.VerseDto
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.ResponseBody
import timber.log.Timber

private val json = Json {
    ignoreUnknownKeys = true
    isLenient = true
}

/**
 * Parses a Server-Sent Events (SSE) [ResponseBody] into a [Flow] of [StreamChunkDto].
 *
 * The backend sends lines of the form:
 *   `data: {"content": "...", "done": false}`       — content chunk
 *   `data: {"type": "metadata", "message_id": "...", "model": "..."}` — metadata event
 * or the terminal sentinel:
 *   `data: [DONE]`
 *
 * Metadata events are emitted as a [StreamChunkDto] with `type="metadata"`, empty `content`,
 * and the `messageId`/`model` fields populated.  Content events (or legacy chunks with no
 * `type` field) are handled as before.
 *
 * The flow completes when either the `[DONE]` sentinel is received or the body is exhausted.
 */
fun ResponseBody.toChunkFlow(): Flow<StreamChunkDto> = flow {
    use { body ->
        val reader = body.charStream().buffered()
        var line: String?
        while (reader.readLine().also { line = it } != null) {
            val raw = line ?: continue
            if (!raw.startsWith("data:")) continue

            val data = raw.removePrefix("data:").trim()
            if (data == "[DONE]") break

            try {
                // Peek at the "type" field using JsonObject to branch the parser.
                val jsonObj = json.decodeFromString<JsonObject>(data)
                when (jsonObj["type"]?.jsonPrimitive?.contentOrNull) {
                    "metadata" -> {
                        // Extract metadata fields and emit a synthetic content-less chunk
                        // carrying messageId, model, detectedTranslation, and verses so the ViewModel can capture them.
                        val messageId = jsonObj["message_id"]?.jsonPrimitive?.contentOrNull ?: ""
                        val model = jsonObj["model"]?.jsonPrimitive?.contentOrNull ?: ""
                        val detectedTranslation = jsonObj["detected_translation"]?.jsonPrimitive?.contentOrNull ?: ""
                        // Extract verses from scripture_context.verses (the primary source for verse data).
                        val verses: List<VerseDto> = try {
                            val ctxEl = jsonObj["scripture_context"]
                            if (ctxEl != null && ctxEl !is JsonNull) {
                                val versesEl = (ctxEl as? JsonObject)?.get("verses")
                                if (versesEl != null) json.decodeFromJsonElement<List<VerseDto>>(versesEl)
                                else emptyList()
                            } else emptyList()
                        } catch (e: Exception) {
                            Timber.w(e, "SSE: failed to parse scripture_context.verses")
                            emptyList()
                        }
                        emit(
                            StreamChunkDto(
                                type = "metadata",
                                content = "",
                                done = false,
                                verses = verses,
                                messageId = messageId,
                                model = model,
                                detectedTranslation = detectedTranslation,
                            ),
                        )
                    }
                    "content", null, "" -> {
                        // Standard content chunk or legacy plain chunk with no type field.
                        val chunk = json.decodeFromString<StreamChunkDto>(data)
                        emit(chunk)
                        if (chunk.done) break
                    }
                    else -> {
                        // Unknown type — log and skip to stay forward-compatible.
                        Timber.d("SSE: ignoring unknown chunk type: %s", jsonObj["type"]?.jsonPrimitive?.contentOrNull)
                    }
                }
            } catch (e: Exception) {
                Timber.w(e, "SSE: failed to parse chunk: %s", data)
            }
        }
    }
}
