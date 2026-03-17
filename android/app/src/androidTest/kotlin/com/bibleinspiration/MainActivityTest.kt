package com.bibleinspiration

import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.waitUntilAtLeastOneExists
import dagger.hilt.android.testing.HiltAndroidRule
import dagger.hilt.android.testing.HiltAndroidTest
import org.junit.Rule
import org.junit.Test
import org.junit.rules.RuleChain

@HiltAndroidTest
class MainActivityTest {

    private val hiltRule = HiltAndroidRule(this)
    private val composeRule = createAndroidComposeRule<MainActivity>()

    // Hilt rule must run before Compose rule
    @get:Rule
    val rules: RuleChain = RuleChain.outerRule(hiltRule).around(composeRule)

    /**
     * Verifies the app launches without crashing and the Conversations screen
     * is displayed. This specifically guards against the "Expected an activity
     * context for creating a HiltViewModelFactory" crash that occurs when
     * LocalContext is replaced with a non-Activity context.
     *
     * Strategy:
     *   - Wait for the empty-state headline ("Start your first conversation")
     *     using [waitUntilAtLeastOneExists], which polls the semantic tree without
     *     calling waitForIdle(). This is critical because the loading state shows a
     *     CircularProgressIndicator whose infinite InfiniteTransition animation
     *     permanently keeps ComposeIdlingResource busy, causing waitForIdle() to
     *     hang indefinitely and making any approach that calls it internally time out.
     *   - Once the empty state is visible, isLoading=false, the spinner is gone, and
     *     Compose is idle — assertIsDisplayed() works normally for the FAB.
     */
    @OptIn(ExperimentalTestApi::class)
    @Test
    fun appLaunchesWithoutCrash_andConversationsScreenIsDisplayed() {
        // Wait until the loading spinner is gone (Room emitted an empty list →
        // isLoading = false → CircularProgressIndicator removed from tree).
        // waitUntilAtLeastOneExists polls the semantic tree directly without
        // calling waitForIdle(), avoiding the infinite-animation deadlock.
        composeRule.waitUntilAtLeastOneExists(
            matcher = hasText("Start your first conversation"),
            timeoutMillis = 15_000,
        )
        // Now Compose is idle — standard assertion is safe.
        composeRule
            .onNodeWithContentDescription("New conversation")
            .assertIsDisplayed()
    }

    /**
     * Verifies the Settings icon is reachable from the Conversations screen.
     * Guards against the BUG C fix regression (onOpenSettings wired correctly).
     */
    @OptIn(ExperimentalTestApi::class)
    @Test
    fun settingsScreenIsReachableFromConversationsScreen() {
        // Same loading-spinner workaround — wait for empty state before asserting.
        composeRule.waitUntilAtLeastOneExists(
            matcher = hasText("Start your first conversation"),
            timeoutMillis = 15_000,
        )
        composeRule
            .onNodeWithContentDescription("Settings")
            .assertIsDisplayed()
    }
}
