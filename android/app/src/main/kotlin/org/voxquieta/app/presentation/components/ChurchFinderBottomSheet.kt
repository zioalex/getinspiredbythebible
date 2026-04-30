package org.voxquieta.app.presentation.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SheetState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import org.voxquieta.app.R
import org.voxquieta.app.domain.models.Church
import org.voxquieta.app.presentation.viewmodels.ChurchFinderSheetState

/**
 * Full-screen bottom sheet for searching churches by location.
 *
 * The sheet has three sections:
 *  1. Header + location text field
 *  2. Search button
 *  3. Results list (loading spinner / error / empty / list of [ChurchResultCard])
 *
 * @param sheetState         Controls the expansion state of the sheet.
 * @param churchFinderState  Current search state from the ViewModel.
 * @param onSearch           Called with the location string when the user taps Search.
 * @param onDismiss          Called when the sheet is dismissed.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChurchFinderBottomSheet(
    churchFinderState: ChurchFinderSheetState,
    onSearch: (location: String) -> Unit,
    onDismiss: () -> Unit,
    sheetState: SheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
) {
    var locationInput by rememberSaveable { mutableStateOf("") }
    var locationTouched by rememberSaveable { mutableStateOf(false) }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxHeight(0.85f)
                .padding(horizontal = 16.dp)
                .navigationBarsPadding()
                .padding(bottom = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            // ── Header ──────────────────────────────────────────────────────────
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Icon(
                    imageVector = Icons.Default.LocationOn,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.secondary,
                    modifier = Modifier.size(24.dp),
                )
                Column {
                    Text(
                        text = stringResource(R.string.church_finder_modal_title),
                        style = MaterialTheme.typography.titleLarge,
                    )
                    Text(
                        text = stringResource(R.string.church_finder_modal_subtitle),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            // ── Location input ───────────────────────────────────────────────
            val locationError = locationTouched && locationInput.isBlank()
            OutlinedTextField(
                value = locationInput,
                onValueChange = { locationInput = it },
                label = { Text(stringResource(R.string.church_finder_search_placeholder)) },
                supportingText = {
                    if (locationError) {
                        Text(stringResource(R.string.church_finder_location_required))
                    } else {
                        Text(stringResource(R.string.church_finder_location_hint))
                    }
                },
                isError = locationError,
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                keyboardOptions = KeyboardOptions(
                    capitalization = KeyboardCapitalization.Words,
                    imeAction = ImeAction.Search,
                ),
                keyboardActions = KeyboardActions(
                    onSearch = {
                        locationTouched = true
                        if (locationInput.isNotBlank()) onSearch(locationInput)
                    },
                ),
            )

            // ── Search button ─────────────────────────────────────────────────
            Button(
                onClick = {
                    locationTouched = true
                    if (locationInput.isNotBlank()) onSearch(locationInput)
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = locationInput.isNotBlank() && churchFinderState !is ChurchFinderSheetState.Loading,
            ) {
                if (churchFinderState is ChurchFinderSheetState.Loading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(18.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.onPrimary,
                    )
                } else {
                    Text(stringResource(R.string.church_finder_search_button))
                }
            }

            HorizontalDivider()

            // ── Results ───────────────────────────────────────────────────────
            when (churchFinderState) {
                is ChurchFinderSheetState.Idle -> {
                    Text(
                        text = stringResource(R.string.church_finder_enter_location),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.align(Alignment.CenterHorizontally),
                    )
                }

                is ChurchFinderSheetState.Loading -> {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(100.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        CircularProgressIndicator()
                    }
                }

                is ChurchFinderSheetState.Error -> {
                    Text(
                        text = churchFinderState.message,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.padding(vertical = 8.dp),
                    )
                    TextButton(
                        onClick = { if (locationInput.isNotBlank()) onSearch(locationInput) },
                        contentPadding = PaddingValues(0.dp),
                    ) {
                        Text(stringResource(R.string.action_retry))
                    }
                }

                is ChurchFinderSheetState.Success -> {
                    val churches = churchFinderState.churches
                    if (churches.isEmpty()) {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 16.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.spacedBy(4.dp),
                        ) {
                            Text(
                                text = stringResource(R.string.church_finder_no_churches_found),
                                style = MaterialTheme.typography.bodyMedium,
                            )
                            Text(
                                text = stringResource(R.string.church_finder_no_churches_hint),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    } else {
                        Text(
                            text = pluralStringResource(
                                R.plurals.church_finder_found_count,
                                churches.size,
                                churches.size,
                            ),
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        LazyColumn(
                            modifier = Modifier
                                .fillMaxWidth()
                                .weight(1f),
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            items(churches) { church ->
                                ChurchResultCard(church = church)
                            }
                        }
                    }
                }
            }
        }
    }
}

/**
 * A single church entry card showing name, location, and optional contact links.
 */
@Composable
private fun ChurchResultCard(
    church: Church,
    modifier: Modifier = Modifier,
) {
    val uriHandler = LocalUriHandler.current

    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Text(
            text = church.name,
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurface,
        )

        if (church.locationLine.isNotBlank()) {
            Text(
                text = church.locationLine,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        if (!church.address.isNullOrBlank()) {
            Text(
                text = church.address,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (!church.website.isNullOrBlank()) {
                TextButton(
                    onClick = {
                        runCatching { uriHandler.openUri(church.website) }
                    },
                    contentPadding = PaddingValues(0.dp),
                ) {
                    Text(
                        text = stringResource(R.string.church_finder_website),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                }
            }

            if (!church.email.isNullOrBlank()) {
                TextButton(
                    onClick = {
                        runCatching { uriHandler.openUri("mailto:${church.email}") }
                    },
                    contentPadding = PaddingValues(0.dp),
                ) {
                    Text(
                        text = stringResource(R.string.church_finder_email),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                }
            }
        }

        HorizontalDivider(modifier = Modifier.padding(top = 4.dp))
    }
}
