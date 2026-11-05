package org.sevamrita.mobile.updates

import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
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
    val context = LocalContext.current
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        model.permissionReturned(context.packageManager.canRequestPackageInstalls())
    }
    fun install() {
        if (context.packageManager.canRequestPackageInstalls()) model.install(context::startActivity)
        else model.permissionNeeded()
    }
    AlertDialog(onDismissRequest = model::dismiss,
        title = { Text(when (state.phase) {
            UpdatePhase.CHECKING -> "Check for updates"
            UpdatePhase.CURRENT -> "You're up to date"
            UpdatePhase.ERROR -> "Update unavailable"
            UpdatePhase.PERMISSION -> "Allow app updates"
            UpdatePhase.READY, UpdatePhase.INSTALLER -> "Ready to install"
            else -> "Update ${state.release?.versionName.orEmpty()}"
        }) },
        text = { Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(model.installedLabel, style = MaterialTheme.typography.labelMedium)
            when (state.phase) {
                UpdatePhase.CHECKING -> Text("Checking for a newer version…")
                UpdatePhase.CURRENT -> Text("You have the latest published version.")
                UpdatePhase.ERROR -> Text(state.message)
                UpdatePhase.PERMISSION -> Text("In Android settings, enable ‘Allow from this source’ for this app. Return here and tap Install update. Android will ask you to confirm the installation.")
                UpdatePhase.READY -> Text("Download verified. Tap Install update to open Android's installer. Your account and app data are kept.")
                UpdatePhase.INSTALLER -> Text("Complete the installation in Android's installer. If you cancelled it, you can open it again below.")
                UpdatePhase.DOWNLOADING -> {
                    val fraction = state.downloadedBytes.toFloat() / (state.release?.sizeBytes ?: 1).toFloat()
                    Text("Downloading update · ${(fraction * 100).toInt()}%")
                    LinearProgressIndicator(progress = { fraction.coerceIn(0f, 1f) }, modifier = Modifier.fillMaxWidth())
                    Text("You can close this panel and continue chatting while it downloads.", style = MaterialTheme.typography.bodySmall)
                }
                else -> {
                    Text("Install the latest version without downloading an APK manually. Android will ask you to confirm installation.")
                    state.release?.let { Text("Download: %.1f MB".format(it.sizeBytes / 1048576.0), style = MaterialTheme.typography.bodySmall) }
                }
            }
            if (state.release?.notes?.isNotBlank() == true) {
                Text("What's new", fontWeight = FontWeight.SemiBold)
                Text(state.release.notes, style = MaterialTheme.typography.bodyMedium)
            }
        } },
        confirmButton = { when (state.phase) {
            UpdatePhase.AVAILABLE -> TextButton(onClick = model::download) { Text("Download update") }
            UpdatePhase.READY, UpdatePhase.INSTALLER -> TextButton(onClick = ::install) { Text("Install update") }
            UpdatePhase.PERMISSION -> TextButton(onClick = {
                if (context.packageManager.canRequestPackageInstalls()) { model.permissionReturned(true); install() }
                else try { permission.launch(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${context.packageName}"))) }
                catch (_: Exception) { model.fail("Open Android Settings → Apps → Special app access → Install unknown apps, and allow this app. Then retry.") }
            }) { Text("Open settings") }
            UpdatePhase.ERROR -> TextButton(onClick = { if (state.release == null) model.check(manual = true) else model.download() }) { Text("Retry") }
            UpdatePhase.CURRENT, UpdatePhase.IDLE -> TextButton(onClick = model::dismiss) { Text("Done") }
            else -> Unit
        } },
        dismissButton = { if (state.phase !in listOf(UpdatePhase.CURRENT, UpdatePhase.IDLE)) TextButton(onClick = model::later) { Text(if (state.phase == UpdatePhase.DOWNLOADING) "Continue in app" else "Later") } })
}
