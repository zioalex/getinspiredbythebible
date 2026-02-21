package com.getinspiredbythebible.data.model

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

/**
 * Response body from GET /api/v1/scripture/search?q=...
 */
@JsonClass(generateAdapter = true)
data class ScriptureSearchResponse(
    @Json(name = "results") val results: List<VerseResult>,
)
