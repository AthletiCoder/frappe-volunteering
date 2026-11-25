package org.sevamrita.mobile.data

import org.json.JSONObject
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean

/** Explicit, encrypted claim attempts. Never creates claims in the background. */
internal class ExpenseRequests(private val store: DurableChat) {
    private val sending = AtomicBoolean(false)
    private val slot = "erp-expense-submission"
    private val statusMethod = "volunteering.volunteering.expense_claim_requests.get_expense_submission_status"
    fun pending(api: PortalApi): JSONObject = store.read(api.endpoint(), api.currentUser, slot)
    fun clear(api: PortalApi) = store.delete(api.endpoint(), api.currentUser, slot)
    fun submit(api: PortalApi, method: String, args: JSONObject, status: (String) -> Unit): JSONObject {
        check(sending.compareAndSet(false, true)) { "Your submission is already being checked." }
        try { return submitSaved(api, method, args, status) }
        finally { sending.set(false) }
    }
    private fun submitSaved(api: PortalApi, method: String, args: JSONObject, status: (String) -> Unit): JSONObject {
        val endpoint = api.endpoint()
        val user = api.currentUser
        fun checkIdentity() = check(api.endpoint() == endpoint && api.currentUser == user) {
            "Your account changed. Sign in to the original account to check its saved submission."
        }
        val guard = ExpenseSubmissionGuard<JSONObject>(
            read = { store.read(endpoint, user, slot).takeIf { it.has("key") }?.let {
                ExpenseAttempt(it.text("key"), it.text("method"), it.optJSONObject("args"), it.optJSONObject("result"))
            } },
            write = { saved -> store.write(endpoint, user, slot, JSONObject().put("key", saved.key).put("method", saved.method)
                .put("args", saved.args).put("result", saved.result)) },
            remove = { store.delete(endpoint, user, slot) },
            send = { methodName, payload, key ->
                checkIdentity()
                api.call(methodName, JSONObject(payload.toString()).put("request_key", key)).also { checkIdentity() }
            },
            recover = { key ->
                checkIdentity()
                api.call(statusMethod, JSONObject().put("request_key", key)).let {
                    checkIdentity()
                    if (it.optBoolean("found")) it.getJSONObject("result") else null
                }
            },
            rejected = { it is PortalApiException && it.status in 400..499 },
            same = { one, two -> one.toString() == two.toString() }, newKey = { UUID.randomUUID().toString() }, status = status)
        return guard.submit(method, args)
    }
    fun retry(api: PortalApi, status: (String) -> Unit): JSONObject {
        val saved = pending(api)
        saved.optJSONObject("result")?.let { return it }
        require(saved.has("args")) { "No saved submission to retry." }
        return submit(api, saved.text("method"), saved.getJSONObject("args"), status)
    }
}
