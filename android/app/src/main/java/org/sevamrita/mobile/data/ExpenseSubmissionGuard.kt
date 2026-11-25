package org.sevamrita.mobile.data

internal data class ExpenseAttempt<T>(val key: String, val method: String = "", val args: T? = null, val result: T? = null)

/** Transport-independent safety rules, also exercised by JVM tests. */
internal class ExpenseSubmissionGuard<T>(
    private val read: () -> ExpenseAttempt<T>?, private val write: (ExpenseAttempt<T>) -> Unit,
    private val remove: () -> Unit, private val send: (String, T, String) -> T,
    private val recover: (String) -> T?, private val rejected: (Exception) -> Boolean,
    private val same: (T, T) -> Boolean, private val newKey: () -> String,
    private val status: (String) -> Unit
) {
    private var sending = false
    fun submit(method: String, args: T): T {
        synchronized(this) { check(!sending) { "Your submission is already being checked." }; sending = true }
        try {
            var saved = read()
            saved?.result?.let { return it }
            if (saved != null) {
                recoverSaved(saved)?.let { return it }
                if (saved.method != method || saved.args == null || !same(saved.args, args)) { remove(); saved = null }
            }
            if (saved == null) {
                saved = ExpenseAttempt(newKey(), method, args)
                write(saved)
            }
            status("Submitting claim and receipts. Please keep this screen open…")
            try { return complete(saved, send(method, requireNotNull(saved.args), saved.key)) }
            catch (error: Exception) {
                if (rejected(error)) { remove(); throw error }
                try { recoverSaved(saved)?.let { return it } } catch (_: Exception) { /* Keep the unresolved request. */ }
                status("Confirmation was interrupted. Your details and receipts are saved. Retry saved submission to check before sending again.")
                throw IllegalStateException("Could not confirm submission. Use the saved-submission option; do not create another claim.", error)
            }
        } finally { synchronized(this) { sending = false } }
    }
    private fun recoverSaved(saved: ExpenseAttempt<T>): T? {
        status("Checking whether your claim was saved…")
        return recover(saved.key)?.let { complete(saved, it) }
    }
    private fun complete(saved: ExpenseAttempt<T>, result: T): T {
        write(ExpenseAttempt(key = saved.key, result = result)) // Remove the receipt/signature bytes.
        status("")
        return result
    }
}
