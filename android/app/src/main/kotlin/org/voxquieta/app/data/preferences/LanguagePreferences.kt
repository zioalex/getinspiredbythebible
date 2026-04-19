package org.voxquieta.app.data.preferences

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Manages persistent language preference via DataStore.
 *
 * Persists the selected BCP-47 language code across app restarts.
 */
@Singleton
class LanguagePreferences @Inject constructor(
    private val dataStore: DataStore<Preferences>,
) {
    companion object {
        private val LANGUAGE_CODE_KEY = stringPreferencesKey("language_code")
        const val DEFAULT_LANGUAGE = "en"
    }

    /** A [Flow] that emits the currently persisted language code (default: "en"). */
    val languageFlow: Flow<String> = dataStore.data.map { prefs ->
        prefs[LANGUAGE_CODE_KEY] ?: DEFAULT_LANGUAGE
    }

    /** Persists [code] as the selected language. */
    suspend fun setLanguage(code: String) {
        dataStore.edit { prefs ->
            prefs[LANGUAGE_CODE_KEY] = code
        }
    }
}
