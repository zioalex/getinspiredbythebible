package com.bibleinspiration.data.repositories

import android.os.Build
import com.bibleinspiration.data.remote.api.BibleApiService
import com.bibleinspiration.data.remote.models.ContactRequestDto
import com.bibleinspiration.domain.repositories.ContactRepository
import timber.log.Timber
import javax.inject.Inject

class ContactRepositoryImpl @Inject constructor(
    private val api: BibleApiService,
) : ContactRepository {

    override suspend fun submitContact(
        subject: String,
        message: String,
        email: String?,
        userAgent: String?,
    ): Int {
        val response = api.submitContact(
            ContactRequestDto(
                subject = subject,
                message = message,
                email = email?.ifBlank { null },
                userAgent = userAgent ?: "Android/${Build.VERSION.RELEASE}",
            ),
        )
        Timber.d("Contact submitted: id=${response.id}, subject=${response.subject}")
        return response.id
    }
}
