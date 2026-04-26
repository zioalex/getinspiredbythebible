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

}
