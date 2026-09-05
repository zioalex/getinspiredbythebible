package org.voxquieta.app.data.remote.api

import kotlinx.serialization.json.Json
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit

object ApiClient {

    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
    }

    fun create(
        baseUrl: String,
        debug: Boolean = false,
        turnstileInterceptor: Interceptor? = null,
        userAgentInterceptor: Interceptor? = null,
    ): BibleApiService {
        val loggingInterceptor = HttpLoggingInterceptor().apply {
            level = if (debug) {
                HttpLoggingInterceptor.Level.BODY
            } else {
                HttpLoggingInterceptor.Level.NONE
            }
        }

        val clientBuilder = OkHttpClient.Builder()
            // Identify the client before anything else runs: without it OkHttp
            // sends "User-Agent: okhttp/<version>", which does not identify the
            // request as Android app traffic for session reporting.
            .apply { userAgentInterceptor?.let { addInterceptor(it) } }
            .addInterceptor(loggingInterceptor)
            // Streaming responses can take a while — generous read timeout.
            .readTimeout(120, TimeUnit.SECONDS)
            .connectTimeout(30, TimeUnit.SECONDS)

        turnstileInterceptor?.let { clientBuilder.addInterceptor(it) }

        val client = clientBuilder.build()

        return Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json; charset=UTF8".toMediaType()))
            .build()
            .create(BibleApiService::class.java)
    }
}
