package com.getinspiredbythebible.data.repository

import com.getinspiredbythebible.data.model.ChatRequest
import com.getinspiredbythebible.data.model.ChatResponse
import com.getinspiredbythebible.data.model.ScriptureSearchResponse
import com.getinspiredbythebible.data.model.VerseResult
import com.getinspiredbythebible.data.remote.BibleApiService
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class ChatRepositoryTest {

    private lateinit var apiService: BibleApiService
    private lateinit var repository: ChatRepositoryImpl

    // ── Fixtures ──────────────────────────────────────────────────────────────

    private val sampleVerse = VerseResult(
        book = "John",
        chapter = 3,
        verse = 16,
        text = "For God so loved the world that he gave his one and only Son...",
        similarity = 0.92,
    )

    private val sampleChatResponse = ChatResponse(
        response = "Here is some encouragement.",
        verses = listOf(sampleVerse),
        sessionId = "session-abc-123",
    )

    @Before
    fun setUp() {
        apiService = mockk()
        repository = ChatRepositoryImpl(apiService)
    }

    // ── sendMessage tests ─────────────────────────────────────────────────────

    @Test
    fun `sendMessage returns success when API call succeeds`() = runTest {
        // Arrange
        coEvery { apiService.sendMessage(any()) } returns sampleChatResponse

        // Act
        val result = repository.sendMessage("I need encouragement")

        // Assert
        assertTrue(result.isSuccess)
        assertEquals(sampleChatResponse, result.getOrNull())
    }

    @Test
    fun `sendMessage passes correct request body to API`() = runTest {
        // Arrange
        val message = "I'm worried about tomorrow"
        val sessionId = "my-session-id"
        coEvery { apiService.sendMessage(any()) } returns sampleChatResponse

        // Act
        repository.sendMessage(message, sessionId)

        // Assert
        coVerify {
            apiService.sendMessage(
                ChatRequest(message = message, sessionId = sessionId),
            )
        }
    }

    @Test
    fun `sendMessage passes null sessionId when not provided`() = runTest {
        // Arrange
        coEvery { apiService.sendMessage(any()) } returns sampleChatResponse

        // Act
        repository.sendMessage("Hello")

        // Assert
        coVerify {
            apiService.sendMessage(ChatRequest(message = "Hello", sessionId = null))
        }
    }

    @Test
    fun `sendMessage returns failure when API throws exception`() = runTest {
        // Arrange
        val exception = RuntimeException("Connection refused")
        coEvery { apiService.sendMessage(any()) } throws exception

        // Act
        val result = repository.sendMessage("Some message")

        // Assert
        assertTrue(result.isFailure)
        assertEquals(exception, result.exceptionOrNull())
    }

    @Test
    fun `sendMessage wraps IOException in Result failure`() = runTest {
        // Arrange
        val ioException = java.io.IOException("No network")
        coEvery { apiService.sendMessage(any()) } throws ioException

        // Act
        val result = repository.sendMessage("Need help")

        // Assert
        assertFalse(result.isSuccess)
        assertTrue(result.exceptionOrNull() is java.io.IOException)
    }

    // ── searchScripture tests ─────────────────────────────────────────────────

    @Test
    fun `searchScripture returns verse list on success`() = runTest {
        // Arrange
        val searchResponse = ScriptureSearchResponse(results = listOf(sampleVerse))
        coEvery { apiService.searchScripture(any()) } returns searchResponse

        // Act
        val result = repository.searchScripture("peace and hope")

        // Assert
        assertTrue(result.isSuccess)
        val verses = result.getOrNull()!!
        assertEquals(1, verses.size)
        assertEquals("John", verses[0].book)
        assertEquals(3, verses[0].chapter)
        assertEquals(16, verses[0].verse)
    }

    @Test
    fun `searchScripture passes query string to API`() = runTest {
        // Arrange
        val query = "forgiveness and grace"
        coEvery { apiService.searchScripture(query) } returns
            ScriptureSearchResponse(results = emptyList())

        // Act
        repository.searchScripture(query)

        // Assert
        coVerify { apiService.searchScripture(query) }
    }

    @Test
    fun `searchScripture returns empty list when API returns no results`() = runTest {
        // Arrange
        coEvery { apiService.searchScripture(any()) } returns
            ScriptureSearchResponse(results = emptyList())

        // Act
        val result = repository.searchScripture("very obscure query xyz")

        // Assert
        assertTrue(result.isSuccess)
        assertTrue(result.getOrNull()!!.isEmpty())
    }

    @Test
    fun `searchScripture returns failure when API throws`() = runTest {
        // Arrange
        coEvery { apiService.searchScripture(any()) } throws Exception("Timeout")

        // Act
        val result = repository.searchScripture("something")

        // Assert
        assertTrue(result.isFailure)
        assertEquals("Timeout", result.exceptionOrNull()?.message)
    }
}
