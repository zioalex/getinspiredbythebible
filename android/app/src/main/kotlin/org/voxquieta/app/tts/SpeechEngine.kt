package org.voxquieta.app.tts

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.os.Build
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.speech.tts.Voice
import androidx.annotation.RequiresApi
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

    /**
     * BITB-205: id of the message whose reading is paused (position kept), or null. At most one
     * message is speaking or paused at a time; [speakingId] and [pausedId] are never both set.
     */
    val pausedId: StateFlow<String?>

    /** Starts engine initialisation (idempotent). Cheap to call repeatedly. */
    fun warmUp()

    /** True when an installed, offline voice exists for [languageTag]'s language. */
    fun hasLocalVoice(languageTag: String): Boolean

    /**
     * Speaks [chunks] in order, replacing anything already speaking.
     * Returns false (and speaks nothing) when no local voice exists or audio focus is denied.
     */
    fun speak(id: String, chunks: List<String>, languageTag: String): Boolean

    /**
     * BITB-205: pauses the current reading and releases audio focus, keeping the position.
     * The platform engine has no pause, so [resume] restarts the chunk that was playing.
     * No-op when nothing is speaking.
     */
    fun pause()

    /**
     * BITB-205: continues a paused reading from the start of the chunk that was playing.
     * Returns false (and stays paused) when nothing is paused or audio focus is denied.
     */
    fun resume(): Boolean

    /** Stops speaking immediately, releases audio focus and discards any paused position. */
    fun stop()
}

/**
 * Installed, offline voices only: drops voices that need the network (their text would leave
 * the device) and voices whose language data is not installed.
 */
internal fun filterLocalVoices(voices: Collection<Voice>?): List<Voice> =
    voices.orEmpty().filter { voice ->
        !voice.isNetworkConnectionRequired &&
            !voice.features.contains(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED)
    }

/** Regional default per UI language; mirrors REGION_DEFAULTS in frontend/src/lib/speech.ts. */
private val REGION_DEFAULTS = mapOf(
    "en" to "en-US",
    "es" to "es-ES",
    "pt" to "pt-BR",
    "fr" to "fr-FR",
    "de" to "de-DE",
    "ar" to "ar-SA",
    "ko" to "ko-KR",
    "hi" to "hi-IN",
    "ru" to "ru-RU",
    "it" to "it-IT",
    "zh" to "zh-CN",
)

/**
 * Orders offline [voices] of [languageTag]'s language, best first. Same preference as the web
 * `findLocalVoice`: exact tag, then the language's regional default (e.g. zh-CN), then any
 * other voice of the language; engine-reported quality breaks ties within a tier.
 */
