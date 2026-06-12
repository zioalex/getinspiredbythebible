package org.voxquieta.app.data.preferences

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import kotlinx.coroutines.flow.first
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Manages a stable, app-lifetime session ID via DataStore.
 *
 * The session ID is a UUID generated once on first access and persisted across
 * app restarts for the lifetime of the installation. It is used by the backend
 * for DAU/MAU analytics, matching the `session_id` behaviour on web (where a
 * UUID is stored in `sessionStorage` per tab).
 */
@Singleton
class SessionPreferences @Inject constructor(
    private val dataStore: DataStore<Preferences>,
) {
    companion object {
        private val SESSION_ID_KEY = stringPreferencesKey("session_id")
        private val INTERACTION_COUNT_KEY = intPreferencesKey("interaction_count")
    }

    /**
     * Reads the persisted interaction count (0 if never written).
     *
     * Persisted so the 10-message limit survives app restarts and conversation
     * loads. Keyed to the session lifetime: reset to 0 by [resetSessionId].
     */
    suspend fun getInteractionCount(): Int =
        dataStore.data.first()[INTERACTION_COUNT_KEY] ?: 0

    /** Persists the interaction count for the current session. */
    suspend fun setInteractionCount(count: Int) {
        dataStore.edit { prefs -> prefs[INTERACTION_COUNT_KEY] = count }
    }

    /**
     * Returns the persisted session ID, creating and persisting a new UUID if
     * no session ID has been stored yet.
     *
     * This function is safe to call concurrently — DataStore's atomic [edit]
     * ensures only one UUID is ever written on first access.
     */
    suspend fun getOrCreateSessionId(): String {
        val existing = dataStore.data.first()[SESSION_ID_KEY]
        if (existing != null) return existing
        val newId = UUID.randomUUID().toString()
        dataStore.edit { prefs -> prefs[SESSION_ID_KEY] = newId }
        return newId
    }

    /**
     * Generates and persists a new session ID, replacing the existing one, and
     * resets the persisted interaction count to 0 in the same atomic edit. Call
     * this when starting a new session so both the backend and the local
     * 10-message limit reset together.
     */
    suspend fun resetSessionId(): String {
        val newId = UUID.randomUUID().toString()
        dataStore.edit { prefs ->
            prefs[SESSION_ID_KEY] = newId
            prefs[INTERACTION_COUNT_KEY] = 0
        }
        return newId
    }
}
