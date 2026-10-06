package org.sevamrita.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Assignment
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.ReceiptLong
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Wallet
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Divider
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import org.json.JSONObject
import org.sevamrita.mobile.data.Server
import org.sevamrita.mobile.data.display
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text
import org.sevamrita.mobile.ui.AdvanceRequestScreen
import org.sevamrita.mobile.ui.ExpenseRequestScreen
import org.sevamrita.mobile.ui.AdvanceQueueScreen
import org.sevamrita.mobile.ui.AdvanceReviewScreen
import org.sevamrita.mobile.ui.ClaimQueueScreen
import org.sevamrita.mobile.ui.ClaimReviewScreen
import org.sevamrita.mobile.ui.ReceiptScreen
import org.sevamrita.mobile.ui.ProposalsScreen
import org.sevamrita.mobile.ui.ProposalScreen
import org.sevamrita.mobile.ui.ProposalFormScreen
import org.sevamrita.mobile.ui.Page
import org.sevamrita.mobile.ui.PortalState
import org.sevamrita.mobile.ui.PortalViewModel

private val green = Color(0xFF08745E)
private val ink = Color(0xFF1D3035)
private val muted = Color(0xFF637378)
private val canvas = Color(0xFFF5F7F4)
private val pale = Color(0xFFE5F3ED)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = lightColorScheme(
                primary = green, onPrimary = Color.White, background = canvas,
                onBackground = ink, surface = Color.White, onSurface = ink,
                secondaryContainer = pale, onSecondaryContainer = ink
            )) {
                val model: PortalViewModel = viewModel()
                PortalApp(model)
            }
        }
    }
}

