package org.voxquieta.app.preferences

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.Preferences
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.voxquieta.app.data.preferences.TtsPreferences

/** BITB-119: the "Show Listen button" preference defaults on and persists. */
@OptIn(ExperimentalCoroutinesApi::class)
class TtsPreferencesTest {

    @get:Rule
    val tmpFolder = TemporaryFolder()

    private val testDispatcher = UnconfinedTestDispatcher()
    private val testScope = TestScope(testDispatcher)

    private lateinit var dataStore: DataStore<Preferences>
    private lateinit var ttsPreferences: TtsPreferences

    @Before
    fun setUp() {
        dataStore = PreferenceDataStoreFactory.create(
            scope = testScope,
            produceFile = { tmpFolder.newFile("test_tts_prefs.preferences_pb") },
        )
        ttsPreferences = TtsPreferences(dataStore)
    }

    @Test
    fun `show listen button defaults to on`() = runTest(testDispatcher) {
        assertTrue(ttsPreferences.showListenButtonFlow.first())
    }

    @Test
    fun `turning it off persists`() = runTest(testDispatcher) {
        ttsPreferences.setShowListenButton(false)
        assertFalse(ttsPreferences.showListenButtonFlow.first())
    }

    @Test
    fun `turning it back on persists`() = runTest(testDispatcher) {
        ttsPreferences.setShowListenButton(false)
        ttsPreferences.setShowListenButton(true)
        assertTrue(ttsPreferences.showListenButtonFlow.first())
    }
}
