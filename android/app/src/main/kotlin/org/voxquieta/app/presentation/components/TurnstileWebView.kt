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
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collectLatest
import org.voxquieta.app.BuildConfig
import org.voxquieta.app.security.TurnstileManager

// Error-recovery backoff bounds for re-rendering a wedged Turnstile widget.
private const val INITIAL_RECOVERY_BACKOFF_MILLIS = 1_000L
private const val MAX_RECOVERY_BACKOFF_MILLIS = 8_000L
private const val MAX_RECOVERY_ATTEMPTS = 5

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

    // Self-heal when the Turnstile widget enters an error state. Cloudflare fires
    // its error-callback after the widget is reset too aggressively (every message
    // forces a fresh single-use token), which used to wedge the app: hasError
    // stayed true for the whole session and every POST went out token-less → 403
    // on both chat and the bug-report form. Here we reload the WebView (a full
    // reload re-runs onTurnstileLoad and re-renders the widget — more reliable
    // than reset() on a wedged widget) with exponential backoff until a fresh
    // token arrives (onTokenReceived clears hasError, ending the loop).
    LaunchedEffect(turnstileManager) {
        turnstileManager.hasError.collectLatest { hasError ->
            if (!hasError) return@collectLatest
            var backoffMillis = INITIAL_RECOVERY_BACKOFF_MILLIS
            repeat(MAX_RECOVERY_ATTEMPTS) {
                delay(backoffMillis)
                // If a token arrived during the wait, hasError is already false and
                // collectLatest will have cancelled this block; the guard is belt-and-braces.
                if (!turnstileManager.hasError.value) return@collectLatest
                webViewRef.value?.reload()
                backoffMillis = (backoffMillis * 2).coerceAtMost(MAX_RECOVERY_BACKOFF_MILLIS)
            }
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
