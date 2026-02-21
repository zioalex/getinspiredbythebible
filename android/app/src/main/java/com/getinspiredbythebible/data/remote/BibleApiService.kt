package com.getinspiredbythebible.data.remote

import com.getinspiredbythebible.data.model.ChatRequest
import com.getinspiredbythebible.data.model.ChatResponse
import com.getinspiredbythebible.data.model.ScriptureSearchResponse
import com.getinspiredbythebible.data.model.VerseResult
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Retrofit interface mirroring the FastAPI backend endpoints.
 *
 * All functions are suspend functions for use with Kotlin Coroutines.
 * The base URL is injected by [com.getinspiredbythebible.di.NetworkModule]
 * from BuildConfig.BASE_URL so it can differ between debug and release builds.
 */
interface BibleApiService {

    /**
     * Send a user message and receive a Bible-grounded AI response.
     */
    @POST("api/v1/chat")
    suspend fun sendMessage(@Body request: ChatRequest): ChatResponse

    /**
     * Semantic search across all Bible verses.
     *
     * @param query Free-text query (e.g., "peace in difficult times").
     */
    @GET("api/v1/scripture/search")
    suspend fun searchScripture(@Query("q") query: String): ScriptureSearchResponse

    /**
     * Retrieve a specific verse by book, chapter, and verse number.
     */
    @GET("api/v1/scripture/verse/{book}/{chapter}/{verse}")
    suspend fun getVerse(
        @Path("book") book: String,
        @Path("chapter") chapter: Int,
        @Path("verse") verse: Int,
    ): VerseResult

    /**
     * Retrieve all verses in a chapter.
     */
    @GET("api/v1/scripture/chapter/{book}/{chapter}")
    suspend fun getChapter(
        @Path("book") book: String,
        @Path("chapter") chapter: Int,
    ): List<VerseResult>
}
