package org.sevamrita.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject
import org.sevamrita.mobile.ActionRow
import org.sevamrita.mobile.Heading
import org.sevamrita.mobile.LabelValue
import org.sevamrita.mobile.SectionCard
import org.sevamrita.mobile.data.display
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text
import org.sevamrita.mobile.money

private data class Breakup(val label: String, val amount: String, val key: String = "")

@Composable
fun ProposalsScreen(state: PortalState, model: PortalViewModel) {
    val all = state.data.items("value")
    val review = state.proposalFilter == "review"
    val shown = if (review) all.filter { it.text("proposal_status") == "Pending Approval" }
        else all.filter { it.text("proposed_by") == state.user }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Heading(if (review) "Review proposals" else "Your proposals", if (review) "Only the assigned manager can decide" else "Drafts, pending requests and decisions") }
        if (!review) item { Button(onClick = { model.open(Page.PROPOSAL_FORM) }, modifier = Modifier.fillMaxWidth()) { Text("Propose a project") } }
        if (shown.isEmpty() && !state.busy) item { SectionCard { Text(if (review) "No pending proposals." else "You have no project proposals yet.") } }
        items(shown) { proposal -> ActionRow(proposal.display("title", "Untitled project"),
            "${proposal.display("proposal_status")} · ${proposal.display("request_kind")} · ${proposal.display("name")}") {
            model.open(Page.PROPOSAL, proposal.text("name"))
        } }
    }
}

