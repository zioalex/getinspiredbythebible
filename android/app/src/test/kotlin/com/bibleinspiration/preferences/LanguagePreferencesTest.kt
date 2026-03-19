package com.bibleinspiration.preferences

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.Preferences
import com.bibleinspiration.data.preferences.LanguagePreferences
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

/**
 * Unit tests for [LanguagePreferences].
 *
 * Uses an in-process [PreferenceDataStoreFactory] backed by a temporary file so
 * tests are hermetic and file-clean-up is handled by the [TemporaryFolder] rule.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class LanguagePreferencesTest {

    @get:Rule
    val tmpFolder = TemporaryFolder()

    private val testDispatcher = UnconfinedTestDispatcher()
    private val testScope = TestScope(testDispatcher)

    private lateinit var dataStore: DataStore<Preferences>
    private lateinit var languagePreferences: LanguagePreferences

    @Before
    fun setUp() {
        dataStore = PreferenceDataStoreFactory.create(
            scope = testScope,
            produceFile = { tmpFolder.newFile("test_language_prefs.preferences_pb") },
        )
        languagePreferences = LanguagePreferences(dataStore)
    }

    @After
    fun tearDown() {
        // TemporaryFolder rule cleans up the DataStore file automatically.
    }

    // ── Default value ─────────────────────────────────────────────────────────

    @Test
    fun `default language code is en`() = runTest(testDispatcher) {
        val code = languagePreferences.languageFlow.first()
        assertEquals("en", code)
    }

    @Test
    fun `DEFAULT_LANGUAGE constant equals en`() {
        assertEquals("en", LanguagePreferences.DEFAULT_LANGUAGE)
    }

    // ── Single set ────────────────────────────────────────────────────────────

    @Test
    fun `setLanguage persists Italian code`() = runTest(testDispatcher) {
        languagePreferences.setLanguage("it")
        assertEquals("it", languagePreferences.languageFlow.first())
    }

    @Test
    fun `setLanguage persists German code`() = runTest(testDispatcher) {
        languagePreferences.setLanguage("de")
        assertEquals("de", languagePreferences.languageFlow.first())
    }

    @Test
    fun `setLanguage persists Spanish code`() = runTest(testDispatcher) {
        languagePreferences.setLanguage("es")
        assertEquals("es", languagePreferences.languageFlow.first())
    }

    @Test
    fun `setLanguage persists French code`() = runTest(testDispatcher) {
        languagePreferences.setLanguage("fr")
        assertEquals("fr", languagePreferences.languageFlow.first())
    }

    @Test
    fun `setLanguage persists Arabic code`() = runTest(testDispatcher) {
        languagePreferences.setLanguage("ar")
        assertEquals("ar", languagePreferences.languageFlow.first())
    }

    @Test
    fun `setLanguage persists Portuguese code`() = runTest(testDispatcher) {
        languagePreferences.setLanguage("pt")
        assertEquals("pt", languagePreferences.languageFlow.first())
    }

    @Test
    fun `setLanguage persists Russian code`() = runTest(testDispatcher) {
        languagePreferences.setLanguage("ru")
        assertEquals("ru", languagePreferences.languageFlow.first())
    }

    @Test
    fun `setLanguage persists Chinese code`() = runTest(testDispatcher) {
        languagePreferences.setLanguage("zh")
        assertEquals("zh", languagePreferences.languageFlow.first())
    }

    @Test
    fun `setLanguage persists Hindi code`() = runTest(testDispatcher) {
        languagePreferences.setLanguage("hi")
        assertEquals("hi", languagePreferences.languageFlow.first())
    }

    @Test
    fun `setLanguage persists Korean code`() = runTest(testDispatcher) {
        languagePreferences.setLanguage("ko")
        assertEquals("ko", languagePreferences.languageFlow.first())
    }

    // ── Sequential overwrites ─────────────────────────────────────────────────

    @Test
    fun `setLanguage twice keeps the last value`() = runTest(testDispatcher) {
        languagePreferences.setLanguage("it")
        languagePreferences.setLanguage("de")
        assertEquals("de", languagePreferences.languageFlow.first())
    }

    @Test
    fun `setLanguage can be reset back to en`() = runTest(testDispatcher) {
        languagePreferences.setLanguage("ar")
        languagePreferences.setLanguage("en")
        assertEquals("en", languagePreferences.languageFlow.first())
    }

    @Test
    fun `setLanguage multiple times keeps only latest value`() = runTest(testDispatcher) {
        languagePreferences.setLanguage("it")
        languagePreferences.setLanguage("de")
        languagePreferences.setLanguage("fr")
        languagePreferences.setLanguage("zh")
        assertEquals("zh", languagePreferences.languageFlow.first())
    }

    // ── Persistence across instances ──────────────────────────────────────────

    @Test
    fun `setLanguage is stable across fresh LanguagePreferences instances sharing DataStore`() =
        runTest(testDispatcher) {
            languagePreferences.setLanguage("ko")

            // Simulate a new instance reusing the same DataStore (e.g. after DI re-creation).
            val anotherInstance = LanguagePreferences(dataStore)
            assertEquals(
                "ko",
                anotherInstance.languageFlow.first(),
            )
        }
}
