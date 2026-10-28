package org.sevamrita.mobile.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
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

private class CorrectedItem(row: JSONObject) {
    val id = row.text("name")
    val currentReceipt = row.text("receipt_attachment")
    var date by mutableStateOf(row.text("expense_date"))
    var category by mutableStateOf(row.text("account"))
    var supplier by mutableStateOf(row.text("supplier_name"))
    var invoiceNumber by mutableStateOf(row.text("invoice_number"))
    var description by mutableStateOf(row.text("description"))
    var amount by mutableStateOf(row.text("amount"))
    var replacement by mutableStateOf<Evidence?>(null)
}

@Composable
fun CorrectClaimScreen(state: PortalState, model: PortalViewModel) {
    val claim = state.data
    val context = LocalContext.current
    val rows = remember(claim) { mutableStateListOf<CorrectedItem>().apply { addAll(claim.items("expenses").map(::CorrectedItem)) } }
    var picking by remember(claim) { mutableStateOf("") }
    var note by remember(claim) { mutableStateOf("") }
    var error by remember(claim) { mutableStateOf("") }
    val bundled = claim.text("expense_submission_id").isNotBlank()
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) try { rows.firstOrNull { it.id == picking }?.replacement = readEvidence(context, uri); error = "" }
        catch (exception: Exception) { error = exception.message ?: "Could not read the replacement receipt." }
    }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading("Correct ${state.detailId}", "Review every item and send the claim through receipt verification again") }
        if (claim.text("receipt_review_notes").isNotBlank()) item { SectionCard { LabelValue("Why correction was requested", claim.text("receipt_review_notes")) } }
        items(rows, key = { it.id }) { row -> SectionCard {
            Text("Expense item", fontWeight = FontWeight.Bold)
            DateField("Date on invoice *", row.date) { row.date = it }
            SelectField("Expense break-up *", row.category,
                claim.items("account_options").map { it.text("value") to it.display("label") }) { row.category = it }
            OutlinedTextField(row.supplier, { row.supplier = it }, label = { Text("Supplier / payee") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(row.invoiceNumber, { row.invoiceNumber = it }, label = { Text("Invoice number") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(row.description, { row.description = it }, label = { Text("Description and business purpose *") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(row.amount, { row.amount = it }, label = { Text("Amount (INR) *") }, modifier = Modifier.fillMaxWidth())
            if (!bundled || row == rows.first()) OutlinedButton(onClick = {
                picking = row.id; picker.launch(arrayOf("application/pdf", "image/png", "image/jpeg"))
            }, modifier = Modifier.fillMaxWidth()) { Text(row.replacement?.let { "Replacement: ${it.name}" } ?: "Replace private receipt") }
            if (row.currentReceipt.isNotBlank()) Text("Current receipt remains unless replaced.")
        } }
        item { SectionCard {
            OutlinedTextField(note, { note = it }, label = { Text("What did you correct? (optional)") }, modifier = Modifier.fillMaxWidth())
            if (error.isNotBlank()) Text(error, color = Color(0xFF9B2D25))
            Button(onClick = {
                error = when {
                    rows.isEmpty() -> "No expense items found."
                    rows.any { it.category.isBlank() || it.description.isBlank() || (it.amount.toDoubleOrNull() ?: 0.0) <= 0 } -> "Complete each category, description and positive amount."
                    rows.any { runCatching { LocalDate.parse(it.date) > LocalDate.now() }.getOrDefault(true) } -> "Enter valid invoice dates, not in the future."
                    rows.any { it.currentReceipt.isBlank() && it.replacement == null } -> "Every item needs a receipt."
                    bundled && rows.map { it.date }.distinct().size != 1 -> "All items on this invoice must have one invoice date."
                    else -> ""
                }
                if (error.isBlank()) {
                    val items = JSONArray()
                    rows.forEach { row ->
                        val item = JSONObject().put("name", row.id).put("expense_date", row.date)
                            .put("account", row.category).put("supplier_name", row.supplier.trim())
                            .put("invoice_number", row.invoiceNumber.trim()).put("description", row.description.trim())
                            .put("amount", row.amount.toDouble())
                        row.replacement?.let { item.put("receipt_filename", it.name).put("receipt_content", it.base64) }
                        items.put(item)
                    }
                    model.resubmitCorrection(JSONObject().put("expenses", items).put("correction_note", note.trim()))
                }
            }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Resubmit for receipt review") }
        } }
    }
}
