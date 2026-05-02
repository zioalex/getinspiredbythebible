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

# ---------------------------------------------------------------------------
# kotlinx.serialization — defense-in-depth on top of bundled consumer rules
# ---------------------------------------------------------------------------
#
# kotlinx-serialization-core-jvm already ships consumer rules that:
#   - Keep @Serializable companion objects and their serializer() methods
#   - Suppress known ClassValue / descriptor-field optimisation issues
#
# The following rules cover gaps that the bundled rules do NOT address:
#
# 1. Keep classes that carry @SerialName-annotated fields (the bundled rules
#    keep companions/serializers but not the enclosing class itself when R8
#    cannot see a direct reference from reachable code).
-keep,allowobfuscation @kotlinx.serialization.Serializable class ** { *; }

# 2. Keep any class that has fields annotated with a kotlinx.serialization
#    annotation (@SerialName, @Required, @Transient …). R8 sees the field
#    annotation but may still prune the class if no constructor is called
#    from explicitly-reachable code (e.g. reflective / proxied paths).
-keepclasseswithmembers class * {
    @kotlinx.serialization.* <fields>;
}

# ---------------------------------------------------------------------------
# Retrofit 2 — defense-in-depth on top of bundled consumer rules
# ---------------------------------------------------------------------------
#
# retrofit2:retrofit already ships consumer rules that:
#   - Keep Signature, InnerClasses, EnclosingMethod, annotation attributes
#   - Keep interfaces with @retrofit2.http.* methods (covers BibleApiService)
#   - Keep the direct return type of each @http-annotated suspend method
#   - Keep kotlin.coroutines.Continuation for suspend-function wrappers
#   - Keep retrofit2.Response
#
# Gap: the bundled -keep for return types uses a shallow class-level keep
# (-keep,allowoptimization,allowshrinking,allowobfuscation class <3>).
# This preserves the top-level DTO class but does NOT prevent R8 from pruning
# *nested* types that only appear as generic type arguments in field
# declarations (e.g. List<VerseDto> inside ChapterResponseDto).
# The generated kotlinx.serialization code for ChapterResponseDto$$serializer
# references VerseDto directly, so R8 usually retains it — but explicit keeps
# provide a stronger safety net for any polymorphic or generic edge cases.
-keep interface org.voxquieta.app.data.remote.api.** { *; }
-keep class org.voxquieta.app.data.remote.models.** { *; }

# ---------------------------------------------------------------------------
# OkHttp 4 / Okio — suppress platform-detection warnings
# ---------------------------------------------------------------------------
#
# OkHttp ships its own consumer rules for its core classes, but it contains
# conditional imports for Conscrypt, BouncyCastle and OpenJSSE that are not
# present on Android. R8 warns about these unresolvable references.
-dontwarn okhttp3.internal.platform.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**

# ---------------------------------------------------------------------------
# Room (local database)
# ---------------------------------------------------------------------------
#
# room-runtime ships a consumer rule that keeps RoomDatabase subclasses.
# KSP generates VoxQuietaDatabase_Impl at compile time, which directly
# references ConversationEntity and MessageEntity constructors/fields, so R8
# sees those classes as reachable without explicit rules.
#
# The one gap: SerializableVerse lives in data.local.mappers and is
# deserialised via Json.decodeFromString<List<SerializableVerse>>(versesJson)
# inside MessageMapper. The reified call emits a direct class reference, so
# R8 should keep it — but keeping the entire local package costs nothing and
# guards against any future TypeConverter additions that use reflection.
-keep class org.voxquieta.app.data.local.** { *; }
