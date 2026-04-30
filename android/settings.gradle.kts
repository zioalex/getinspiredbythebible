pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral {
            content {
                excludeGroupByRegex("com\\.android.*")
                excludeGroupByRegex("androidx.*")
            }
        }
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google {
            // Optimization hint: fetch Android/AndroidX artifacts from Google Maven first.
            // Note: com.google.* is intentionally NOT included here because many Google
            // artifacts (Dagger/Hilt, Guava, ErrorProne) live on Maven Central, not Google Maven.
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral {
            // Exclude artifacts that are definitively Google Maven-only to avoid
            // unnecessary Maven Central requests (and transient 403 rate-limits).
            content {
                excludeGroupByRegex("com\\.android.*")
                excludeGroupByRegex("androidx.*")
            }
        }
        maven {
            url = uri("https://jitpack.io")
            content {
                excludeGroupByRegex("com\\.android.*")
                excludeGroupByRegex("androidx.*")
            }
        }
    }
}

rootProject.name = "VoxQuieta"
include(":app")
