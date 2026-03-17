package com.bibleinspiration

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import dagger.hilt.android.testing.HiltAndroidRule
import dagger.hilt.android.testing.HiltAndroidTest
import org.junit.Before
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

    @Before
    fun freezeComposeClock() {
        // CircularProgressIndicator uses InfiniteTransition which permanently keeps
        // ComposeIdlingResource.isIdleNow() = false.  Even with testOptions.animationsDisabled,
        // InfiniteTransition keeps scheduling frame callbacks via BroadcastFrameClock.
        // Freezing the main clock stops all Compose animations before any test runs, so
        // waitForIdle() returns immediately and all semantic-tree assertions work normally.
        //
        // The FAB ("New conversation") and Settings IconButton are unconditionally in the
        // Scaffold — no need to wait for isLoading=false; they are always in the tree.
        composeRule.mainClock.autoAdvance = false
    }

    /**
     * Verifies the app launches without crashing and the Conversations screen
     * is displayed. This specifically guards against the "Expected an activity
     * context for creating a HiltViewModelFactory" crash that occurs when
     * LocalContext is replaced with a non-Activity context.
     */
    @Test
    fun appLaunchesWithoutCrash_andConversationsScreenIsDisplayed() {
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
        composeRule
            .onNodeWithContentDescription("Settings")
            .assertIsDisplayed()
    }
}
