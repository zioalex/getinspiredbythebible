package org.voxquieta.app.data.remote.interceptors

import android.os.Build
import okhttp3.Interceptor
import okhttp3.Response
import java.util.Locale

/**
 * Stamps every outgoing request with an app-identifying `User-Agent` and the
 * active UI language as `Accept-Language`.
 *
 * Without this OkHttp sends its own default `User-Agent: okhttp/<version>` and
 * no `Accept-Language` at all. The backend derives session analytics from those
 * two headers (`api/utils/session_tracker.py`), so every Android session was
 * stored with `is_mobile = false` and `language = NULL` — which is why the
 * weekly digest attributed all Android traffic to the web app.
 *
 * [userAgent] and [languageProvider] are injected so unit tests never touch the
 * Android framework statics.
 */
class UserAgentInterceptor(
    private val userAgent: String,
    private val languageProvider: () -> String? = { Locale.getDefault().language.ifBlank { null } },
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val builder = chain.request().newBuilder()
            .header("User-Agent", userAgent)
        languageProvider()?.let { language ->
            sanitizeHeaderValue(language).takeIf { it.isNotBlank() }?.let {
                builder.header("Accept-Language", it)
            }
        }
        return chain.proceed(builder.build())
    }

    companion object {
        /**
         * Builds the app's User-Agent, e.g. `VoxQuieta/1.8.0 (Android 14; Pixel 7)`.
         *
         * The literal "Android" is what the backend's mobile detection keys on,
         * so keep it in the string.
         */
        fun defaultUserAgent(versionName: String): String {
            val release = Build.VERSION.RELEASE?.takeIf { it.isNotBlank() } ?: "unknown"
            val model = Build.MODEL?.takeIf { it.isNotBlank() } ?: "unknown"
            val version = versionName.takeIf { it.isNotBlank() } ?: "unknown"
            return sanitizeHeaderValue(
                "VoxQuieta/$version (Android $release; $model)",
            )
        }

        /**
         * OkHttp rejects header values containing anything outside printable
         * ASCII, and [Build.MODEL] is vendor-supplied free text that can carry
         * accents or emoji. Drop those characters rather than crash the request.
         */
        internal fun sanitizeHeaderValue(value: String): String =
            value.filter { it in ' '..'~' }.trim()
    }
}
