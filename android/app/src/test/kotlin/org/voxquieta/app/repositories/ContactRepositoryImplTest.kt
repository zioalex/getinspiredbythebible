package org.voxquieta.app.repositories

import org.voxquieta.app.data.remote.api.BibleApiService
import org.voxquieta.app.data.remote.models.ContactRequestDto
import org.voxquieta.app.data.remote.models.ContactResponseDto
import org.voxquieta.app.data.repositories.ContactRepositoryImpl
import org.voxquieta.app.security.TurnstileManager
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import io.mockk.slot
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import java.io.IOException

/**
 * Unit tests for [ContactRepositoryImpl].
 *
 * Verifies that the repository correctly:
 * - Delegates to [BibleApiService.submitContact]
 * - Returns the ID from the response DTO
 * - Sanitises blank email to null before sending
 * - Provides a default userAgent when none is supplied
 * - Propagates exceptions to the caller
 */
@OptIn(ExperimentalCoroutinesApi::class)
class ContactRepositoryImplTest {

    private lateinit var api: BibleApiService
    private lateinit var turnstileManager: TurnstileManager
    private lateinit var repository: ContactRepositoryImpl

    @Before
    fun setUp() {
        api = mockk(relaxed = true)
        turnstileManager = mockk(relaxed = true)
        repository = ContactRepositoryImpl(api, turnstileManager)
    }

    // ── Happy path ────────────────────────────────────────────────────────────

    @Test
    fun `submitContact returns response id on success`() = runTest {
        coEvery { api.submitContact(any()) } returns ContactResponseDto(
            id = 42,
            subject = "bug",
            createdAt = "2026-01-01T00:00:00Z",
        )

        val result = repository.submitContact(
            subject = "bug",
            message = "App crashes on startup",
            email = "user@example.com",
            userAgent = "Android/14",
        )

        assertEquals(42, result)
    }

    @Test
    fun `submitContact returns id 1 when response id is 1`() = runTest {
        coEvery { api.submitContact(any()) } returns ContactResponseDto(
            id = 1,
            subject = "feedback",
            createdAt = "2026-01-02T00:00:00Z",
        )

        val result = repository.submitContact(
            subject = "feedback",
            message = "Great app!",
            email = null,
            userAgent = null,
        )

        assertEquals(1, result)
    }

    @Test
    fun `submitContact calls onTokenConsumed after success`() = runTest {
        coEvery { api.submitContact(any()) } returns ContactResponseDto(
            id = 1,
            subject = "bug",
            createdAt = "2026-03-01T00:00:00Z",
        )

        repository.submitContact(
            subject = "bug",
            message = "Fix this",
            email = null,
            userAgent = null,
        )

        coVerify { turnstileManager.onTokenConsumed() }
    }

    // ── API delegation ────────────────────────────────────────────────────────

    @Test
    fun `submitContact passes subject and message to API`() = runTest {
        val requestSlot = slot<ContactRequestDto>()
        coEvery { api.submitContact(capture(requestSlot)) } returns ContactResponseDto(
            id = 10,
            subject = "feature",
            createdAt = "2026-03-01T00:00:00Z",
        )

        repository.submitContact(
            subject = "feature",
            message = "Please add dark mode.",
            email = null,
            userAgent = "Android/13",
        )

        assertEquals("feature", requestSlot.captured.subject)
        assertEquals("Please add dark mode.", requestSlot.captured.message)
    }

    @Test
    fun `submitContact passes email to API when email is non-blank`() = runTest {
        val requestSlot = slot<ContactRequestDto>()
        coEvery { api.submitContact(capture(requestSlot)) } returns ContactResponseDto(
            id = 7,
            subject = "other",
            createdAt = "2026-03-01T00:00:00Z",
        )

        repository.submitContact(
            subject = "other",
            message = "Hello",
            email = "reply@example.com",
            userAgent = "Android/12",
        )

        assertEquals("reply@example.com", requestSlot.captured.email)
    }

    @Test
    fun `submitContact converts blank email to null before sending to API`() = runTest {
        val requestSlot = slot<ContactRequestDto>()
        coEvery { api.submitContact(capture(requestSlot)) } returns ContactResponseDto(
            id = 5,
            subject = "bug",
            createdAt = "2026-03-01T00:00:00Z",
        )

        repository.submitContact(
            subject = "bug",
            message = "Something is broken.",
            email = "   ", // blank — should become null
            userAgent = "Android/14",
        )

        assertEquals(null, requestSlot.captured.email)
    }

    @Test
    fun `submitContact converts empty-string email to null before sending to API`() = runTest {
        val requestSlot = slot<ContactRequestDto>()
        coEvery { api.submitContact(capture(requestSlot)) } returns ContactResponseDto(
            id = 3,
            subject = "other",
            createdAt = "2026-03-01T00:00:00Z",
        )

        repository.submitContact(
            subject = "other",
            message = "Test",
            email = "",
            userAgent = "Android/13",
        )

        assertEquals(null, requestSlot.captured.email)
    }

    @Test
    fun `submitContact provides default userAgent when userAgent param is null`() = runTest {
        val requestSlot = slot<ContactRequestDto>()
        coEvery { api.submitContact(capture(requestSlot)) } returns ContactResponseDto(
            id = 9,
            subject = "spiritual",
            createdAt = "2026-03-01T00:00:00Z",
        )

        repository.submitContact(
            subject = "spiritual",
            message = "I have a question.",
            email = null,
            userAgent = null, // should fall back to "Android/<version>"
        )

        // The default is "Android/${Build.VERSION.RELEASE}" — we just verify it's non-null
        // and starts with "Android/" since the exact OS version is environment-specific.
        val capturedAgent = requestSlot.captured.userAgent
        assertEquals(true, capturedAgent?.startsWith("Android/"))
    }

    @Test
    fun `submitContact uses supplied userAgent when provided`() = runTest {
        val requestSlot = slot<ContactRequestDto>()
        coEvery { api.submitContact(capture(requestSlot)) } returns ContactResponseDto(
            id = 11,
            subject = "bug",
            createdAt = "2026-03-01T00:00:00Z",
        )

        repository.submitContact(
            subject = "bug",
            message = "Crash report",
            email = null,
            userAgent = "Android/14 (custom)",
        )

        assertEquals("Android/14 (custom)", requestSlot.captured.userAgent)
    }

    @Test
    fun `submitContact calls API exactly once`() = runTest {
        coEvery { api.submitContact(any()) } returns ContactResponseDto(
            id = 1,
            subject = "feedback",
            createdAt = "2026-03-01T00:00:00Z",
        )

        repository.submitContact("feedback", "Good app", null, null)

        coVerify(exactly = 1) { api.submitContact(any()) }
    }

    // ── Error propagation ─────────────────────────────────────────────────────

    @Test(expected = IOException::class)
    fun `submitContact rethrows IOException from API`() = runTest {
        coEvery { api.submitContact(any()) } throws IOException("no network")

        repository.submitContact("bug", "Crash on start", null, null)
    }

    @Test(expected = RuntimeException::class)
    fun `submitContact rethrows RuntimeException from API`() = runTest {
        coEvery { api.submitContact(any()) } throws RuntimeException("server error")

        repository.submitContact("feature", "Add widget", null, null)
    }
}
