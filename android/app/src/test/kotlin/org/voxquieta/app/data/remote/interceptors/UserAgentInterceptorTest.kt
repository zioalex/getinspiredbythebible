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
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The backend classifies a session as mobile purely from the `User-Agent`
 * header (api/utils/session_tracker.py) and picks the session language from
 * `Accept-Language`. OkHttp sets neither on its own, which is why the weekly
 * digest reported every Android user as a web user.
 */
class UserAgentInterceptorTest {

    private val userAgent = "VoxQuieta/1.8.0 (Android 14; Pixel 7)"

    @Test
    fun `stamps the app User-Agent on outgoing requests`() {
        val interceptor = UserAgentInterceptor(userAgent) { "de" }

        val captured = runIntercept(interceptor, post("https://api.example.com/api/v1/chat/stream"))

        assertEquals(userAgent, captured.header("User-Agent"))
    }

    @Test
    fun `User-Agent names Android so the backend counts the session as mobile`() {
        val interceptor = UserAgentInterceptor(userAgent) { "en" }

        val captured = runIntercept(interceptor, get("https://api.example.com/api/v1/config"))

        assertTrue(
            "backend mobile detection keys on the literal 'android'",
            captured.header("User-Agent")!!.lowercase().contains("android"),
        )
    }

    @Test
    fun `sends the active UI language as Accept-Language`() {
        val interceptor = UserAgentInterceptor(userAgent) { "it" }

        val captured = runIntercept(interceptor, post("https://api.example.com/api/v1/chat/stream"))

        assertEquals("it", captured.header("Accept-Language"))
    }

    @Test
    fun `omits Accept-Language when no language is available`() {
        val interceptor = UserAgentInterceptor(userAgent) { null }

        val captured = runIntercept(interceptor, get("https://api.example.com/api/v1/config"))

        assertNull(captured.header("Accept-Language"))
    }

    @Test
    fun `omits Accept-Language when the provider returns blank`() {
        val interceptor = UserAgentInterceptor(userAgent) { "  " }

        val captured = runIntercept(interceptor, get("https://api.example.com/api/v1/config"))

        assertNull(captured.header("Accept-Language"))
    }

    @Test
    fun `replaces the existing User-Agent rather than appending a second one`() {
        val interceptor = UserAgentInterceptor(userAgent) { "en" }
        val request = Request.Builder()
            .url("https://api.example.com/api/v1/config")
            .header("User-Agent", "okhttp/4.12.0")
            .get()
            .build()

        val captured = runIntercept(interceptor, request)

        assertEquals(listOf(userAgent), captured.headers("User-Agent"))
    }

    @Test
    fun `strips non-ASCII characters that OkHttp would reject in a header`() {
        // Build.MODEL is vendor-supplied free text; an accented or emoji model
        // name must not make every request throw.
        val sanitized = UserAgentInterceptor.sanitizeHeaderValue(
            "VoxQuieta/1.8.0 (Android 14; Xiaomi Redmi Nöte 🚀)",
        )

        assertEquals("VoxQuieta/1.8.0 (Android 14; Xiaomi Redmi Nte )", sanitized)
        val interceptor = UserAgentInterceptor(sanitized) { "en" }
        assertEquals(
            sanitized,
            runIntercept(interceptor, get("https://api.example.com/api/v1/config"))
                .header("User-Agent"),
        )
    }

    private fun runIntercept(interceptor: UserAgentInterceptor, request: Request): Request {
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
