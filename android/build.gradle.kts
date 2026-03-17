// Top-level build file — configuration shared across all sub-projects/modules.
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.hilt) apply false
    alias(libs.plugins.ksp) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    // Firebase — declared here so the Gradle Plugin Portal resolves them; applied per-module.
    alias(libs.plugins.google.services) apply false
    alias(libs.plugins.firebase.crashlytics) apply false
    // NOTE: OWASP Dependency Check is intentionally NOT applied via the Gradle plugin
    // because OWASP v12+ pulls in BouncyCastle 1.78+ which conflicts with AGP signing.
    // CI uses the OWASP CLI directly (see .github/workflows/android-ci.yml).
}

// Force BouncyCastle to stay at a version compatible with AGP signing.
// OWASP Dependency Check v12+ pulls in BC 1.78+ which breaks validateSigningDebug
// when BC 1.78 lacks EdECObjectIdentifiers at the class path AGP uses.
buildscript {
    configurations.all {
        resolutionStrategy {
            // Downgrade BouncyCastle to the version AGP 8.4.x ships with / expects
            force("org.bouncycastle:bcprov-jdk18on:1.77")
            force("org.bouncycastle:bcpkix-jdk18on:1.77")
        }
    }
}
