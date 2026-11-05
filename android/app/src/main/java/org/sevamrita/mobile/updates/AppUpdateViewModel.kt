package org.sevamrita.mobile.updates

import android.app.Application
import android.content.Intent
import androidx.compose.runtime.mutableStateOf
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.sevamrita.mobile.BuildConfig
import java.io.File

internal enum class UpdatePhase { IDLE, CHECKING, AVAILABLE, DOWNLOADING, READY, PERMISSION, INSTALLER, CURRENT, ERROR }
internal data class AppUpdateState(
    val phase: UpdatePhase = UpdatePhase.IDLE, val release: UpdateRelease? = null,
    val downloadedBytes: Long = 0, val message: String = "", val dialog: Boolean = false, val banner: Boolean = false
)

/** App updates never enter the chat's loading, error, session or navigation state. */
internal class AppUpdateViewModel(application: Application) : AndroidViewModel(application) {
    val state = mutableStateOf(AppUpdateState())
    private val client = AppUpdateClient(application)
    private val preferences = application.getSharedPreferences("app_updates", 0)
    private var apk: File? = null

    fun check(manual: Boolean = false) {
        val current = state.value
        if (current.phase in listOf(UpdatePhase.CHECKING, UpdatePhase.DOWNLOADING)) {
            if (manual) state.value = current.copy(dialog = true)
            return
        }
        if (current.release != null && current.phase != UpdatePhase.ERROR) {
            if (manual) state.value = current.copy(dialog = true)
            return
        }
        val now = System.currentTimeMillis()
        val last = preferences.getLong("last_check", 0)
        if (!manual && now >= last && now - last < 6 * 60 * 60 * 1000) return
        state.value = current.copy(phase = UpdatePhase.CHECKING, dialog = manual, message = "")
        viewModelScope.launch {
            try {
                val release = withContext(Dispatchers.IO) { client.latest() }
                preferences.edit().putLong("last_check", now).apply()
                state.value = state.value.copy(phase = if (release == null) UpdatePhase.CURRENT else UpdatePhase.AVAILABLE,
                    release = release, banner = release != null)
            } catch (error: Exception) {
                if (error is CancellationException) throw error
                // Quiet automatic checks must never interrupt work when offline.
                state.value = state.value.copy(phase = UpdatePhase.ERROR, message = "Could not check for updates. Check your connection and try again.")
                preferences.edit().putLong("last_check", now - 5 * 60 * 60 * 1000).apply()
            }
        }
    }

    fun show() { state.value = state.value.copy(dialog = true) }
    fun later() { state.value = state.value.copy(dialog = false, banner = false) }
    fun dismiss() { state.value = state.value.copy(dialog = false) }

    fun download() {
        val release = state.value.release ?: return
        if (state.value.phase == UpdatePhase.DOWNLOADING) return
        state.value = state.value.copy(phase = UpdatePhase.DOWNLOADING, downloadedBytes = 0, message = "")
        viewModelScope.launch {
            try {
                var lastProgress = 0L
                apk = withContext(Dispatchers.IO) {
                    client.download(release) { bytes ->
                        if (bytes - lastProgress >= 128 * 1024 || bytes == release.sizeBytes) {
                            lastProgress = bytes
                            viewModelScope.launch { state.value = state.value.copy(downloadedBytes = bytes) }
                        }
                    }
                }
                state.value = state.value.copy(phase = UpdatePhase.READY, downloadedBytes = release.sizeBytes)
            } catch (error: Exception) {
                if (error is CancellationException) throw error
                fail(error.message ?: "The update could not be downloaded. Please retry.")
            }
        }
    }

    fun install(start: (Intent) -> Unit) {
        val release = state.value.release ?: return
        val file = apk ?: run { download(); return }
        viewModelScope.launch {
            try {
                val intent = withContext(Dispatchers.IO) { client.installIntent(file, release) }
                start(intent)
                state.value = state.value.copy(phase = UpdatePhase.INSTALLER)
            } catch (error: Exception) {
                if (error is CancellationException) throw error
                fail("Android could not open the update: ${error.message.orEmpty()}")
            }
        }
    }

    fun permissionNeeded() { state.value = state.value.copy(phase = UpdatePhase.PERMISSION) }
    fun permissionReturned(allowed: Boolean) {
        state.value = state.value.copy(phase = if (allowed) UpdatePhase.READY else UpdatePhase.PERMISSION)
    }
    fun fail(message: String) { state.value = state.value.copy(phase = UpdatePhase.ERROR, message = message) }
    val installedLabel get() = "${BuildConfig.APP_NAME} ${BuildConfig.VERSION_NAME}"
}
