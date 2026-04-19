package org.voxquieta.app.preferences

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.Preferences
import org.voxquieta.app.data.preferences.TranslationPreferences
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
class TranslationPreferencesTest {

    @get:Rule
    val tmpFolder = TemporaryFolder()

    private val testDispatcher = UnconfinedTestDispatcher()
    private val testScope = TestScope(testDispatcher)

    private lateinit var dataStore: DataStore<Preferences>
    private lateinit var translationPreferences: TranslationPreferences

    @Before
    fun setUp() {
        dataStore = PreferenceDataStoreFactory.create(
            scope = testScope,
            produceFile = { tmpFolder.newFile("test_translation_prefs.preferences_pb") },
        )
        translationPreferences = TranslationPreferences(dataStore)
    }

    @After
    fun tearDown() {
        // DataStore file is cleaned up by TemporaryFolder rule.
    }

    @Test
    fun `default preferred translation is empty string`() = runTest(testDispatcher) {
        val translation = translationPreferences.preferredTranslationFlow.first()
        assertEquals("", translation)
    }

    @Test
    fun `set KJV persists KJV translation id`() = runTest(testDispatcher) {
        translationPreferences.setPreferredTranslation("KJV")
        val translation = translationPreferences.preferredTranslationFlow.first()
        assertEquals("KJV", translation)
    }

    @Test
    fun `set NIV persists NIV translation id`() = runTest(testDispatcher) {
        translationPreferences.setPreferredTranslation("NIV")
        val translation = translationPreferences.preferredTranslationFlow.first()
        assertEquals("NIV", translation)
    }

    @Test
    fun `set KJV then clear returns empty string`() = runTest(testDispatcher) {
        translationPreferences.setPreferredTranslation("KJV")
        translationPreferences.setPreferredTranslation("")
        val translation = translationPreferences.preferredTranslationFlow.first()
        assertEquals("", translation)
    }

    @Test
    fun `set KJV then NIV returns NIV`() = runTest(testDispatcher) {
        translationPreferences.setPreferredTranslation("KJV")
        translationPreferences.setPreferredTranslation("NIV")
        val translation = translationPreferences.preferredTranslationFlow.first()
        assertEquals("NIV", translation)
    }
}
