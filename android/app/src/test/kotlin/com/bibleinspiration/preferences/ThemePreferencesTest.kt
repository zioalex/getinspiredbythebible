package com.bibleinspiration.preferences

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.Preferences
import com.bibleinspiration.data.preferences.ThemePreferences
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

@OptIn(ExperimentalCoroutinesApi::class)
class ThemePreferencesTest {

    @get:Rule
    val tmpFolder = TemporaryFolder()

    private val testDispatcher = UnconfinedTestDispatcher()
    private val testScope = TestScope(testDispatcher)

    private lateinit var dataStore: DataStore<Preferences>
    private lateinit var themePreferences: ThemePreferences

    @Before
    fun setUp() {
        dataStore = PreferenceDataStoreFactory.create(
            scope = testScope,
            produceFile = { tmpFolder.newFile("test_theme_prefs.preferences_pb") },
        )
        themePreferences = ThemePreferences(dataStore)
    }

    @After
    fun tearDown() {
        // DataStore file is cleaned up by TemporaryFolder rule.
    }

    @Test
    fun `default theme mode is system`() = runTest(testDispatcher) {
        val mode = themePreferences.themeModeFlow.first()
        assertEquals("system", mode)
    }

    @Test
    fun `set dark persists dark mode`() = runTest(testDispatcher) {
        themePreferences.setThemeMode("dark")
        val mode = themePreferences.themeModeFlow.first()
        assertEquals("dark", mode)
    }

    @Test
    fun `set light persists light mode`() = runTest(testDispatcher) {
        themePreferences.setThemeMode("light")
        val mode = themePreferences.themeModeFlow.first()
        assertEquals("light", mode)
    }

    @Test
    fun `set dark then light returns light`() = runTest(testDispatcher) {
        themePreferences.setThemeMode("dark")
        themePreferences.setThemeMode("light")
        val mode = themePreferences.themeModeFlow.first()
        assertEquals("light", mode)
    }

    @Test
    fun `set light then system returns system`() = runTest(testDispatcher) {
        themePreferences.setThemeMode("light")
        themePreferences.setThemeMode("system")
        val mode = themePreferences.themeModeFlow.first()
        assertEquals("system", mode)
    }
}
