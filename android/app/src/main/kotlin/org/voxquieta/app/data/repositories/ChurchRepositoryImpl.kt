package org.voxquieta.app.data.repositories

import org.voxquieta.app.data.remote.api.BibleApiService
import org.voxquieta.app.data.remote.models.ChurchSearchRequestDto
import org.voxquieta.app.domain.models.Church
import org.voxquieta.app.domain.repositories.ChurchRepository
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
