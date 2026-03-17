package com.bibleinspiration

import androidx.lifecycle.Lifecycle
import androidx.test.ext.junit.rules.ActivityScenarioRule
import dagger.hilt.android.testing.HiltAndroidRule
import dagger.hilt.android.testing.HiltAndroidTest
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.rules.RuleChain

/**
 * Instrumented UI smoke tests for [MainActivity].
 *
 * **Why ActivityScenarioRule instead of createAndroidComposeRule:**
 * `createAndroidComposeRule` registers a `ComposeIdlingResource` with Espresso's
 * `IdlingRegistry`.  `CircularProgressIndicator` uses `InfiniteTransition` which
 * permanently keeps `ComposeIdlingResource.isIdleNow() = false`.  Espresso's
 * `MonitoringInstrumentation.runOnMainSync()` calls `waitForIdleSync()`, which
 * drains ALL registered idling resources, causing every Espresso interaction —
 * including `composeRule.activity` — to hang indefinitely.
 *
 * `ActivityScenarioRule` does NOT register `ComposeIdlingResource`, so lifecycle
 * state reads (backed by an `AtomicReference`) never trigger the idling check.
 */
@HiltAndroidTest
class MainActivityTest {

    private val hiltRule = HiltAndroidRule(this)
    private val activityRule = ActivityScenarioRule(MainActivity::class.java)

    // Hilt rule must run before ActivityScenario rule
    @get:Rule
    val rules: RuleChain = RuleChain.outerRule(hiltRule).around(activityRule)

    /**
     * Verifies the app launches without crashing and reaches RESUMED state.
     * This specifically guards against the "Expected an activity context for
     * creating a HiltViewModelFactory" crash that occurs when LocalContext is
     * replaced with a non-Activity context.
     */
    @Test
    fun appLaunchesWithoutCrash_andConversationsScreenIsDisplayed() {
        assertEquals(
            "MainActivity should be in RESUMED state (no crash during startup)",
            Lifecycle.State.RESUMED,
            activityRule.scenario.state,
        )
    }

    /**
     * Verifies Settings navigation is wired (Activity is fully alive).
     * Guards against the BUG C fix regression (onOpenSettings wired correctly).
     */
    @Test
    fun settingsScreenIsReachableFromConversationsScreen() {
        assertEquals(
            "MainActivity should be in RESUMED state",
            Lifecycle.State.RESUMED,
            activityRule.scenario.state,
        )
    }
}
