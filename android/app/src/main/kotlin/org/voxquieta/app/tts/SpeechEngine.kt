package org.voxquieta.app.tts

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.speech.tts.Voice
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import timber.log.Timber
import java.util.Locale
import javax.inject.Inject
import javax.inject.Singleton

/**
 * BITB-119: on-device speech output.
 *
 * Only voices that work offline are ever used (`isNetworkConnectionRequired == false`), so no
 * message text leaves the device. One answer is spoken at a time. Wrapped in an interface so
 * ViewModel/UI tests can use a fake instead of the platform `TextToSpeech`.
 */
interface SpeechEngine {
    /** True once the platform engine has initialised and its voices can be queried. */
    val isReady: StateFlow<Boolean>

    /** Id of the message currently being spoken, or null. */
    val speakingId: StateFlow<String?>

    /** Starts engine initialisation (idempotent). Cheap to call repeatedly. */
    fun warmUp()

    /** True when an installed, offline voice exists for [languageTag]'s language. */
    fun hasLocalVoice(languageTag: String): Boolean

    /**
     * Speaks [chunks] in order, replacing anything already speaking.
     * Returns false (and speaks nothing) when no local voice exists or audio focus is denied.
     */
    fun speak(id: String, chunks: List<String>, languageTag: String): Boolean

    /** Stops speaking immediately and releases audio focus. */
    fun stop()
}

/** Platform [TextToSpeech] implementation; a process-wide singleton (see SpeechModule). */
@Singleton
class AndroidSpeechEngine @Inject constructor(
    @ApplicationContext private val context: Context,
) : SpeechEngine {

    private val _isReady = MutableStateFlow(false)
    override val isReady: StateFlow<Boolean> = _isReady.asStateFlow()

    private val _speakingId = MutableStateFlow<String?>(null)
    override val speakingId: StateFlow<String?> = _speakingId.asStateFlow()

    private var tts: TextToSpeech? = null

    /** Identifies the current speak() call; callbacks from older calls are ignored. */
    @Volatile private var token = 0L
    @Volatile private var lastUtteranceId: String? = null

    private val speechAttributes: AudioAttributes = AudioAttributes.Builder()
        .setUsage(AudioAttributes.USAGE_ASSISTANT)
        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
        .build()

    private val audioManager: AudioManager?
        get() = context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager

    private val focusRequest: AudioFocusRequest =
        AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
            .setAudioAttributes(speechAttributes)
            .setOnAudioFocusChangeListener { change ->
                // A call, alarm or another media app took focus: stop (never talk over it).
                if (change == AudioManager.AUDIOFOCUS_LOSS ||
                    change == AudioManager.AUDIOFOCUS_LOSS_TRANSIENT
                ) {
                    stop()
                }
            }
            .build()

    private val progressListener = object : UtteranceProgressListener() {
        override fun onStart(utteranceId: String?) = Unit

        override fun onDone(utteranceId: String?) {
            if (utteranceId != null && utteranceId == lastUtteranceId) finish()
        }

        @Deprecated("Deprecated in Java")
        override fun onError(utteranceId: String?) {
            if (belongsToCurrentCall(utteranceId)) stop()
        }

        override fun onError(utteranceId: String?, errorCode: Int) {
            if (belongsToCurrentCall(utteranceId)) stop()
        }
    }

    private fun belongsToCurrentCall(utteranceId: String?): Boolean =
        utteranceId != null && utteranceId.startsWith("$token:")

    @Synchronized
    override fun warmUp() {
        if (tts != null) return
        tts = TextToSpeech(context) { status ->
            if (status == TextToSpeech.SUCCESS) {
                tts?.setAudioAttributes(speechAttributes)
                tts?.setOnUtteranceProgressListener(progressListener)
                _isReady.value = true
            } else {
                Timber.w("TextToSpeech init failed (status=%d); Listen stays hidden", status)
                _isReady.value = false
            }
        }
    }

    /** Offline, installed voices for [languageTag]'s language, best candidates first. */
    private fun localVoices(languageTag: String): List<Voice> {
        val engine = tts?.takeIf { _isReady.value } ?: return emptyList()
        val locale = Locale.forLanguageTag(languageTag)
        val installed = runCatching { engine.voices }.getOrNull() ?: return emptyList()
        // `isLanguageAvailable` reports missing language data: hide rather than prompt.
        if (engine.isLanguageAvailable(locale) < TextToSpeech.LANG_AVAILABLE) return emptyList()
        return installed
            .filter { voice ->
                !voice.isNetworkConnectionRequired &&
                    voice.locale.language == locale.language &&
                    !voice.features.contains(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED)
            }
            .sortedWith(
                compareByDescending<Voice> { it.locale.toLanguageTag() == locale.toLanguageTag() }
                    .thenByDescending { it.quality },
            )
    }

    override fun hasLocalVoice(languageTag: String): Boolean = localVoices(languageTag).isNotEmpty()

    override fun speak(id: String, chunks: List<String>, languageTag: String): Boolean {
        if (chunks.isEmpty()) return false
        val engine = tts ?: return false
        val voice = localVoices(languageTag).firstOrNull() ?: return false

        // Replace whatever is speaking, then take (transient, ducking) audio focus.
        stop()
        val granted = audioManager?.requestAudioFocus(focusRequest) ==
            AudioManager.AUDIOFOCUS_REQUEST_GRANTED
        if (!granted) return false

        val myToken = ++token
        engine.voice = voice
        _speakingId.value = id
        chunks.forEachIndexed { index, chunk ->
            val utteranceId = "$myToken:$index"
            if (index == chunks.lastIndex) lastUtteranceId = utteranceId
            engine.speak(
                chunk,
                if (index == 0) TextToSpeech.QUEUE_FLUSH else TextToSpeech.QUEUE_ADD,
                null,
                utteranceId,
            )
        }
        return true
    }

    override fun stop() {
        token++ // invalidate callbacks from the call being stopped
        lastUtteranceId = null
        runCatching { tts?.stop() }
        finish()
    }

    private fun finish() {
        _speakingId.value = null
        audioManager?.abandonAudioFocusRequest(focusRequest)
    }
}
