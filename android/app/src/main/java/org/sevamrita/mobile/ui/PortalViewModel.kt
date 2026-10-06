package org.sevamrita.mobile.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import org.sevamrita.mobile.data.PortalApi
import org.sevamrita.mobile.data.SecureSessionStore
import org.sevamrita.mobile.data.Server
import org.sevamrita.mobile.data.text

enum class Page { HOME, WORK, PROJECTS, PROJECT, PROPOSALS, PROPOSAL, PROPOSAL_FORM, ADVANCES, ADVANCE, NEW_ADVANCE, CLAIMS, CLAIM, NEW_CLAIM, ADVANCE_QUEUE, ADVANCE_REVIEW, CLAIM_QUEUE, CLAIM_REVIEW, RECEIPT, PROFILE, UNAVAILABLE }

data class PortalState(
    val signedIn: Boolean = false,
    val booting: Boolean = true,
    val busy: Boolean = false,
    val page: Page = Page.HOME,
    val server: Server = Server.PRODUCTION,
    val user: String = "",
    val error: String = "",
    val notice: String = "",
    val home: JSONObject = JSONObject(),
    val data: JSONObject = JSONObject(),
    val form: JSONObject = JSONObject(),
    val detailId: String = "",
    val unavailableLabel: String = "",
    val receiptBytes: ByteArray? = null,
    val receiptName: String = "",
    val receiptReturn: Page = Page.CLAIM_REVIEW,
    val proposalFilter: String = "mine"
)

class PortalViewModel(application: Application) : AndroidViewModel(application) {
    private val api = PortalApi(SecureSessionStore(application))
    private var navigationRevision = 0
    var state = androidx.compose.runtime.mutableStateOf(PortalState(server = api.server()))
        private set

    init {
        if (!api.hasSession()) state.value = state.value.copy(booting = false)
        else runTask(onFailure = { api.logoutLocal(); state.value = state.value.copy(signedIn = false, booting = false) }) {
            api.bootstrap()
            val home = api.call(HOME, get = true)
            state.value = state.value.copy(signedIn = true, booting = false, home = home, user = api.currentUser)
        }
    }

    fun selectServer(server: Server) {
        api.setServer(server)
        state.value = state.value.copy(server = server, error = "", notice = "")
    }

    fun login(username: String, password: String) {
        if (username.isBlank() || password.isBlank()) { error("Enter your email and password."); return }
        runTask {
            api.login(username.trim(), password)
            val home = api.call(HOME, get = true)
            state.value = state.value.copy(signedIn = true, booting = false, home = home, user = api.currentUser, page = Page.HOME)
        }
    }

    fun logout() {
        navigationRevision++
        runTask {
            api.logout()
            state.value = PortalState(booting = false, server = api.server())
        }
    }

    fun refreshHome() = runTask {
        val home = api.call(HOME, get = true)
        state.value = state.value.copy(home = home)
    }

    fun open(page: Page, id: String = "") {
        val revision = ++navigationRevision
        state.value = state.value.copy(page = page, detailId = id, error = "", notice = "", data = JSONObject(), form = JSONObject())
        val method = when (page) {
            Page.PROJECTS -> "volunteering.volunteering.project_workspace.get_projects"
            Page.PROJECT -> "volunteering.volunteering.project_workspace.get_project"
            Page.PROPOSALS -> "volunteering.volunteering.project_proposals.get_proposals"
            Page.PROPOSAL -> "volunteering.volunteering.project_proposals.get_proposal"
            Page.PROPOSAL_FORM -> "volunteering.volunteering.project_workspace.get_setup_options"
            Page.ADVANCES -> "volunteering.volunteering.advance_portal.get_my_advances"
            Page.ADVANCE -> "volunteering.volunteering.advance_portal.get_advance_detail"
            Page.NEW_ADVANCE -> "volunteering.volunteering.advance_portal.get_advance_request_form"
            Page.CLAIMS -> "volunteering.volunteering.expense_claim_portal.get_my_expense_claims"
            Page.CLAIM -> "volunteering.volunteering.expense_claim_portal.get_my_expense_claim"
            Page.NEW_CLAIM -> "volunteering.volunteering.expense_claim_portal.get_expense_claim_form"
            Page.PROFILE -> "volunteering.volunteering.employee_profile.get_my_profile"
            Page.ADVANCE_QUEUE -> "volunteering.volunteering.advance_workflow_portal.get_advance_work_queue"
            Page.ADVANCE_REVIEW -> "volunteering.volunteering.advance_workflow_portal.get_advance_work_item"
            Page.CLAIM_QUEUE -> "volunteering.volunteering.expense_claim_workflow_portal.get_expense_claim_work_queue"
            Page.CLAIM_REVIEW -> "volunteering.volunteering.expense_claim_workflow_portal.get_expense_claim_work_item"
            else -> null
        }
        if (method != null) runTask {
            val args = when (page) {
                Page.PROJECT -> JSONObject().put("project", id)
                Page.PROPOSAL -> JSONObject().put("proposal", id)
                Page.ADVANCE, Page.CLAIM, Page.ADVANCE_REVIEW, Page.CLAIM_REVIEW -> JSONObject().put("name", id)
                else -> JSONObject()
            }
            val data = api.call(method, args)
            if (revision != navigationRevision) return@runTask
            state.value = if (page == Page.NEW_ADVANCE || page == Page.NEW_CLAIM || page == Page.PROPOSAL_FORM) state.value.copy(form = data)
                else state.value.copy(data = data)
            if (page == Page.PROPOSAL_FORM && id.isNotBlank()) {
                val proposal = api.call("volunteering.volunteering.project_proposals.get_proposal", JSONObject().put("proposal", id))
                if (revision != navigationRevision) return@runTask
                state.value = state.value.copy(data = proposal)
            }
            if (page == Page.PROFILE) {
                val bank = api.call("volunteering.volunteering.employee_bank_accounts.get_my_bank_account_summary")
                if (revision != navigationRevision) return@runTask
                state.value = state.value.copy(form = bank)
            }
        }
    }

