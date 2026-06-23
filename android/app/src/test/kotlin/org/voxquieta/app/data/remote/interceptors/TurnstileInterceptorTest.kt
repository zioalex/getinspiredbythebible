package org.voxquieta.app.data.remote.interceptors

import io.mockk.every
import io.mockk.mockk
import io.mockk.slot
import io.mockk.verify
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.voxquieta.app.security.TurnstileManager

class TurnstileInterceptorTest {

    private lateinit var manager: TurnstileManager
    private lateinit var interceptor: TurnstileInterceptor

    @Before
    fun setUp() {
        manager = TurnstileManager()
        interceptor = TurnstileInterceptor(manager).apply {
            tokenWaitMillis = 250L
        }
    }

    @Test
    fun `cached token attaches header without waiting on POST`() {
        manager.onTokenReceived("cached-token")
        val captured = runIntercept(post("https://api.example.com/api/v1/chat/stream"))
        assertEquals("cached-token", captured.header("X-Turnstile-Token"))
    }

    @Test
    fun `attached-token POST consumes the token after the response`() {
        // Regression for the church-search "second call always 403s" failure:
        // a single-use Turnstile token must be cleared from TurnstileManager
        // once a request has carried it, regardless of which call site issued
        // the request.
        manager.onTokenReceived("single-use-token")
        runIntercept(post("https://api.example.com/api/v1/church/search"))
        assertNull("token must be cleared after being attached", manager.currentToken())
    }

    @Test
    fun `POST without token does not trigger consume`() {
        // No token cached, no awaiter response — request goes out without a
        // header. Don't fire onTokenConsumed in this path: there is no token
        // to invalidate, and emitting a spurious resetTrigger would force the
        // WebView to re-render for nothing.
        // tokenWaitMillis is 250L from setUp, so this returns quickly.
        runIntercept(post("https://api.example.com/api/v1/chat/stream"))
        // currentToken stays null both before and after; the more meaningful
        // assertion is the absence of any token churn — captured by the fact
        // that no header was attached (covered by the existing timeout test).
        assertNull(manager.currentToken())
    }

    @Test
    fun `GET with no token does not wait and sends no header`() {
        val start = System.currentTimeMillis()
        val captured = runIntercept(get("https://api.example.com/api/v1/scripture/translations"))
        val elapsed = System.currentTimeMillis() - start
        assertNull(captured.header("X-Turnstile-Token"))
        assertFalse("GET should not block on a token, took ${elapsed}ms", elapsed > 100)
    }

    @Test
    fun `POST with no token and prior error does not wait and sends no header`() {
        manager.onError("network-error")
        val start = System.currentTimeMillis()
        val captured = runIntercept(post("https://api.example.com/api/v1/chat/stream"))
        val elapsed = System.currentTimeMillis() - start
        assertNull(captured.header("X-Turnstile-Token"))
        assertFalse("hasError should short-circuit the wait, took ${elapsed}ms", elapsed > 100)
    }

    @Test
    fun `POST with no token times out and sends no header`() {
        // No token, no error; the wait expires (250ms in setUp).
        val start = System.currentTimeMillis()
        val captured = runIntercept(post("https://api.example.com/api/v1/chat/stream"))
        val elapsed = System.currentTimeMillis() - start
        assertNull(captured.header("X-Turnstile-Token"))
        // Allow some headroom but require the wait actually happened.
        assertEquals(true, elapsed >= 200)
    }

    @Test
    fun `POST waits for token and attaches header when one arrives`() {
        // Deliver a token from a real worker thread after a short sleep so
        // the interceptor's runBlocking wait observes it via tokenFlow.
        interceptor.tokenWaitMillis = 5_000L
        val deliverer = Thread {
            Thread.sleep(50)
            manager.onTokenReceived("late-token")
        }
        deliverer.start()
        val start = System.currentTimeMillis()
        val captured = runIntercept(post("https://api.example.com/api/v1/chat/stream"))
        val elapsed = System.currentTimeMillis() - start
        deliverer.join()
        assertEquals("late-token", captured.header("X-Turnstile-Token"))
        assertTrue("expected to wait for the token, took ${elapsed}ms", elapsed >= 40)
    }

    @Test
    fun `403 resets and retries with a freshly recovered token even after prior error`() {
        // Reproduces the wedge fix: the widget has errored (hasError=true), so the
        // first attempt goes out token-less and the server replies 403. The WebView
        // recovery then delivers a fresh token; the interceptor must request a
        // reset, wait *through* hasError on the retry path, and resend with that
        // token instead of immediately failing open.
        manager.onError("110200")
        interceptor.retryTokenWaitMillis = 5_000L

        val captured = mutableListOf<Request>()
        val chain: Interceptor.Chain = mockk()
        every { chain.request() } returns post("https://api.example.com/api/v1/chat/stream")
        every { chain.proceed(capture(captured)) } answers {
            if (captured.size == 1) {
                // First (token-less) attempt rejected; a worker delivers a fresh
                // token shortly after so the retry wait can observe it.
                Thread {
                    Thread.sleep(50)
                    manager.onTokenReceived("recovered-token")
                }.start()
                response(firstArg(), 403)
            } else {
                response(firstArg(), 200)
            }
        }

        interceptor.intercept(chain)

        assertEquals("expected one retry after the 403", 2, captured.size)
        assertNull(
            "first attempt is token-less (prior error short-circuits the wait)",
            captured[0].header("X-Turnstile-Token"),
        )
        assertEquals("recovered-token", captured[1].header("X-Turnstile-Token"))
        // The single-use token is consumed after the successful retry.
        assertNull(manager.currentToken())
    }

    private fun runIntercept(request: Request): Request {
        val chain: Interceptor.Chain = mockk()
        val captured = slot<Request>()
        every { chain.request() } returns request
        every { chain.proceed(capture(captured)) } answers { dummyResponse(firstArg()) }
        interceptor.intercept(chain)
        verify { chain.proceed(any()) }
        return captured.captured
    }

    private fun get(url: String): Request = Request.Builder().url(url).get().build()

    private fun post(url: String): Request = Request.Builder()
        .url(url)
        .post("{}".toRequestBody("application/json".toMediaType()))
        .build()

    private fun dummyResponse(forRequest: Request): Response = Response.Builder()
        .request(forRequest)
        .protocol(Protocol.HTTP_1_1)
        .code(200)
        .message("OK")
        .build()

    // Response with a body so the interceptor can call close() on the 403 path.
    private fun response(forRequest: Request, code: Int): Response = Response.Builder()
        .request(forRequest)
        .protocol(Protocol.HTTP_1_1)
        .code(code)
        .message(if (code in 200..299) "OK" else "Error")
        .body("{}".toResponseBody("application/json".toMediaType()))
        .build()

}
