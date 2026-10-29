package org.voxquieta.app.presentation.components

import android.content.Intent
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.robolectric.annotation.Config
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import org.voxquieta.app.testing.ComposeTestHarness
import org.voxquieta.app.testing.crisisFixture

/**
 * Robolectric-backed Compose UI tests for [CrisisResourcesCard] (BITB-251).
 *
 * Runs in the English default locale under Robolectric, on a tall phone-sized screen: the
 * card is taller than Robolectric's default 320x470dp viewport, which would leave its lower
 * rows off-screen (not displayed, clicks dropped). In the app it sits in the scrolling chat list.
 */
@Config(qualifiers = "w411dp-h1400dp")
class CrisisResourcesCardComposeTest : ComposeTestHarness() {

    private val launched = mutableListOf<Intent>()
    private val picked = mutableListOf<String>()

    private fun mount(resources: org.voxquieta.app.domain.models.CrisisResources = crisisFixture) =
        setContentThemed {
            CrisisResourcesCard(
                resources = resources,
                onCountrySelected = { picked.add(it) },
                launchIntent = { launched.add(it) },
            )
        }

    @Test
    fun `shows the heading, emergency number and each line`() {
        mount()

        composeRule.onNodeWithText("You don't have to face this alone", substring = true).assertIsDisplayed()
        composeRule.onNodeWithText("Emergency number: 112").assertIsDisplayed()
        composeRule.onNodeWithText("Telefono Amico").assertIsDisplayed()
        composeRule.onNodeWithText("10:00-24:00").assertIsDisplayed()
        composeRule.onNodeWithText("Call +39 02 2327 2327").assertIsDisplayed()
        composeRule.onNodeWithText("Text +39 324 011 7252").assertIsDisplayed()
        composeRule.onNodeWithText("More helplines worldwide").assertIsDisplayed()
    }

    @Test
    fun `tapping the emergency number fires ACTION_DIAL with the tel uri`() {
        mount()

        composeRule.onNodeWithContentDescription("Call emergency number 112").performClick()

        val intent = launched.single()
        assertEquals(Intent.ACTION_DIAL, intent.action)
        assertEquals("tel:112", intent.data.toString())
    }

    @Test
    fun `tapping call on a line dials the number with separators stripped`() {
        mount()

        composeRule.onNodeWithContentDescription("Call Telefono Amico").performClick()

        val intent = launched.single()
        assertEquals(Intent.ACTION_DIAL, intent.action)
        assertEquals("tel:+390223272327", intent.data.toString())
    }

    @Test
    fun `tapping text on a line opens SMS via ACTION_SENDTO`() {
        mount()

        composeRule.onNodeWithContentDescription("Text Telefono Amico").performClick()

        val intent = launched.single()
        assertEquals(Intent.ACTION_SENDTO, intent.action)
        assertEquals("smsto:+393240117252", intent.data.toString())
    }

    @Test
    fun `a line without sms has no text action and parentheses are stripped from tel`() {
        mount()

        composeRule.onNodeWithContentDescription("Text Samaritans").assertDoesNotExist()
        composeRule.onNodeWithContentDescription("Call Samaritans").performClick()

        assertEquals("tel:116123", launched.single().data.toString())
    }

    @Test
    fun `never uses ACTION_CALL so no CALL_PHONE permission is needed`() {
        mount()

        composeRule.onNodeWithContentDescription("Call emergency number 112").performClick()
        composeRule.onNodeWithContentDescription("Call Telefono Amico").performClick()
        composeRule.onNodeWithContentDescription("Text Telefono Amico").performClick()

        assertEquals(3, launched.size)
        assertTrue(launched.none { it.action == Intent.ACTION_CALL })
    }

    @Test
    fun `the international link opens findahelpline`() {
        mount()

        composeRule.onNodeWithText("More helplines worldwide").performClick()

        assertEquals(Intent.ACTION_VIEW, launched.single().action)
        assertEquals("https://findahelpline.com", launched.single().data.toString())
    }

    @Test
    fun `picker reports the chosen country and confirms it`() {
        mount()

        composeRule.onNodeWithText("Not in Italy?").performClick()
        composeRule.onNodeWithText("Austria").performClick()

        assertEquals(listOf("AT"), picked)
        composeRule.onNodeWithText("We'll use Austria numbers from your next message.").assertIsDisplayed()
        assertTrue(launched.isEmpty())
    }

    @Test
    fun `without an emergency number only lines and the international link render`() {
        mount(crisisFixture.copy(emergencyNumber = null, country = null, lines = emptyList()))

        composeRule.onNodeWithContentDescription("Call emergency number 112").assertDoesNotExist()
        composeRule.onNodeWithText("More helplines worldwide").assertIsDisplayed()
        composeRule.onNodeWithText("Choose your country").assertIsDisplayed()
    }

    @Test
    fun `without an emergency number the local-emergency hint is a 112 dial target`() {
        mount(crisisFixture.copy(emergencyNumber = null, country = null, lines = emptyList()))

        val hint = "Call your local emergency number (112 works from most mobile phones)."
        composeRule.onNodeWithText(hint).assertIsDisplayed()
        composeRule.onNodeWithText(hint).performClick()

        val intent = launched.single()
        assertEquals(Intent.ACTION_DIAL, intent.action)
        assertEquals("tel:112", intent.data.toString())
    }

    @Test
    fun `no local-emergency hint when the emergency number is known`() {
        mount()

        composeRule
            .onNodeWithText("Call your local emergency number", substring = true)
            .assertDoesNotExist()
    }

    @Test
    fun `next-message note disappears once the card is re-rendered for the picked country`() {
        var resources by androidx.compose.runtime.mutableStateOf(crisisFixture)
        setContentThemed {
            CrisisResourcesCard(
                resources = resources,
                onCountrySelected = { picked.add(it) },
                launchIntent = { launched.add(it) },
            )
        }

        composeRule.onNodeWithText("Not in Italy?").performClick()
        composeRule.onNodeWithText("Austria").performClick()
        composeRule.onNodeWithText("We'll use Austria numbers from your next message.").assertIsDisplayed()

        // The ViewModel swapped in the Austrian numbers: the card shows them, no stale note.
        resources = crisisFixture.copy(
            country = "AT",
            countrySource = "override",
            emergencyNumber = "144",
        )
        composeRule.waitForIdle()

        composeRule.onNodeWithText("Emergency number: 144").assertIsDisplayed()
        composeRule.onNodeWithText("Emergency number: 112").assertDoesNotExist()
        composeRule
            .onNodeWithText("We'll use Austria numbers from your next message.")
            .assertDoesNotExist()
        composeRule.onNodeWithText("Not in Austria?").assertIsDisplayed()
    }

    @Test
    fun `dialableNumber strips separators but keeps the plus`() {
        assertEquals("+390223272327", dialableNumber("+39 02 2327 2327"))
        assertEquals("116123", dialableNumber("(116) 123"))
        assertEquals("18002738255", dialableNumber("1-800-273-8255"))
        assertFalse(dialableNumber("+1 (800) 273.8255").contains(" "))
        assertNotEquals("", dialableNumber("112"))
    }
}
