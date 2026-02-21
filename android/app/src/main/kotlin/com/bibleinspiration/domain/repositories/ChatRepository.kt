package com.bibleinspiration.domain.repositories

import com.bibleinspiration.domain.models.ChatRequest
import com.bibleinspiration.domain.models.ChatResponse
import com.bibleinspiration.domain.models.StreamChunk
import kotlinx.coroutines.flow.Flow

interface ChatRepository {
    /**
     * Send a message and receive the full (non-streaming) response.
     */
    suspend fun chat(request: ChatRequest): ChatResponse

    /**
     * Send a message and receive a cold [Flow] of [StreamChunk]s.
     * The flow completes after the chunk with [StreamChunk.done] == true is emitted.
     */
    fun chatStream(request: ChatRequest): Flow<StreamChunk>
}
