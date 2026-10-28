package org.sevamrita.mobile.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
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
import java.time.LocalDate

private class BillItem {
    var category by mutableStateOf("")
    var description by mutableStateOf("")
    var amount by mutableStateOf("")
}

private class Bill(val key: Int) {
    var date by mutableStateOf(LocalDate.now().toString())
    var number by mutableStateOf("")
    var supplier by mutableStateOf("")
    var evidence by mutableStateOf<Evidence?>(null)
    val items = mutableStateListOf(BillItem())
    fun total(): Double = items.sumOf { it.amount.toDoubleOrNull() ?: 0.0 }
}

@Composable
fun MultiClaimScreen(state: PortalState, model: PortalViewModel) {
    val form = state.form
    val context = LocalContext.current
    val bills = remember(form) { mutableStateListOf(Bill(1), Bill(2)) }
    var nextKey by remember(form) { mutableStateOf(3) }
    var project by remember(form) { mutableStateOf(state.detailId) }
    var source by remember(form) { mutableStateOf("PERSONAL") }
    var advance by remember(form) { mutableStateOf("") }
    var emergency by remember(form) { mutableStateOf(false) }
    var emergencyDate by remember(form) { mutableStateOf(LocalDate.now().toString()) }
    var emergencyReason by remember(form) { mutableStateOf("") }
    var pickingBill by remember(form) { mutableStateOf<Int?>(null) }
    var error by remember(form) { mutableStateOf("") }
    val accounts = state.data.items("value")
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) try {
            bills.firstOrNull { it.key == pickingBill }?.evidence = readEvidence(context, uri)
            error = ""
        } catch (exception: Exception) { error = exception.message ?: "Could not read invoice." }
    }
    LaunchedEffect(form) { if (project.isNotBlank() && form.items("projects").isNotEmpty()) model.projectAccounts(project) }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading("Submit multiple invoices", "Each invoice gets its own claim and accounting date") }
        item { SectionCard {
            LabelValue("Employee", form.display("employee_name"))
            SelectField("Project *", project, form.items("projects").map { it.text("value") to it.display("label") }) {
                project = it; bills.forEach { bill -> bill.items.forEach { item -> item.category = "" } }; model.projectAccounts(it)
            }
            SelectField("How were these paid?", source, buildList {
                add("PERSONAL" to "Paid personally")
                if (form.items("own_advances").isNotEmpty()) add("OWN_ADVANCE" to "Against my advance")
                if (form.optJSONObject("manager_advance")?.optBoolean("available") == true) add("MANAGER_ADVANCE" to "Against manager's advance")
            }) { source = it; advance = "" }
            if (source == "OWN_ADVANCE") SelectField("Paid advance *", advance,
                form.items("own_advances").map { it.text("name") to "${it.text("name")} · ${money(it.optDouble("residual"))}" }) { advance = it }
            if (source == "MANAGER_ADVANCE") Text("Available from manager: ${money(form.optJSONObject("manager_advance")?.optDouble("maximum_available") ?: 0.0)}")
        } }
        item { SectionCard {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(emergency, { emergency = it }); Text("These were emergency expenses")
            }
            if (emergency) {
                DateField("Emergency date *", emergencyDate) { emergencyDate = it }
                OutlinedTextField(emergencyReason, { emergencyReason = it }, label = { Text("Why was prior approval unavailable? *") }, modifier = Modifier.fillMaxWidth())
            }
        } }
        items(bills, key = { it.key }) { bill -> SectionCard {
            Text("Invoice ${bills.indexOf(bill) + 1}", fontWeight = FontWeight.Bold)
            DateField("Date on invoice *", bill.date) { bill.date = it }
            OutlinedTextField(bill.number, { bill.number = it }, label = { Text("Invoice number (optional)") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(bill.supplier, { bill.supplier = it }, label = { Text("Supplier / payee (optional)") }, modifier = Modifier.fillMaxWidth())
            OutlinedButton(onClick = { pickingBill = bill.key; picker.launch(arrayOf("application/pdf", "image/png", "image/jpeg")) }, modifier = Modifier.fillMaxWidth()) {
                Text(bill.evidence?.let { "Invoice: ${it.name}" } ?: "Attach private invoice *")
            }
            Text("Items on this invoice", fontWeight = FontWeight.SemiBold)
            bill.items.forEachIndexed { index, item ->
                Text("Item ${index + 1}")
                SelectField("Expense break-up *", item.category, accounts.map { it.text("value") to it.display("label") }) { item.category = it }
                OutlinedTextField(item.description, { item.description = it }, label = { Text("Description and business purpose *") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(item.amount, { item.amount = it }, label = { Text("Amount (INR) *") }, modifier = Modifier.fillMaxWidth())
                if (bill.items.size > 1) TextButton(onClick = { bill.items.remove(item) }) { Text("Remove item") }
            }
            if (bill.items.size < 10) OutlinedButton(onClick = { bill.items.add(BillItem()) }) { Text("Add item") }
            LabelValue("Invoice total", money(bill.total()))
            if (bills.size > 2) TextButton(onClick = { bills.remove(bill) }) { Text("Remove invoice") }
        } }
        if (bills.size < 10) item { OutlinedButton(onClick = { bills.add(Bill(nextKey++)) }, modifier = Modifier.fillMaxWidth()) { Text("Add invoice") } }
        item { SectionCard {
            LabelValue("Combined amount", money(bills.sumOf { it.total() }))
            Text("Approval authority is checked against the combined amount. Each bill retains its own date and private receipt.")
            if (error.isNotBlank()) Text(error, color = Color(0xFF9B2D25))
            Button(onClick = {
                val today = LocalDate.now()
                error = when {
                    project.isBlank() -> "Choose a project."
                    source == "OWN_ADVANCE" && advance.isBlank() -> "Choose a paid advance."
                    emergency && emergencyReason.isBlank() -> "Explain the emergency."
                    accounts.isEmpty() -> "No expense break-up is available for this project."
                    bills.any { runCatching { LocalDate.parse(it.date) > today }.getOrDefault(true) } -> "Invoice dates must be valid and not in the future."
                    bills.any { it.evidence == null } -> "Attach a receipt to every invoice."
                    bills.any { it.items.any { item -> item.category.isBlank() || item.description.isBlank() || (item.amount.toDoubleOrNull() ?: 0.0) <= 0 } } -> "Complete every expense item with category, description and positive amount."
                    source == "MANAGER_ADVANCE" && bills.sumOf { it.total() } > (form.optJSONObject("manager_advance")?.optDouble("maximum_available") ?: 0.0) -> "The manager's advance does not cover the combined amount."
                    else -> ""
                }
                if (error.isBlank()) {
                    val invoices = JSONArray()
                    bills.forEach { bill ->
                        val items = JSONArray()
                        bill.items.forEach { item -> items.put(JSONObject().put("account", item.category)
                            .put("description", item.description.trim()).put("amount", item.amount.toDouble())) }
                        invoices.put(JSONObject().put("invoice_date", bill.date).put("invoice_number", bill.number.trim())
                            .put("supplier_name", bill.supplier.trim()).put("receipt_filename", bill.evidence!!.name)
                            .put("receipt_content", bill.evidence!!.base64).put("items", items))
                    }
                    val payload = JSONObject().put("project", project).put("reimbursement_source", source)
                        .put("is_emergency", if (emergency) 1 else 0).put("invoices", invoices)
                    if (source == "OWN_ADVANCE") payload.put("employee_advance", advance)
                    if (emergency) payload.put("emergency_date", emergencyDate).put("emergency_reason", emergencyReason.trim())
                    model.submitMultiClaim(payload)
                }
            }, enabled = !state.busy && form.items("projects").isNotEmpty(), modifier = Modifier.fillMaxWidth()) { Text("Submit all invoices for review") }
        } }
    }
}

@Composable
fun MultiResultScreen(state: PortalState, model: PortalViewModel) {
    val claims = state.data.items("claims")
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Heading("Invoices submitted", "${claims.size} claims · ${money(state.data.optDouble("total"))} combined") }
        items(claims) { claim -> ActionRow(claim.display("name"), claim.display("stage", "Awaiting review")) { model.open(Page.CLAIM, claim.text("name")) } }
        item { Button(onClick = { model.open(Page.CLAIMS) }, modifier = Modifier.fillMaxWidth()) { Text("View all claims") } }
    }
}
