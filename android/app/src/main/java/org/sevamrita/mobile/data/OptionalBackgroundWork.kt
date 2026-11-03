package org.sevamrita.mobile.data

/** Optional background services must never invalidate a successful foreground login. */
internal fun runOptionalBackgroundWork(work: () -> Unit, onFailure: (Exception) -> Unit = {}): Boolean = try {
    work()
    true
} catch (error: Exception) {
    if (error is java.util.concurrent.CancellationException) throw error
    onFailure(error)
    false
}

class PortalSessionRequiredException(message: String = "Your session has ended. Please sign in again.") : java.io.IOException(message)
