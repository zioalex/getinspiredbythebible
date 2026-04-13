package org.voxquieta.app.data.remote.api

import org.voxquieta.app.data.remote.models.ChapterResponseDto
import org.voxquieta.app.data.remote.models.ChatRequestDto
import org.voxquieta.app.data.remote.models.ChurchSearchRequestDto
import org.voxquieta.app.data.remote.models.ChurchSearchResponseDto
import org.voxquieta.app.data.remote.models.ContactRequestDto
import org.voxquieta.app.data.remote.models.ContactResponseDto
import org.voxquieta.app.data.remote.models.FeedbackRequestDto
import org.voxquieta.app.data.remote.models.BookNamesResponseDto
import org.voxquieta.app.data.remote.models.TranslationsResponseDto
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query
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
    @GET("api/v1/scripture/translations")
    suspend fun getTranslations(): TranslationsResponseDto

    /**
     * Fetches localized book name mappings and the list of multi-word book names.
     */
    @GET("api/v1/scripture/book-names")
    suspend fun getBookNames(): BookNamesResponseDto

    /**
     * Fetches all verses for a given book and chapter.
     */
    @GET("api/v1/scripture/chapter/{book}/{chapter}")
    suspend fun getChapter(
        @Path("book") book: String,
        @Path("chapter") chapter: Int,
        @Query("translation") translation: String? = null,
    ): ChapterResponseDto

    /**
     * Submits thumbs-up / thumbs-down feedback for a finished assistant message.
     * Returns a [Response] wrapper so callers can ignore the body (best-effort).
     */
    @POST("api/v1/feedback")
    suspend fun submitFeedback(@Body body: FeedbackRequestDto): Response<Unit>

    /**
     * Searches for churches near the given location.
     * Returns a list of churches with name, address, and contact details.
     */
    @POST("api/v1/church/search")
    suspend fun searchChurches(@Body body: ChurchSearchRequestDto): ChurchSearchResponseDto

    /**
     * Submits a contact form message (subject + free-text, optional email).
     * Returns the server-assigned record ID.
     */
    @POST("api/v1/feedback/contact")
    suspend fun submitContact(@Body body: ContactRequestDto): ContactResponseDto
}