@Composable
private fun PortalApp(model: PortalViewModel) {
    val state = model.state.value
    if (state.booting) {
        Box(Modifier.fillMaxSize().background(canvas), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }
        return
    }
    if (!state.signedIn) { LoginScreen(state, model); return }
    Scaffold(
        containerColor = canvas,
        topBar = {
            Column {
                Row(
                    Modifier.fillMaxWidth().background(Color.White).padding(horizontal = 16.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    if (state.page !in listOf(Page.HOME, Page.WORK, Page.PROJECTS, Page.ADVANCES, Page.CLAIMS, Page.PROFILE)) {
                        IconButton(onClick = { if (state.page == Page.RECEIPT) model.closeReceipt() else model.open(parentOf(state.page)) }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                        }
                    }
                    Column(Modifier.weight(1f)) {
                        Text("SEVAMRITA", color = green, fontWeight = FontWeight.Bold, fontSize = 12.sp, letterSpacing = 2.sp)
                        Text(pageTitle(state), fontWeight = FontWeight.SemiBold, fontSize = 21.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    }
                    if (state.page == Page.HOME) IconButton(onClick = { model.refreshHome() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh Home", tint = green)
                    }
                }
                if (state.busy) androidx.compose.material3.LinearProgressIndicator(Modifier.fillMaxWidth())
            }
        },
        bottomBar = {
            NavigationBar(containerColor = Color.White) {
                val entries = listOf(
                    Triple(Page.HOME, "Home", Icons.Default.Home),
                    Triple(Page.WORK, "My work", Icons.Default.Assignment),
                    Triple(Page.PROJECTS, "Projects", Icons.Default.Folder),
                    Triple(Page.CLAIMS, "Expenses", Icons.Default.ReceiptLong),
                    Triple(Page.PROFILE, "Profile", Icons.Default.AccountCircle)
                )
                for ((page, label, icon) in entries) NavigationBarItem(
                    selected = state.page == page,
                    onClick = { if (page == Page.HOME) model.open(page).also { model.refreshHome() } else model.open(page) },
                    icon = { Icon(icon, contentDescription = null) },
                    label = { Text(label, fontSize = 10.sp) }
                )
            }
        }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            if (state.error.isNotBlank()) MessageBar(state.error, isError = true, onDismiss = model::dismissMessage)
            if (state.notice.isNotBlank()) MessageBar(state.notice, isError = false, onDismiss = model::dismissMessage)
            when (state.page) {
                Page.HOME -> HomeScreen(state, model)
                Page.WORK -> WorkScreen(state, model)
                Page.PROJECTS -> ProjectsScreen(state, model)
                Page.PROJECT -> ProjectScreen(state, model)
                Page.PROPOSALS -> ProposalsScreen(state, model)
                Page.PROPOSAL -> ProposalScreen(state, model)
                Page.PROPOSAL_FORM -> ProposalFormScreen(state, model)
                Page.ADVANCES -> AdvancesScreen(state, model)
                Page.ADVANCE -> AdvanceScreen(state)
                Page.NEW_ADVANCE -> AdvanceRequestScreen(state.form, state.detailId, state.busy, model::submitAdvance)
                Page.CLAIMS -> ClaimsScreen(state, model)
                Page.CLAIM -> ClaimScreen(state)
                Page.NEW_CLAIM -> ExpenseRequestScreen(state.form, state.data, state.detailId, state.busy, model::projectAccounts, model::submitClaim)
                Page.ADVANCE_QUEUE -> AdvanceQueueScreen(state, model)
                Page.ADVANCE_REVIEW -> AdvanceReviewScreen(state, model)
                Page.CLAIM_QUEUE -> ClaimQueueScreen(state, model)
                Page.CLAIM_REVIEW -> ClaimReviewScreen(state, model)
                Page.RECEIPT -> ReceiptScreen(state)
                Page.PROFILE -> ProfileScreen(state, model)
                Page.UNAVAILABLE -> UnavailableScreen(state)
            }
        }
    }
}

private fun pageTitle(state: PortalState) = when (state.page) {
    Page.HOME -> "Home"; Page.WORK -> "My work"; Page.PROJECTS -> "Projects"
    Page.PROJECT -> state.detailId; Page.ADVANCES -> "Advances"; Page.ADVANCE -> state.detailId
    Page.PROPOSALS -> "Project proposals"; Page.PROPOSAL -> state.detailId; Page.PROPOSAL_FORM -> "Project proposal"
    Page.NEW_ADVANCE -> "Request an advance"; Page.CLAIMS -> "Expense claims"; Page.CLAIM -> state.detailId
    Page.NEW_CLAIM -> "Submit an expense"; Page.PROFILE -> "My profile"; Page.UNAVAILABLE -> state.unavailableLabel
    Page.ADVANCE_QUEUE -> "Advance approvals"; Page.ADVANCE_REVIEW -> state.detailId
    Page.CLAIM_QUEUE -> "Expense review"; Page.CLAIM_REVIEW -> state.detailId
    Page.RECEIPT -> state.receiptName
}
private fun parentOf(page: Page) = when (page) {
    Page.PROJECT -> Page.PROJECTS; Page.ADVANCE, Page.NEW_ADVANCE -> Page.ADVANCES
    Page.PROPOSAL, Page.PROPOSAL_FORM -> Page.PROPOSALS
    Page.CLAIM, Page.NEW_CLAIM -> Page.CLAIMS; else -> Page.HOME
}

@Composable
private fun LoginScreen(state: PortalState, model: PortalViewModel) {
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var expanded by remember { mutableStateOf(false) }
    LazyColumn(
        Modifier.fillMaxSize().background(canvas), contentPadding = PaddingValues(24.dp),
        verticalArrangement = Arrangement.Center
    ) {
        item {
            Surface(color = green, shape = RoundedCornerShape(18.dp), modifier = Modifier.size(58.dp)) {
                Box(contentAlignment = Alignment.Center) { Text("S", fontSize = 30.sp, color = Color.White, fontWeight = FontWeight.Bold) }
            }
            Spacer(Modifier.height(22.dp))
            Text("Sevamrita", fontSize = 34.sp, fontWeight = FontWeight.Bold, color = ink)
            Text("Your projects, expenses and advances in one place.", color = muted, fontSize = 16.sp)
            Spacer(Modifier.height(30.dp))
            SectionCard {
                Text("Sign in", fontWeight = FontWeight.SemiBold, fontSize = 21.sp)
                Spacer(Modifier.height(16.dp))
                Box {
                    OutlinedButton(onClick = { expanded = true }, modifier = Modifier.fillMaxWidth()) { Text("Server: ${state.server.label}") }
                    DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                        Server.available().forEach { server ->
                            DropdownMenuItem(text = { Text(server.label) }, onClick = { expanded = false; model.selectServer(server) })
                        }
                    }
                }
                OutlinedTextField(username, { username = it }, label = { Text("Email or username") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(password, { password = it }, label = { Text("Password") }, singleLine = true,
                    visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(10.dp))
                Button(onClick = { model.login(username, password) }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) {
                    Text(if (state.busy) "Signing in…" else "Sign in")
                }
            }
            if (state.error.isNotBlank()) {
                Spacer(Modifier.height(12.dp))
                Text(state.error, color = MaterialTheme.colorScheme.error)
            }
            Spacer(Modifier.height(16.dp))
            Text("This is a native app. Your account and permissions are the same as the Sevamrita portal.", color = muted, fontSize = 13.sp)
        }
    }
}

@Composable
private fun HomeScreen(state: PortalState, model: PortalViewModel) {
    val home = state.home
    val projects = home.items("member_projects")
    val actions = home.optJSONObject("actions") ?: JSONObject()
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        if (projects.isNotEmpty()) {
            item { Heading("Your active projects", "Choose the project before starting work") }
            items(projects) { project ->
                SectionCard {
                    Text(project.display("project_name"), fontWeight = FontWeight.Bold, fontSize = 19.sp)
                    Text(project.display("name"), color = muted, fontSize = 12.sp)
                    if (project.text("purpose").isNotBlank()) Text(project.text("purpose"), color = muted)
                    Spacer(Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        SmallAction("Expense", Modifier.weight(1f), enabled = project.optBoolean("can_submit_expense")) { model.open(Page.NEW_CLAIM, project.text("name")) }
                        SmallAction("Advance", Modifier.weight(1f)) { model.open(Page.NEW_ADVANCE, project.text("name")) }
                    }
                    TextButton(onClick = { model.open(Page.PROJECT, project.text("name")) }) { Text("View project →") }
                }
            }
        } else item {
            Heading("Welcome, ${home.display("full_name", "there")}", "Your Sevamrita workspace")
        }
        if (home.items("waiting").isNotEmpty()) {
            item { Heading("Waiting on you") }
            items(home.items("waiting").take(5)) { row -> ActionRow(row.display("title"), row.text("subtitle")) {
                model.openAction(row.display("title"), row.text("route"))
            } }
        }
        if (home.items("resume").isNotEmpty()) {
            item { Heading("Pick up where you left off") }
            items(home.items("resume").take(4)) { row -> ActionRow(row.display("title"), row.text("subtitle")) {
                model.openAction(row.display("title"), row.text("route"))
            } }
        }
        item { Heading("Explore", "Only the actions available to your account are shown") }
        val sections = listOf("projects" to "Projects", "money" to "Money", "accounts" to "Accounts", "team" to "Team", "time" to "Time & leave", "hr_management" to "HR", "system_management" to "System", "organisation" to "Organisation")
        sections.forEach { (key, label) ->
            val rows = actions.items(key).filterNot { it.text("route").startsWith("/desk/") }
            if (rows.isNotEmpty()) {
                item { Text(label.uppercase(), color = green, fontWeight = FontWeight.Bold, fontSize = 12.sp, letterSpacing = 1.sp) }
                items(rows) { row -> ActionRow(row.display("label"), row.text("hint")) { model.openAction(row.display("label"), row.text("route")) } }
            }
        }
        item { Spacer(Modifier.height(8.dp)) }
    }
}

@Composable
private fun WorkScreen(state: PortalState, model: PortalViewModel) {
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Heading("Your work", "Approvals, follow-ups and drafts") }
        item { Text("WAITING ON YOU", color = green, fontSize = 12.sp, fontWeight = FontWeight.Bold) }
        if (state.home.items("waiting").isEmpty()) item { EmptyState("Nothing waiting right now") }
        items(state.home.items("waiting")) { row -> ActionRow(row.display("title"), row.text("subtitle")) { model.openAction(row.display("title"), row.text("route")) } }
        item { Text("YOUR DRAFTS", color = green, fontSize = 12.sp, fontWeight = FontWeight.Bold) }
        if (state.home.items("resume").isEmpty()) item { EmptyState("No drafts to resume") }
        items(state.home.items("resume")) { row -> ActionRow(row.display("title"), row.text("subtitle")) { model.openAction(row.display("title"), row.text("route")) } }
    }
}

