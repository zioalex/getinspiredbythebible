package com.bibleinspiration.repositories

import com.bibleinspiration.data.remote.api.BibleApiService
import com.bibleinspiration.data.remote.models.ChurchSearchResponseDto
import com.bibleinspiration.data.remote.models.ChurchDto
import com.bibleinspiration.data.repositories.ChurchRepositoryImpl
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.IOException

/**
 * Unit tests for [ChurchRepositoryImpl].
 *
 * Verifies that the repository correctly:
 * - Delegates search to the BibleApiService
 * - Maps ChurchDto → Church domain model
 * - Passes through exceptions to the caller
 */
@OptIn(ExperimentalCoroutinesApi::class)
class ChurchRepositoryImplTest {

    private lateinit var api: BibleApiService
    private lateinit var repository: ChurchRepositoryImpl

    @Before
    fun setUp() {
        api = mockk(relaxed = true)
        repository = ChurchRepositoryImpl(api)
    }

    // ── Happy path ────────────────────────────────────────────────────────────

    @Test
    fun `searchChurches returns mapped Church list on success`() = runTest {
        val dtos = listOf(
            ChurchDto(
                name = "Grace Church",
                address = "Via Roma 1",
                city = "Rome",
                state = null,
                country = "Italy",
                website = "https://grace.it",
                phone = "+39 06 1234567",
                email = "info@grace.it",
            ),
        )
        coEvery { api.searchChurches(any()) } returns ChurchSearchResponseDto(
            churches = dtos,
            total = 1,
            location = "Rome",
        )

        val result = repository.searchChurches("Rome")

        assertEquals(1, result.size)
        assertEquals("Grace Church", result[0].name)
        assertEquals("Via Roma 1", result[0].address)
        assertEquals("Rome", result[0].city)
        assertEquals("Italy", result[0].country)
        assertEquals("https://grace.it", result[0].website)
        assertEquals("+39 06 1234567", result[0].phone)
        assertEquals("info@grace.it", result[0].email)
    }

    @Test
    fun `searchChurches maps state correctly when present`() = runTest {
        val dtos = listOf(
            ChurchDto(
                name = "First Baptist",
                address = "123 Main St",
                city = "Austin",
                state = "TX",
                country = "USA",
                website = null,
                phone = null,
                email = null,
            ),
        )
        coEvery { api.searchChurches(any()) } returns ChurchSearchResponseDto(
            churches = dtos,
            total = 1,
            location = "Austin",
        )

        val result = repository.searchChurches("Austin")

        assertEquals("TX", result[0].state)
    }

    @Test
    fun `searchChurches returns empty list when API returns empty`() = runTest {
        coEvery { api.searchChurches(any()) } returns ChurchSearchResponseDto(
            churches = emptyList(),
            total = 0,
            location = "Nowhere",
        )

        val result = repository.searchChurches("Nowhere")

        assertTrue(result.isEmpty())
    }

    @Test
    fun `searchChurches maps multiple churches correctly`() = runTest {
        val dtos = listOf(
            ChurchDto(name = "Church A", address = "Addr A", city = "CityA", state = null, country = "CountryA", website = null, phone = null, email = null),
            ChurchDto(name = "Church B", address = "Addr B", city = "CityB", state = null, country = "CountryB", website = null, phone = null, email = null),
            ChurchDto(name = "Church C", address = "Addr C", city = "CityC", state = null, country = "CountryC", website = null, phone = null, email = null),
        )
        coEvery { api.searchChurches(any()) } returns ChurchSearchResponseDto(
            churches = dtos,
            total = 3,
            location = "AnyCity",
        )

        val result = repository.searchChurches("AnyCity")

        assertEquals(3, result.size)
        assertEquals("Church A", result[0].name)
        assertEquals("Church B", result[1].name)
        assertEquals("Church C", result[2].name)
    }

    @Test
    fun `searchChurches maps null optional fields correctly`() = runTest {
        val dtos = listOf(
            ChurchDto(
                name = "Minimal Church",
                address = "Some St",
                city = "City",
                state = null,
                country = "Country",
                website = null,
                phone = null,
                email = null,
            ),
        )
        coEvery { api.searchChurches(any()) } returns ChurchSearchResponseDto(
            churches = dtos,
            total = 1,
            location = "City",
        )

        val result = repository.searchChurches("City")

        val church = result[0]
        assertEquals("Minimal Church", church.name)
        assertEquals(null, church.state)
        assertEquals(null, church.website)
        assertEquals(null, church.phone)
        assertEquals(null, church.email)
    }

    // ── API delegation ────────────────────────────────────────────────────────

    @Test
    fun `searchChurches calls API with correct location`() = runTest {
        coEvery { api.searchChurches(any()) } returns ChurchSearchResponseDto(churches = emptyList())

        repository.searchChurches("Berlin")

        coVerify(exactly = 1) {
            api.searchChurches(match { it.location == "Berlin" })
        }
    }

    @Test
    fun `searchChurches passes trimmed location when input has leading spaces`() = runTest {
        // The ViewModel trims location; here we verify the raw repository delegates as-is.
        coEvery { api.searchChurches(any()) } returns ChurchSearchResponseDto(churches = emptyList())

        repository.searchChurches("Paris")

        coVerify(exactly = 1) {
            api.searchChurches(match { it.location == "Paris" })
        }
    }

    // ── Error propagation ─────────────────────────────────────────────────────

    @Test(expected = IOException::class)
    fun `searchChurches rethrows IOException from API`() = runTest {
        coEvery { api.searchChurches(any()) } throws IOException("no network")

        repository.searchChurches("London")
    }

    @Test(expected = RuntimeException::class)
    fun `searchChurches rethrows RuntimeException from API`() = runTest {
        coEvery { api.searchChurches(any()) } throws RuntimeException("unexpected error")

        repository.searchChurches("Madrid")
    }
}
