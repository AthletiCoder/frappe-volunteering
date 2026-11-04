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
import org.sevamrita.mobile.data.ChatSnapshotCache
import org.sevamrita.mobile.data.PortalSessionRequiredException
import org.sevamrita.mobile.reminders.WorkReminders
import org.sevamrita.mobile.data.PortalApiException
import org.sevamrita.mobile.data.DemoLogins
import org.sevamrita.mobile.data.SecureSessionStore
import org.sevamrita.mobile.data.Server
import org.sevamrita.mobile.data.display
import org.sevamrita.mobile.data.text
import org.sevamrita.mobile.data.items

enum class Page { HOME, WORK, PROJECTS, PROJECT, PROPOSALS, PROPOSAL, PROPOSAL_FORM, ADVANCES, ADVANCE, NEW_ADVANCE, CLAIMS, CLAIM, CORRECT_CLAIM, NEW_CLAIM, COMBINED_START, COMBINED_INVOICE, MULTI_CLAIM, MULTI_RESULT, ADVANCE_QUEUE, ADVANCE_REVIEW, CLAIM_QUEUE, CLAIM_REVIEW, RECEIPT, PROFILE, INVOICE, INVOICE_RESULT, BUDGET_HEALTH, CHART, LEDGER, ACCOUNT_FORM, OPENING_BALANCES, DONATIONS, BANK_ACCOUNT, OFFICE_ADDRESSES, OFFICE_ADDRESS_FORM, TEAM, PROJECT_MAPPING, PROJECT_MAPPING_DETAIL, CLAIM_LIMITS, FISCAL_YEARS, HR_MANAGEMENT, EMPLOYEE_FORM, SYSTEM_MANAGEMENT, USER_FORM, COLLABORATION, UNAVAILABLE }

data class PortalState(
    val signedIn: Boolean = false,
    val booting: Boolean = true,
    val busy: Boolean = false,
    val page: Page = Page.COLLABORATION,
    val server: Server = Server.PRODUCTION,
    val localAddress: String = "10.0.2.2",
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
    val proposalFilter: String = "mine",
    val ledgerFrom: String = "",
    val ledgerTo: String = "",
    val chatHome: JSONObject = JSONObject(),
    val chatRoom: JSONObject = JSONObject(),
    val chatWork: JSONObject = JSONObject(),
    val chatNavigation: ChatNavigation = ChatNavigation(),
    val trackerFilter: String = DEFAULT_TRACKER_FILTER,
    val chatLoading: Boolean = false
)

class PortalViewModel(application: Application) : AndroidViewModel(application) {
    private val api = PortalApi(SecureSessionStore(application))
    private var navigationRevision = 0
    @Volatile private var sessionGeneration = 0
    private val snapshotRevision = java.util.concurrent.atomic.AtomicLong()
    private var chatChangeVersion = 0
    private var chatRefreshing = false
    private var foregroundTasks = 0
    private val snapshots = ChatSnapshotCache(application)
    private val chatScreens = linkedMapOf<String, JSONObject>()
    var state = androidx.compose.runtime.mutableStateOf(PortalState(server = api.server(), localAddress = api.localAddress()))
        private set

    init {
        val generation = sessionGeneration
        if (!api.hasSession()) state.value = state.value.copy(booting = false)
        else runTask(showBusy = false, silent = true, onFailure = {
            state.value = state.value.copy(booting = false,
                error = if (state.value.signedIn) "" else "Unable to connect. Check the laptop Wi-Fi address and try again.")
        }) {
            val saved = snapshots.read(api.endpoint(), api.rememberedUser())
            if (generation != sessionGeneration) return@runTask
            if (saved != null) {
                synchronized(chatScreens) { saved.optJSONObject("screens")?.let { rooms -> rooms.keys().forEach { key -> chatScreens[key] = rooms.getJSONObject(key) } } }
                state.value = state.value.copy(signedIn = true, booting = false, user = api.rememberedUser(),
                    chatHome = saved.optJSONObject("home") ?: JSONObject(), chatWork = saved.optJSONObject("work") ?: JSONObject())
            }
            api.bootstrap()
            val chat = api.call(CHAT + "get_collaboration_home")
            val work = api.call(CHAT + "get_my_work")
            if (generation != sessionGeneration) return@runTask
            state.value = state.value.copy(signedIn = true, booting = false, page = Page.COLLABORATION,
                chatHome = chat, chatWork = work, user = api.currentUser)
            persistChatScreens()
            startBackgroundReminders()
            prefetchChatScreens()
        }
    }

    fun selectServer(server: Server) {
        api.setServer(server)
        state.value = state.value.copy(server = server, error = "", notice = "")
    }

    fun setLocalAddress(address: String) {
        try {
            api.setLocalAddress(address)
            state.value = state.value.copy(localAddress = api.localAddress(), error = "")
        } catch (exception: IllegalArgumentException) {
            error(exception.message ?: "Enter a private Wi-Fi IPv4 address.")
        }
    }

    fun login(username: String, password: String, localAddress: String? = null) {
        if (username.isBlank() || password.isBlank()) { error("Enter your email and password."); return }
        if (api.server() == Server.LOCAL) {
            try {
                api.setLocalAddress(localAddress.orEmpty())
                state.value = state.value.copy(localAddress = api.localAddress())
            } catch (exception: IllegalArgumentException) {
                error(exception.message ?: "Enter a private Wi-Fi IPv4 address.")
                return
            }
        }
        sessionGeneration++
        runTask(onFailure = { if (!state.value.signedIn) api.logoutLocal() }) {
            api.login(username.trim(), password)
            val chat = api.call(CHAT + "get_collaboration_home")
            val work = api.call(CHAT + "get_my_work")
            state.value = state.value.copy(signedIn = true, booting = false, home = JSONObject(),
                chatHome = chat, chatRoom = JSONObject(), chatWork = work, chatNavigation = ChatNavigation(),
                user = api.currentUser, page = Page.COLLABORATION)
            persistChatScreens()
            startBackgroundReminders()
            prefetchChatScreens()
        }
    }