internal fun rankLocalVoices(voices: Collection<Voice>, languageTag: String): List<Voice> {
    val locale = Locale.forLanguageTag(languageTag)
    val wantedTag = locale.toLanguageTag()
    val regionDefault = REGION_DEFAULTS[locale.language]
    fun tier(voice: Voice): Int {
        val tag = voice.locale.toLanguageTag()
        return when {
            tag.equals(wantedTag, ignoreCase = true) -> 0
            regionDefault != null && tag.equals(regionDefault, ignoreCase = true) -> 1
            else -> 2
        }
    }
    return voices
        .filter { it.locale.language == locale.language }
        .sortedWith(compareBy<Voice> { tier(it) }.thenByDescending { it.quality })
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

    private val _pausedId = MutableStateFlow<String?>(null)
    override val pausedId: StateFlow<String?> = _pausedId.asStateFlow()

    private var tts: TextToSpeech? = null

    /** Creates the platform engine; replaceable in tests. */
    internal var ttsFactory: (Context, TextToSpeech.OnInitListener) -> TextToSpeech =
        { ctx, listener -> TextToSpeech(ctx, listener) }

    /**
     * Offline voices, fetched once after init: `TextToSpeech.getVoices()` is a binder call and
     * must not run on every recomposition / telemetry recompute on the main thread.
     * Voices (or language data) installed mid-session are only picked up after a process
     * restart; accepted for v1.
     */
    @Volatile private var cachedLocalVoices: List<Voice> = emptyList()

    /** Per-language availability, cached for the same reason (`isLanguageAvailable` is IPC). */
    private val languageAvailability = java.util.concurrent.ConcurrentHashMap<String, Boolean>()

    /** Identifies the current speak() call; callbacks from older calls are ignored. */
    @Volatile private var token = 0L
    @Volatile private var lastUtteranceId: String? = null

    // BITB-205: the current call, kept so a paused reading can be re-queued from the chunk that
    // was playing. `playingIndex` is set from UtteranceProgressListener.onStart (binder thread).
    @Volatile private var currentId: String? = null
    @Volatile private var currentChunks: List<String> = emptyList()
    @Volatile private var currentLanguageTag: String = ""
    @Volatile private var playingIndex = 0

    private val speechAttributes: AudioAttributes = AudioAttributes.Builder()
        // USAGE_ASSISTANT is API 26; minSdk is 24.
        .setUsage(
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                AudioAttributes.USAGE_ASSISTANT
            } else {
                AudioAttributes.USAGE_MEDIA
            },
        )
        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
        .build()

    private val audioManager: AudioManager?
        get() = context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager

    private val focusChangeListener = AudioManager.OnAudioFocusChangeListener { change ->
        onAudioFocusChange(change)
    }

    // Held untyped and built on first use from an API 26+ path only, so API 24-25 never
    // load [AudioFocusRequest] and lint's NewApi check sees every use behind @RequiresApi.
    private var focusRequestHolder: Any? = null

    @RequiresApi(Build.VERSION_CODES.O)
    private fun focusRequest(): AudioFocusRequest =
        focusRequestHolder as? AudioFocusRequest
            ?: AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
                .setAudioAttributes(speechAttributes)
                .setOnAudioFocusChangeListener(focusChangeListener)
                .build()
                .also { focusRequestHolder = it }

    private fun requestFocus(): Boolean {
        val am = audioManager ?: return false
        val result = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            am.requestAudioFocus(focusRequest())
        } else {
            @Suppress("DEPRECATION")
            am.requestAudioFocus(
                focusChangeListener,
                AudioManager.STREAM_MUSIC,
                AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK,
            )
        }
        return result == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
    }

    private fun abandonFocus() {
        val am = audioManager ?: return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            am.abandonAudioFocusRequest(focusRequest())
        } else {
            @Suppress("DEPRECATION")
            am.abandonAudioFocus(focusChangeListener)
        }
    }

    /** A call, alarm or another media app took focus: pause (never talk over it; BITB-205). */
    internal fun onAudioFocusChange(change: Int) {
        if (change == AudioManager.AUDIOFOCUS_LOSS ||
            change == AudioManager.AUDIOFOCUS_LOSS_TRANSIENT
        ) {
            pause()
        }
    }

    private val progressListener = object : UtteranceProgressListener() {
        override fun onStart(utteranceId: String?) {
            // Ids are "$token:$index"; remember which chunk is audible for resume().
            if (!belongsToCurrentCall(utteranceId)) return
            utteranceId?.substringAfter(':')?.toIntOrNull()?.let { playingIndex = it }
        }

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
        // (Re-)initialising invalidates anything cached from a previous engine.
        cachedLocalVoices = emptyList()
        languageAvailability.clear()
        tts = ttsFactory(context) { status ->
            if (status == TextToSpeech.SUCCESS) {
                tts?.setAudioAttributes(speechAttributes)
                tts?.setOnUtteranceProgressListener(progressListener)
                cachedLocalVoices = filterLocalVoices(runCatching { tts?.voices }.getOrNull())
                _isReady.value = true
            } else {
                Timber.w("TextToSpeech init failed (status=%d); Listen stays hidden", status)
                cachedLocalVoices = emptyList()
                _isReady.value = false
            }
        }
    }

    /** Offline, installed voices for [languageTag]'s language, best candidates first. */
    private fun localVoices(languageTag: String): List<Voice> {
        val engine = tts?.takeIf { _isReady.value } ?: return emptyList()
        val locale = Locale.forLanguageTag(languageTag)
        // `isLanguageAvailable` reports missing language data: hide rather than prompt.
        val available = languageAvailability.getOrPut(locale.toLanguageTag()) {
            engine.isLanguageAvailable(locale) >= TextToSpeech.LANG_AVAILABLE
        }
        if (!available) return emptyList()
        return rankLocalVoices(cachedLocalVoices, languageTag)
    }

    override fun hasLocalVoice(languageTag: String): Boolean = localVoices(languageTag).isNotEmpty()

    override fun speak(id: String, chunks: List<String>, languageTag: String): Boolean {
        if (chunks.isEmpty()) return false
        // Any new speak() discards a paused position (one position at a time; BITB-205).
        _pausedId.value = null
        return startSpeaking(id, chunks, languageTag, fromIndex = 0)
    }

    /** Shared by [speak] and [resume]: queues `chunks.drop(fromIndex)` under [id]. */
    private fun startSpeaking(id: String, chunks: List<String>, languageTag: String, fromIndex: Int): Boolean {
        val engine = tts ?: return false
        val voice = localVoices(languageTag).firstOrNull() ?: return false

        // Replace whatever is speaking without releasing focus first (a release/re-request
        // would briefly un-duck other apps), then take (transient, ducking) audio focus.
        token++
        lastUtteranceId = null
        runCatching { tts?.stop() }
        if (!requestFocus()) {
            finish()
            return false
        }

        val myToken = ++token
        currentId = id
        currentChunks = chunks
        currentLanguageTag = languageTag
        playingIndex = fromIndex
        engine.voice = voice
        _speakingId.value = id
        chunks.forEachIndexed { index, chunk ->
            if (index < fromIndex) return@forEachIndexed
            val utteranceId = "$myToken:$index"
            if (index == chunks.lastIndex) lastUtteranceId = utteranceId
            engine.speak(
                chunk,
                if (index == fromIndex) TextToSpeech.QUEUE_FLUSH else TextToSpeech.QUEUE_ADD,
                null,
                utteranceId,
            )
        }
        return true
    }

    override fun pause() {
        val id = _speakingId.value ?: return
        token++ // invalidate callbacks from the interrupted queue
        lastUtteranceId = null
        runCatching { tts?.stop() }
        _speakingId.value = null
        _pausedId.value = id
        abandonFocus()
    }

    override fun resume(): Boolean {
        val id = _pausedId.value ?: return false
        val chunks = currentChunks
        val index = playingIndex.coerceIn(0, (chunks.size - 1).coerceAtLeast(0))
        if (currentId != id || chunks.isEmpty()) {
            clearPosition()
            return false
        }
        val language = currentLanguageTag
        // Never both speaking and paused: clear paused first, restore it on failure.
        _pausedId.value = null
        if (!startSpeaking(id, chunks, language, index)) {
            // Focus denied / voice gone: startSpeaking cleared the position; keep it paused.
            currentId = id
            currentChunks = chunks
            currentLanguageTag = language
            playingIndex = index
            _pausedId.value = id
            return false
        }
        return true
    }

    override fun stop() {
        token++ // invalidate callbacks from the call being stopped
        lastUtteranceId = null
        runCatching { tts?.stop() }
        finish()
    }

    private fun clearPosition() {
        currentId = null
        currentChunks = emptyList()
        playingIndex = 0
        _pausedId.value = null
    }

    private fun finish() {
        _speakingId.value = null
        clearPosition()
        abandonFocus()
    }
}
