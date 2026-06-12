package org.voxquieta.app.preferences

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.Preferences
import org.voxquieta.app.data.preferences.SessionPreferences
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

@OptIn(ExperimentalCoroutinesApi::class)
class SessionPreferencesTest {

    @get:Rule
    val tmpFolder = TemporaryFolder()

    private val testDispatcher = UnconfinedTestDispatcher()
    private val testScope = TestScope(testDispatcher)

    private lateinit var dataStore: DataStore<Preferences>
    private lateinit var sessionPreferences: SessionPreferences

    @Before
    fun setUp() {
        dataStore = PreferenceDataStoreFactory.create(
            scope = testScope,
            produceFile = { tmpFolder.newFile("test_session_prefs.preferences_pb") },
        )
        sessionPreferences = SessionPreferences(dataStore)
    }

    /**
     * Test A (variant): [SessionPreferences.getOrCreateSessionId] returns a non-blank UUID.
     */
    @Test
    fun `getOrCreateSessionId returns a non-blank id`() = runTest(testDispatcher) {
        val id = sessionPreferences.getOrCreateSessionId()
        assertNotNull(id)
        assertTrue("Session ID must not be blank", id.isNotBlank())
    }

    /**
     * Test A (variant): [SessionPreferences.getOrCreateSessionId] returns a well-formed UUID.
     */
    @Test
    fun `getOrCreateSessionId returns a valid UUID format`() = runTest(testDispatcher) {
        val id = sessionPreferences.getOrCreateSessionId()
        // UUID regex: 8-4-4-4-12 hex characters
        val uuidPattern = Regex(
            "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        )
        assertTrue(
            "Session ID '$id' is not a valid UUID",
            uuidPattern.matches(id),
        )
    }

    /**
     * Test C: [SessionPreferences.getOrCreateSessionId] returns the same ID on repeated calls
     * (stable for the lifetime of the app installation).
     */
    @Test
    fun `getOrCreateSessionId returns stable ID across calls`() = runTest(testDispatcher) {
        val first = sessionPreferences.getOrCreateSessionId()
        val second = sessionPreferences.getOrCreateSessionId()
        val third = sessionPreferences.getOrCreateSessionId()

        assertEquals("Session ID must be identical on every call", first, second)
        assertEquals("Session ID must be identical on every call", first, third)
    }

    /**
     * Test C (variant): a second [SessionPreferences] instance backed by the same DataStore
     * returns the same ID — simulating an app restart with persisted DataStore.
     */
    @Test
    fun `getOrCreateSessionId is stable across fresh SessionPreferences instances sharing DataStore`() =
        runTest(testDispatcher) {
            val id1 = sessionPreferences.getOrCreateSessionId()

            // Simulate a new instance (e.g. after process restart) reusing the same DataStore file
            val anotherInstance = SessionPreferences(dataStore)
            val id2 = anotherInstance.getOrCreateSessionId()

            assertEquals(
                "Session ID must persist across SessionPreferences re-instantiation",
                id1,
                id2,
            )
        }

    /** The interaction count defaults to 0 before anything is written. */
    @Test
    fun `getInteractionCount defaults to zero`() = runTest(testDispatcher) {
        assertEquals(0, sessionPreferences.getInteractionCount())
    }

    /** [SessionPreferences.setInteractionCount] persists the value for later reads. */
    @Test
    fun `setInteractionCount persists the value`() = runTest(testDispatcher) {
        sessionPreferences.setInteractionCount(7)
        assertEquals(7, sessionPreferences.getInteractionCount())
    }

    /**
     * The persisted interaction count survives re-instantiation (process restart),
     * so the 10-message limit is restored on cold start.
     */
    @Test
    fun `interaction count persists across fresh SessionPreferences instances`() =
        runTest(testDispatcher) {
            sessionPreferences.setInteractionCount(9)

            val anotherInstance = SessionPreferences(dataStore)
            assertEquals(9, anotherInstance.getInteractionCount())
        }

    /** Starting a new session via [resetSessionId] zeroes the interaction count. */
    @Test
    fun `resetSessionId resets interaction count to zero`() = runTest(testDispatcher) {
        sessionPreferences.setInteractionCount(10)
        val oldId = sessionPreferences.getOrCreateSessionId()

        val newId = sessionPreferences.resetSessionId()

        assertEquals(0, sessionPreferences.getInteractionCount())
        assertTrue("resetSessionId must issue a new session id", newId != oldId)
    }
}
