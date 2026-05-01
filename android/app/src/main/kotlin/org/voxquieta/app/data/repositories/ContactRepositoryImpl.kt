package org.voxquieta.app.data.repositories

import android.os.Build
import org.voxquieta.app.data.remote.api.BibleApiService
import org.voxquieta.app.data.remote.models.ContactRequestDto
import org.voxquieta.app.domain.repositories.ContactRepository
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
        // Turnstile reset is centralised in TurnstileInterceptor.
        Timber.d("Contact submitted: id=${response.id}, subject=${response.subject}")
        return response.id
    }
}