@Composable
private fun ProjectsScreen(state: PortalState, model: PortalViewModel) {
    val projects = state.data.items("projects")
    val capabilities = state.data.optJSONObject("capabilities") ?: JSONObject()
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Heading("Approved projects", "Projects you are permitted to view") }
        if (capabilities.optBoolean("can_create")) item {
            Button(onClick = { model.open(Page.PROPOSAL_FORM) }, modifier = Modifier.fillMaxWidth()) { Text("Propose a project") }
        }
        if (capabilities.optBoolean("can_create")) item {
            OutlinedButton(onClick = { model.openProposals("mine") }, modifier = Modifier.fillMaxWidth()) { Text("Your proposals and change requests") }
        }
        if (capabilities.optBoolean("can_manage")) item {
            OutlinedButton(onClick = { model.openProposals("review") }, modifier = Modifier.fillMaxWidth()) { Text("Review pending proposals") }
        }
        if (projects.isEmpty() && !state.busy) item { EmptyState("No approved projects available") }
        items(projects) { project -> ActionRow(project.display("project_name"), "${project.display("name")} · ${project.display("operational_status")}") {
            model.open(Page.PROJECT, project.text("name"))
        } }
    }
}

@Composable
private fun ProjectScreen(state: PortalState, model: PortalViewModel) {
    val project = state.data
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading(project.display("project_name", state.detailId), project.display("name")) }
        item { SectionCard {
            LabelValue("Status", project.display("operational_status"))
            LabelValue("Purpose", project.display("project_purpose"))
            if (project.text("project_type").isNotBlank()) LabelValue("Type", project.text("project_type"))
            if (project.text("project_owner").isNotBlank()) LabelValue("Owner", project.text("project_owner"))
            if (project.text("expected_start_date").isNotBlank()) LabelValue("Starts", project.text("expected_start_date"))
            if (project.text("expected_end_date").isNotBlank()) LabelValue("Ends", project.text("expected_end_date"))
        } }
        if (project.items("members").isNotEmpty()) item { SectionCard {
            Text("Project members", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            project.items("members").forEach { Text(it.display("full_name", it.display("user")), color = muted) }
        } }
        project.optJSONObject("financial_status")?.let { finance -> item { SectionCard {
            Text("Financial status", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            listOf("approved_budget" to "Approved budget", "pending_commitments" to "Pending commitments", "approved_expenditure" to "Approved expenditure", "available_after_commitments" to "Available after commitments").forEach { (key, label) ->
                if (finance.has(key)) LabelValue(label, money(finance.optDouble(key)))
            }
        } } }
        if (project.items("permitted_accounts").isNotEmpty()) item { SectionCard {
            Text("Expense break-up", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            project.items("permitted_accounts").forEach { Text(it.display("employee_label"), color = ink) }
        } }
        val currentUser = project.optJSONObject("capabilities")?.text("current_user").orEmpty()
        val isMember = (project.optJSONArray("participants") ?: org.json.JSONArray()).let { people ->
            (0 until people.length()).any { people.optString(it) == currentUser }
        }
        if (isMember && project.text("operational_status") == "Active") {
            item { Button(onClick = { model.open(Page.NEW_CLAIM, state.detailId) }, modifier = Modifier.fillMaxWidth()) { Text("Submit an expense") } }
            item { OutlinedButton(onClick = { model.open(Page.NEW_ADVANCE, state.detailId) }, modifier = Modifier.fillMaxWidth()) { Text("Request an advance") } }
        }
    }
}

@Composable
private fun AdvancesScreen(state: PortalState, model: PortalViewModel) {
    val advances = state.data.items("advances")
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Heading("Your advances", "Requests, approvals and settlement") }
        item { Button(onClick = { model.open(Page.NEW_ADVANCE) }, modifier = Modifier.fillMaxWidth()) { Icon(Icons.Default.Add, null); Text(" New request") } }
        if (advances.isEmpty() && !state.busy) item { EmptyState("No advance requests yet") }
        items(advances) { row -> ActionRow(row.display("purpose", row.display("name")), "${money(row.optDouble("advance_amount"))} · ${row.display("workflow_state", row.display("status"))}") {
            model.open(Page.ADVANCE, row.text("name"))
        } }
    }
}