    fun openAction(label: String, route: String) {
        val target = routeTarget(route)
        if (target == null) state.value = state.value.copy(page = Page.UNAVAILABLE, unavailableLabel = label, error = "", notice = "")
        else if (target.first == Page.PROPOSALS) openProposals(target.second)
        else open(target.first, target.second)
    }

    fun openProposals(filter: String) {
        state.value = state.value.copy(proposalFilter = filter)
        open(Page.PROPOSALS)
    }

    fun saveProposal(data: JSONObject, approver: String, submitNow: Boolean) = runTask {
        val current = state.value.data
        val args = JSONObject().put("data", data.toString()).put("assigned_approver", approver)
        if (current.text("name").isNotBlank()) {
            args.put("proposal", current.text("name")).put("modified", current.text("modified"))
        }
        val saved = api.call("volunteering.volunteering.project_proposals.save_proposal", args)
        // Keep the saved request visible even if final submission validation fails.
        state.value = state.value.copy(data = saved, detailId = saved.text("name"))
        val result = if (submitNow) api.call("volunteering.volunteering.project_proposals.submit_proposal",
            JSONObject().put("proposal", saved.text("name")).put("modified", saved.text("modified"))) else saved
        state.value = state.value.copy(page = Page.PROPOSAL, data = result, detailId = result.text("name"),
            notice = if (submitNow) "Proposal sent for approval." else "Proposal draft saved.")
    }

    fun submitSavedProposal() = runTask {
        val proposal = state.value.data
        val result = api.call("volunteering.volunteering.project_proposals.submit_proposal",
            JSONObject().put("proposal", proposal.text("name")).put("modified", proposal.text("modified")))
        state.value = state.value.copy(data = result, notice = "Proposal sent for approval.")
    }

    fun reviewProposal(action: String, comments: String) = runTask {
        val proposal = state.value.data
        val result = api.call("volunteering.volunteering.project_proposals.review_proposal",
            JSONObject().put("proposal", proposal.text("name")).put("modified", proposal.text("modified"))
                .put("action", action).put("comments", comments))
        state.value = state.value.copy(data = result, notice = "Proposal decision recorded: $action.")
    }

    fun projectAccounts(project: String) {
        if (project.isBlank()) return
        val revision = navigationRevision
        runTask {
            val accounts = api.call(
                "volunteering.volunteering.expense_claim_portal.get_project_accounts",
                JSONObject().put("project", project)
            )
            if (revision == navigationRevision && state.value.page == Page.NEW_CLAIM) {
                state.value = state.value.copy(data = accounts)
            }
        }
    }

    fun submitAdvance(payload: JSONObject) = runTask {
        val result = api.call(
            "volunteering.volunteering.advance_portal.save_advance_request",
            JSONObject().put("payload", payload.toString()).put("submit_request", 1)
        )
        val id = result.optString("name")
        if (id.isBlank()) throw IllegalStateException("The server did not return an advance number.")
        val detail = api.call("volunteering.volunteering.advance_portal.get_advance_detail", JSONObject().put("name", id))
        state.value = state.value.copy(page = Page.ADVANCE, detailId = id, data = detail,
            notice = "Advance request $id submitted.")
    }

    fun submitClaim(payload: JSONObject) = runTask {
        val result = api.call(
            "volunteering.volunteering.expense_claim_portal.submit_expense_claim",
            JSONObject().put("payload", payload.toString())
        )
        val id = result.optString("name")
        if (id.isBlank()) throw IllegalStateException("The server did not return a claim number.")
        val detail = api.call("volunteering.volunteering.expense_claim_portal.get_my_expense_claim", JSONObject().put("name", id))
        state.value = state.value.copy(page = Page.CLAIM, detailId = id, data = detail,
            notice = "Expense claim $id submitted for review.")
    }

