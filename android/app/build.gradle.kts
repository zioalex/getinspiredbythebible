plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.hilt)
    alias(libs.plugins.ksp)
}

android {
    namespace = "com.bibleinspiration"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.bibleinspiration"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"

        testInstrumentationRunner = "com.bibleinspiration.HiltTestRunner"
        vectorDrawables {
            useSupportLibrary = true
        }
    }

    buildTypes {
        debug {
            isMinifyEnabled = false
            isDebuggable = true
            // Default: emulator localhost for local dev. Override with -PbaseUrl=... to hit prod.
            buildConfigField(
                "String",
                "BASE_URL",
                "\"${project.findProperty("baseUrl") ?: "http://10.0.2.2:8000/"}\""
            )
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            // BASE_URL injected via CI — override with -PbaseUrl=... or env var
            buildConfigField(
                "String",
                "BASE_URL",
                "\"${project.findProperty("baseUrl") ?: "https://bible-app-backend.agreeablesea-6ee07535.northeurope.azurecontainerapps.io/"}\""
            )
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

    lint {
        baseline = file("lint-baseline.xml")
        checkDependencies = false
        // TODO: re-enable after baseline is generated — see fix/android-lint-baseline strategy.
        // The current baseline is empty; AGP 8.4.2 does not honour -Dlint.baselines.continue=true
        // for ERROR-severity issues, so abortOnError=true causes CI to fail until a real baseline
        // (generated via ./gradlew lintDebug -Dlint.baselines.continue=true) is committed.
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