@Composable
private fun AdvanceScreen(state: PortalState) {
    val advance = state.data
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading(advance.display("purpose", state.detailId), state.detailId) }
        item { SectionCard {
            LabelValue("Status", advance.display("workflow_state", advance.display("status")))
            LabelValue("Requested", money(advance.optDouble("advance_amount")))
            LabelValue("Paid", money(advance.optDouble("paid_amount")))
            LabelValue("Still to settle", money(advance.optDouble("residual")))
            LabelValue("Project", advance.display("intended_project"))
            LabelValue("Needed by", advance.display("required_by_date"))
            LabelValue("Expected settlement", advance.display("expected_settlement_date"))
            if (advance.text("advance_additional_note").isNotBlank()) LabelValue("Note", advance.text("advance_additional_note"))
        } }
    }
}

@Composable
private fun ClaimsScreen(state: PortalState, model: PortalViewModel) {
    val claims = state.data.items("claims")
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Heading("Your expense claims", "Review progress and payment status") }
        item { Button(onClick = { model.open(Page.NEW_CLAIM) }, modifier = Modifier.fillMaxWidth()) { Icon(Icons.Default.Add, null); Text(" New claim") } }
        if (claims.isEmpty() && !state.busy) item { EmptyState("No expense claims yet") }
        items(claims) { row -> ActionRow(row.display("name"), "${row.display("project_name")} · ${money(row.optDouble("claimed_amount"))} · ${row.display("stage")}") {
            model.open(Page.CLAIM, row.text("name"))
        } }
    }
}

