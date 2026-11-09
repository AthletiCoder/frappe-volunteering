package org.sevamrita.mobile.updates

import android.app.Application
import android.content.ActivityNotFoundException
import androidx.compose.runtime.mutableStateOf
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.sevamrita.mobile.BuildConfig

internal enum class UpdatePhase { IDLE, CHECKING, CURRENT, AVAILABLE, ERROR }

internal data class AppUpdateState(
    val phase: UpdatePhase = UpdatePhase.IDLE,
    val release: UpdateRelease? = null,
    val dialog: Boolean = false,
    val banner: Boolean = false,
    val message: String = "",
    val browserError: Boolean = false
)

internal class AppUpdateViewModel(application: Application) : AndroidViewModel(application) {
    val state = mutableStateOf(AppUpdateState())
    private val client = AppUpdateClient(application)
    private val preferences = application.getSharedPreferences("app_updates", 0)
    private var checkJob: Job? = null

    fun check(manual: Boolean = false) {
        val current = state.value
        if (checkJob?.isActive == true) {
            if (manual) state.value = current.copy(dialog = true)
            return
        }
        val now = System.currentTimeMillis()
        val last = preferences.getLong("last_erp_check", 0)
        if (!manual && (current.dialog || now >= last && now - last < 6 * 60 * 60 * 1000)) return

        state.value = AppUpdateState(phase = UpdatePhase.CHECKING, dialog = manual)
        checkJob = viewModelScope.launch {
            try {
                val release = withContext(Dispatchers.IO) { client.latest() }
                preferences.edit().putLong("last_erp_check", now).apply()
                state.value = state.value.copy(
                    phase = if (release == null) UpdatePhase.CURRENT else UpdatePhase.AVAILABLE,
                    release = release,
                    banner = release != null
                )
            } catch (error: Exception) {
                if (error is CancellationException) throw error
                val message = if (error is NoPublishedUpdateException) {
                    "No update for this app has been published on Sevamrita ERP yet."
                } else {
                    "Could not check Sevamrita ERP for updates. Please try again."
                }
                state.value = state.value.copy(phase = UpdatePhase.ERROR, message = message)
                preferences.edit().putLong("last_erp_check", now - 5 * 60 * 60 * 1000).apply()
            }
        }
    }

    fun show() { state.value = state.value.copy(dialog = true, browserError = false) }
    fun later() { state.value = state.value.copy(dialog = false, banner = false) }
    fun dismiss() { state.value = state.value.copy(dialog = false) }

    fun openRelease(openUri: (String) -> Unit) {
        if (state.value.phase != UpdatePhase.AVAILABLE) return
        try {
            openUri(UpdatePolicy.releasePage(getApplication<Application>().packageName))
            state.value = state.value.copy(dialog = false, browserError = false)
        } catch (_: IllegalArgumentException) {
            state.value = state.value.copy(dialog = true, browserError = true)
        } catch (_: ActivityNotFoundException) {
            state.value = state.value.copy(dialog = true, browserError = true)
        }
    }

    val installedLabel get() = "${BuildConfig.APP_NAME} ${BuildConfig.VERSION_NAME}"
}
