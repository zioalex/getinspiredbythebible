package com.bibleinspiration.domain.repositories

import com.bibleinspiration.domain.models.Church

interface ChurchRepository {
    /**
     * Searches for churches near the given [location] (free-text city name in English).
     * Returns the list of matching churches, or throws on network/server error.
     */
    suspend fun searchChurches(location: String): List<Church>
}
