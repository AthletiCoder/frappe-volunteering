package org.sevamrita.mobile.ui

import android.app.DatePickerDialog
import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import android.util.Base64
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
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
import java.io.ByteArrayOutputStream
import java.time.LocalDate
import java.time.format.DateTimeFormatter

private data class Evidence(val name: String, val base64: String)

@Composable
fun AdvanceRequestScreen(form: JSONObject, projectHint: String, busy: Boolean, submit: (JSONObject) -> Unit) {
    var project by remember(form) { mutableStateOf(projectHint) }
    var amount by remember(form) { mutableStateOf("") }
    var purpose by remember(form) { mutableStateOf("") }
    var needed by remember(form) { mutableStateOf(LocalDate.now().toString()) }
    var settle by remember(form) { mutableStateOf(LocalDate.now().plusDays(30).toString()) }
    var note by remember(form) { mutableStateOf("") }
    var error by remember { mutableStateOf("") }
    val projects = form.items("projects")
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading("Request an advance", "Choose the project and explain what the funds are for") }
        item { SectionCard {
            LabelValue("Employee", form.display("employee_name"))
            LabelValue("Approver", form.optJSONObject("approver")?.display("name") ?: "—")
            val bank = form.optJSONObject("approved_bank")
            Text(if (bank == null) "An approved reimbursement bank account may be required before payment." else "Approved bank account on file", fontWeight = FontWeight.Medium)
        } }
        item { SectionCard {
            SelectField("Project *", project, projects.map { it.text("value") to it.display("label") }) { project = it }
            OutlinedTextField(amount, { amount = it }, label = { Text("Amount (INR) *") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(purpose, { purpose = it }, label = { Text("Purpose *") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
            DateField("Needed by", needed) { needed = it }
            DateField("Expected settlement", settle) { settle = it }
            OutlinedTextField(note, { note = it }, label = { Text("Additional note (optional)") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
        } }
        if (form.optJSONObject("freeze")?.optBoolean("frozen") == true) item { Text("Your advances are currently frozen. Contact your manager before requesting another.") }
        if (error.isNotBlank()) item { Text(error, color = androidx.compose.material3.MaterialTheme.colorScheme.error) }
        item { Button(onClick = {
            val value = amount.toDoubleOrNull()
            error = when {
                project.isBlank() -> "Choose a project."
                value == null || !value.isFinite() || value <= 0 -> "Enter a positive amount."
                purpose.isBlank() -> "Explain the purpose."
                else -> ""
            }
            if (error.isBlank()) submit(JSONObject().put("intended_project", project).put("amount", value)
                .put("purpose", purpose.trim()).put("required_by_date", needed)
                .put("expected_settlement_date", settle).put("additional_note", note.trim()))
        }, enabled = !busy && projects.isNotEmpty(), modifier = Modifier.fillMaxWidth()) { Text("Submit request") } }
    }
}

@Composable
fun ExpenseRequestScreen(
    form: JSONObject,
    accountData: JSONObject,
    projectHint: String,
    busy: Boolean,
    loadAccounts: (String) -> Unit,
    submit: (JSONObject) -> Unit
) {
    var project by remember(form) { mutableStateOf(projectHint) }
    var source by remember(form) { mutableStateOf("PERSONAL") }
    var advance by remember(form) { mutableStateOf("") }
    var date by remember(form) { mutableStateOf(LocalDate.now().toString()) }
    var category by remember(form) { mutableStateOf("") }
    var supplier by remember(form) { mutableStateOf("") }
    var invoice by remember(form) { mutableStateOf("") }
    var description by remember(form) { mutableStateOf("") }
    var amount by remember(form) { mutableStateOf("") }
    var emergency by remember(form) { mutableStateOf(false) }
    var emergencyReason by remember(form) { mutableStateOf("") }
    var receipt by remember(form) { mutableStateOf<Evidence?>(null) }
    var error by remember { mutableStateOf("") }
    val context = LocalContext.current
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) try { receipt = readEvidence(context, uri); error = "" }
        catch (exception: Exception) { receipt = null; error = exception.message ?: "Unable to read receipt." }
    }
    val projects = form.items("projects")
    val accounts = accountData.items("value")
    LaunchedEffect(form) {
        if (form.items("projects").isNotEmpty() && project.isNotBlank()) loadAccounts(project)
    }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading("Submit an expense", "One dated bill per claim, with private receipt evidence") }
        item { SectionCard {
            LabelValue("Employee", form.display("employee_name"))
            SelectField("Project *", project, projects.map { it.text("value") to it.display("label") }) {
                project = it; category = ""; loadAccounts(it)
            }
            if (project.isNotBlank() && accounts.isEmpty()) {
                TextButton(onClick = { loadAccounts(project) }) { Text("Load expense categories") }
            }
        } }
        item { SectionCard {
            Text("How was this paid?", fontWeight = FontWeight.SemiBold)
            val choices = buildList {
                add("PERSONAL" to "Paid personally")
                if (form.items("own_advances").isNotEmpty()) add("OWN_ADVANCE" to "Against my advance")
                if (form.optJSONObject("manager_advance")?.optBoolean("available") == true) add("MANAGER_ADVANCE" to "Against manager's advance")
            }
            SelectField("Payment source", source, choices) { source = it; advance = "" }
            if (source == "OWN_ADVANCE") SelectField("Paid advance *", advance,
                form.items("own_advances").map { it.text("name") to "${it.text("name")} · ₹${it.optDouble("residual")}" }) { advance = it }
        } }
        item { SectionCard {
            Text("Bill and expense", fontWeight = FontWeight.SemiBold)
            DateField("Date on bill *", date) { date = it }
            SelectField("Expense break-up *", category, accounts.map { it.text("value") to it.display("label") }) { category = it }
            OutlinedTextField(supplier, { supplier = it }, label = { Text("Supplier / payee") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(invoice, { invoice = it }, label = { Text("Receipt / invoice number") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(description, { description = it }, label = { Text("Description and business purpose *") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
            OutlinedTextField(amount, { amount = it }, label = { Text("Amount (INR) *") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedButton(onClick = { picker.launch(arrayOf("application/pdf", "image/png", "image/jpeg")) }, modifier = Modifier.fillMaxWidth()) {
                Text(receipt?.let { "Receipt: ${it.name}" } ?: "Attach private receipt *")
            }
            Text("PDF, PNG or JPEG; up to 5 MB. The bill date sets this claim's accounting period.", color = androidx.compose.material3.MaterialTheme.colorScheme.onSurfaceVariant)
        } }
        item { SectionCard {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(checked = emergency, onCheckedChange = { emergency = it })
                Text("This was an emergency expense")
            }
            if (emergency) OutlinedTextField(emergencyReason, { emergencyReason = it }, label = { Text("Why was prior approval unavailable? *") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
        } }
        if (error.isNotBlank()) item { Text(error, color = androidx.compose.material3.MaterialTheme.colorScheme.error) }
        item { Button(onClick = {
            val value = amount.toDoubleOrNull()
            error = when {
                project.isBlank() -> "Choose a project."
                category.isBlank() -> "Choose an expense break-up."
                source == "OWN_ADVANCE" && advance.isBlank() -> "Choose a paid advance."
                description.isBlank() -> "Describe the expense and business purpose."
                value == null || !value.isFinite() || value <= 0 -> "Enter a positive amount."
                receipt == null -> "Attach the receipt."
                emergency && emergencyReason.isBlank() -> "Explain the emergency."
                else -> ""
            }
            if (error.isBlank()) {
                val bill = JSONObject().put("expense_date", date).put("account", category)
                    .put("supplier_name", supplier.trim()).put("invoice_number", invoice.trim())
                    .put("description", description.trim()).put("amount", value)
                    .put("receipt_filename", receipt!!.name).put("receipt_content", receipt!!.base64)
                val payload = JSONObject().put("project", project).put("reimbursement_source", source)
                    .put("is_emergency", if (emergency) 1 else 0)
                    .put("expenses", JSONArray().put(bill))
                if (source == "OWN_ADVANCE") payload.put("employee_advance", advance)
                if (emergency) payload.put("emergency_date", date).put("emergency_reason", emergencyReason.trim())
                submit(payload)
            }
        }, enabled = !busy && projects.isNotEmpty(), modifier = Modifier.fillMaxWidth()) { Text("Submit for receipt review") } }
        item { Text("For several invoices with different dates, submit each separately. The portal also supports a bundled submission, which is not yet in this Android app.") }
    }
}

@Composable
internal fun SelectField(label: String, selected: String, options: List<Pair<String, String>>, choose: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    val display = options.firstOrNull { it.first == selected }?.second ?: "Choose…"
    Column {
        Text(label, fontWeight = FontWeight.Medium)
        androidx.compose.foundation.layout.Box {
            OutlinedButton(onClick = { expanded = true }, modifier = Modifier.fillMaxWidth()) { Text(display, maxLines = 2) }
            DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                options.forEach { (value, name) -> DropdownMenuItem(text = { Text(name) }, onClick = { expanded = false; choose(value) }) }
            }
        }
    }
}

@Composable
internal fun DateField(label: String, value: String, set: (String) -> Unit) {
    val context = LocalContext.current
    Column {
        Text(label, fontWeight = FontWeight.Medium)
        OutlinedButton(onClick = {
            val date = runCatching { LocalDate.parse(value) }.getOrDefault(LocalDate.now())
            DatePickerDialog(context, { _, year, month, day ->
                set(LocalDate.of(year, month + 1, day).toString())
            }, date.year, date.monthValue - 1, date.dayOfMonth).show()
        }, modifier = Modifier.fillMaxWidth()) {
            Text(if (value.isBlank()) "Choose date (optional)" else runCatching { LocalDate.parse(value).format(DateTimeFormatter.ofPattern("dd MMM yyyy")) }.getOrDefault(value))
        }
    }
}

private fun readEvidence(context: Context, uri: Uri): Evidence {
    val resolver = context.contentResolver
    val name = resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
        if (cursor.moveToFirst()) cursor.getString(0) else null
    } ?: "receipt.pdf"
    val ext = name.substringAfterLast('.', "").lowercase()
    require(ext in setOf("pdf", "png", "jpg", "jpeg")) { "Choose a PDF, PNG or JPEG file." }
    val max = 5 * 1024 * 1024
    val buffer = ByteArray(8192)
    val output = ByteArrayOutputStream()
    resolver.openInputStream(uri)?.use { input ->
        while (true) {
            val count = input.read(buffer)
            if (count < 0) break
            require(output.size() + count <= max) { "Receipt must be 5 MB or smaller." }
            output.write(buffer, 0, count)
        }
    } ?: throw IllegalArgumentException("The selected file could not be opened.")
    require(output.size() > 0) { "The selected file is empty." }
    return Evidence(name, Base64.encodeToString(output.toByteArray(), Base64.NO_WRAP))
}
