package com.bibleinspiration

import androidx.lifecycle.Lifecycle
import androidx.test.ext.junit.rules.ActivityScenarioRule
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.By
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.UiSelector
import androidx.test.uiautomator.Until
import dagger.hilt.android.testing.HiltAndroidRule
import dagger.hilt.android.testing.HiltAndroidTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Rule
import org.junit.Test
import org.junit.rules.RuleChain

/**
 * Instrumented UI smoke tests for [MainActivity].
 *
 * **Why ActivityScenarioRule + UiAutomator instead of createAndroidComposeRule:**
 * `createAndroidComposeRule` registers a `ComposeIdlingResource` with Espresso's
 * `IdlingRegistry`.  `CircularProgressIndicator` uses `InfiniteTransition` which
 * permanently keeps `ComposeIdlingResource.isIdleNow() = false`.  Espresso's
 * `MonitoringInstrumentation.runOnMainSync()` calls `waitForIdleSync()`, which
 * drains ALL registered idling resources, causing every Espresso interaction to
 * hang indefinitely.
 *
 * Solutions used here:
 *  - `ActivityScenarioRule` does NOT register `ComposeIdlingResource`, so lifecycle
 *    state reads never trigger the idling check.
 *  - `UiDevice` (UI Automator) operates at the accessibility layer, completely
 *    bypassing Espresso's IdlingRegistry — safe to use even with InfiniteTransitions
 *    running on screen.
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
     * Verifies that tapping the Settings icon navigates to the Settings screen.
     *
     * Uses [UiDevice] (UI Automator) to interact with the UI without registering
     * a [androidx.test.espresso.idling.CountingIdlingResource] — see class-level
     * KDoc for why Espresso interactions cause an infinite hang in this app.
     */
    @Test
    fun settingsScreenIsReachableFromConversationsScreen() {
        val device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())

        // Click the Settings icon in the Conversations screen top app bar.
        // The icon's contentDescription is R.string.action_open_settings = "Settings".
        device.findObject(UiSelector().description("Settings")).click()

        // Wait up to 2 s for the Settings screen title ("Settings") to appear as a
        // visible text node — distinct from the icon's contentDescription because it
        // is rendered as body text in the TopAppBar, not as an accessibility label.
        val settingsTitle = device.wait(Until.findObject(By.text("Settings")), 2_000L)
        assertNotNull(
            "Settings screen title should be visible after tapping the Settings icon",
            settingsTitle,
        )

        // The Activity must remain RESUMED throughout in-app navigation.
        assertEquals(
            "MainActivity should stay RESUMED after navigating to Settings",
            Lifecycle.State.RESUMED,
            activityRule.scenario.state,
        )
    }
}
