package org.voxquieta.app.data.remote.interceptors

import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeoutOrNull
import okhttp3.Interceptor
import okhttp3.Response
import org.voxquieta.app.security.TurnstileManager
import javax.inject.Inject

class TurnstileInterceptor @Inject constructor(
    private val turnstileManager: TurnstileManager,
) : Interceptor {

    // Mutable so unit tests can shorten the wait without spinning up a coroutine
    // dispatcher. Hilt provides the production instance via the @Inject constructor.
    internal var tokenWaitMillis: Long = DEFAULT_TOKEN_WAIT_MILLIS

    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        // Turnstile-gated endpoints on this backend are all POST requests
        // (chat, chat/stream, church/search, feedback, feedback/contact). For
        // GETs we never block waiting for a token — they don't need one and
        // we don't want to add latency at app startup before the WebView has
        // had a chance to mount.
        val needsToken = original.method.equals("POST", ignoreCase = true)
        val token = turnstileManager.currentToken()
            ?: if (needsToken) awaitTokenOrNull() else null
        return if (token != null) {
            chain.proceed(
                original.newBuilder()
                    .header("X-Turnstile-Token", token)
                    .build()
            )
        } else {
            chain.proceed(original)
        }
    }

    // Bounded wait for the Turnstile WebView to deliver a token. Returns null
    // if the widget already errored (so we don't sit on the request thread for
    // nothing) or if the timeout elapses (so the request still goes through and
    // the server's 403 surfaces, instead of the user staring at a hung UI).
    private fun awaitTokenOrNull(): String? {
        if (turnstileManager.hasError.value) return null
        return runBlocking {
            withTimeoutOrNull(tokenWaitMillis) {
                turnstileManager.tokenFlow.filterNotNull().first()
            }
        }
    }

    companion object {
        const val DEFAULT_TOKEN_WAIT_MILLIS: Long = 5_000L
    }
}
