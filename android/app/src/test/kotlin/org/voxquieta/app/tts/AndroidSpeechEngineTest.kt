package org.voxquieta.app.tts

import android.content.Context
import android.media.AudioManager
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
        every { audio.requestAudioFocus(any<android.media.AudioFocusRequest>()) } returns focusResult
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
}
