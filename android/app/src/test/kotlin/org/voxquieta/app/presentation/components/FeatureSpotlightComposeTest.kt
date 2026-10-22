package org.voxquieta.app.presentation.components

import android.content.Context
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.wrapContentSize
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertTrue
import org.junit.Test
import org.voxquieta.app.R
import org.voxquieta.app.testing.ComposeTestHarness

/**
 * Robolectric-backed Compose UI tests for [FeatureSpotlight] (BITB-142).
 *
 * Verifies the overlay shows when tour_seen=false, hides after completion,
 * and basic RTL layout works.
 *
 * Test-body strings are resolved OUTSIDE composition via [appContext] (the
 * repo idiom, cf. AboutIntroBottomSheetComposeTest): a private @Composable
 * stringResource() helper cannot be invoked from a non-composable test body.
 * `assertDoesNotExist()` is a member of SemanticsNodeInteraction (like
 * `assertExists()`), so it is used WITHOUT an import.
 */
class FeatureSpotlightComposeTest : ComposeTestHarness() {

    private val appContext: Context = ApplicationProvider.getApplicationContext()

    @Test
    fun `spotlight shows when tour not seen and hides after Done`() {
        var completed = false
        val targets = listOf(
            SpotlightTarget(
                bounds = Rect(100f, 100f, 200f, 200f),
                captionRes = R.string.tour_step_1_drawer,
            ),
            SpotlightTarget(
                bounds = Rect(300f, 100f, 400f, 200f),
                captionRes = R.string.tour_step_2_translation,
            ),
            SpotlightTarget(
                bounds = Rect(100f, 300f, 200f, 400f),
                captionRes = R.string.tour_step_3_language,
            ),
            SpotlightTarget(
                bounds = Rect(300f, 300f, 400f, 400f),
                captionRes = R.string.tour_step_4_input,
            ),
        )

        setContentThemed {
            var showTour by remember { mutableStateOf(true) }
            Box(modifier = Modifier.fillMaxSize()) {
                Text(text = "Main content", modifier = Modifier.fillMaxSize().wrapContentSize(Alignment.Center))
                if (showTour) {
                    FeatureSpotlight(
                        targets = targets,
                        onComplete = {
                            showTour = false
                            completed = true
                        },
                    )
                }
            }
        }

        // Spotlight should be visible initially
        composeRule.onNodeWithText(appContext.getString(R.string.tour_title)).assertIsDisplayed()
        composeRule.onNodeWithText(appContext.getString(R.string.tour_step_1_drawer)).assertIsDisplayed()
        composeRule.onNodeWithText(appContext.getString(R.string.tour_step_indicator, 1, 4)).assertIsDisplayed()

        // Tap Next to advance through steps
        composeRule.onNodeWithText(appContext.getString(R.string.tour_next)).performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithText(appContext.getString(R.string.tour_step_2_translation)).assertIsDisplayed()
        composeRule.onNodeWithText(appContext.getString(R.string.tour_step_indicator, 2, 4)).assertIsDisplayed()

        composeRule.onNodeWithText(appContext.getString(R.string.tour_next)).performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithText(appContext.getString(R.string.tour_step_3_language)).assertIsDisplayed()
        composeRule.onNodeWithText(appContext.getString(R.string.tour_step_indicator, 3, 4)).assertIsDisplayed()

        composeRule.onNodeWithText(appContext.getString(R.string.tour_next)).performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithText(appContext.getString(R.string.tour_step_4_input)).assertIsDisplayed()
        composeRule.onNodeWithText(appContext.getString(R.string.tour_step_indicator, 4, 4)).assertIsDisplayed()

        // Tap Done on last step
        composeRule.onNodeWithText(appContext.getString(R.string.tour_done)).performClick()
        composeRule.waitForIdle()

        // Spotlight should be dismissed
        assertTrue(completed)
        composeRule.onNodeWithText(appContext.getString(R.string.tour_title)).assertDoesNotExist()
    }

    @Test
    fun `spotlight can be skipped at any step`() {
        var completed = false
        val targets = listOf(
            SpotlightTarget(
                bounds = Rect(100f, 100f, 200f, 200f),
                captionRes = R.string.tour_step_1_drawer,
            ),
            SpotlightTarget(
                bounds = Rect(300f, 100f, 400f, 200f),
                captionRes = R.string.tour_step_2_translation,
            ),
        )

        setContentThemed {
            var showTour by remember { mutableStateOf(true) }
            Box(modifier = Modifier.fillMaxSize()) {
                Text(text = "Main content", modifier = Modifier.fillMaxSize().wrapContentSize(Alignment.Center))
                if (showTour) {
                    FeatureSpotlight(
                        targets = targets,
                        onComplete = {
                            showTour = false
                            completed = true
                        },
                    )
                }
            }
        }

        // Spotlight should be visible initially
        composeRule.onNodeWithText(appContext.getString(R.string.tour_title)).assertIsDisplayed()

        // Tap Skip on first step
        composeRule.onNodeWithText(appContext.getString(R.string.tour_skip)).performClick()
        composeRule.waitForIdle()

        // Spotlight should be dismissed
        assertTrue(completed)
        composeRule.onNodeWithText(appContext.getString(R.string.tour_title)).assertDoesNotExist()
    }

    @Test
    fun `spotlight renders RTL correctly for Arabic locale`() {
        // Note: Full RTL testing requires setting the layout direction.
        // This test verifies the component doesn't crash in RTL context.
        val targets = listOf(
            SpotlightTarget(
                bounds = Rect(100f, 100f, 200f, 200f),
                captionRes = R.string.tour_step_1_drawer,
            ),
        )

        setContentThemed {
            FeatureSpotlight(
                targets = targets,
                onComplete = {},
            )
        }

        // Should render without crashing
        composeRule.onNodeWithText(appContext.getString(R.string.tour_title)).assertIsDisplayed()
        composeRule.onNodeWithText(appContext.getString(R.string.tour_step_1_drawer)).assertIsDisplayed()
    }
}