    fun loginDemo(email: String, localAddress: String) {
        val password = DemoLogins.password(email, api.server())
        if (password == null) { error("Select a local demo account."); return }
        login(email, password, localAddress)
    }

    fun requestPasswordReset(email: String, address: String) {
        if (email.isBlank()) { error("Enter your email address first."); return }
        if (api.server() == Server.LOCAL) {
            try { api.setLocalAddress(address) }
            catch (exception: IllegalArgumentException) { error(exception.message.orEmpty()); return }
        }
        runTask {
            api.requestPasswordReset(email)
            state.value = state.value.copy(notice = "If this email is registered, password reset instructions will be sent to it. Check your inbox.")
        }
    }

    private fun startBackgroundReminders() {
        if (!WorkReminders.start(getApplication())) state.value = state.value.copy(
            notice = "You are signed in. Background reminders are unavailable; you can continue using chats and trackers.")
    }

    fun logout() {
        sessionGeneration++
        snapshotRevision.incrementAndGet()
        navigationRevision++
        synchronized(chatScreens) { chatScreens.clear() }
        snapshots.clear()
        WorkReminders.clear(getApplication())
        runTask {
            api.logout()
            state.value = PortalState(booting = false, server = api.server(), localAddress = api.localAddress())
        }
    }

    fun refreshHome() = runTask {
        val home = api.call(HOME, get = true)
        state.value = state.value.copy(home = home)
    }

