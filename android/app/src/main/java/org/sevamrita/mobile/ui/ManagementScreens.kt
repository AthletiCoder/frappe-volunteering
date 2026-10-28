package org.sevamrita.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject
import org.sevamrita.mobile.Heading
import org.sevamrita.mobile.LabelValue
import org.sevamrita.mobile.SectionCard
import org.sevamrita.mobile.data.display
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text
import org.sevamrita.mobile.money

@Composable
fun ProjectMappingScreen(state: PortalState, model: PortalViewModel) {
    val projects = state.data.items("projects")
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading("Project account suggestions", "Accounts Managers can suggest several ledgers for each approved expense label") }
        if (projects.isEmpty() && !state.busy) item { SectionCard { Text("No approved projects are available for mapping.") } }
        items(projects) { project -> SectionCard {
            Text(project.display("project_name"), fontWeight = FontWeight.Bold)
            Text(project.display("name"), color = Color(0xFF637378))
            LabelValue("Mapping", if (project.optBoolean("ready")) "Suggested accounts saved" else "Needs suggestions")
            TextButton(onClick = { model.open(Page.PROJECT_MAPPING_DETAIL, project.text("name")) }) { Text("Open project →") }
        } }
    }
}

private class AccountChoice(val value: String, selected: Boolean) { var checked by mutableStateOf(selected) }

@Composable
fun ProjectMappingDetailScreen(state: PortalState, model: PortalViewModel) {
    val project = state.data.optJSONObject("project") ?: JSONObject()
    val accounts = state.data.items("accounts")
    val rows = project.items("rows")
    val choices = remember(state.data) { rows.associate { row ->
        val selected = row.optJSONArray("expense_accounts")?.let { array ->
            (0 until array.length()).map { array.optString(it) }.toSet()
        }.orEmpty()
        row.text("budget_key") to accounts.map { AccountChoice(it.text("name"), it.text("name") in selected) }
    } }
    var error by remember(state.data) { mutableStateOf("") }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading(project.display("project_name"), project.display("name")) }
        item { SectionCard { Text("Suggestions are optional for receiving claims. Accounts decides final ledger splits before posting each approved claim.") } }
        items(rows) { row -> SectionCard {
            Text(row.display("employee_label"), fontWeight = FontWeight.Bold)
            LabelValue("Approved budget", money(row.optDouble("approved_amount")))
            for (account in accounts) {
                val choice = choices[row.text("budget_key")]?.firstOrNull { it.value == account.text("name") }
                if (choice != null) androidx.compose.foundation.layout.Row {
                    Checkbox(choice.checked, { choice.checked = it })
                    Text(account.display("account_name"), modifier = Modifier.fillMaxWidth())
                }
            }
        } }
        item { if (error.isNotBlank()) Text(error, color = Color(0xFF9B2D25)) }
        item { Button(onClick = {
            val output = JSONArray()
            rows.forEach { row ->
                val names = JSONArray()
                choices[row.text("budget_key")].orEmpty().filter { it.checked }.forEach { names.put(it.value) }
                output.put(JSONObject().put("budget_key", row.text("budget_key")).put("expense_accounts", names))
            }
            if (rows.isEmpty()) error = "No approved labels found."
            else model.saveProjectMapping(output)
        }, enabled = !state.busy && !project.optBoolean("closed"), modifier = Modifier.fillMaxWidth()) { Text("Save account suggestions") } }
    }
}

private class LimitEntry(val grade: String, initial: Double, val unlimited: Boolean, val advance: Double) {
    var amount by mutableStateOf(initial.toString())
}

@Composable
fun ClaimLimitsScreen(state: PortalState, model: PortalViewModel) {
    val rows = remember(state.data) { state.data.items("rows").map {
        LimitEntry(it.text("grade"), it.optDouble("expense_claim_limit"), it.optBoolean("unlimited"), it.optDouble("advance_approval_limit"))
    } }
    var error by remember(state.data) { mutableStateOf("") }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading("Expense claim approval limits", "The claim amount determines how far it must travel through the reporting chain") }
        items(rows) { row -> SectionCard {
            Text(row.grade, fontWeight = FontWeight.Bold)
            LabelValue("Advance authority", if (row.unlimited) "Unlimited" else money(row.advance))
            if (row.unlimited) Text("Expense approval: Unlimited")
            else OutlinedTextField(row.amount, { row.amount = it }, label = { Text("Expense approval limit (INR)") },
                singleLine = true, modifier = Modifier.fillMaxWidth())
        } }
        item { if (error.isNotBlank()) Text(error, color = Color(0xFF9B2D25)) }
        item { Button(onClick = {
            error = if (rows.any { !it.unlimited && (it.amount.toDoubleOrNull()?.let { n -> n.isFinite() && n >= 0 } != true) })
                "All limits must be non-negative amounts." else ""
            if (error.isBlank()) {
                val output = JSONArray()
                rows.forEach { output.put(JSONObject().put("grade", it.grade)
                    .put("expense_claim_limit", if (it.unlimited) 0 else it.amount.toDouble())) }
                model.saveClaimLimits(output)
            }
        }, enabled = !state.busy && rows.isNotEmpty(), modifier = Modifier.fillMaxWidth()) { Text("Save expense limits") } }
    }
}

@Composable
fun FiscalYearsScreen(state: PortalState, model: PortalViewModel) {
    var year by remember { mutableStateOf("") }
    var error by remember { mutableStateOf("") }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading("Fiscal Years", "System Managers can activate an existing April–March year or create the next year") }
        item { SectionCard {
            OutlinedTextField(year, { year = it }, label = { Text("Starting year, e.g. 2026") },
                singleLine = true, modifier = Modifier.fillMaxWidth())
            if (error.isNotBlank()) Text(error, color = Color(0xFF9B2D25))
            Button(onClick = {
                error = if (!year.matches(Regex("20\\d{2}"))) "Enter a four-digit year starting with 20." else ""
                if (error.isBlank()) model.createFiscalYear(year)
            }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Create Fiscal Year") }
        } }
        items(state.data.items("years")) { row -> SectionCard {
            Text(row.display("name"), fontWeight = FontWeight.Bold)
            LabelValue("Period", "${row.display("start_date")} – ${row.display("end_date")}")
            LabelValue("Status", if (row.optBoolean("active")) "Active" else "Inactive")
            if (row.optBoolean("current")) Text("Current date falls in this year")
            if (row.optBoolean("can_activate")) TextButton(onClick = { model.activateFiscalYear(row.text("name")) }) { Text("Activate") }
        } }
    }
}
