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

        val response = if (token != null) {
            val r = chain.proceed(
                original.newBuilder()
                    .header("X-Turnstile-Token", token)
                    .build()
            )
            // Turnstile tokens are single-use — Cloudflare rejects reused
            // tokens with timeout-or-duplicate. Consume here, on every
            // attached-token request, regardless of upstream HTTP status, so
            // every call site (chat, church search, feedback, contact) gets
            // a fresh token next time without each repository having to
            // remember to call onTokenConsumed().
            turnstileManager.onTokenConsumed()
            r
        } else {
            chain.proceed(original)
        }

        // On 403 for any POST the token was missing or stale. The WebView reset
        // was already triggered by onTokenConsumed() above (or was never needed).
        // Wait for the fresh token and retry exactly once before surfacing the
        // error — fail-open: if still no token after the wait, proceed without one.
        if (response.code == 403 && needsToken) {
            response.close()
            val freshToken = awaitTokenOrNull()
                ?: return chain.proceed(original)
            val retried = chain.proceed(
                original.newBuilder()
                    .header("X-Turnstile-Token", freshToken)
                    .build()
            )
            turnstileManager.onTokenConsumed()
            return retried
        }

        return response
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
