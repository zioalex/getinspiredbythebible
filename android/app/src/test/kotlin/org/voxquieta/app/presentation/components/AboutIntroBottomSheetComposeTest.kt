package org.voxquieta.app.presentation.components

import android.content.Context
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertTrue
import org.junit.Test
import org.voxquieta.app.R
import org.voxquieta.app.testing.ComposeTestHarness

/**
 * Robolectric-backed Compose UI tests for [AboutIntroContent] (BITB-082).
 *
 * Mounts [AboutIntroContent] instead of [AboutIntroBottomSheet] to avoid [ModalBottomSheet]
 * rendering caveats under Robolectric — same pattern as [VerseDetailBottomSheetComposeTest].
 */
class AboutIntroBottomSheetComposeTest : ComposeTestHarness() {

    private val context: Context = ApplicationProvider.getApplicationContext()

    @Test
    fun `renders the intro title and body`() {
        setContentThemed {
            AboutIntroContent(onDismiss = {}, onLearnMore = {})
        }

        composeRule.onNodeWithText(context.getString(R.string.about_intro_title))
            .assertIsDisplayed()
        composeRule.onNodeWithText(context.getString(R.string.about_intro_body))
            .assertIsDisplayed()
    }

    @Test
    fun `secondary action invokes onDismiss`() {
        var dismissed = false
        setContentThemed {
            AboutIntroContent(onDismiss = { dismissed = true }, onLearnMore = {})
        }

        composeRule.onNodeWithText(context.getString(R.string.about_intro_secondary_cta))
            .performClick()

        assertTrue("expected onDismiss to be invoked", dismissed)
    }

    @Test
    fun `primary action invokes onLearnMore`() {
        var learnMoreClicked = false
        setContentThemed {
            AboutIntroContent(onDismiss = {}, onLearnMore = { learnMoreClicked = true })
        }

        composeRule.onNodeWithText(context.getString(R.string.about_intro_primary_cta))
            .performClick()

        assertTrue("expected onLearnMore to be invoked", learnMoreClicked)
    }
}