@Composable
private fun ClaimScreen(state: PortalState) {
    val claim = state.data
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading(state.detailId, claim.display("project_name")) }
        item { SectionCard {
            LabelValue("Stage", claim.display("stage"))
            LabelValue("Claimed", money(claim.optDouble("claimed_amount")))
            LabelValue("Sanctioned", money(claim.optDouble("sanctioned_amount")))
            LabelValue("Reimbursed", money(claim.optDouble("reimbursed_amount")))
            LabelValue("Payment", claim.display("payment_status"))
            LabelValue("Receipt review", claim.display("receipt_review_status"))
            if (claim.text("pending_with").isNotBlank()) LabelValue("Pending with", claim.text("pending_with"))
        } }
        item { Heading("Expense items") }
        items(claim.items("expenses")) { row -> SectionCard {
            Text(row.display("description"), fontWeight = FontWeight.SemiBold)
            LabelValue("Amount", money(row.optDouble("amount")))
            LabelValue("Invoice date", row.display("expense_date"))
            LabelValue("Category", row.display("category"))
            LabelValue("Supplier", row.display("supplier_name"))
            LabelValue("Receipt", if (row.text("receipt_attachment").isBlank()) "Not attached" else "Attached privately")
        } }
        if (claim.items("timeline").isNotEmpty()) {
            item { Heading("History") }
            items(claim.items("timeline")) { row -> SectionCard {
                Text(row.display("label"), fontWeight = FontWeight.SemiBold)
                Text(row.display("when"), color = muted, fontSize = 13.sp)
                if (row.text("detail").isNotBlank()) Text(row.text("detail"), color = muted)
            } }
        }
    }
}

