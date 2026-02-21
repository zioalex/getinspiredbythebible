package com.getinspiredbythebible.data.repository

import com.getinspiredbythebible.data.model.ChatResponse
import com.getinspiredbythebible.data.model.VerseResult

/**
 * Contract for the chat and scripture repository.
 *
 * Keeping this as an interface enables easy mocking in unit tests and
 * clean separation between the domain/UI layer and the data source.
 */
interface ChatRepository {

    /**
     * Send a user message to the backend and return the AI response with Bible verses.
     *
     * @param message The user's message / prayer request.
     * @param sessionId Optional session UUID for conversation continuity.
     * @return [Result] wrapping [ChatResponse] on success or an exception on failure.
     */
    suspend fun sendMessage(message: String, sessionId: String? = null): Result<ChatResponse>

    /**
     * Semantically search Bible verses matching the given query.
     *
     * @param query Free-text search query.
     * @return [Result] wrapping a list of [VerseResult] on success or an exception on failure.
     */
    suspend fun searchScripture(query: String): Result<List<VerseResult>>
}