    fun decideAdvance(action: String, reason: String) = runTask {
        api.call("volunteering.volunteering.advance_workflow_portal.decide_advance",
            JSONObject().put("name", state.value.detailId).put("action", action).put("reason", reason))
        val queue = api.call("volunteering.volunteering.advance_workflow_portal.get_advance_work_queue")
        val home = api.call(HOME, get = true)
        state.value = state.value.copy(page = Page.ADVANCE_QUEUE, data = queue, home = home,
            notice = "Advance decision recorded: $action.")
    }

    fun reviewClaimReceipt(decision: String, notes: String) = runTask {
        api.call("volunteering.volunteering.expense_claim_workflow_portal.review_expense_claim_receipts",
            JSONObject().put("name", state.value.detailId).put("decision", decision).put("notes", notes))
        val queue = api.call("volunteering.volunteering.expense_claim_workflow_portal.get_expense_claim_work_queue")
        val home = api.call(HOME, get = true)
        state.value = state.value.copy(page = Page.CLAIM_QUEUE, data = queue, home = home,
            notice = "Receipt review saved.")
    }

    fun decideClaim(action: String, reason: String, amounts: JSONObject) = runTask {
        api.call("volunteering.volunteering.expense_claim_workflow_portal.decide_expense_claim",
            JSONObject().put("name", state.value.detailId).put("action", action)
                .put("reason", reason).put("sanctioned_amounts", amounts.toString()))
        val queue = api.call("volunteering.volunteering.expense_claim_workflow_portal.get_expense_claim_work_queue")
        val home = api.call(HOME, get = true)
        state.value = state.value.copy(page = Page.CLAIM_QUEUE, data = queue, home = home,
            notice = "Claim decision recorded: $action.")
    }

    fun openReceipt(path: String, returnTo: Page) = runTask {
        val bytes = api.privateFile(path)
        state.value = state.value.copy(page = Page.RECEIPT, receiptBytes = bytes,
            receiptName = path.substringAfterLast('/'), receiptReturn = returnTo)
    }

    fun closeReceipt() {
        state.value = state.value.copy(page = state.value.receiptReturn, receiptBytes = null, receiptName = "")
    }

    fun error(message: String) { state.value = state.value.copy(error = message) }
    fun dismissMessage() { state.value = state.value.copy(error = "", notice = "") }

    private fun runTask(onFailure: (() -> Unit)? = null, action: suspend () -> Unit) {
        viewModelScope.launch {
            state.value = state.value.copy(busy = true, error = "")
            try { withContext(Dispatchers.IO) { action() } }
            catch (exception: Exception) {
                onFailure?.invoke()
                state.value = state.value.copy(error = exception.message ?: "Something went wrong.", booting = false)
            }
            finally { state.value = state.value.copy(busy = false) }
        }
    }

    companion object {
        private const val HOME = "volunteering.volunteering.home_service.get_home_payload"
    }
}

/** Explicit allow-list: a Home action can never navigate to Desk or a WebView. */
fun routeTarget(route: String): Pair<Page, String>? {
    val path = route.substringBefore('?')
    val params = route.substringAfter('?', "")
    fun query(name: String): String = params.split('&').firstOrNull { it.substringBefore('=') == name }
        ?.substringAfter('=', "")?.let { java.net.URLDecoder.decode(it, "UTF-8") } ?: ""
    return when {
        path == "/volunteering/home" -> Page.HOME to ""
        path == "/volunteering/todos" -> Page.WORK to ""
        path == "/volunteering/projects" && params.contains("new=1") -> Page.PROPOSAL_FORM to ""
        path == "/volunteering/projects" && query("proposal").isNotBlank() -> Page.PROPOSAL to query("proposal")
        path == "/volunteering/projects" && query("project").isNotBlank() -> Page.PROJECT to query("project")
        path == "/volunteering/projects" && query("view") == "mine" -> Page.PROPOSALS to "mine"
        path == "/volunteering/projects" -> Page.PROJECTS to ""
        path == "/volunteering/project-proposals/review" -> Page.PROPOSALS to "review"
        path == "/volunteering/advances" && params.contains("new=1") -> Page.NEW_ADVANCE to ""
        path == "/volunteering/advances" -> Page.ADVANCES to ""
        path.startsWith("/volunteering/advances/") -> Page.ADVANCE to path.substringAfterLast('/')
        path == "/volunteering/expense-claim" -> Page.NEW_CLAIM to ""
        path == "/volunteering/advance-workflow" && query("advance").isNotBlank() -> Page.ADVANCE_REVIEW to query("advance")
        path == "/volunteering/advance-workflow" -> Page.ADVANCE_QUEUE to ""
        path == "/volunteering/expense-claim-workflow" && query("claim").isNotBlank() -> Page.CLAIM_REVIEW to query("claim")
        path == "/volunteering/expense-claim-workflow" -> Page.CLAIM_QUEUE to ""
        path == "/volunteering/expense-claims" && query("claim").isNotBlank() -> Page.CLAIM to query("claim")
        path == "/volunteering/expense-claims" -> Page.CLAIMS to ""
        path.startsWith("/volunteering/expense-claims/") -> Page.CLAIM to path.substringAfterLast('/')
        path == "/volunteering/profile" -> Page.PROFILE to ""
        else -> null
    }
}
