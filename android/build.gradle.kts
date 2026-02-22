// Top-level build file where you can add configuration options common to all sub-projects/modules.
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.hilt.android) apply false
    alias(libs.plugins.ksp) apply false
    alias(libs.plugins.owasp.dependency.check) apply false
}

// OWASP Dependency Check configuration (applied at root level so it scans all modules)
dependencyCheck {
    // Fail the build if any dependency has a CVSS score >= 7.0 (HIGH or CRITICAL)
    failBuildOnCVSS = 7.0f
    // XML file listing known false positives to suppress
    suppressionFile = "dependency-check-suppressions.xml"
    // Output report format
    format = "HTML"
    nvd {
        // Optional: speeds up NVD data download; leave blank to use anonymous rate-limited access
        apiKey = System.getenv("NVD_API_KEY") ?: ""
    }
}
