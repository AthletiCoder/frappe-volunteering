package org.sevamrita.mobile.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
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
import org.sevamrita.mobile.Heading
import org.sevamrita.mobile.LabelValue
import org.sevamrita.mobile.SectionCard
import org.sevamrita.mobile.data.display
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text
import java.time.LocalDate

@Composable
fun CombinedClaimScreen(state: PortalState, model: PortalViewModel) {
    val form = state.form
    val context = LocalContext.current
    var project by remember(form) { mutableStateOf(state.detailId) }
    var source by remember(form) { mutableStateOf("PERSONAL") }
    var advance by remember(form) { mutableStateOf("") }
    var invoicePath by remember(form) { mutableStateOf("") }
    var date by remember(form) { mutableStateOf(LocalDate.now().toString()) }
    var category by remember(form) { mutableStateOf("") }
    var supplier by remember(form) { mutableStateOf("") }
    var invoiceNumber by remember(form) { mutableStateOf("") }
    var description by remember(form) { mutableStateOf("") }
    var amount by remember(form) { mutableStateOf("") }
    var receipt by remember(form) { mutableStateOf<Evidence?>(null) }
    var emergency by remember(form) { mutableStateOf(false) }
    var emergencyReason by remember(form) { mutableStateOf("") }
    var error by remember(form) { mutableStateOf("") }
    val accounts = state.data.items("value")
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) try { receipt = readEvidence(context, uri); error = "" }
        catch (exception: Exception) { receipt = null; error = exception.message ?: "Could not read invoice." }
    }
    LaunchedEffect(form) { if (project.isNotBlank() && form.items("projects").isNotEmpty()) model.projectAccounts(project) }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading("Invoice and expense", "Start with the claim, then attach an invoice or prepare and sign one") }
        item { SectionCard {
            LabelValue("Employee", form.display("employee_name"))
            SelectField("Project *", project, form.items("projects").map { it.text("value") to it.display("label") }) {
                project = it; category = ""; model.projectAccounts(it)
            }
            SelectField("How was this paid?", source, buildList {
                add("PERSONAL" to "Paid personally")
                if (form.items("own_advances").isNotEmpty()) add("OWN_ADVANCE" to "Against my advance")
                if (form.optJSONObject("manager_advance")?.optBoolean("available") == true) add("MANAGER_ADVANCE" to "Against manager's advance")
            }) { source = it; advance = "" }
            if (source == "OWN_ADVANCE") SelectField("Paid advance *", advance,
                form.items("own_advances").map { it.text("name") to it.display("name") }) { advance = it }
        } }
        item { SectionCard {
            DateField("Date on invoice *", date) { date = it }
            SelectField("Expense break-up *", category, accounts.map { it.text("value") to it.display("label") }) { category = it }
            OutlinedTextField(description, { description = it }, label = { Text("Description and business purpose *") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(amount, { amount = it }, label = { Text("Amount (INR) *") }, modifier = Modifier.fillMaxWidth())
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(emergency, { emergency = it }); Text("This was an emergency expense")
            }
            if (emergency) OutlinedTextField(emergencyReason, { emergencyReason = it }, label = { Text("Why was prior approval unavailable? *") }, modifier = Modifier.fillMaxWidth())
        } }
        item { SectionCard {
            Text("Invoice for this expense", fontWeight = FontWeight.Bold)
            SelectField("Do you already have an invoice? *", invoicePath,
                listOf("EXISTING" to "Yes, attach the invoice", "GENERATE" to "No, prepare and sign one")) { invoicePath = it }
            if (invoicePath == "EXISTING") {
                OutlinedTextField(supplier, { supplier = it }, label = { Text("Supplier / payee") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(invoiceNumber, { invoiceNumber = it }, label = { Text("Invoice number") }, modifier = Modifier.fillMaxWidth())
                OutlinedButton(onClick = { picker.launch(arrayOf("application/pdf", "image/png", "image/jpeg")) }, modifier = Modifier.fillMaxWidth()) {
                    Text(receipt?.let { "Attached: ${it.name}" } ?: "Attach private invoice *")
                }
            } else if (invoicePath == "GENERATE") Text("Next, fill the supplier and item details and sign on screen. The PDF is sent directly to receipt review.")
        } }
        item { SectionCard {
            if (error.isNotBlank()) Text(error, color = Color(0xFF9B2D25))
            Button(onClick = {
                val value = amount.toDoubleOrNull()
                error = when {
                    project.isBlank() -> "Choose a project."
                    category.isBlank() -> "Choose an expense break-up."
                    source == "OWN_ADVANCE" && advance.isBlank() -> "Choose a paid advance."
                    description.isBlank() -> "Describe the expense and business purpose."
                    value == null || !value.isFinite() || value <= 0 -> "Enter a positive amount."
                    runCatching { LocalDate.parse(date) > LocalDate.now() }.getOrDefault(true) -> "Choose a valid invoice date, not in the future."
                    emergency && emergencyReason.isBlank() -> "Explain the emergency."
                    invoicePath.isBlank() -> "Choose whether to attach or generate an invoice."
                    invoicePath == "EXISTING" && receipt == null -> "Attach the invoice."
                    source == "MANAGER_ADVANCE" && value > (form.optJSONObject("manager_advance")?.optDouble("maximum_available") ?: 0.0) -> "The manager's advance does not cover this expense."
                    else -> ""
                }
                if (error.isBlank()) {
                    val item = JSONObject().put("expense_date", date).put("account", category)
                        .put("description", description.trim()).put("amount", value)
                    if (invoicePath == "EXISTING") item.put("supplier_name", supplier.trim())
                        .put("invoice_number", invoiceNumber.trim()).put("receipt_filename", receipt!!.name)
                        .put("receipt_content", receipt!!.base64)
                    val claim = JSONObject().put("project", project).put("reimbursement_source", source)
                        .put("employee_advance", if (source == "OWN_ADVANCE") advance else "")
                        .put("is_emergency", emergency).put("emergency_date", if (emergency) date else "")
                        .put("emergency_reason", if (emergency) emergencyReason.trim() else "")
                        .put("expenses", JSONArray().put(item))
                    if (invoicePath == "EXISTING") model.submitClaim(claim)
                    else model.openCombinedInvoice(claim)
                }
            }, enabled = !state.busy && form.items("projects").isNotEmpty(), modifier = Modifier.fillMaxWidth()) {
                Text(if (invoicePath == "GENERATE") "Continue to prepare invoice" else "Submit expense for review")
            }
        } }
    }
}
