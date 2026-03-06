# Keep JavascriptInterface methods for Turnstile WebView bridge
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
