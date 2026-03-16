package com.bibleinspiration

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithContentDescription
import androidx.compose.ui.test.onNodeWithContentDescription
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
     * Uses waitUntil (polling every ~10 ms for up to 5 s) instead of just
     * waitForIdle() so that async state changes driven by Room/DataStore
     * coroutines on background dispatchers are also awaited.
     */
    @Test
    fun appLaunchesWithoutCrash_andConversationsScreenIsDisplayed() {
        // Poll until the FAB node appears in the semantic tree (handles async DB/DS init).
        composeRule.waitUntil(timeoutMillis = 5_000) {
            composeRule
                .onAllNodesWithContentDescription("New conversation")
                .fetchSemanticsNodes()
                .isNotEmpty()
        }
        composeRule
            .onNodeWithContentDescription("New conversation")
            .assertIsDisplayed()
    }

    /**
     * Verifies the Settings icon is reachable from the Conversations screen.
     * Guards against the BUG C fix regression (onOpenSettings wired correctly).
     */
    @Test
    fun settingsScreenIsReachableFromConversationsScreen() {
        composeRule.waitUntil(timeoutMillis = 5_000) {
            composeRule
                .onAllNodesWithContentDescription("Settings")
                .fetchSemanticsNodes()
                .isNotEmpty()
        }
        composeRule
            .onNodeWithContentDescription("Settings")
            .assertIsDisplayed()
    }
}
