package com.bibleinspiration.data.preferences

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
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
     * Generates and persists a new session ID, replacing the existing one.
     * Call this when starting a new session so the backend resets its
     * per-session message counter.
     */
    suspend fun resetSessionId(): String {
        val newId = UUID.randomUUID().toString()
        dataStore.edit { prefs -> prefs[SESSION_ID_KEY] = newId }
        return newId
    }
}
