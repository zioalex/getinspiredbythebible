package org.voxquieta.app.i18n

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * BITB-334: regression tests for welcome-screen translations, read straight from the
 * resource XML (JVM unit tests have no Android resources).
 */
class WelcomeTranslationsTest {

    private fun stringsFile(dir: String): File {
        // Gradle runs unit tests with the module dir (android/app) as the working dir;
        // fall back to the repo root / android dir for IDE runs.
        val rel = "src/main/res/$dir/strings.xml"
        return listOf(File(rel), File("app/$rel"), File("android/app/$rel"))
            .firstOrNull { it.exists() }
            ?: error("Cannot locate $rel from ${File(".").absolutePath}")
    }

    private fun stringValue(dir: String, name: String): String {
        val xml = stringsFile(dir).readText()
        val match = Regex("""<string name="$name"[^>]*>(.*?)</string>""", RegexOption.DOT_MATCHES_ALL)
            .find(xml)
        return requireNotNull(match) { "$name missing from $dir" }.groupValues[1]
    }

    @Test
    fun `italian welcome_subtitle says portano conforto not parlano conforto`() {
        val subtitle = stringValue("values-it", "welcome_subtitle")
        assertTrue(subtitle, subtitle.contains("portano conforto"))
        assertFalse(subtitle, subtitle.contains("parlano conforto"))
    }

    @Test
    fun `romance welcome_subtitles do not use the speaks-comfort calque`() {
        val banned = mapOf(
            "values-es" to "hablan consuelo",
            "values-pt" to "fala conforto",
            "values-de" to "spricht Trost",
        )
        for ((dir, phrase) in banned) {
            val subtitle = stringValue(dir, "welcome_subtitle")
            assertFalse("$dir: $subtitle", subtitle.contains(phrase))
        }
    }
}
