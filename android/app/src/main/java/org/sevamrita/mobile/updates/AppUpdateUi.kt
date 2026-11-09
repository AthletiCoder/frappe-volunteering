package org.sevamrita.mobile.updates

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

internal val LocalAppUpdates = staticCompositionLocalOf<AppUpdateViewModel> { error("App updater unavailable") }

@Composable
internal fun AppUpdateBanner() {
    val model = LocalAppUpdates.current
    val state = model.state.value
    if (!state.banner || state.release == null) return
    Surface(color = MaterialTheme.colorScheme.secondaryContainer) {
        Row(Modifier.fillMaxWidth().padding(start = 16.dp, end = 8.dp, top = 4.dp, bottom = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("Update ${state.release.versionName} available", Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
            TextButton(onClick = model::show) { Text("View") }
            TextButton(onClick = model::later) { Text("Later") }
        }
    }
}

@Composable
internal fun AppUpdateDialogs(model: AppUpdateViewModel) {
    val state = model.state.value
    if (!state.dialog) return
    val uriHandler = LocalUriHandler.current
    val release = state.release
    AlertDialog(
        onDismissRequest = model::dismiss,
        title = {
            Text(when (state.phase) {
                UpdatePhase.CURRENT -> "You're up to date"
                UpdatePhase.AVAILABLE -> if (state.browserError) "Could not open the browser" else "Update ${release?.versionName.orEmpty()} available"
                UpdatePhase.ERROR -> "Update check unavailable"
                else -> "Check for updates"
            })
        },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(model.installedLabel, style = MaterialTheme.typography.labelMedium)
                when (state.phase) {
                    UpdatePhase.CHECKING -> Text("Checking Sevamrita ERP for updates…")
                    UpdatePhase.CURRENT -> Text("You have the latest version available on Sevamrita ERP.")
                    UpdatePhase.ERROR -> Text(state.message)
                    UpdatePhase.AVAILABLE -> {
                        if (state.browserError) {
                            Text("Check that you have a browser and try again.")
                        } else {
                            Text("Download the update from Sevamrita ERP in your browser.")
                            if (release != null && release.notes.isNotBlank()) {
                                Text("What's new", fontWeight = FontWeight.SemiBold)
                                Text(release.notes, style = MaterialTheme.typography.bodyMedium)
                            }
                        }
                    }
                    UpdatePhase.IDLE -> Unit
                }
            }
        },
        confirmButton = {
            when (state.phase) {
                UpdatePhase.AVAILABLE -> TextButton(onClick = { model.openRelease(uriHandler::openUri) }) {
                    Text(if (state.browserError) "Retry" else "Open ERP downloads")
                }
                UpdatePhase.ERROR -> TextButton(onClick = { model.check(manual = true) }) { Text("Retry") }
                UpdatePhase.CURRENT -> TextButton(onClick = model::dismiss) { Text("Done") }
                else -> Unit
            }
        },
        dismissButton = {
            when (state.phase) {
                UpdatePhase.AVAILABLE -> TextButton(onClick = model::later) { Text("Later") }
                UpdatePhase.CHECKING, UpdatePhase.ERROR -> TextButton(onClick = model::dismiss) { Text("Close") }
                else -> Unit
            }
        }
    )
}
