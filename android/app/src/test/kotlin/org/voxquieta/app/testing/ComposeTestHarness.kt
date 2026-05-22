package org.voxquieta.app.testing

import androidx.compose.runtime.Composable
import androidx.compose.ui.test.junit4.ComposeContentTestRule
import androidx.compose.ui.test.junit4.createComposeRule
import org.junit.Rule
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.voxquieta.app.presentation.theme.VoxQuietaTheme

/**
 * Base class for Robolectric-backed Compose UI tests (BITB-034).
 *
 * Subclasses inherit [composeRule] and the [setContentThemed] helper that
 * wraps the content under [VoxQuietaTheme] — matching the production
 * theme wiring so MaterialTheme tokens resolve correctly.
 *
 * Config notes:
 * - [RobolectricTestRunner] provides a real Android [android.content.Context]
 *   without requiring an emulator.
 * - [Config.sdk] pinned to API 34 — Robolectric 4.14.1 bundles API-34 jars;
 *   compileSdk 35 behaviours must be covered by instrumented tests.
 * - [Config.application] set to the plain [android.app.Application] to keep
 *   Hilt out of unit-test scope; composable-only tests don't need DI.
 */
@RunWith(RobolectricTestRunner::class)
@Config(
    sdk = [34],
    application = android.app.Application::class,
)
abstract class ComposeTestHarness {

    @get:Rule
    val composeRule: ComposeContentTestRule = createComposeRule()

    /** Mounts [content] wrapped in [VoxQuietaTheme]. */
    protected fun setContentThemed(content: @Composable () -> Unit) {
        composeRule.setContent {
            VoxQuietaTheme {
                content()
            }
        }
    }
}
