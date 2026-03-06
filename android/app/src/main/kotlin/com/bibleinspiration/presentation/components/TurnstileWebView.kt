package com.bibleinspiration.presentation.components

import android.annotation.SuppressLint
import android.webkit.JavascriptInterface
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.bibleinspiration.security.TurnstileManager

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun TurnstileWebView(
    turnstileManager: TurnstileManager,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val htmlContent = remember {
        context.assets.open("turnstile.html").bufferedReader().use { it.readText() }
    }

    AndroidView(
        modifier = modifier.size(1.dp),
        factory = { ctx ->
            WebView(ctx).apply {
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
                    "https://getinspiredbythebible.ai4you.sh",
                    htmlContent,
                    "text/html",
                    "UTF-8",
                    null,
                )
            }
        },
    )
}
