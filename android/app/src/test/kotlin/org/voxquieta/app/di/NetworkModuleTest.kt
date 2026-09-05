package org.voxquieta.app.di

import android.os.Build
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.voxquieta.app.data.remote.interceptors.TurnstileInterceptor

@RunWith(RobolectricTestRunner::class)
class NetworkModuleTest {

    @Test
    fun `production service sends Android app User-Agent without device model`() = runTest {
        var captured: Request? = null
        val terminalInterceptor = mockk<TurnstileInterceptor>()
        every { terminalInterceptor.intercept(any()) } answers {
            val chain = firstArg<Interceptor.Chain>()
            captured = chain.request()
            Response.Builder()
                .request(chain.request())
                .protocol(Protocol.HTTP_1_1)
                .code(200)
                .message("OK")
                .body("{\"chat\":{}}".toResponseBody("application/json".toMediaType()))
                .build()
        }

        NetworkModule.provideBibleApiService(terminalInterceptor).getConfig()

        val userAgent = requireNotNull(captured).header("User-Agent").orEmpty()
        assertTrue(userAgent.startsWith("VoxQuieta/"))
        assertTrue(userAgent.contains("(Android "))
        assertFalse(userAgent.contains(";"))
        Build.MODEL.takeIf { it.isNotBlank() }?.let { assertFalse(userAgent.contains(it)) }
    }
}
