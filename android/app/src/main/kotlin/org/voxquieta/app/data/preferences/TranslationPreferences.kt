package org.voxquieta.app.data.preferences

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import org.voxquieta.app.data.remote.models.TranslationDto
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Manages persistent Bible translation preference via DataStore, scoped per UI
 * language so switching the app's language never carries over a version chosen
 * under a different one (BITB-115). Empty string means no preference for that
 * language — the backend falls back to the language's default.
 */
@Singleton
class TranslationPreferences @Inject constructor(
    private val dataStore: DataStore<Preferences>,
) {
    companion object {
        // Pre-BITB-115 global key, read once for a one-time migration then discarded.
        private val LEGACY_PREFERRED_TRANSLATION_KEY = stringPreferencesKey("preferred_translation")
        const val DEFAULT_TRANSLATION = "" // empty = let backend decide
    }

    private fun keyFor(locale: String) = stringPreferencesKey("preferred_translation_$locale")

    /** A [Flow] emitting the persisted preferred translation ID for [locale] (default: ""). */
    fun preferredTranslationFlow(locale: String): Flow<String> = dataStore.data.map { prefs ->
        prefs[keyFor(locale)] ?: DEFAULT_TRANSLATION
    }

    /** Persists [id] as the preferred translation for [locale]. Pass "" to clear it. */
    suspend fun setPreferredTranslation(locale: String, id: String) {
        dataStore.edit { prefs ->
            if (id.isBlank()) {
                prefs.remove(keyFor(locale))
            } else {
                prefs[keyFor(locale)] = id
            }
        }
    }

    /**
     * One-time migration from the pre-BITB-115 global preference: maps the legacy
     * value to its own language (from [availableTranslations]) so it survives only
     * there, never leaking into whichever language happens to be active when this
     * runs. A value whose language can't be resolved is discarded. No-op once the
     * legacy key is gone.
     */
    suspend fun migrateLegacyPreference(availableTranslations: List<TranslationDto>) {
        val legacy = dataStore.data.first()[LEGACY_PREFERRED_TRANSLATION_KEY] ?: return
        val match = if (legacy.isNotBlank()) availableTranslations.find { it.id == legacy } else null
        dataStore.edit { prefs ->
            if (match != null) {
                val scopedKey = keyFor(match.languageCode)
                if (prefs[scopedKey] == null) {
                    prefs[scopedKey] = legacy
                }
            }
            prefs.remove(LEGACY_PREFERRED_TRANSLATION_KEY)
        }
    }
}