@Composable
private fun ProfileScreen(state: PortalState, model: PortalViewModel) {
    val account = state.data.optJSONObject("account") ?: JSONObject()
    val employee = state.data.optJSONObject("employee") ?: JSONObject()
    val bank = state.form.optJSONObject("approved")
    val pending = state.form.optJSONObject("pending")
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading(account.display("full_name", "My profile"), account.display("email")) }
        item { SectionCard {
            Text("Employee", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            LabelValue("Employee ID", employee.display("name"))
            LabelValue("Role", employee.display("designation"))
            LabelValue("Grade", employee.display("grade"))
            LabelValue("Reports to", employee.display("reporting_manager_name"))
            LabelValue("Work email", employee.display("company_email"))
        } }
        item { SectionCard {
            Text("Reimbursement bank account", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            if (bank == null) Text("No approved account on file", color = muted)
            else {
                LabelValue("Bank", bank.display("bank_name"))
                LabelValue("Account", bank.display("account_number_masked"))
                LabelValue("IFSC", bank.display("ifsc"))
                LabelValue("Holder", bank.display("account_holder_name"))
            }
            if (pending != null) Text("A bank-account request is awaiting review.", color = green)
        } }
        item { OutlinedButton(onClick = model::logout, modifier = Modifier.fillMaxWidth()) { Text("Log out") } }
        item { Text("Connected to ${state.server.label}. This app does not include Desk access.", color = muted, fontSize = 12.sp) }
    }
}

@Composable
private fun UnavailableScreen(state: PortalState) {
    Box(Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
        SectionCard {
            Text("${state.unavailableLabel} isn't in the Android app yet", fontWeight = FontWeight.Bold, fontSize = 20.sp)
            Spacer(Modifier.height(8.dp))
            Text("This action is available on the Home portal, but it needs a dedicated native screen. The app will never open Desk or a web page for it.", color = muted)
        }
    }
}

@Composable
internal fun SectionCard(content: @Composable androidx.compose.foundation.layout.ColumnScope.() -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = Color.White), shape = RoundedCornerShape(20.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp), content = content)
    }
}

@Composable
internal fun Heading(title: String, subtitle: String = "") {
    Column {
        Text(title, fontWeight = FontWeight.Bold, fontSize = 23.sp, color = ink)
        if (subtitle.isNotBlank()) Text(subtitle, color = muted, fontSize = 14.sp)
    }
}

@Composable
internal fun LabelValue(label: String, value: String) {
    Column {
        Text(label, color = muted, fontSize = 12.sp)
        Text(value, color = ink, fontSize = 15.sp)
    }
}

@Composable
internal fun ActionRow(title: String, subtitle: String, onClick: () -> Unit) {
    Card(onClick = onClick, colors = CardDefaults.cardColors(containerColor = Color.White), shape = RoundedCornerShape(17.dp), modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(title, fontWeight = FontWeight.SemiBold, maxLines = 2, overflow = TextOverflow.Ellipsis)
                if (subtitle.isNotBlank()) Text(subtitle, color = muted, fontSize = 13.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
            }
            Icon(Icons.Default.ChevronRight, null, tint = green)
        }
    }
}

@Composable
private fun SmallAction(label: String, modifier: Modifier, enabled: Boolean = true, onClick: () -> Unit) {
    OutlinedButton(onClick = onClick, enabled = enabled, modifier = modifier, contentPadding = PaddingValues(horizontal = 7.dp)) { Text(label, fontSize = 12.sp, maxLines = 1) }
}

@Composable
private fun EmptyState(text: String) { SectionCard { Text(text, color = muted) } }

@Composable
private fun MessageBar(text: String, isError: Boolean, onDismiss: () -> Unit) {
    Surface(color = if (isError) Color(0xFFFFE6E3) else pale, modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(horizontal = 16.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(text, modifier = Modifier.weight(1f), color = if (isError) Color(0xFF9B2D25) else ink, fontSize = 13.sp)
            TextButton(onClick = onDismiss) { Text("Dismiss") }
        }
    }
}

internal fun money(amount: Double): String = "₹" + "%,.2f".format(java.util.Locale.US, amount)
