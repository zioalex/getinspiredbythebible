package com.bibleinspiration.data.repositories

import com.bibleinspiration.data.remote.api.BibleApiService
import com.bibleinspiration.data.remote.mappers.toDomain
import com.bibleinspiration.data.remote.mappers.toDto
import com.bibleinspiration.data.streaming.toChunkFlow
import com.bibleinspiration.domain.models.ChatRequest
import com.bibleinspiration.domain.models.ChatResponse
import com.bibleinspiration.domain.models.StreamChunk
import com.bibleinspiration.domain.repositories.ChatRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject

class ChatRepositoryImpl @Inject constructor(
    private val api: BibleApiService,
) : ChatRepository {

    override suspend fun chat(request: ChatRequest): ChatResponse =
        api.chat(request.toDto()).toDomain()

    override fun chatStream(request: ChatRequest): Flow<StreamChunk> =
        api.chatStream(request.toDto()).toChunkFlow().map { it.toDomain() }
}
