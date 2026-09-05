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
 * no `Accept-Language` at all. The identifying UA lets the backend classify
 * updated app sessions; the language header is a fallback for requests that do
 * not carry the app's explicit language in their body.
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
         * Builds the app's User-Agent, e.g. `VoxQuieta/1.8.0 (Android 14)`.
         *
         * The literal "Android" is what the backend's mobile detection keys on,
         * so keep it in the string.
         */
        fun defaultUserAgent(versionName: String): String {
            val release = Build.VERSION.RELEASE?.takeIf { it.isNotBlank() } ?: "unknown"
            return buildUserAgent(versionName, release)
        }

        internal fun buildUserAgent(versionName: String, androidRelease: String): String {
            val version = versionName.takeIf { it.isNotBlank() } ?: "unknown"
            val release = androidRelease.takeIf { it.isNotBlank() } ?: "unknown"
            return sanitizeHeaderValue("VoxQuieta/$version (Android $release)")
        }

        /**
         * OkHttp rejects header values containing anything outside printable
         * ASCII. Drop those characters rather than crash the request.
         */
        internal fun sanitizeHeaderValue(value: String): String =
            value.filter { it in ' '..'~' }.trim()
    }
}
