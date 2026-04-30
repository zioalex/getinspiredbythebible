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
                excludeGroupByRegex("com\\.google.*")
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
            // Fetch all Google/Android/AndroidX artifacts exclusively from Google Maven.
            // Without this exclusion Gradle also checks mavenCentral() for com.google.*
            // artifacts, which causes transient 403 failures when GitHub Actions IPs are
            // rate-limited by Maven Central.
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral {
            // Mirror of the above: keep Maven Central from being queried for artifacts
            // that are definitively served by Google Maven.
            content {
                excludeGroupByRegex("com\\.android.*")
                excludeGroupByRegex("com\\.google.*")
                excludeGroupByRegex("androidx.*")
            }
        }
        maven {
            url = uri("https://jitpack.io")
            content {
                excludeGroupByRegex("com\\.android.*")
                excludeGroupByRegex("com\\.google.*")
                excludeGroupByRegex("androidx.*")
            }
        }
    }
}

rootProject.name = "VoxQuieta"
include(":app")
