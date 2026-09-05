package org.voxquieta.app

import androidx.test.ext.junit.runners.AndroidJUnit4
import java.net.HttpURLConnection
import java.net.URL
import javax.net.ssl.HttpsURLConnection
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ApiCompatibilityTest {
    @Test
    fun productionTlsHandshakeAndHealthCheckSucceed() {
        val connection = URL("https://api.voxquieta.org/health/live")
            .openConnection() as HttpsURLConnection
        connection.connectTimeout = 15_000
        connection.readTimeout = 15_000

        try {
            assertEquals(HttpURLConnection.HTTP_OK, connection.responseCode)
            assertTrue(connection.inputStream.bufferedReader().use { it.readText() }.contains("alive"))
        } finally {
            connection.disconnect()
        }
    }
}
