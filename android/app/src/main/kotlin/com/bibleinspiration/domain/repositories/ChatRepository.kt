package com.bibleinspiration.domain.repositories

import com.bibleinspiration.domain.models.ChatRequest
import com.bibleinspiration.domain.models.Conversation
import com.bibleinspiration.domain.models.FeedbackRating
import com.bibleinspiration.domain.models.Message
import com.bibleinspiration.domain.models.StreamChunk
import kotlinx.coroutines.flow.Flow

interface ChatRepository {
    /**
     * Send a message and receive a cold [Flow] of [StreamChunk]s.
     * The flow completes after the chunk with [StreamChunk.done] == true is emitted.
     */
    fun chatStream(request: ChatRequest): Flow<StreamChunk>

    // ── Persistence ───────────────────────────────────────────────────────────

    /** Observe all conversations ordered by most-recently updated first. */
    fun observeConversations(): Flow<List<Conversation>>

    /** Observe the ordered list of messages belonging to [conversationId]. */
    fun observeMessages(conversationId: String): Flow<List<Message>>

    /** Persist a single [message] into [conversationId]. */
    suspend fun saveMessage(conversationId: String, message: Message)

    /**
     * Create and persist a new [Conversation].
     *
     * @param id   A pre-generated UUID.
     * @param title First user message, will be truncated to 60 characters.
     */
    suspend fun createConversation(id: String, title: String): Conversation

    /**
     * Update the `updatedAt` timestamp on an existing conversation so it
     * bubbles to the top of the list after new messages arrive.
     */
    suspend fun touchConversation(conversationId: String)

    /** Delete a single conversation and all its messages (CASCADE). */
    suspend fun deleteConversation(conversationId: String)

    /** Delete every conversation and all messages. */
    suspend fun clearAllConversations()

    /**
     * Submit thumbs-up / thumbs-down feedback for a finished assistant message.
     *
     * Best-effort: network errors are silently swallowed so a transient failure
     * never surfaces a disruptive error to the user.
     *
     * @param messageId Backend-assigned UUID from the SSE metadata event.
     * @param rating    [FeedbackRating.POSITIVE] or [FeedbackRating.NEGATIVE].
     * @param userMessage   The user's original question (provides context).
     * @param assistantResponse The assistant's reply text (provides context).
     */
    suspend fun submitFeedback(
        messageId: String,
        rating: FeedbackRating,
        userMessage: String = "",
        assistantResponse: String = "",
    )
}
