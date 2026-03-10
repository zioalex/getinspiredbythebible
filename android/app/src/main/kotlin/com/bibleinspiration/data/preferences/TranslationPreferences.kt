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
 * Manages persistent Bible translation preference via DataStore.
 *
 * Persists the user's preferred translation ID (e.g. "KJV") across app restarts.
 * An empty string means no preference — the backend will use its own default.
 */
@Singleton
class TranslationPreferences @Inject constructor(
    private val dataStore: DataStore<Preferences>,
) {
    companion object {
        private val PREFERRED_TRANSLATION_KEY = stringPreferencesKey("preferred_translation")
        const val DEFAULT_TRANSLATION = "" // empty = let backend decide
    }

    /** A [Flow] that emits the currently persisted preferred translation ID (default: ""). */
    val preferredTranslationFlow: Flow<String> = dataStore.data.map { prefs ->
        prefs[PREFERRED_TRANSLATION_KEY] ?: DEFAULT_TRANSLATION
    }

    /** Persists [id] as the user's preferred translation. Pass "" to clear the preference. */
    suspend fun setPreferredTranslation(id: String) {
        dataStore.edit { prefs ->
            prefs[PREFERRED_TRANSLATION_KEY] = id
        }
    }
}
