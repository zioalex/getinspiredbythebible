package org.voxquieta.app.data.preferences

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

/**
 * BITB-119: persists the "Show Listen button" preference via DataStore (default on).
 */
@Singleton
class TtsPreferences @Inject constructor(
    private val dataStore: DataStore<Preferences>,
) {
    companion object {
        private val SHOW_LISTEN_BUTTON_KEY = booleanPreferencesKey("show_listen_button")
        const val DEFAULT_SHOW_LISTEN_BUTTON = true
    }

    /** A [Flow] that emits whether the Listen (read aloud) button should be shown. */
    val showListenButtonFlow: Flow<Boolean> = dataStore.data.map { prefs ->
        prefs[SHOW_LISTEN_BUTTON_KEY] ?: DEFAULT_SHOW_LISTEN_BUTTON
    }

    /** Persists whether the Listen button is shown. */
    suspend fun setShowListenButton(show: Boolean) {
        dataStore.edit { prefs ->
            prefs[SHOW_LISTEN_BUTTON_KEY] = show
        }
    }
}
