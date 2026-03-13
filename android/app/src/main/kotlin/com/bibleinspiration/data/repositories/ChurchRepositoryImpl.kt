package com.bibleinspiration.data.repositories

import com.bibleinspiration.data.remote.api.BibleApiService
import com.bibleinspiration.data.remote.models.ChurchSearchRequestDto
import com.bibleinspiration.domain.models.Church
import com.bibleinspiration.domain.repositories.ChurchRepository
import timber.log.Timber
import javax.inject.Inject

class ChurchRepositoryImpl @Inject constructor(
    private val api: BibleApiService,
) : ChurchRepository {

    override suspend fun searchChurches(location: String): List<Church> {
        val response = api.searchChurches(ChurchSearchRequestDto(location = location))
        return response.churches.map { dto ->
            Church(
                name = dto.name,
                address = dto.address,
                city = dto.city,
                state = dto.state,
                country = dto.country,
                website = dto.website,
                phone = dto.phone,
                email = dto.email,
            )
        }
    }
}
