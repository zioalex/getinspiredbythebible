plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.hilt)
    alias(libs.plugins.ksp)
    alias(libs.plugins.google.services)
}

android {
    namespace = "org.voxquieta.app"
    compileSdk = 35

    // Helper: read a Gradle property, treating blank/empty as absent so the default kicks in.
    // This prevents CI from injecting an empty string when a GitHub variable is unset.
    fun gradleProp(name: String, default: String): String =
        (project.findProperty(name) as String?)?.takeIf { it.isNotBlank() } ?: default

    signingConfigs {
        create("release") {
            val keystorePath = System.getenv("KEYSTORE_PATH")
                ?: (project.findProperty("KEYSTORE_PATH") as String?)
            val keystorePassword = System.getenv("KEYSTORE_PASSWORD")
                ?: (project.findProperty("KEYSTORE_PASSWORD") as String?)
            val keyAlias = System.getenv("KEY_ALIAS")
                ?: (project.findProperty("KEY_ALIAS") as String?) ?: "release"
            val keyPassword = System.getenv("KEY_PASSWORD")
                ?: (project.findProperty("KEY_PASSWORD") as String?)
            if (keystorePath != null && keystorePassword != null && keyPassword != null) {
                storeFile = file(keystorePath)
                storePassword = keystorePassword
                this.keyAlias = keyAlias
                this.keyPassword = keyPassword
            }
        }
    }

    defaultConfig {
        applicationId = "org.voxquieta.app"
        minSdk = 26
        targetSdk = 35
        versionCode = (project.findProperty("versionCode") as String?)?.toIntOrNull() ?: 1
        versionName = (project.findProperty("versionName") as String?) ?: "1.0.0"

        testInstrumentationRunner = "org.voxquieta.app.HiltTestRunner"
        vectorDrawables {
            useSupportLibrary = true
        }
    }

    buildTypes {
        debug {
            isMinifyEnabled = false
            isDebuggable = true
            // Default: emulator localhost for local dev. Override with -PbaseUrl=... to hit prod.
            buildConfigField("String", "BASE_URL", "\"${gradleProp("baseUrl", "http://10.0.2.2:8000/")}\"")
            // Firebase is disabled in debug builds — no crash reports or analytics sent.
            buildConfigField("Boolean", "FIREBASE_ENABLED", "false")
            buildConfigField("String", "PRIVACY_POLICY_URL", "\"${gradleProp("privacyPolicyUrl", "https://voxquieta.org/privacy")}\"")
            buildConfigField("String", "FRONTEND_URL", "\"${gradleProp("frontendUrl", "https://voxquieta.org")}\"")
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.getByName("release")
            // BASE_URL injected via CI — override with -PbaseUrl=... or env var
            buildConfigField("String", "BASE_URL", "\"${gradleProp("baseUrl", "https://api.voxquieta.org/")}\"")
            // Firebase is enabled only in release builds.
            buildConfigField("Boolean", "FIREBASE_ENABLED", "true")
            buildConfigField("String", "PRIVACY_POLICY_URL", "\"${gradleProp("privacyPolicyUrl", "https://voxquieta.org/privacy")}\"")
            buildConfigField("String", "FRONTEND_URL", "\"${gradleProp("frontendUrl", "https://voxquieta.org")}\"")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    testOptions {
        // Disable system animations during instrumented tests.
        // CircularProgressIndicator uses InfiniteTransition which permanently keeps
        // ComposeIdlingResource busy (isIdleNow() = false), causing waitForIdle() to
        // hang forever. Setting animationsDisabled=true sets all animator duration
        // scales to 0 on the test device so infinite animations complete immediately,
        // unblocking waitForIdle() and any Compose test API that calls it internally.
        animationsDisabled = true
    }

    lint {
        baseline = file("lint-baseline.xml")
        checkDependencies = false
        // TODO: Re-enable abortOnError=true once lint-baseline.xml is populated.
        // Steps to regenerate the baseline in a full Android SDK environment:
        //   1. ./gradlew lintDebug -Dlint.baselines.continue=true
        //   2. Commit the updated lint-baseline.xml
        //   3. Set abortOnError = true here
        // Note: AGP 8.4.2 does not honour -Dlint.baselines.continue=true for ERROR-severity
        // issues in the same run; run the task twice if needed.
        abortOnError = false
        warningsAsErrors = false   // Warnings (e.g. from compose-markdown) do not elevate to errors
        // Suppress rules that fire on generated/third-party code even with checkDependencies=false
        disable += setOf(
            "ObsoleteLintCustomCheck",
            "InvalidPackage",
        )
    }
}

ksp {
    arg("room.schemaLocation", "$projectDir/schemas")
}

dependencies {
    // Core
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)

    // Compose BOM
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)
    implementation(libs.androidx.material.icons.extended)

    // Navigation
    implementation(libs.androidx.navigation.compose)

    // Hilt
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)
    implementation(libs.hilt.navigation.compose)

    // Room
    implementation(libs.room.runtime)
    ksp(libs.room.compiler)
    implementation(libs.room.ktx)

    // DataStore
    implementation(libs.datastore.preferences)

    // Networking
    implementation(libs.retrofit)
    implementation(libs.retrofit.kotlinx.serialization)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging)

    // Serialization
    implementation(libs.kotlinx.serialization.json)

    // Coroutines
    implementation(libs.kotlinx.coroutines.android)

    // Logging
    implementation(libs.timber)

    // Splash Screen
    implementation(libs.androidx.core.splashscreen)

    // Markdown rendering
    implementation(libs.compose.markdown)

    // Firebase (BOM ensures all Firebase libraries use compatible versions)
    implementation(platform(libs.firebase.bom))
    implementation(libs.firebase.crashlytics)
    implementation(libs.firebase.analytics)

    // --- Testing ---
    testImplementation(libs.junit)
    testImplementation(libs.mockk)
    testImplementation(libs.kotlinx.coroutines.test)

    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.ui.test.junit4)
    // Instrumented / UI tests
    androidTestImplementation(libs.hilt.android.testing)
    kspAndroidTest(libs.hilt.android.compiler.test)
    androidTestImplementation(libs.androidx.test.runner)
    debugImplementation(libs.androidx.ui.tooling)
    debugImplementation(libs.androidx.ui.test.manifest)
}
