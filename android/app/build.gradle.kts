plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.hilt)
    alias(libs.plugins.ksp)
    alias(libs.plugins.google.services)
    alias(libs.plugins.firebase.crashlytics.gradle)
}

android {
    namespace = "org.voxquieta.app"
    compileSdk = 35

    // Helper: read a Gradle property, treating blank/empty as absent so the default kicks in.
    // This prevents CI from injecting an empty string when a GitHub variable is unset.
    fun gradleProp(name: String, default: String): String =
        (project.findProperty(name) as String?)?.takeIf { it.isNotBlank() } ?: default

    // Read the canonical version from the release-please manifest at the
    // repo root. Keeps the Android closed-testing track in sync with the
    // rest of the repo without needing CI to inject `-PversionName=...`.
    val manifestVersionName: String = run {
        val manifestFile = rootProject.projectDir.parentFile?.resolve(".release-please-manifest.json")
        val fallback = "1.0.0"
        if (manifestFile == null || !manifestFile.exists()) {
            fallback
        } else {
            val text = manifestFile.readText(Charsets.UTF_8)
            // Single-source manifest shape: { ".": "1.8.0" }
            val match = Regex("""\"\.\"\s*:\s*\"([^\"]+)\"""").find(text)
            match?.groupValues?.get(1) ?: fallback
        }
    }

    // Resolve release signing inputs once, treating blanks as absent.
    val releaseKeystorePath = (System.getenv("KEYSTORE_PATH")
        ?: (project.findProperty("KEYSTORE_PATH") as String?))?.takeIf { it.isNotBlank() }
    val releaseKeystorePassword = (System.getenv("KEYSTORE_PASSWORD")
        ?: (project.findProperty("KEYSTORE_PASSWORD") as String?))?.takeIf { it.isNotBlank() }
    val releaseKeyAlias = (System.getenv("KEY_ALIAS")
        ?: (project.findProperty("KEY_ALIAS") as String?))?.takeIf { it.isNotBlank() } ?: "release"
    val releaseKeyPassword = (System.getenv("KEY_PASSWORD")
        ?: (project.findProperty("KEY_PASSWORD") as String?))?.takeIf { it.isNotBlank() }
    val releaseSigningConfigured =
        releaseKeystorePath != null && releaseKeystorePassword != null && releaseKeyPassword != null

    signingConfigs {
        if (releaseSigningConfigured) {
            create("release") {
                storeFile = file(releaseKeystorePath!!)
                storePassword = releaseKeystorePassword
                this.keyAlias = releaseKeyAlias
                this.keyPassword = releaseKeyPassword
            }
        }
    }

    defaultConfig {
        applicationId = "org.voxquieta"
        minSdk = 26
        targetSdk = 35
        versionCode = (project.findProperty("versionCode") as String?)?.toIntOrNull() ?: 1
        versionName = (project.findProperty("versionName") as String?)?.takeIf { it.isNotBlank() }
            ?: manifestVersionName

        testInstrumentationRunner = "org.voxquieta.app.HiltTestRunner"
        vectorDrawables {
            useSupportLibrary = true
        }

        // Bundle native debug symbols into the AAB so Play Console can
        // de-obfuscate native (NDK) crashes and ANRs. Resolves the
        // "you've not uploaded debug symbols" warning at upload time.
        ndk {
            debugSymbolLevel = "FULL"
        }
    }

    buildTypes {
        debug {
            isMinifyEnabled = false
            isDebuggable = true
            // Separate package name so debug and release can be installed side-by-side
            // and the release versionCode (Unix timestamp) never blocks a debug install.
            applicationIdSuffix = ".debug"
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
            if (releaseSigningConfigured) {
                signingConfig = signingConfigs.getByName("release")
            } else {
                // Fail only when a release signing task is actually requested, so non-signing
                // tasks (assembleDebug, lint, unit tests, ./gradlew tasks) keep working.
                gradle.taskGraph.whenReady {
                    val needsSigning = allTasks.any { task ->
                        task.project.path == project.path &&
                            (task.name == "signReleaseBundle" ||
                                task.name == "packageReleaseBundle" ||
                                task.name == "signReleaseApk" ||
                                task.name == "packageRelease" ||
                                task.name == "bundleRelease" ||
                                task.name == "assembleRelease")
                    }
                    if (needsSigning) {
                        throw GradleException(
                            "Release signing is not configured. Set KEYSTORE_PATH, KEYSTORE_PASSWORD, " +
                                "KEY_ALIAS and KEY_PASSWORD (env vars or Gradle properties) before " +
                                "running release tasks (e.g. bundleRelease)."
                        )
                    }
                }
            }
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

    packaging {
        jniLibs {
            // Store native (.so) libraries uncompressed so bundletool can page-align
            // them on 16 KB boundaries in the AAB. This is the default for minSdk 26,
            // but is set explicitly here because it is a precondition for Google Play's
            // 16 KB memory-page-size compliance (paired with AGP 8.7+ zipalign).
            useLegacyPackaging = false
        }
    }

    testOptions {
        // Disable system animations during instrumented tests.
        // CircularProgressIndicator uses InfiniteTransition which permanently keeps
        // ComposeIdlingResource busy (isIdleNow() = false), causing waitForIdle() to
        // hang forever. Setting animationsDisabled=true sets all animator duration
        // scales to 0 on the test device so infinite animations complete immediately,
        // unblocking waitForIdle() and any Compose test API that calls it internally.
        animationsDisabled = true
        unitTests {
            // Return default values (0 / false / null) from Android framework stubs
            // instead of throwing RuntimeException("Stub!"). Required for any unit test
            // that transitively touches an Android API (e.g. AppCompatDelegate, Bundle).
            isReturnDefaultValues = true
            // Merge Android resources into the test classpath so Robolectric can resolve
            // stringResource() calls and other resource lookups (BITB-034).
            isIncludeAndroidResources = true
        }
    }

    // BITB-059 AC#4: make the shared cross-platform verse-reference regression corpus
    // (repo-root tests/fixtures/verse_reference_corpus.json — also consumed by the Python and
    // web test suites) available on the JVM unit-test classpath as a plain resource, so
    // VerseCorpusParityTest can load it without duplicating the file into the Android module.
    sourceSets {
        getByName("test") {
            resources.srcDir("../../tests/fixtures")
        }
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
        abortOnError = true
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
    implementation(libs.androidx.appcompat)
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
    // Force the transitive graphics-path native lib to a 16 KB-aligned build so
    // the AAB passes Google Play's 16 KB memory-page-size check (BITB / prod-release).
    implementation(libs.androidx.graphics.path)

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

    // Play In-App Update
    implementation(libs.play.app.update)

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
    // Robolectric-backed Compose UI tests (BITB-034)
    testImplementation(libs.robolectric)
    testImplementation(platform(libs.androidx.compose.bom))
    testImplementation(libs.androidx.ui.test.junit4)
    // ApplicationProvider for Robolectric-backed non-Compose tests (BITB-057)
    testImplementation(libs.androidx.test.core)

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

// ─────────────────────────────────────────────────────────────────────────────
// BITB-031: generate assets/changelog.json from repo-root CHANGELOG.md so the
// in-app "What's New" screen can render release notes without network access.
// Re-runs only when CHANGELOG.md changes (incremental build safe).
// ─────────────────────────────────────────────────────────────────────────────
val generateChangelogJson by tasks.registering {
    val changelogFile = rootProject.projectDir.parentFile.resolve("CHANGELOG.md")
    val outputFile = layout.projectDirectory
        .file("src/main/assets/changelog.json").asFile

    inputs.file(changelogFile).withPropertyName("changelog")
        .withPathSensitivity(org.gradle.api.tasks.PathSensitivity.RELATIVE)
        .optional()
    outputs.file(outputFile).withPropertyName("output")

    doLast {
        outputFile.parentFile.mkdirs()
        if (!changelogFile.exists()) {
            outputFile.writeText("[]")
            return@doLast
        }
        val content = changelogFile.readText(Charsets.UTF_8)
        val headerRe = Regex(
            """^##\s+\[?(\d+\.\d+\.\d+[^\]\s]*)\]?(?:\([^)]*\))?(?:\s*[-–—]\s*(\d{4}-\d{2}-\d{2})|\s+\((\d{4}-\d{2}-\d{2})\))?\s*$""",
            setOf(RegexOption.MULTILINE),
        )
        val matches = headerRe.findAll(content).toList()
        val entries = matches.mapIndexed { idx, m ->
            val version = m.groupValues[1]
            val date = m.groupValues[2].ifBlank { m.groupValues[3] }
            val bodyStart = m.range.last + 1
            val bodyEnd = if (idx + 1 < matches.size) matches[idx + 1].range.first else content.length
            val body = content.substring(bodyStart, bodyEnd).trim()
            Triple(version, date, body)
        }
        fun esc(s: String) = buildString {
            for (c in s) when (c) {
                '\\' -> append("\\\\")
                '"'  -> append("\\\"")
                '\n' -> append("\\n")
                '\r' -> append("\\r")
                '\t' -> append("\\t")
                else -> if (c.code < 0x20) append("\\u%04x".format(c.code)) else append(c)
            }
        }
        val json = buildString {
            append("[\n")
            entries.forEachIndexed { i, (v, d, b) ->
                append("  {")
                append("\"version\":\"").append(esc(v)).append("\",")
                append("\"date\":\"").append(esc(d)).append("\",")
                append("\"body\":\"").append(esc(b)).append("\"")
                append("}")
                if (i < entries.size - 1) append(",")
                append("\n")
            }
            append("]\n")
        }
        outputFile.writeText(json, Charsets.UTF_8)
    }
}

tasks.named("preBuild").configure { dependsOn(generateChangelogJson) }

// BITB-034: Exclude *ComposeTest classes from the required unit-test check so Compose-UI
// flakiness cannot block merges. The exclusion is skipped when -PcomposeTestsOnly is passed
// so the compose-tests workflow can still target these classes via --tests "*ComposeTest".
// tasks.matching().configureEach is lazy — safe to call before AGP registers the task.
tasks.matching { it.name == "testDebugUnitTest" }.configureEach {
    if (!providers.gradleProperty("composeTestsOnly").isPresent) {
        (this as Test).exclude("**/*ComposeTest.class")
    }
}
