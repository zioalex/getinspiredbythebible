package com.bibleinspiration.data.preferences

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Manages persistent theme preference via DataStore.
 *
 * Persists the user's chosen theme mode ("light", "dark", or "system") across app restarts.
 */
@Singleton
class ThemePreferences @Inject constructor(
    private val dataStore: DataStore<Preferences>,
) {
    companion object {
        private val THEME_MODE_KEY = stringPreferencesKey("theme_mode")
        const val DEFAULT_THEME_MODE = "system"
    }

    /** A [Flow] that emits the currently persisted theme mode (default: "system"). */
    val themeModeFlow: Flow<String> = dataStore.data.map { prefs ->
        prefs[THEME_MODE_KEY] ?: DEFAULT_THEME_MODE
    }

    /** Persists [mode] as the selected theme mode ("light", "dark", or "system"). */
    suspend fun setThemeMode(mode: String) {
        dataStore.edit { prefs ->
            prefs[THEME_MODE_KEY] = mode
        }
    }
}
