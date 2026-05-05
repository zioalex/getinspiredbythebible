package org.voxquieta.app.data.preferences

import android.content.Context
import android.content.Context.MODE_PRIVATE
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import dagger.hilt.android.qualifiers.ApplicationContext
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
    @ApplicationContext private val context: Context,
) {
    companion object {
        private val LANGUAGE_CODE_KEY = stringPreferencesKey("language_code")
        const val DEFAULT_LANGUAGE = "en"
        private const val SYNC_PREFS_FILE = "language_sync_prefs"
        private const val SYNC_KEY = "language_code"

        fun readSync(context: Context): String =
            context.getSharedPreferences(SYNC_PREFS_FILE, MODE_PRIVATE)
                .getString(SYNC_KEY, DEFAULT_LANGUAGE) ?: DEFAULT_LANGUAGE
    }

    /** A [Flow] that emits the currently persisted language code (default: "en"). */
    val languageFlow: Flow<String> = dataStore.data.map { prefs ->
        prefs[LANGUAGE_CODE_KEY] ?: DEFAULT_LANGUAGE
    }

    /** Returns the persisted language code synchronously (reads from SharedPreferences). */
    fun readInitial(): String = readSync(context)

    /**
     * Persists [code] as the selected language.
     *
     * Writes the SharedPreferences mirror with `commit()` so that the value is visible
     * to [readSync] on disk before this call returns. This is required because
     * [MainActivity.attachBaseContext] reads via [readSync] when the Activity is
     * recreated after a language change — using `apply()` (async) would race the
     * recreate and leave the new Activity in the previous locale.
     */
    suspend fun setLanguage(code: String) {
        @Suppress("ApplySharedPref")
        context.getSharedPreferences(SYNC_PREFS_FILE, MODE_PRIVATE)
            .edit()
            .putString(SYNC_KEY, code)
            .commit()
        dataStore.edit { prefs ->
            prefs[LANGUAGE_CODE_KEY] = code
        }
    }
}