@Composable
fun ProposalScreen(state: PortalState, model: PortalViewModel) {
    val proposal = state.data
    val data = proposal.optJSONObject("data") ?: JSONObject()
    var comments by remember(proposal.text("modified")) { mutableStateOf("") }
    var error by remember { mutableStateOf("") }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading(proposal.display("title", "Project proposal"), proposal.display("name")) }
        item { SectionCard {
            LabelValue("Status", proposal.display("proposal_status"))
            LabelValue("Kind", proposal.display("request_kind"))
            LabelValue("Proposed by", proposal.display("proposed_by"))
            LabelValue("Assigned manager", proposal.display("assigned_approver"))
            if (proposal.text("request_reason").isNotBlank()) LabelValue("Reason for change", proposal.text("request_reason"))
            if (proposal.optBoolean("stale")) Text("The approved project changed after this request was drafted. Review the latest baseline before deciding.")
        } }
        item { SectionCard {
            Text("Project details", fontWeight = FontWeight.SemiBold)
            LabelValue("Name", data.display("project_name"))
            LabelValue("Purpose / scope", data.display("project_purpose"))
            if (data.text("project_outcomes").isNotBlank()) LabelValue("Expected outcomes", data.text("project_outcomes"))
            LabelValue("Project owner", data.display("project_owner"))
            LabelValue("Operational status", data.display("operational_status"))
            if (data.text("expected_start_date").isNotBlank()) LabelValue("Start", data.text("expected_start_date"))
            if (data.text("expected_end_date").isNotBlank()) LabelValue("End", data.text("expected_end_date"))
            val people = data.optJSONArray("participants") ?: JSONArray()
            LabelValue("Members", (0 until people.length()).mapNotNull { index ->
                val value = people.opt(index)
                when (value) { is JSONObject -> value.text("user"); is String -> value; else -> null }
            }.joinToString("\n").ifBlank { "—" })
        } }
        if (proposal.optBoolean("can_view_financials")) item { SectionCard {
            Text("Budget and expense break-up", fontWeight = FontWeight.SemiBold)
            LabelValue("Total budget", money(data.optDouble("total_approved_budget")))
            LabelValue("Cost centre", data.display("cost_center"))
            data.items("account_budgets").forEach { row ->
                LabelValue(row.display("employee_label"), money(row.optDouble("approved_amount")))
            }
        } }
        if (proposal.items("events").isNotEmpty()) {
            item { Heading("History") }
            items(proposal.items("events")) { event -> SectionCard {
                Text(event.display("action"), fontWeight = FontWeight.SemiBold)
                Text("${event.display("actor")} · ${event.display("acted_on")}")
                if (event.text("comment").isNotBlank()) Text(event.text("comment"))
            } }
        }
        if (proposal.optBoolean("can_edit") && proposal.text("request_kind") == "New Project") item {
            OutlinedButton(onClick = { model.open(Page.PROPOSAL_FORM, proposal.text("name")) }, modifier = Modifier.fillMaxWidth()) { Text("Edit proposal") }
        }
        if (proposal.optBoolean("can_submit")) item {
            Button(onClick = { model.submitSavedProposal() }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Submit for approval") }
        }
        if (proposal.optBoolean("can_review")) item { SectionCard {
            Text("Manager decision", fontWeight = FontWeight.SemiBold)
            OutlinedTextField(comments, { comments = it }, label = { Text("Review comments") }, minLines = 2, modifier = Modifier.fillMaxWidth())
            if (error.isNotBlank()) Text(error)
            Button(onClick = { model.reviewProposal("approve", comments) }, enabled = !state.busy && !proposal.optBoolean("stale"), modifier = Modifier.fillMaxWidth()) { Text("Approve as submitted") }
            OutlinedButton(onClick = {
                if (comments.isBlank()) error = "Comments are required." else model.reviewProposal("return", comments)
            }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Return for correction") }
            OutlinedButton(onClick = {
                if (comments.isBlank()) error = "Comments are required." else model.reviewProposal("reject", comments)
            }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Reject") }
        } }
    }
}

@Composable
fun ProposalFormScreen(state: PortalState, model: PortalViewModel) {
    val options = state.form
    val proposal = state.data
    val initial = remember(proposal) { proposal.optJSONObject("data") ?: JSONObject() }
    val editing = state.detailId.isNotBlank()
    var name by remember(initial) { mutableStateOf(initial.text("project_name")) }
    var purpose by remember(initial) { mutableStateOf(initial.text("project_purpose")) }
    var outcomes by remember(initial) { mutableStateOf(initial.text("project_outcomes")) }
    var owner by remember(initial, options) { mutableStateOf(initial.text("project_owner").ifBlank { options.text("current_user") }) }
    var status by remember(initial) { mutableStateOf(initial.text("operational_status").ifBlank { "Planned" }) }
    var start by remember(initial) { mutableStateOf(initial.text("expected_start_date")) }
    var end by remember(initial) { mutableStateOf(initial.text("expected_end_date")) }
    var costCenter by remember(initial) { mutableStateOf(initial.text("cost_center")) }
    var budget by remember(initial) { mutableStateOf(initial.text("total_approved_budget").ifBlank { "0" }) }
    var approver by remember(proposal) { mutableStateOf(proposal.text("assigned_approver")) }
    var error by remember { mutableStateOf("") }
    val members = remember(initial, options) {
        val existing = initial.optJSONArray("participants")
        val values = if (existing == null) listOf(options.text("current_user")) else (0 until existing.length()).mapNotNull {
            when (val value = existing.opt(it)) { is JSONObject -> value.text("user"); is String -> value; else -> null }
        }
        mutableStateListOf<String>().apply { addAll(values.filter { it.isNotBlank() }.distinct()) }
    }
    val breakup = remember(initial) {
        mutableStateListOf<Breakup>().apply { addAll(initial.items("account_budgets")
            .filter { it.text("employee_label") != "Others" }
            .map { Breakup(it.text("employee_label"), it.text("approved_amount"), it.text("budget_key")) }) }
    }
    val users = options.items("users")
    val managers = options.items("project_managers")
    val costCentres = options.items("cost_centres")
    val submitted = proposal.text("proposal_status") == "Pending Approval"
    fun payload(): JSONObject {
        val rows = JSONArray()
        breakup.forEach { row -> rows.put(JSONObject().put("budget_key", row.key)
            .put("employee_label", row.label.trim()).put("approved_amount", row.amount.toDoubleOrNull() ?: 0.0).put("is_active", 1)) }
        return JSONObject().put("project_name", name.trim()).put("project_purpose", purpose.trim())
            .put("project_outcomes", outcomes.trim()).put("project_owner", owner)
            .put("operational_status", status).put("expected_start_date", start)
            .put("expected_end_date", end).put("priority", "Medium")
            .put("cost_center", costCenter).put("total_approved_budget", budget.toDoubleOrNull() ?: 0.0)
            .put("project_budget_control", "No Control").put("account_budget_control", "No Control")
            .put("participants", JSONArray().apply { members.forEach { put(it) } })
            .put("account_budgets", rows)
    }
    fun save(submitNow: Boolean) {
        val amount = budget.toDoubleOrNull()
        error = when {
            amount == null || !amount.isFinite() || amount < 0 -> "Enter a valid project budget."
            breakup.any { it.label.isBlank() || (it.amount.toDoubleOrNull() ?: -1.0) < 0 } -> "Complete each expense break-up row."
            breakup.sumOf { it.amount.toDoubleOrNull() ?: 0.0 } > (amount ?: 0.0) -> "Expense break-up cannot exceed the total budget."
            submitNow && name.isBlank() -> "Enter the project name."
            submitNow && purpose.isBlank() -> "Enter the project purpose."
            submitNow && owner.isBlank() -> "Choose the project owner."
            submitNow && members.isEmpty() -> "Add at least one project member."
            submitNow && costCenter.isBlank() -> "Choose a cost centre."
            submitNow && approver.isBlank() -> "Choose the Projects Manager who will review this."
            else -> ""
        }
        if (error.isBlank()) model.saveProposal(payload(), approver, submitNow)
    }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading(if (editing) "Edit project proposal" else "Propose a project", "A draft can be saved before all details are known") }
        item { SectionCard {
            Text("01 · Scope and ownership", fontWeight = FontWeight.Bold)
            OutlinedTextField(name, { name = it }, label = { Text("Project name *") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(purpose, { purpose = it }, label = { Text("Purpose / scope *") }, minLines = 3, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(outcomes, { outcomes = it }, label = { Text("Expected outcomes") }, minLines = 2, modifier = Modifier.fillMaxWidth())
            SelectField("Project owner *", owner, users.map { it.text("name") to it.display("full_name", it.display("name")) }) { owner = it }
            SelectField("Operational status", status, listOf("Planned", "Active", "On Hold", "Completed", "Cancelled").map { it to it }) { status = it }
            DateField("Expected start", start) { start = it }
            DateField("Expected end", end) { end = it }
        } }
        item { SectionCard {
            Text("02 · Participants", fontWeight = FontWeight.Bold)
            Text("Every member receives basic project visibility and may submit bills.")
            SelectField("Add member", "", users.filter { it.text("name") !in members }.map {
                it.text("name") to it.display("full_name", it.display("name"))
            }) { if (it !in members) members.add(it) }
            members.forEach { person -> Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text(users.firstOrNull { it.text("name") == person }?.display("full_name", person) ?: person, Modifier.weight(1f))
                TextButton(onClick = { members.remove(person) }) { Text("Remove") }
            } }
        } }
        item { SectionCard {
            Text("03 · Budget", fontWeight = FontWeight.Bold)
            SelectField("Cost centre *", costCenter, costCentres.map { it.text("name") to it.display("name") }) { costCenter = it }
            OutlinedTextField(budget, { budget = it }, label = { Text("Total project budget (INR) *") }, modifier = Modifier.fillMaxWidth())
            Text("Expense break-up is optional. Any remainder becomes Others when approved.")
            breakup.forEachIndexed { index, row ->
                OutlinedTextField(row.label, { breakup[index] = row.copy(label = it) }, label = { Text("Expense label ${index + 1}") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(row.amount, { breakup[index] = row.copy(amount = it) }, label = { Text("Allocation (INR)") }, modifier = Modifier.fillMaxWidth())
                TextButton(onClick = { breakup.removeAt(index) }) { Text("Remove label") }
            }
            OutlinedButton(onClick = { breakup.add(Breakup("", "0")) }, modifier = Modifier.fillMaxWidth()) { Text("Add expense break-up") }
        } }
        item { SectionCard {
            Text("04 · Send for approval", fontWeight = FontWeight.Bold)
            SelectField("Assigned Projects Manager *", approver, managers.map {
                it.text("name") to it.display("full_name", it.display("name"))
            }) { approver = it }
            Text("Only this manager can decide the request. Other Projects Managers may view it.")
        } }
        if (error.isNotBlank()) item { Text(error, color = androidx.compose.material3.MaterialTheme.colorScheme.error) }
        if (submitted) {
            item { Button(onClick = { save(false) }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Save manager edits") } }
        } else {
            item { OutlinedButton(onClick = { save(false) }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Save draft") } }
            item { Button(onClick = { save(true) }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Save and submit for approval") } }
        }
    }
}
