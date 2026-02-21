package com.bibleinspiration.data.streaming

import com.bibleinspiration.data.remote.models.StreamChunkDto
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.serialization.json.Json
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
 *   `data: {"content": "...", "done": false}`
 * or the terminal sentinel:
 *   `data: [DONE]`
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
                val chunk = json.decodeFromString<StreamChunkDto>(data)
                emit(chunk)
                if (chunk.done) break
            } catch (e: Exception) {
                Timber.w(e, "SSE: failed to parse chunk: %s", data)
            }
        }
    }
}
