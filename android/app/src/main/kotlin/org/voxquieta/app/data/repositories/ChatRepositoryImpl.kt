package org.voxquieta.app.data.repositories

import org.voxquieta.app.data.local.VoxQuietaDatabase
import org.voxquieta.app.data.local.ConversationEntity
import org.voxquieta.app.data.local.mappers.toDomain
import org.voxquieta.app.data.local.mappers.toEntity
import org.voxquieta.app.data.remote.api.BibleApiService
import org.voxquieta.app.data.remote.mappers.toDomain
import org.voxquieta.app.data.remote.mappers.toDto
import org.voxquieta.app.data.remote.models.FeedbackRequestDto
import org.voxquieta.app.data.streaming.toChunkFlow
import org.voxquieta.app.domain.models.ChatRequest
import org.voxquieta.app.domain.models.Conversation
import org.voxquieta.app.domain.models.FeedbackRating
import org.voxquieta.app.domain.models.Message
import org.voxquieta.app.domain.models.StreamChunk
import org.voxquieta.app.domain.repositories.ChatRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.flow.map
import timber.log.Timber
import javax.inject.Inject

class ChatRepositoryImpl @Inject constructor(
    private val api: BibleApiService,
    private val db: VoxQuietaDatabase,
) : ChatRepository {

    // ── Network ───────────────────────────────────────────────────────────────

    override fun chatStream(request: ChatRequest): Flow<StreamChunk> = flow {
        // api.chatStream is a suspend function; call it inside a flow builder so it
        // runs within a coroutine context, then forward each parsed chunk downstream.
        val responseBody = api.chatStream(request.toDto())
        responseBody.toChunkFlow().collect { emit(it.toDomain()) }
    }.flowOn(Dispatchers.IO)

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
            title = truncateTitle(title),
            createdAt = now,
            updatedAt = now,
        )
        db.conversationDao().upsert(entity)
        return entity.toDomain()
    }

    /**
     * Truncates [text] at the nearest word boundary before [maxLength] characters,
     * appending an ellipsis when truncation occurs.
     */
    private fun truncateTitle(text: String, maxLength: Int = 60): String {
        if (text.length <= maxLength) return text
        val truncated = text.take(maxLength)
        val lastSpace = truncated.lastIndexOf(' ')
        return if (lastSpace > maxLength / 2) truncated.substring(0, lastSpace) + "…"
        else truncated + "…"
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

    // ── Feedback ──────────────────────────────────────────────────────────────

    override suspend fun submitFeedback(
        messageId: String,
        rating: FeedbackRating,
        userMessage: String,
        assistantResponse: String,
        comment: String?,
    ) {
        try {
            val dto = FeedbackRequestDto(
                messageId = messageId,
                rating = if (rating == FeedbackRating.POSITIVE) "positive" else "negative",
                userMessage = userMessage,
                assistantResponse = assistantResponse,
                comment = comment?.takeIf { it.isNotBlank() },
            )
            api.submitFeedback(dto)
        } catch (e: Exception) {
            if (e is CancellationException) throw e
            // Best-effort: silently swallow all errors so feedback never
            // disrupts the user's experience.
            Timber.w(e, "submitFeedback failed (non-fatal)")
        }
    }
}
