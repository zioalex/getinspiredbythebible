package org.voxquieta.app.tts

import android.content.Context
import android.media.AudioManager
import android.os.Build
import android.speech.tts.TextToSpeech
import android.speech.tts.Voice
import io.mockk.every
import io.mockk.mockk
import io.mockk.slot
import io.mockk.verify
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.util.Locale

/**
 * BITB-119: [AndroidSpeechEngine] behaviour that must hold on a real device — audio-focus loss
 * stops speech, network voices are never used, stop() releases focus, voices are queried once.
 * Uses a mocked platform [TextToSpeech] / [AudioManager]; Robolectric supplies the android classes.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], application = android.app.Application::class)
class AndroidSpeechEngineTest {

    private fun voice(
        tag: String,
        network: Boolean = false,
        features: Set<String> = emptySet(),
        quality: Int = Voice.QUALITY_NORMAL,
    ) = Voice("v-$tag-$network", Locale.forLanguageTag(tag), quality, Voice.LATENCY_NORMAL, network, features)

    private class Harness(val tts: TextToSpeech, val audio: AudioManager) {
        lateinit var engine: AndroidSpeechEngine
    }

    private fun harness(voices: List<Voice>, focusResult: Int = AudioManager.AUDIOFOCUS_REQUEST_GRANTED): Harness {
        val tts = mockk<TextToSpeech>(relaxed = true)
        every { tts.voices } returns voices.toSet()
        every { tts.isLanguageAvailable(any()) } returns TextToSpeech.LANG_AVAILABLE
        val audio = mockk<AudioManager>(relaxed = true)
        // The AudioFocusRequest overload only exists on API 26+; stubbing it under an API 25
        // Robolectric SDK throws NoSuchMethodError before the engine runs.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            every { audio.requestAudioFocus(any<android.media.AudioFocusRequest>()) } returns focusResult
        }
        @Suppress("DEPRECATION")
        every { audio.requestAudioFocus(any(), any(), any()) } returns focusResult
        val context = mockk<Context>(relaxed = true)
        every { context.getSystemService(Context.AUDIO_SERVICE) } returns audio

        val h = Harness(tts, audio)
        val engine = AndroidSpeechEngine(context)
        val listener = slot<TextToSpeech.OnInitListener>()
        engine.ttsFactory = { _, l ->
            listener.captured = l
            tts
        }
        engine.warmUp()
        listener.captured.onInit(TextToSpeech.SUCCESS)
        h.engine = engine
        return h
    }

    @Test
    fun `filterLocalVoices drops network and not-installed voices`() {
        val local = voice("en-US")
        val network = voice("en-GB", network = true)
        val missing = voice("en-AU", features = setOf(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED))
        assertEquals(listOf(local), filterLocalVoices(listOf(network, local, missing)))
        assertEquals(emptyList<Voice>(), filterLocalVoices(null))
    }

    @Test
    fun `network-only voices are ignored by hasLocalVoice`() {
        val h = harness(listOf(voice("en-US", network = true)))
        assertFalse(h.engine.hasLocalVoice("en"))
        assertFalse(h.engine.speak("m1", listOf("Hello."), "en"))
        assertNull(h.engine.speakingId.value)
    }

    @Test
    fun `local voice is found and speak starts`() {
        val h = harness(listOf(voice("en-US", network = true), voice("en-GB")))
        assertTrue(h.engine.hasLocalVoice("en-US"))
        assertTrue(h.engine.speak("m1", listOf("Hello."), "en"))
        assertEquals("m1", h.engine.speakingId.value)
    }

    @Test
    fun `audio focus loss stops speaking`() {
        for (loss in listOf(AudioManager.AUDIOFOCUS_LOSS, AudioManager.AUDIOFOCUS_LOSS_TRANSIENT)) {
            val h = harness(listOf(voice("en-US")))
            assertTrue(h.engine.speak("m1", listOf("Hello."), "en"))
            assertEquals("m1", h.engine.speakingId.value)
            h.engine.onAudioFocusChange(loss)
            assertNull("focus change $loss must stop", h.engine.speakingId.value)
        }
    }

    @Test
    fun `ducking and gain focus changes do not stop speaking`() {
        val h = harness(listOf(voice("en-US")))
        assertTrue(h.engine.speak("m1", listOf("Hello."), "en"))
        h.engine.onAudioFocusChange(AudioManager.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK)
        h.engine.onAudioFocusChange(AudioManager.AUDIOFOCUS_GAIN)
        assertEquals("m1", h.engine.speakingId.value)
    }

    @Test
    fun `stop abandons audio focus and clears speakingId`() {
        val h = harness(listOf(voice("en-US")))
        assertTrue(h.engine.speak("m1", listOf("Hello."), "en"))
        h.engine.stop()
        assertNull(h.engine.speakingId.value)
        verify { h.audio.abandonAudioFocusRequest(any()) }
    }

    @Test
    fun `denied audio focus speaks nothing`() {
        val h = harness(listOf(voice("en-US")), focusResult = AudioManager.AUDIOFOCUS_REQUEST_FAILED)
        assertFalse(h.engine.speak("m1", listOf("Hello."), "en"))
        assertNull(h.engine.speakingId.value)
    }

    @Test
    fun `voices are queried once not on every availability check`() {
        val h = harness(listOf(voice("en-US")))
        repeat(5) { h.engine.hasLocalVoice("en") }
        verify(exactly = 1) { h.tts.voices }
        verify(exactly = 1) { h.tts.isLanguageAvailable(any()) }
    }

    @Test
    @Config(sdk = [25])
    fun `api 25 engine constructs and uses the legacy audio focus calls`() {
        val h = harness(listOf(voice("en-US")))
        assertTrue(h.engine.speak("m1", listOf("Hello."), "en"))
        assertEquals("m1", h.engine.speakingId.value)
        @Suppress("DEPRECATION")
        verify(exactly = 1) {
            h.audio.requestAudioFocus(
                any(),
                AudioManager.STREAM_MUSIC,
                AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK,
            )
        }
        // No verify on the AudioFocusRequest overloads here: they don't exist on API 25, so any
        // call from the engine would already have failed this test with NoSuchMethodError.
        h.engine.stop()
        assertNull(h.engine.speakingId.value)
        @Suppress("DEPRECATION")
        verify(exactly = 1) { h.audio.abandonAudioFocus(any()) }
    }

    @Test
    @Config(sdk = [25])
    fun `api 25 denied legacy focus speaks nothing`() {
        val h = harness(listOf(voice("en-US")), focusResult = AudioManager.AUDIOFOCUS_REQUEST_FAILED)
        assertFalse(h.engine.speak("m1", listOf("Hello."), "en"))
        assertNull(h.engine.speakingId.value)
    }

    @Test
    fun `api 34 uses the AudioFocusRequest path`() {
        val h = harness(listOf(voice("en-US")))
        assertTrue(h.engine.speak("m1", listOf("Hello."), "en"))
        verify(exactly = 1) { h.audio.requestAudioFocus(any<android.media.AudioFocusRequest>()) }
        @Suppress("DEPRECATION")
        verify(exactly = 0) { h.audio.requestAudioFocus(any(), any(), any()) }
    }

    @Test
    fun `rankLocalVoices prefers exact tag then regional default then quality`() {
        val enGbHigh = voice("en-GB", quality = Voice.QUALITY_VERY_HIGH)
        val enUs = voice("en-US")
        val enAu = voice("en-AU", quality = Voice.QUALITY_HIGH)
        val fr = voice("fr-FR")
        // Region default en-US beats higher-quality en-GB/en-AU; other languages dropped.
        assertEquals(listOf(enUs, enGbHigh, enAu), rankLocalVoices(listOf(enGbHigh, enAu, fr, enUs), "en"))
        // Exact tag beats the regional default.
        assertEquals(enGbHigh, rankLocalVoices(listOf(enUs, enGbHigh), "en-GB").first())
        // zh falls back to zh-CN over zh-TW / zh-HK regardless of quality.
        val zhTw = voice("zh-TW", quality = Voice.QUALITY_VERY_HIGH)
        val zhCn = voice("zh-CN")
        assertEquals(zhCn, rankLocalVoices(listOf(zhTw, zhCn), "zh").first())
        // Without a regional default, quality decides.
        val ptPt = voice("pt-PT", quality = Voice.QUALITY_HIGH)
        val ptAo = voice("pt-AO")
        assertEquals(ptPt, rankLocalVoices(listOf(ptAo, ptPt), "pt").first())
        assertEquals(emptyList<Voice>(), rankLocalVoices(listOf(fr), "de"))
    }
}
