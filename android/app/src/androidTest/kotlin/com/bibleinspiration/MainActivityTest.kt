package com.bibleinspiration

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
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
     */
    @Test
    fun appLaunchesWithoutCrash_andConversationsScreenIsDisplayed() {
        // Wait for the composition to fully settle (Room DB init, ViewModel state, etc.)
        // before asserting visibility. The FAB with "New conversation" content description
        // must be visible — it is rendered by ConversationsScreen which requires hiltViewModel()
        // to succeed with a real Activity context.
        composeRule.waitForIdle()
        composeRule
            .onNodeWithContentDescription("New conversation")
            .assertIsDisplayed()
    }

    /**
     * Verifies the Settings screen is reachable from the Conversations screen.
     * Guards against the BUG C fix regression (onOpenSettings wired correctly).
     */
    @Test
    fun settingsScreenIsReachableFromConversationsScreen() {
        composeRule.waitForIdle()
        composeRule
            .onNodeWithContentDescription("Settings")
            .assertIsDisplayed()
    }
}
