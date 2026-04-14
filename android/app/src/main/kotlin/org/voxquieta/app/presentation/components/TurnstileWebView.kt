package org.voxquieta.app.presentation.components

import android.annotation.SuppressLint
import android.app.Activity
import android.content.ContextWrapper
import android.webkit.JavascriptInterface
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import org.voxquieta.app.BuildConfig
import org.voxquieta.app.security.TurnstileManager

/**
 * Unwraps a [ContextWrapper] chain until an [Activity] is found.
 * Returns the original context if no Activity is found in the chain.
 *
 * This is necessary because [LocalContext] may be overridden with a
 * [android.content.Context.createConfigurationContext] result (e.g. for locale
 * switching). A configuration context lacks a window token, which causes
 * [WebView] to crash with a BadTokenException. We always want to pass the
 * real Activity context to [WebView].
 */
private fun unwrapActivity(context: android.content.Context): android.content.Context {
    var ctx = context
    while (ctx is ContextWrapper) {
        if (ctx is Activity) return ctx
        ctx = ctx.baseContext
    }
    return context
}

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun TurnstileWebView(
    turnstileManager: TurnstileManager,
    modifier: Modifier = Modifier,
) {
    // Unwrap to the real Activity context before reading assets or constructing a
    // WebView.  LocalContext may be overridden with a ConfigurationContext for
    // locale switching, which has no window token and causes WebView to crash.
    val activityContext = unwrapActivity(LocalContext.current)
    val htmlContent = remember {
        activityContext.assets.open("turnstile.html").bufferedReader().use { it.readText() }
    }

    // Hold a reference to the WebView so the LaunchedEffect can reach it.
    val webViewRef = remember { androidx.compose.runtime.mutableStateOf<WebView?>(null) }

    // Whenever TurnstileManager signals that the token was consumed, reset the
    // Cloudflare widget so a fresh single-use token is generated.
    LaunchedEffect(turnstileManager) {
        turnstileManager.resetTrigger.collect {
            webViewRef.value?.evaluateJavascript("window.resetWidget()", null)
        }
    }

    AndroidView(
        modifier = modifier.size(1.dp),
        factory = { _ ->
            // Use activityContext (unwrapped from ConfigurationContext) — a real Activity
            // context is required by WebView to access the WindowManager.
            WebView(activityContext).apply {
                settings.javaScriptEnabled = true
                settings.domStorageEnabled = true
                webViewClient = WebViewClient()
                addJavascriptInterface(
                    object {
                        @JavascriptInterface
                        fun onToken(token: String) {
                            turnstileManager.onTokenReceived(token)
                        }

                        @JavascriptInterface
                        fun onExpired() {
                            turnstileManager.onTokenExpired()
                        }

                        @JavascriptInterface
                        fun onError(code: String) {
                            turnstileManager.onError(code)
                        }
                    },
                    "Android",
                )
                loadDataWithBaseURL(
                    BuildConfig.FRONTEND_URL,
                    htmlContent,
                    "text/html",
                    "UTF-8",
                    null,
                )
                webViewRef.value = this
            }
        },
    )
}
