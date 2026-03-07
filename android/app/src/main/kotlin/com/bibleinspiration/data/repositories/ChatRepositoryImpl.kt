package com.bibleinspiration.data.repositories

import com.bibleinspiration.data.local.BibleInspirationDatabase
import com.bibleinspiration.data.local.ConversationEntity
import com.bibleinspiration.data.local.mappers.toDomain
import com.bibleinspiration.data.local.mappers.toEntity
import com.bibleinspiration.data.remote.api.BibleApiService
import com.bibleinspiration.data.remote.mappers.toDomain
import com.bibleinspiration.data.remote.mappers.toDto
import com.bibleinspiration.data.streaming.toChunkFlow
import com.bibleinspiration.domain.models.ChatRequest
import com.bibleinspiration.domain.models.ChatResponse
import com.bibleinspiration.domain.models.Conversation
import com.bibleinspiration.domain.models.Message
import com.bibleinspiration.domain.models.StreamChunk
import com.bibleinspiration.domain.repositories.ChatRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject

class ChatRepositoryImpl @Inject constructor(
    private val api: BibleApiService,
    private val db: BibleInspirationDatabase,
) : ChatRepository {

    // ── Network ───────────────────────────────────────────────────────────────

    override suspend fun chat(request: ChatRequest): ChatResponse =
        api.chat(request.toDto()).toDomain()

    override fun chatStream(request: ChatRequest): Flow<StreamChunk> = flow {
        // api.chatStream is a suspend function; call it inside a flow builder so it
        // runs within a coroutine context, then forward each parsed chunk downstream.
        val responseBody = api.chatStream(request.toDto())
        responseBody.toChunkFlow().collect { emit(it.toDomain()) }
    }

    // ── Persistence ───────────────────────────────────────────────────────────

    override fun observeConversations(): Flow<List<Conversation>> =
        db.conversationDao().observeAll().map { list -> list.map { it.toDomain() } }

    override fun observeMessages(conversationId: String): Flow<List<Message>> =
        db.messageDao().observeByConversation(conversationId).map { list ->
            list.map { it.toDomain() }
        }

    override suspend fun saveMessage(conversationId: String, message: Message) {
        db.messageDao().upsert(message.toEntity(conversationId))
    }

    override suspend fun createConversation(id: String, title: String): Conversation {
        val now = System.currentTimeMillis()
        val entity = ConversationEntity(
            id = id,
            title = title.take(60),
            createdAt = now,
            updatedAt = now,
        )
        db.conversationDao().upsert(entity)
        return entity.toDomain()
    }

    override suspend fun touchConversation(conversationId: String) {
        db.conversationDao().touch(conversationId, System.currentTimeMillis())
    }

    override suspend fun deleteConversation(conversationId: String) {
        // Cascade delete handles messages automatically via ForeignKey.CASCADE.
        db.conversationDao().delete(
            ConversationEntity(id = conversationId, title = "", createdAt = 0, updatedAt = 0),
        )
    }

    override suspend fun clearAllConversations() {
        db.conversationDao().deleteAll()
    }
}
