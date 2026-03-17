# Keep JavascriptInterface methods for Turnstile WebView bridge
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

# ---------------------------------------------------------------------------
# Firebase Crashlytics
# ---------------------------------------------------------------------------
# Preserve the Crashlytics SDK and its internal stack-trace deobfuscation support.
# The Crashlytics Gradle plugin uploads the R8/ProGuard mapping file automatically
# so crash stacks are deobfuscated in the Firebase console.
-keepattributes SourceFile,LineNumberTable
-keep public class * extends java.lang.Exception

# Ensure Crashlytics can read thread names for grouping.
-keep class com.google.firebase.crashlytics.** { *; }
-dontwarn com.google.firebase.crashlytics.**

# ---------------------------------------------------------------------------
# Firebase Analytics
# ---------------------------------------------------------------------------
-keep class com.google.android.gms.measurement.** { *; }
-dontwarn com.google.android.gms.measurement.**
