package org.voxquieta.app.data.preferences

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import kotlinx.coroutines.flow.first
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Persists the id of the conversation the user most recently opened so that the
 * app can resume directly into that chat on the next cold start.
 */
@Singleton
class LastConversationPreferences @Inject constructor(
    private val dataStore: DataStore<Preferences>,
) {
    companion object {
        private val LAST_CONVERSATION_ID_KEY = stringPreferencesKey("last_conversation_id")
    }

    suspend fun getLastConversationId(): String? =
        dataStore.data.first()[LAST_CONVERSATION_ID_KEY]

    suspend fun setLastConversationId(id: String?) {
        dataStore.edit { prefs ->
            if (id == null) {
                prefs.remove(LAST_CONVERSATION_ID_KEY)
            } else {
                prefs[LAST_CONVERSATION_ID_KEY] = id
            }
        }
    }
}
