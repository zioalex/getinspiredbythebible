package org.voxquieta.app.presentation.screens

import kotlinx.serialization.Serializable

@Serializable
data class ChangelogEntry(
    val version: String,
    val date: String,
    val body: String,
)
