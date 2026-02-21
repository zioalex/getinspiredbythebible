package com.getinspiredbythebible.data.repository

import com.getinspiredbythebible.data.model.ChatRequest
import com.getinspiredbythebible.data.model.ChatResponse
import com.getinspiredbythebible.data.model.VerseResult
import com.getinspiredbythebible.data.remote.BibleApiService
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Production implementation of [ChatRepository] that delegates to the Retrofit [BibleApiService].
 *
 * All network errors are caught and wrapped in [Result.failure] so the ViewModel never
 * has to handle raw exceptions directly.
 */
@Singleton
class ChatRepositoryImpl @Inject constructor(
    private val apiService: BibleApiService,
) : ChatRepository {

    override suspend fun sendMessage(message: String, sessionId: String?): Result<ChatResponse> =
        runCatching {
            apiService.sendMessage(ChatRequest(message = message, sessionId = sessionId))
        }

    override suspend fun searchScripture(query: String): Result<List<VerseResult>> =
        runCatching {
            apiService.searchScripture(query).results
        }
}
