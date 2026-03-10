package com.bibleinspiration.data.remote.api

import com.bibleinspiration.data.remote.models.ChatRequestDto
import com.bibleinspiration.data.remote.models.TranslationsResponseDto
import okhttp3.ResponseBody
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Streaming

interface BibleApiService {

    /**
     * Streaming chat endpoint (Server-Sent Events).
     * The response body is parsed manually — do NOT let Retrofit deserialize it.
     */
    @Streaming
    @POST("api/v1/chat/stream")
    suspend fun chatStream(@Body request: ChatRequestDto): ResponseBody

    /**
     * Fetches the list of available Bible translations from the backend.
     */
    @GET("api/v1/translations")
    suspend fun getTranslations(): TranslationsResponseDto
}
