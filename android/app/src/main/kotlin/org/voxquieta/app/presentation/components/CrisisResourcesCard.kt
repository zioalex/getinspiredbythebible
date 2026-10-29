package org.voxquieta.app.presentation.components

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Call
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import org.voxquieta.app.R
import org.voxquieta.app.domain.models.CrisisLine
import org.voxquieta.app.domain.models.CrisisResources
import timber.log.Timber
import java.util.Locale

/** Minimum touch target (Material / WCAG): 48dp. */
private val MinTarget = 48.dp

/** Strips spaces, dashes, dots and parentheses from a display phone number; keeps a leading +. */
internal fun dialableNumber(raw: String): String = raw.replace(Regex("[\\s\\-.()]"), "")

/**
 * `ACTION_DIAL` opens the dialer pre-filled; it never places the call, so no CALL_PHONE
 * permission is needed (and `ACTION_CALL` must never be used here).
 */
internal fun dialIntent(number: String): Intent =
    Intent(Intent.ACTION_DIAL, Uri.parse("tel:${dialableNumber(number)}"))

/** `ACTION_SENDTO` with `smsto:` opens the default messaging app addressed to [number]. */
internal fun smsIntent(number: String): Intent =
    Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:${dialableNumber(number)}"))

internal fun viewUrlIntent(url: String): Intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))

/** Localized country name for an ISO 3166-1 alpha-2 [code]; falls back to the code itself. */
internal fun countryDisplayName(code: String): String =
    Locale("", code).getDisplayCountry(Locale.getDefault()).ifBlank { code }

private fun launchSafely(context: Context, intent: Intent) {
    try {
        if (context !is Activity) intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
    } catch (e: ActivityNotFoundException) {
        Timber.w(e, "No activity to handle %s", intent.action)
    }
}

/**
 * Deterministic emergency / crisis contacts pinned above the assistant reply on self-harm and
 * threat-to-others turns (BITB-251). Mirrors the web `CrisisResourcesCard`.
 *
 * - Dial and SMS go through `ACTION_DIAL` / `ACTION_SENDTO` (no permission needed).
 * - The card is a polite live region so TalkBack announces it when it appears.
 * - Every action is at least 48dp tall and carries a descriptive content description.
 * - "Not in X?" opens a country picker; the pick is reported via [onCountrySelected] and used
 *   (with `region_override = true`) from the next message on.
 *
 * @param launchIntent Hook for tests; defaults to `startActivity` on the current context.
 */
@Composable
fun CrisisResourcesCard(
    resources: CrisisResources,
    onCountrySelected: (String) -> Unit,
    modifier: Modifier = Modifier,
    launchIntent: ((Intent) -> Unit)? = null,
) {
    val context = LocalContext.current
    val launch: (Intent) -> Unit = launchIntent ?: { launchSafely(context, it) }

    var pickerOpen by remember { mutableStateOf(false) }
    var chosenCountry by rememberSaveable { mutableStateOf<String?>(null) }
    val shownCountry = chosenCountry ?: resources.country

    Surface(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 6.dp)
            .semantics { liveRegion = LiveRegionMode.Polite },
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.errorContainer,
        contentColor = MaterialTheme.colorScheme.onErrorContainer,
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(
                text = stringResource(R.string.crisis_heading),
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.semantics { heading() },
            )

            resources.emergencyNumber?.let { number ->
                val emergencyAria = stringResource(R.string.crisis_emergency_aria, number)
                Button(
                    onClick = { launch(dialIntent(number)) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = MinTarget)
                        .semantics { contentDescription = emergencyAria },
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.error,
                        contentColor = MaterialTheme.colorScheme.onError,
                    ),
                ) {
                    Icon(Icons.Default.Call, contentDescription = null, modifier = Modifier.size(20.dp))
                    Text(
                        text = "${stringResource(R.string.crisis_emergency_label)}: $number",
                        style = MaterialTheme.typography.titleMedium,
                        modifier = Modifier.padding(start = 8.dp),
                    )
                }
            }

            resources.lines.forEach { line ->
                CrisisLineRow(line = line, launch = launch)
            }

            TextButton(
                onClick = { launch(viewUrlIntent(resources.internationalUrl)) },
                modifier = Modifier.heightIn(min = MinTarget),
            ) {
                Text(stringResource(R.string.crisis_international))
            }

            if (resources.availableCountries.isNotEmpty()) {
                TextButton(
                    onClick = { pickerOpen = true },
                    modifier = Modifier.heightIn(min = MinTarget),
                ) {
                    Text(
                        text = shownCountry?.let {
                            stringResource(R.string.crisis_not_in_country, countryDisplayName(it))
                        } ?: stringResource(R.string.crisis_choose_country),
                    )
                }
            }

            chosenCountry?.let {
                Text(
                    text = stringResource(R.string.crisis_region_saved, countryDisplayName(it)),
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }

    if (pickerOpen) {
        CountryPickerDialog(
            countries = resources.availableCountries,
            onSelect = { code ->
                chosenCountry = code
                pickerOpen = false
                onCountrySelected(code)
            },
            onDismiss = { pickerOpen = false },
        )
    }
}

@Composable
private fun CrisisLineRow(line: CrisisLine, launch: (Intent) -> Unit) {
    Surface(
        shape = RoundedCornerShape(10.dp),
        color = MaterialTheme.colorScheme.surface,
        contentColor = MaterialTheme.colorScheme.onSurface,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(line.name, style = MaterialTheme.typography.titleSmall)
            line.hours?.takeIf { it.isNotBlank() }?.let {
                Text(it, style = MaterialTheme.typography.bodySmall)
            }
            line.phone?.takeIf { it.isNotBlank() }?.let { phone ->
                val callAria = stringResource(R.string.crisis_call_line_aria, line.name)
                OutlinedButton(
                    onClick = { launch(dialIntent(phone)) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = MinTarget)
                        .semantics { contentDescription = callAria },
                ) {
                    Text("${stringResource(R.string.crisis_call)} $phone")
                }
            }
            line.sms?.takeIf { it.isNotBlank() }?.let { sms ->
                val textAria = stringResource(R.string.crisis_text_line_aria, line.name)
                OutlinedButton(
                    onClick = { launch(smsIntent(sms)) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = MinTarget)
                        .semantics { contentDescription = textAria },
                ) {
                    Text("${stringResource(R.string.crisis_text)} $sms")
                }
            }
            line.url?.takeIf { it.isNotBlank() }?.let { url ->
                TextButton(
                    onClick = { launch(viewUrlIntent(url)) },
                    modifier = Modifier.heightIn(min = MinTarget),
                ) {
                    Text(url.removePrefix("https://").removePrefix("http://"), textAlign = TextAlign.Start)
                }
            }
        }
    }
}

@Composable
private fun CountryPickerDialog(
    countries: List<String>,
    onSelect: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    val sorted = remember(countries) {
        countries.map { it to countryDisplayName(it) }.sortedBy { it.second }
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.crisis_choose_country)) },
        text = {
            LazyColumn {
                items(sorted, key = { it.first }) { (code, name) ->
                    TextButton(
                        onClick = { onSelect(code) },
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = MinTarget),
                    ) {
                        Text(name, modifier = Modifier.fillMaxWidth(), textAlign = TextAlign.Start)
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss, modifier = Modifier.heightIn(min = MinTarget)) {
                Text(stringResource(R.string.action_cancel))
            }
        },
    )
}
