package org.voxquieta.app.utils

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Parity + behaviour tests for [TRADITIONAL_TO_SIMPLIFIED] / [normalizeTraditionalToSimplified]
 * (BITB-110, the Android fast-follow to BITB-025).
 *
 * The fixture-parity test loads tests/fixtures/t2s_char_map.json — the cross-platform source of
 * truth, also verified against by api/tests/test_chinese_script.py and
 * frontend/src/lib/chineseScript.test.ts — from the test classpath via the
 * sourceSets["test"].resources.srcDir("../../tests/fixtures") entry in build.gradle.kts (already
 * wired for VerseCorpusParityTest / LocalizedBookToEnglishTest).
 *
 * The rest of the cases mirror frontend/src/lib/chineseScript.test.ts's list, adapted to
 * Kotlin/JUnit, so the two platforms' guarantees stay demonstrably identical.
 */
@Serializable
private data class T2sCharMapFixture(
    val description: String,
    val char_map: Map<String, String>,
)

class ChineseScriptTest {

    private fun loadFixture(): Map<String, String> {
        val stream = javaClass.classLoader?.getResourceAsStream("t2s_char_map.json")
            ?: error(
                "t2s_char_map.json not found on the test classpath — check the " +
                    "sourceSets[\"test\"].resources.srcDir(\"../../tests/fixtures\") entry in " +
                    "android/app/build.gradle.kts"
            )
        val raw = stream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        return Json { ignoreUnknownKeys = true }
            .decodeFromString<T2sCharMapFixture>(raw)
            .char_map
    }

    // ── Fixture parity ──────────────────────────────────────────────────────────

    @Test
    fun `TRADITIONAL_TO_SIMPLIFIED matches tests:fixtures:t2s_char_map json exactly`() {
        val fixture = loadFixture()
        val actual = TRADITIONAL_TO_SIMPLIFIED.entries.associate { (k, v) -> k.toString() to v.toString() }

        val missing = fixture.keys - actual.keys
        val extra = actual.keys - fixture.keys
        val mismatched = (fixture.keys intersect actual.keys).filter { fixture[it] != actual[it] }

        val failures = mutableListOf<String>()
        if (missing.isNotEmpty()) failures += "missing keys (in fixture, not in Kotlin): $missing"
        if (extra.isNotEmpty()) failures += "extra keys (in Kotlin, not in fixture): $extra"
        for (key in mismatched) {
            failures += "value mismatch for '$key': fixture='${fixture[key]}' kotlin='${actual[key]}'"
        }

        assertTrue(
            "ChineseScript.kt's TRADITIONAL_TO_SIMPLIFIED is out of sync with " +
                "tests/fixtures/t2s_char_map.json.\n" + failures.joinToString("\n"),
            failures.isEmpty(),
        )
    }

    @Test
    fun `fixture has 29 entries`() {
        assertEquals(29, loadFixture().size)
        assertEquals(29, TRADITIONAL_TO_SIMPLIFIED.size)
    }

    // ── normalizeTraditionalToSimplified behaviour ──────────────────────────────

    @Test
    fun `converts every table entry`() {
        for ((traditional, simplified) in TRADITIONAL_TO_SIMPLIFIED) {
            assertEquals(simplified.toString(), normalizeTraditionalToSimplified(traditional.toString()))
        }
    }

    @Test
    fun `is a no-op on English text`() {
        val text = "John 3:16, for God so loved the world"
        assertEquals(text, normalizeTraditionalToSimplified(text))
    }

    @Test
    fun `is a no-op on Cyrillic text`() {
        val text = "Иоанна 3:16"
        assertEquals(text, normalizeTraditionalToSimplified(text))
    }

    @Test
    fun `is a no-op on Korean text`() {
        val text = "요한복음 3:16"
        assertEquals(text, normalizeTraditionalToSimplified(text))
    }

    @Test
    fun `is a no-op on Arabic text`() {
        val text = "يوحنا 3:16"
        assertEquals(text, normalizeTraditionalToSimplified(text))
    }

    @Test
    fun `is a no-op on already-Simplified text`() {
        val text = "约翰福音 3:16"
        assertEquals(text, normalizeTraditionalToSimplified(text))
    }

    @Test
    fun `is a no-op on an empty string`() {
        assertEquals("", normalizeTraditionalToSimplified(""))
    }

    @Test
    fun `is length-preserving over every table entry`() {
        for (traditional in TRADITIONAL_TO_SIMPLIFIED.keys) {
            val s = traditional.toString()
            assertEquals(s.length, normalizeTraditionalToSimplified(s).length)
        }
    }

    @Test
    fun `is length-preserving over mixed text`() {
        val text = "請閱讀約翰福音 3:16, danke, 谢谢, 감사합니다"
        assertEquals(text.length, normalizeTraditionalToSimplified(text).length)
    }

    @Test
    fun `is length-preserving over arbitrary strings`() {
        // Property check: length-preservation must hold regardless of script mix or repetition,
        // not just for the specific fixtures above.
        val samples = listOf(
            "",
            "a",
            "約翰福音約翰福音約翰福音",
            "創世记 1:1 傳道书 3:1 羅馬書 8:28",
            "mixed 約 english 记 text 123",
        )
        for (s in samples) {
            assertEquals(s.length, normalizeTraditionalToSimplified(s).length)
        }
    }

    @Test
    fun `is idempotent`() {
        val text = "約翰福音 3:16"
        val once = normalizeTraditionalToSimplified(text)
        val twice = normalizeTraditionalToSimplified(once)
        assertEquals(once, twice)
    }

    @Test
    fun `converts Johns book name`() {
        assertEquals("约翰福音", normalizeTraditionalToSimplified("約翰福音"))
    }

    @Test
    fun `converts Matthews book name`() {
        assertEquals("马太福音", normalizeTraditionalToSimplified("馬太福音"))
    }

    @Test
    fun `handles mixed-script text (single Traditional character)`() {
        assertEquals("创世记", normalizeTraditionalToSimplified("創世记"))
    }

    @Test
    fun `maps both Traditional variants of qi to the same Simplified target`() {
        assertEquals("启", normalizeTraditionalToSimplified("啟"))
        assertEquals("启", normalizeTraditionalToSimplified("啓"))
    }
}
