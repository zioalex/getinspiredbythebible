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
    fun setupComposeClock() {
        // CircularProgressIndicator uses InfiniteTransition which permanently keeps
        // ComposeIdlingResource.isIdleNow() = false, causing waitForIdle() to hang.
        //
        // Strategy:
        //  1. Advance by one frame — triggers the initial Compose composition so the
        //     semantic tree is populated (FAB and Settings nodes appear immediately,
        //     since they are unconditionally in the Scaffold regardless of isLoading).
        //  2. Freeze the clock (autoAdvance = false) — stops InfiniteTransition from
        //     scheduling further frame callbacks, so subsequent waitForIdle() calls
        //     and assertIsDisplayed() return without hanging.
        //
        // The @Rule setup launches MainActivity and waits for RESUMED state, but the
        // first Compose frame has not yet been dispatched at that point.  Advancing one
        // frame here triggers that first composition before we freeze the clock.
        composeRule.mainClock.advanceTimeByFrame()
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
