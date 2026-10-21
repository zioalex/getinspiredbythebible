package org.voxquieta.app.testing

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.voxquieta.app.tts.SpeechEngine

/** In-memory [SpeechEngine] for ViewModel/UI tests (BITB-119). Records every call. */
class FakeSpeechEngine(
    ready: Boolean = true,
    /** Primary language codes this fake pretends to have an offline voice for. */
    val localLanguages: MutableSet<String> = mutableSetOf("en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"),
) : SpeechEngine {

    data class Spoken(val id: String, val chunks: List<String>, val languageTag: String)

    private val _isReady = MutableStateFlow(ready)
    override val isReady: StateFlow<Boolean> = _isReady.asStateFlow()

    private val _speakingId = MutableStateFlow<String?>(null)
    override val speakingId: StateFlow<String?> = _speakingId.asStateFlow()

    val spoken = mutableListOf<Spoken>()
    var warmUpCalls = 0
        private set
    var stopCalls = 0
        private set

    /** Simulates audio focus being denied: speak() then refuses. */
    var audioFocusGranted = true

    fun setReady(value: Boolean) {
        _isReady.value = value
    }

    /** Simulates the last chunk finishing on its own. */
    fun finishSpeaking() {
        _speakingId.value = null
    }

    override fun warmUp() {
        warmUpCalls++
    }

    override fun hasLocalVoice(languageTag: String): Boolean =
        _isReady.value && languageTag.substringBefore('-').substringBefore('_').lowercase() in localLanguages

    override fun speak(id: String, chunks: List<String>, languageTag: String): Boolean {
        if (chunks.isEmpty() || !hasLocalVoice(languageTag) || !audioFocusGranted) return false
        spoken += Spoken(id, chunks, languageTag)
        _speakingId.value = id // replaces whatever was speaking: one voice at a time
        return true
    }

    override fun stop() {
        stopCalls++
        _speakingId.value = null
    }
}
