package com.bibleinspiration.data.remote.interceptors

import com.bibleinspiration.security.TurnstileManager
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject

class TurnstileInterceptor @Inject constructor(
    private val turnstileManager: TurnstileManager,
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        val token = turnstileManager.currentToken()
        return if (token != null) {
            val request = original.newBuilder()
                .header("X-Turnstile-Token", token)
                .build()
            chain.proceed(request)
        } else {
            chain.proceed(original)
        }
    }
}
