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

    // Wait used on the 403-retry path; longer than the first-attempt wait because
    // it may need to cover the WebView's error-recovery backoff. Mutable for tests.
    internal var retryTokenWaitMillis: Long = DEFAULT_RETRY_TOKEN_WAIT_MILLIS

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

        // On 403 for any POST the token was missing or stale. Kick the widget to
        // re-render (this also nudges recovery if the widget is in an error state —
        // TurnstileWebView reloads on hasError) and wait for a fresh token, then
        // retry exactly once. We wait via awaitFreshTokenOrNull(), which — unlike
        // the first-attempt path — does NOT short-circuit on hasError: a 403 means
        // we already need a token, so we give the WebView's recovery a chance to
        // deliver one instead of immediately failing open. Fail-open remains the
        // last resort: if no token arrives within the (longer) wait, proceed
        // without one and let the backend's 403 surface to the user.
        if (response.code == 403 && needsToken) {
            response.close()
            turnstileManager.requestReset()
            val freshToken = awaitFreshTokenOrNull()
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

    // Like awaitTokenOrNull() but does NOT short-circuit on hasError, and waits
    // longer. Used only on the 403-retry path: a 403 means the request genuinely
    // needs a token, so we give the WebView's error-recovery (reload + re-render,
    // which can take a backoff tick) time to produce a fresh one rather than
    // bailing out immediately the way the latency-sensitive first attempt does.
    private fun awaitFreshTokenOrNull(): String? = runBlocking {
        withTimeoutOrNull(retryTokenWaitMillis) {
            turnstileManager.tokenFlow.filterNotNull().first()
        }
    }

    companion object {
        const val DEFAULT_TOKEN_WAIT_MILLIS: Long = 5_000L
        const val DEFAULT_RETRY_TOKEN_WAIT_MILLIS: Long = 8_000L
    }
}