    fun open(page: Page, id: String = "") {
        val revision = ++navigationRevision
        state.value = state.value.copy(page = page, detailId = id, error = "", notice = "", data = JSONObject(), form = JSONObject())
        if (page == Page.COLLABORATION) { refreshChat(); return }
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
            Page.MULTI_CLAIM -> "volunteering.volunteering.expense_claim_portal.get_expense_claim_form"
            Page.COMBINED_START -> "volunteering.volunteering.expense_claim_portal.get_expense_claim_form"
            Page.PROFILE -> "volunteering.volunteering.employee_profile.get_my_profile"
            Page.ADVANCE_QUEUE -> "volunteering.volunteering.advance_workflow_portal.get_advance_work_queue"
            Page.ADVANCE_REVIEW -> "volunteering.volunteering.advance_workflow_portal.get_advance_work_item"
            Page.CLAIM_QUEUE -> "volunteering.volunteering.expense_claim_workflow_portal.get_expense_claim_work_queue"
            Page.CLAIM_REVIEW -> "volunteering.volunteering.expense_claim_workflow_portal.get_expense_claim_work_item"
            Page.CHART -> "volunteering.volunteering.chart_of_accounts_portal.get_chart_of_accounts"
            Page.OPENING_BALANCES -> "volunteering.volunteering.opening_balances_portal.get_opening_balances"
            Page.DONATIONS -> "volunteering.volunteering.donation_portal.get_donation_workspace"
            Page.INVOICE -> "volunteering.volunteering.invoice_generator.get_invoice_generator_defaults"
            Page.BUDGET_HEALTH -> "volunteering.volunteering.budget_service.get_budget_health"
            Page.BANK_ACCOUNT -> "volunteering.volunteering.employee_bank_accounts.get_bank_account_workspace"
            Page.OFFICE_ADDRESSES -> "volunteering.volunteering.office_addresses.get_office_address_workspace"
            Page.TEAM -> "volunteering.volunteering.team_portal.get_team_dashboard"
            Page.PROJECT_MAPPING, Page.PROJECT_MAPPING_DETAIL -> "volunteering.volunteering.project_account_mapping.get_mapping_workspace"
            Page.CLAIM_LIMITS -> "volunteering.volunteering.expense_approval_limits_portal.get_expense_approval_limits"
            Page.FISCAL_YEARS -> "volunteering.volunteering.fiscal_year_portal.get_fiscal_year_workspace"
            Page.HR_MANAGEMENT -> "volunteering.volunteering.people_management.get_hr_management_workspace"
            Page.SYSTEM_MANAGEMENT -> "volunteering.volunteering.people_management.get_system_management_workspace"
            else -> null
        }
        if (method != null) runTask {
            if (page == Page.PROPOSAL_FORM && id.isNotBlank()) {
                val proposal = api.call("volunteering.volunteering.project_proposals.get_proposal",
                    JSONObject().put("proposal", id))
                val setupArgs = JSONObject()
                if (proposal.text("project").isNotBlank()) setupArgs.put("project", proposal.text("project"))
                val options = api.call(method, setupArgs)
                if (revision == navigationRevision) state.value = state.value.copy(form = options, data = proposal)
                return@runTask
            }
            val args = when (page) {
                Page.PROJECT -> JSONObject().put("project", id)
                Page.PROJECT_MAPPING_DETAIL -> JSONObject().put("project", id)
                Page.PROPOSAL -> JSONObject().put("proposal", id)
                Page.ADVANCE, Page.CLAIM, Page.ADVANCE_REVIEW, Page.CLAIM_REVIEW -> JSONObject().put("name", id)
                else -> JSONObject()
            }
            val data = api.call(method, args)
            if (revision != navigationRevision) return@runTask
            state.value = if (page == Page.NEW_ADVANCE || page == Page.NEW_CLAIM || page == Page.MULTI_CLAIM || page == Page.COMBINED_START || page == Page.PROPOSAL_FORM) state.value.copy(form = data)
                else state.value.copy(data = data)
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

    fun openLedger(account: String) {
        val workspace = state.value.data
        val from = workspace.text("default_from_date")
        val to = workspace.text("default_to_date")
        state.value = state.value.copy(page = Page.LEDGER, detailId = account, form = workspace,
            data = JSONObject(), ledgerFrom = from, ledgerTo = to, error = "")
        loadLedger(from, to, 1)
    }

    fun loadLedger(from: String, to: String, page: Int) = runTask {
        val account = state.value.detailId
        val result = api.call("volunteering.volunteering.chart_of_accounts_portal.get_account_ledger",
            JSONObject().put("account", account).put("from_date", from).put("to_date", to).put("page", page))
        if (state.value.page == Page.LEDGER && state.value.detailId == account)
            state.value = state.value.copy(data = result, ledgerFrom = from, ledgerTo = to)
    }

    fun openAccountForm(account: JSONObject = JSONObject(), parent: String = "") {
        val selected = JSONObject(account.toString())
        if (selected.length() == 0 && parent.isNotBlank()) selected.put("parent_account", parent)
        state.value = state.value.copy(page = Page.ACCOUNT_FORM, form = selected, error = "", notice = "")
    }

    fun saveAccount(details: JSONObject) = runTask {
        val original = state.value.form
        val args = JSONObject().put("details", details.toString())
        if (original.text("name").isNotBlank()) args.put("account", original.text("name"))
            .put("expected_modified", original.text("modified"))
        val workspace = api.call("volunteering.volunteering.chart_of_accounts_portal.save_account", args)
        state.value = state.value.copy(page = Page.CHART, data = workspace, form = JSONObject(),
            notice = "Account saved. Check the chart before posting to it.")
    }

    fun deleteAccount() = runTask {
        val account = state.value.form
        val workspace = api.call("volunteering.volunteering.chart_of_accounts_portal.delete_account",
            JSONObject().put("account", account.text("name")).put("expected_modified", account.text("modified")))
        state.value = state.value.copy(page = Page.CHART, data = workspace, form = JSONObject(), notice = "Unused account deleted.")
    }

    fun submitBankAccount(details: JSONObject) = runTask {
        api.call("volunteering.volunteering.employee_bank_accounts.submit_bank_account_request",
            JSONObject().put("details", details.toString()))
        val workspace = api.call("volunteering.volunteering.employee_bank_accounts.get_bank_account_workspace")
        state.value = state.value.copy(data = workspace, notice = "Bank details sent to Accounts for approval.")
    }

    fun reviewBankAccount(request: JSONObject, action: String, comments: String) = runTask {
        api.call("volunteering.volunteering.employee_bank_accounts.review_bank_account_request",
            JSONObject().put("request", request.text("name")).put("modified", request.text("modified"))
                .put("action", action).put("comments", comments))
        val workspace = api.call("volunteering.volunteering.employee_bank_accounts.get_bank_account_workspace")
        state.value = state.value.copy(data = workspace, notice = "Bank-account decision recorded: $action.")
    }

    fun openOfficeAddress(row: JSONObject = JSONObject()) {
        state.value = state.value.copy(page = Page.OFFICE_ADDRESS_FORM, form = JSONObject(row.toString()), error = "")
    }

    fun saveOfficeAddress(details: JSONObject) = runTask {
        val original = state.value.form
        val args = JSONObject().put("details", details.toString())
        if (original.text("name").isNotBlank()) args.put("name", original.text("name"))
            .put("expected_modified", original.text("modified"))
        val workspace = api.call("volunteering.volunteering.office_addresses.save_office_address", args)
        state.value = state.value.copy(page = Page.OFFICE_ADDRESSES, data = workspace,
            notice = "Office address saved.")
    }

    fun deleteOfficeAddress() = runTask {
        val original = state.value.form
        val workspace = api.call("volunteering.volunteering.office_addresses.delete_office_address",
            JSONObject().put("name", original.text("name"))
                .put("expected_modified", original.text("modified")))
        state.value = state.value.copy(page = Page.OFFICE_ADDRESSES, data = workspace,
            notice = "Office address deleted.")
    }

    fun setAdvanceFreeze(employee: String, frozen: Boolean, reason: String) = runTask {
        api.call("volunteering.volunteering.advance_freeze.set_advance_freeze",
            JSONObject().put("employee", employee).put("frozen", if (frozen) 1 else 0)
                .put("reason", reason))
        val dashboard = api.call("volunteering.volunteering.team_portal.get_team_dashboard")
        state.value = state.value.copy(data = dashboard,
            notice = if (frozen) "New advance requests frozen for this employee." else "Advance requests unfrozen.")
    }

    fun loadOpeningParties(partyType: String) = runTask {
        val rows = api.call("volunteering.volunteering.opening_balances_portal.get_opening_parties",
            JSONObject().put("party_type", partyType))
        state.value = state.value.copy(form = JSONObject().put("party_type", partyType)
            .put("parties", rows.optJSONArray("value") ?: JSONArray()))
    }

    fun recordOpeningBalance(details: JSONObject) = runTask {
        val result = api.call("volunteering.volunteering.opening_balances_portal.record_opening_balance",
            JSONObject().put("details", details.toString()))
        state.value = state.value.copy(data = result.optJSONObject("workspace") ?: JSONObject(),
            notice = "Opening balance posted as ${result.text("journal_entry")}.")
    }

    fun saveProjectMapping(mappings: JSONArray) = runTask {
        val project = state.value.data.optJSONObject("project") ?: JSONObject()
        val result = api.call("volunteering.volunteering.project_account_mapping.save_account_mapping",
            JSONObject().put("project", project.text("name")).put("modified", project.text("modified"))
                .put("mappings", mappings.toString()))
        val workspace = api.call("volunteering.volunteering.project_account_mapping.get_mapping_workspace",
            JSONObject().put("project", result.text("name")))
        state.value = state.value.copy(data = workspace, notice = "Suggested accounts saved for the project labels.")
    }

    fun saveClaimLimits(rows: JSONArray) = runTask {
        val result = api.call("volunteering.volunteering.expense_approval_limits_portal.save_expense_approval_limits",
            JSONObject().put("rows", rows.toString()))
        state.value = state.value.copy(data = result, notice = "Expense approval limits saved.")
    }

    fun createFiscalYear(startYear: String) = runTask {
        val result = api.call("volunteering.volunteering.fiscal_year_portal.create_fiscal_year",
            JSONObject().put("start_year", startYear))
        state.value = state.value.copy(data = result, notice = "Fiscal Year created.")
    }

    fun activateFiscalYear(name: String) = runTask {
        val result = api.call("volunteering.volunteering.fiscal_year_portal.activate_fiscal_year",
            JSONObject().put("name", name))
        state.value = state.value.copy(data = result, notice = "Fiscal Year activated.")
    }

    fun saveDonationSettings(details: JSONObject) = runTask {
        val workspace = api.call("volunteering.volunteering.donation_portal.save_donation_receipt_settings",
            JSONObject().put("details", details.toString()))
        state.value = state.value.copy(data = workspace, notice = "Receipt identity saved.")
    }

    fun saveDonationSignatory(name: String, designation: String, signature: String) = runTask {
        val workspace = api.call("volunteering.volunteering.donation_portal.save_donation_signatory",
            JSONObject().put("name", name).put("designation", designation).put("signature_data", signature))
        state.value = state.value.copy(data = workspace, notice = "Authorised signatory registered.")
    }

    fun registerDonation(details: JSONObject) = runTask {
        if (details.text("donor_signature_data").isNotBlank()) {
            val proof = api.call("volunteering.volunteering.donation_portal.bind_donation_donor_signature",
                JSONObject().put("details", details.toString()))
            details.put("donor_signature_proof", proof.text("proof"))
        }
        val result = api.call("volunteering.volunteering.donation_portal.register_donation",
            JSONObject().put("details", details.toString()))
        val workspace = api.call("volunteering.volunteering.donation_portal.get_donation_workspace")
        state.value = state.value.copy(data = workspace,
            notice = "Donation ${result.text("name")} posted${if (result.text("receipt_number").isNotBlank()) " · receipt ${result.text("receipt_number")}" else ""}.")
    }

    fun openManagedEmployee(name: String = "") {
        if (name.isBlank()) { state.value = state.value.copy(page = Page.EMPLOYEE_FORM, form = JSONObject()); return }
        runTask {
            val detail = api.call("volunteering.volunteering.people_management.get_managed_employee",
                JSONObject().put("name", name))
            state.value = state.value.copy(page = Page.EMPLOYEE_FORM, form = detail)
        }
    }

    fun saveManagedEmployee(details: JSONObject) = runTask {
        val original = state.value.form
        val args = JSONObject().put("details", details.toString())
        if (original.text("name").isNotBlank()) args.put("name", original.text("name"))
            .put("expected_modified", original.text("modified"))
        api.call("volunteering.volunteering.people_management.save_managed_employee", args)
        val workspace = api.call("volunteering.volunteering.people_management.get_hr_management_workspace")
        state.value = state.value.copy(page = Page.HR_MANAGEMENT, data = workspace, notice = "Employee saved.")
    }

    fun openManagedUser(name: String = "") {
        if (name.isBlank()) { state.value = state.value.copy(page = Page.USER_FORM, form = JSONObject()); return }
        runTask {
            val detail = api.call("volunteering.volunteering.people_management.get_managed_user",
                JSONObject().put("name", name))
            state.value = state.value.copy(page = Page.USER_FORM, form = detail)
        }
    }

    fun saveManagedUser(details: JSONObject) = runTask {
        val original = state.value.form
        val args = JSONObject().put("details", details.toString())
        if (original.text("name").isNotBlank()) args.put("name", original.text("name"))
            .put("expected_modified", original.text("modified"))
        val result = api.call("volunteering.volunteering.people_management.save_managed_user", args)
        state.value = state.value.copy(page = Page.SYSTEM_MANAGEMENT,
            data = result.optJSONObject("workspace") ?: JSONObject(), notice = "User saved.")
    }

    fun sendManagedPasswordReset(name: String) = runTask {
        api.call("volunteering.volunteering.people_management.send_managed_user_password_reset",
            JSONObject().put("name", name))
        state.value = state.value.copy(notice = "Password-reset email requested for $name.")
    }

    fun generateInvoice(details: JSONObject, format: String, generationReference: String = "") = runTask {
        val payload = JSONObject(details.toString())
        for (kind in listOf("volunteer", "vendor")) {
            if (kind == "vendor" && !payload.optBoolean("vendor_will_sign")) continue
            val proof = api.call("volunteering.volunteering.invoice_generator.bind_invoice_signature",
                JSONObject().put("payload", payload.toString()).put("kind", kind))
            payload.put("${kind}_signature_proof", proof.text("proof"))
        }
        val args = JSONObject().put("payload", payload.toString()).put("output_format", format)
        if (generationReference.isNotBlank()) args.put("generation_reference", generationReference)
        val result = api.call("volunteering.volunteering.invoice_generator.generate_invoice_documents", args)
        state.value = state.value.copy(page = Page.INVOICE_RESULT, data = result, form = details,
            notice = "Invoice ${result.text("invoice_number")} generated as ${format.uppercase()}.")
    }

    fun submitMultiClaim(details: JSONObject) = runTask {
        val result = api.call("volunteering.volunteering.expense_claim_portal.submit_multi_invoice_expense_claim",
            JSONObject().put("payload", details.toString()))
        state.value = state.value.copy(page = Page.MULTI_RESULT, data = result,
            notice = "${result.optJSONArray("claims")?.length() ?: 0} invoices submitted for review.")
    }

    fun openCombinedInvoice(claim: JSONObject) = runTask {
        val defaults = api.call("volunteering.volunteering.invoice_generator.get_invoice_generator_defaults")
        state.value = state.value.copy(page = Page.COMBINED_INVOICE, data = defaults, form = claim)
    }

    fun submitGeneratedInvoice(details: JSONObject) = runTask {
        val claim = state.value.form
        val payload = JSONObject(details.toString())
        val expense = claim.optJSONArray("expenses")?.optJSONObject(0) ?: JSONObject()
        val context = JSONObject().put("project", claim.text("project"))
            .put("reimbursement_source", claim.text("reimbursement_source"))
            .put("employee_advance", claim.text("employee_advance"))
            .put("is_emergency", claim.optBoolean("is_emergency"))
            .put("emergency_date", claim.text("emergency_date"))
            .put("emergency_reason", claim.text("emergency_reason"))
            .put("expense", JSONObject().put("expense_date", expense.text("expense_date"))
                .put("account", expense.text("account")).put("description", expense.text("description"))
                .put("amount", expense.optDouble("amount")))
        payload.put("signature_context", context)
        for (kind in listOf("volunteer", "vendor")) {
            if (kind == "vendor" && !payload.optBoolean("vendor_will_sign")) continue
            val proof = api.call("volunteering.volunteering.invoice_generator.bind_invoice_signature",
                JSONObject().put("payload", payload.toString()).put("kind", kind))
            payload.put("${kind}_signature_proof", proof.text("proof"))
        }
        val result = api.call("volunteering.volunteering.expense_claim_portal.submit_generated_invoice_expense_claim",
            JSONObject().put("claim_payload", claim.toString()).put("invoice_payload", payload.toString()))
        val name = result.text("name")
        val detail = api.call("volunteering.volunteering.expense_claim_portal.get_my_expense_claim",
            JSONObject().put("name", name))
        state.value = state.value.copy(page = Page.CLAIM, detailId = name, data = detail,
            notice = "Signed invoice ${result.text("generated_invoice_number")} attached and claim submitted for review.")
    }

    fun startCorrection() {
        if (state.value.data.optBoolean("can_correct")) state.value = state.value.copy(page = Page.CORRECT_CLAIM)
    }

    fun resubmitCorrection(details: JSONObject) = runTask {
        val name = state.value.detailId
        api.call("volunteering.volunteering.expense_claim_portal.resubmit_expense_claim",
            JSONObject().put("name", name).put("payload", details.toString()))
        val claim = api.call("volunteering.volunteering.expense_claim_portal.get_my_expense_claim",
            JSONObject().put("name", name))
        state.value = state.value.copy(page = Page.CLAIM, data = claim,
            notice = "Corrections to $name were submitted for receipt review.")
    }

    fun previewGeneratedInvoice() {
        val pdf = state.value.data.optJSONObject("pdf") ?: return
        val encoded = pdf.text("content_base64")
        val bytes = android.util.Base64.decode(encoded, android.util.Base64.DEFAULT)
        state.value = state.value.copy(page = Page.RECEIPT, receiptBytes = bytes,
            receiptName = pdf.display("filename"), receiptReturn = Page.INVOICE_RESULT)
    }

    fun saveProposal(data: JSONObject, approver: String, submitNow: Boolean, reason: String = "") = runTask {
        val current = state.value.data
        val args = JSONObject().put("data", data.toString()).put("assigned_approver", approver)
        if (current.text("project").isNotBlank()) args.put("project", current.text("project"))
        if (reason.isNotBlank() || current.text("request_reason").isNotBlank()) args.put("reason", reason.ifBlank { current.text("request_reason") })
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

    fun openChangeRequest() {
        val project = state.value.data
        val projectId = project.text("name")
        if (projectId.isBlank()) return
        val baseline = JSONObject(project.toString())
        runTask {
            val options = api.call("volunteering.volunteering.project_workspace.get_setup_options",
                JSONObject().put("project", projectId))
            state.value = state.value.copy(page = Page.PROPOSAL_FORM, detailId = "", form = options,
                data = JSONObject().put("project", projectId).put("request_kind", "Project Change")
                    .put("can_view_financials", project.optJSONObject("capabilities")?.optBoolean("can_view_financials") ?: false)
                    .put("data", baseline))
        }
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

    fun uploadProposalDocument(filename: String, content: String, visibility: String) = runTask {
        val proposal = state.value.data
        val updated = api.call("volunteering.volunteering.project_proposals.upload_proposal_document",
            JSONObject().put("proposal", proposal.text("name")).put("modified", proposal.text("modified"))
                .put("filename", filename).put("content", content).put("visibility", visibility))
        state.value = state.value.copy(data = updated, notice = "Supporting document added as $visibility.")
    }

    fun projectAccounts(project: String) {
        if (project.isBlank()) return
        val revision = navigationRevision
        runTask {
            val accounts = api.call(
                "volunteering.volunteering.expense_claim_portal.get_project_accounts",
                JSONObject().put("project", project)
            )
            if (revision == navigationRevision && state.value.page in listOf(Page.NEW_CLAIM, Page.MULTI_CLAIM, Page.COMBINED_START)) {
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

    fun disburseAdvance(payment: JSONObject) = runTask {
        api.call("volunteering.volunteering.advance_workflow_portal.disburse_advance",
            JSONObject().put("name", state.value.detailId).put("payment", payment.toString()))
        val queue = api.call("volunteering.volunteering.advance_workflow_portal.get_advance_work_queue")
        val home = api.call(HOME, get = true)
        state.value = state.value.copy(page = Page.ADVANCE_QUEUE, data = queue, home = home,
            notice = "Advance disbursement posted.")
    }

    fun recordAdvanceReturn(details: JSONObject) = runTask {
        api.call("volunteering.volunteering.advance_workflow_portal.record_advance_return",
            JSONObject().put("name", state.value.detailId).put("details", details.toString()))
        val queue = api.call("volunteering.volunteering.advance_workflow_portal.get_advance_work_queue")
        val home = api.call(HOME, get = true)
        state.value = state.value.copy(page = Page.ADVANCE_QUEUE, data = queue, home = home,
            notice = "Unused advance return posted.")
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

    fun classifyClaim(allocations: JSONArray, note: String) = runTask {
        api.call("volunteering.volunteering.expense_claim_workflow_portal.classify_expense_claim_accounts",
            JSONObject().put("name", state.value.detailId).put("allocations", allocations.toString()).put("note", note))
        val queue = api.call("volunteering.volunteering.expense_claim_workflow_portal.get_expense_claim_work_queue")
        val home = api.call(HOME, get = true)
        state.value = state.value.copy(page = Page.CLAIM_QUEUE, data = queue, home = home,
            notice = "Expense accounts classified and claim posted.")
    }

    fun reimburseClaim(payment: JSONObject) = runTask {
        api.call("volunteering.volunteering.expense_claim_workflow_portal.reimburse_expense_claim",
            JSONObject().put("name", state.value.detailId).put("payment", payment.toString()))
        val queue = api.call("volunteering.volunteering.expense_claim_workflow_portal.get_expense_claim_work_queue")
        val home = api.call(HOME, get = true)
        state.value = state.value.copy(page = Page.CLAIM_QUEUE, data = queue, home = home,
            notice = "Reimbursement Payment Entry posted.")
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

    private fun screenKey(route: ChatRoute) = if (route.item.isNotBlank()) "item:${route.item}" else "room:${route.room}"

    private fun persistChatScreens() {
        val current = state.value
        if (!current.signedIn) return
        val screens = JSONObject()
        synchronized(chatScreens) { chatScreens.entries.toList().takeLast(25).forEach { (key, value) -> screens.put(key, value) } }
        val generation = sessionGeneration
        val revision = snapshotRevision.incrementAndGet()
        val endpoint = api.endpoint()
        val snapshot = JSONObject().put("home", current.chatHome).put("work", current.chatWork).put("screens", screens)
        viewModelScope.launch(Dispatchers.IO) {
            snapshots.write(endpoint, current.user, snapshot) { generation == sessionGeneration && revision == snapshotRevision.get() }
        }
    }

    private fun seedChatScreen(route: ChatRoute): JSONObject {
        synchronized(chatScreens) { chatScreens[screenKey(route)]?.let { return it } }
        val room = synchronized(chatScreens) { chatScreens["room:${route.room}"] }
        if (route.item.isBlank() && room != null) return room
        val work = (state.value.chatWork.items("trackers") + state.value.chatWork.items("open_progress") + state.value.chatWork.items("calendar"))
        val item = room?.items("items")?.firstOrNull { it.text("name") == route.item } ?: work.firstOrNull { it.text("name") == route.item }
        if (route.item.isNotBlank() && item != null) {
            val member = state.value.chatHome.items("spaces").firstOrNull { it.text("name") == route.room }
            val meta = member ?: JSONObject().put("name", route.room).put("title", item.text("space_title"))
                .put("access_level", "SharedView").put("can_post", false).put("members", JSONArray()).put("item_only", true)
            return JSONObject().put("space", meta).put("items", JSONArray().put(item)).put("entries", JSONArray())
        }
        return JSONObject().put("space", JSONObject().put("name", route.room))
    }

    private fun prefetchChatScreens() {
        val generation = sessionGeneration
        val rooms = state.value.chatHome.items("spaces").filterNot { it.optBoolean("archived") }.take(8)
        runTask(showBusy = false, silent = true) {
            fetchChatPreviews(rooms, generation)
            if (generation == sessionGeneration) persistChatScreens()
        }
    }

    private fun fetchChatPreviews(rooms: List<JSONObject>, generation: Int) {
        for (room in rooms) {
            if (generation != sessionGeneration) return
            val version = chatChangeVersion
            val name = room.text("name")
            val data = api.call(CHAT + "get_space", JSONObject().put("name", name))
            if (generation != sessionGeneration || version != chatChangeVersion) return
            synchronized(chatScreens) { chatScreens["room:$name"] = data }
            acknowledgeDelivery(name, data)
        }
    }

    private fun acknowledgeDelivery(name: String, room: JSONObject) {
        if (!room.has("delivered_through")) return
        val latest = room.items("entries").lastOrNull() ?: return
        if (latest.text("creation") > room.text("delivered_through")) {
            api.call(CHAT + "mark_delivered", JSONObject().put("space", name).put("entry", latest.text("name")))
        }
    }

    fun refreshChat() {
        if (chatRefreshing || !state.value.signedIn) return
        chatRefreshing = true
        val generation = sessionGeneration
        val version = chatChangeVersion
        runTask(showBusy = false, silent = true, onFailure = { chatRefreshing = false }) {
            try {
                val home = api.call(CHAT + "get_collaboration_home")
                val work = api.call(CHAT + "get_my_work")
                if (generation != sessionGeneration || version != chatChangeVersion) return@runTask
                val workChanged = work.toString() != state.value.chatWork.toString()
                if (state.value.page == Page.COLLABORATION) state.value = state.value.copy(chatHome = home, chatWork = work)
                if (workChanged) WorkReminders.requestSync(getApplication())
                // Drop snapshots whose chat membership or individual share is no longer present.
                val allowedRooms = home.items("spaces").map { it.text("name") }.toSet()
                val allowedItems = (work.items("trackers") + work.items("open_progress") + work.items("calendar")).map { it.text("name") }.toSet()
                synchronized(chatScreens) { chatScreens.entries.removeAll { (key, value) ->
                    value.optJSONObject("space")?.text("name") !in allowedRooms && (key.startsWith("room:") || key.removePrefix("item:") !in allowedItems)
                } }
                val name = state.value.chatNavigation.current.room
                if (name.isNotBlank() && state.value.page == Page.COLLABORATION) reloadChatRoom(name)
                fetchChatPreviews(home.items("spaces").filter {
                    it.text("name") != name && it.optBoolean("delivery_pending")
                }.take(8), generation)
                persistChatScreens()
            } finally {
                chatRefreshing = false
                if (generation == sessionGeneration && version != chatChangeVersion) withContext(Dispatchers.Main) { refreshChat() }
            }
        }
    }

    private fun reloadChatRoom(name: String) {
        val route = state.value.chatNavigation.current
        val generation = sessionGeneration
        val version = chatChangeVersion
        val args = JSONObject().put("name", name)
        val detail = route.view in listOf(ChatView.TRACKER, ChatView.TASK) && route.room == name
        val room = if (detail) api.call(CHAT + "get_work_item", JSONObject().put("name", route.item)) else api.call(CHAT + "get_space", args)
        if (generation != sessionGeneration || version != chatChangeVersion || state.value.page != Page.COLLABORATION || state.value.chatNavigation.current != route || state.value.chatRoom.optJSONObject("space")?.text("name") != name) return
        val current = state.value.chatRoom
        if (!detail && current.items("entries").isNotEmpty()) {
            val incoming = room.items("entries")
            val cached = current.items("entries")
            val entries = (cached + incoming).associateBy { it.text("name") }.values
                .sortedWith(compareBy({ it.text("creation") }, { it.text("name") }))
            room.put("entries", JSONArray(entries))
            if (entries.firstOrNull()?.text("name") != incoming.firstOrNull()?.text("name"))
                room.put("older_cursor", current.opt("older_cursor"))
        }
        synchronized(chatScreens) { chatScreens[screenKey(route)] = room }
        state.value = state.value.copy(chatRoom = room, chatLoading = false)
        persistChatScreens()
        if (!detail) acknowledgeDelivery(name, room)
    }

    fun markChatSeen(name: String, entry: JSONObject) = runTask(showBusy = false, silent = true) {
        val route = ChatRoute(ChatView.CHAT, name)
        val generation = sessionGeneration
        val stamp = entry.text("creation")
        if (state.value.chatNavigation.current != route || stamp <= state.value.chatRoom.text("seen_through")) return@runTask
        api.call(CHAT + "mark_seen", JSONObject().put("space", name).put("entry", entry.text("name")))
        withContext(Dispatchers.Main) {
            val current = state.value
            if (sessionGeneration == generation && current.chatNavigation.current == route && stamp > current.chatRoom.text("seen_through")) {
                val room = JSONObject(current.chatRoom.toString()).put("seen_through", stamp)
                state.value = current.copy(chatRoom = room)
            }
        }
    }

    fun openChatRoom(name: String) {
        moveChat(state.value.chatNavigation.navigate(ChatRoute(ChatView.CHAT, name)))
    }

    fun closeChatRoom() { showChatConversations() }

    fun showChatConversations() = moveChat(state.value.chatNavigation.navigate(ChatRoute()))
    fun showPersonalTasks() = moveChat(state.value.chatNavigation.navigate(ChatRoute(ChatView.MY_TASKS)))
    fun showPersonalTrackers() = moveChat(state.value.chatNavigation.navigate(ChatRoute(ChatView.MY_TRACKERS)))
    fun showRoomTrackers() {
        val room = state.value.chatNavigation.current.room
        if (room.isNotBlank()) openTrackers(room)
    }
    fun openTrackers(room: String) = moveChat(state.value.chatNavigation.navigate(ChatRoute(ChatView.TRACKERS, room)))
    fun openTracker(room: String, item: String) = moveChat(state.value.chatNavigation.navigate(ChatRoute(ChatView.TRACKER, room, item)))
    fun openTask(room: String, item: String) = moveChat(state.value.chatNavigation.navigate(ChatRoute(ChatView.TASK, room, item)))
    fun setTrackerFilter(filter: String) {
        if (filter in TRACKER_FILTERS) state.value = state.value.copy(trackerFilter = filter)
    }
    fun showRoomTasks() {
        val room = state.value.chatNavigation.current.room
        if (room.isNotBlank()) moveChat(state.value.chatNavigation.navigate(ChatRoute(ChatView.TASKS, room)))
    }

    fun backInChat(): Boolean {
        if (state.value.page == Page.RECEIPT) { closeReceipt(); return true }
        val navigation = state.value.chatNavigation
        if (!navigation.canGoBack) return false
        moveChat(navigation.back())
        return true
    }

    private fun moveChat(navigation: ChatNavigation) {
        val previousRoute = state.value.chatNavigation.current
        val room = navigation.current.room
        navigationRevision++
        val seeded = if (room.isBlank()) JSONObject() else seedChatScreen(navigation.current)
        state.value = state.value.copy(page = Page.COLLABORATION, chatNavigation = navigation,
            error = "", notice = "", chatRoom = seeded, chatLoading = room.isNotBlank() && seeded.optJSONObject("space")?.has("access_level") != true)
        if (room.isNotBlank() && previousRoute != navigation.current) runTask(showBusy = false) { reloadChatRoom(room) }
    }

    fun olderChatMessages() = runTask {
        val current = state.value.chatRoom
        val name = current.optJSONObject("space")?.text("name").orEmpty()
        val cursor = current.text("older_cursor")
        if (name.isBlank() || cursor.isBlank()) return@runTask
        val older = api.call(CHAT + "get_space", JSONObject().put("name", name).put("before", cursor))
        if (state.value.page == Page.COLLABORATION && state.value.chatRoom.optJSONObject("space")?.text("name") == name) {
            state.value = state.value.copy(chatRoom = JSONObject(current.toString()).put("entries", JSONArray(older.items("entries") + current.items("entries"))).put("older_cursor", older.opt("older_cursor")))
        }
    }

    private fun applyChatItem(item: JSONObject) {
        if (item.text("item_kind") !in listOf("Task", "Tracker")) return
        val id = item.text("name")
        // Mutation responses contain the item only. Keep its chat heading while the feed refreshes.
        if (item.text("space_title").isBlank()) {
            val title = state.value.chatHome.items("spaces").firstOrNull { it.text("name") == item.text("space") }?.text("title")
                ?: (state.value.chatWork.items("trackers") + state.value.chatWork.items("open_progress"))
                    .firstOrNull { it.text("name") == id }?.text("space_title")
            if (!title.isNullOrBlank()) item.put("space_title", title)
        }
        val open = item.text("status") in listOf("Open", "In progress")
        fun replace(json: JSONObject, field: String, add: Boolean, keep: Boolean = true): JSONObject {
            val rows = json.items(field)
            val index = rows.indexOfFirst { it.text("name") == id }
            val updated = rows.filter { it.text("name") != id }.toMutableList()
            if (keep && (index >= 0 || add)) updated.add(if (index >= 0) minOf(index, updated.size) else 0, item)
            return JSONObject(json.toString()).put(field, JSONArray(updated))
        }
        val mine = item.text("owner") == state.value.user || item.text("assignee") == state.value.user || item.optBoolean("shared_with_me") ||
            item.optJSONObject("item_data")?.items("stages")?.any { it.text("assignee") == state.value.user } == true
        var work = state.value.chatWork
        work = replace(work, "trackers", mine && item.text("item_kind") == "Tracker", item.text("item_kind") == "Tracker")
        work = replace(work, "open_progress", mine && open, open)
        work = replace(work, "today", false, open)
        synchronized(chatScreens) { chatScreens.keys.toList().forEach { key ->
            val cached = chatScreens.getValue(key)
            if (cached.optJSONObject("space")?.text("name") == item.text("space")) chatScreens[key] = replace(cached, "items", key.startsWith("room:"))
        } }
        val route = state.value.chatNavigation.current
        val room = if (route.room == item.text("space")) replace(state.value.chatRoom, "items", route.item.isBlank() || route.item == id) else state.value.chatRoom
        state.value = state.value.copy(chatWork = work, chatRoom = room)
        persistChatScreens()
    }

    fun chatCall(method: String, args: JSONObject = JSONObject(), success: (JSONObject) -> Unit = {}) {
        val generation = sessionGeneration
        val changed = !method.startsWith("get_")
        runTask(showBusy = changed) {
            val result = api.call(CHAT + method, args)
            if (generation != sessionGeneration) return@runTask
            withContext(Dispatchers.Main) {
                if (changed) { chatChangeVersion++; applyChatItem(result) }
                success(result)
            }
            if (changed) {
                WorkReminders.requestSync(getApplication())
                refreshChat()
            }
        }
    }

    private fun runTask(onFailure: (() -> Unit)? = null, showBusy: Boolean = true, silent: Boolean = false, action: suspend () -> Unit) {
        val generation = sessionGeneration
        viewModelScope.launch {
            if (showBusy) { foregroundTasks++; state.value = state.value.copy(busy = true, error = "") }
            try { withContext(Dispatchers.IO) { action() } }
            catch (exception: Exception) {
                if (exception is kotlinx.coroutines.CancellationException) throw exception
                if (generation != sessionGeneration) return@launch
                onFailure?.invoke()
                if (exception is PortalSessionRequiredException) {
                    sessionGeneration++
                    snapshotRevision.incrementAndGet()
                    WorkReminders.clear(getApplication())
                    api.logoutLocal()
                    synchronized(chatScreens) { chatScreens.clear() }; snapshots.clear()
                    state.value = PortalState(booting = false, server = api.server(), localAddress = api.localAddress(), error = exception.message.orEmpty())
                    return@launch
                }
                if (exception is PortalApiException && exception.status == 403 && state.value.page == Page.COLLABORATION) {
                    snapshotRevision.incrementAndGet()
                    synchronized(chatScreens) { chatScreens.clear() }; snapshots.clear()
                    state.value = state.value.copy(chatHome = JSONObject(), chatRoom = JSONObject(), chatWork = JSONObject())
                }
                state.value = state.value.copy(chatLoading = false)
                if (!silent) state.value = state.value.copy(error = exception.message ?: "Something went wrong.", booting = false)
            }
            finally { if (showBusy) { foregroundTasks = (foregroundTasks - 1).coerceAtLeast(0); state.value = state.value.copy(busy = foregroundTasks > 0) } }
        }
    }

    companion object {
        private const val HOME = "volunteering.volunteering.home_service.get_home_payload"
        private const val CHAT = "volunteering.volunteering.collaboration_mobile."
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
        path == "/volunteering/collaboration" -> Page.COLLABORATION to query("view")
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
        path == "/volunteering/expense-claim/multiple" -> Page.MULTI_CLAIM to ""
        path == "/volunteering/invoice-expense-claim" -> Page.COMBINED_START to ""
        path == "/volunteering/advance-workflow" && query("advance").isNotBlank() -> Page.ADVANCE_REVIEW to query("advance")
        path == "/volunteering/advance-workflow" -> Page.ADVANCE_QUEUE to ""
        path == "/volunteering/expense-claim-workflow" && query("claim").isNotBlank() -> Page.CLAIM_REVIEW to query("claim")
        path == "/volunteering/expense-claim-workflow" -> Page.CLAIM_QUEUE to ""
        path == "/volunteering/expense-claims" && query("claim").isNotBlank() -> Page.CLAIM to query("claim")
        path == "/volunteering/expense-claims" -> Page.CLAIMS to ""
        path.startsWith("/volunteering/expense-claims/") -> Page.CLAIM to path.substringAfterLast('/')
        path == "/volunteering/profile" -> Page.PROFILE to ""
        path == "/volunteering/chart-of-accounts" -> Page.CHART to ""
        path == "/volunteering/opening-balances" -> Page.OPENING_BALANCES to ""
        path == "/volunteering/donations" -> Page.DONATIONS to ""
        path == "/volunteering/invoice-generator" -> Page.INVOICE to ""
        path == "/volunteering/budget-health" -> Page.BUDGET_HEALTH to ""
        path == "/volunteering/project-account-mapping" -> Page.PROJECT_MAPPING to ""
        path == "/volunteering/expense-approval-limits" -> Page.CLAIM_LIMITS to ""
        path == "/volunteering/fiscal-years" -> Page.FISCAL_YEARS to ""
        path == "/volunteering/hr-management" -> Page.HR_MANAGEMENT to ""
        path == "/volunteering/system-management" -> Page.SYSTEM_MANAGEMENT to ""
        path == "/volunteering/bank-account" -> Page.BANK_ACCOUNT to ""
        path == "/volunteering/office-addresses" -> Page.OFFICE_ADDRESSES to ""
        path == "/volunteering/team" -> Page.TEAM to ""
        else -> null
    }
}
