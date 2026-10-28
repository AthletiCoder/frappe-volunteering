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
import androidx.compose.runtime.Composable
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
import org.sevamrita.mobile.Heading
import org.sevamrita.mobile.LabelValue
import org.sevamrita.mobile.SectionCard
import org.sevamrita.mobile.data.display
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text
import org.sevamrita.mobile.money

@Composable
fun OpeningBalancesScreen(state: PortalState, model: PortalViewModel) {
    val workspace = state.data
    val accounts = workspace.items("accounts")
    var account by remember(workspace) { mutableStateOf("") }
    var date by remember(workspace) { mutableStateOf(workspace.text("default_opening_date")) }
    var amount by remember(workspace) { mutableStateOf("") }
    var side by remember(workspace) { mutableStateOf("Debit") }
    var partyType by remember(workspace) { mutableStateOf("") }
    var party by remember(workspace) { mutableStateOf("") }
    var source by remember(workspace) { mutableStateOf("") }
    var confirmed by remember(workspace) { mutableStateOf(false) }
    var error by remember(workspace) { mutableStateOf("") }
    val attachments = remember(workspace) { mutableStateListOf<Evidence>() }
    val context = LocalContext.current
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) runCatching { readEvidence(context, uri) }
            .onSuccess { if (attachments.size < 3) attachments.add(it) else error = "Attach no more than three documents." }
            .onFailure { error = it.message ?: "Unable to read proof document." }
    }
    val selectedAccount = accounts.firstOrNull { it.text("name") == account }
    val accountType = selectedAccount?.text("account_type").orEmpty()
    val needsParty = accountType == "Receivable" || accountType == "Payable"
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading("Opening balances", "One verified starting amount per account and party") }
        item { SectionCard {
            LabelValue("Company", workspace.display("company"))
            LabelValue("Current FY opening date", workspace.display("default_opening_date"))
            LabelValue("Temporary Opening balance", money(workspace.optDouble("temporary_balance")))
            Text("Opening balances are accounting entries. The offset stays in Temporary Opening until all opening positions are reconciled.", color = Color(0xFF637378))
        } }
        item { SectionCard {
            Text("Record a starting amount", fontWeight = FontWeight.Bold)
            SelectField("Ledger account *", account, accounts.map { it.text("name") to "${it.display("account_name")} · ${it.display("root_type")}" }) {
                account = it; partyType = ""; party = ""
            }
            DateField("Opening date *", date) { date = it }
            OutlinedTextField(amount, { amount = it }, label = { Text("Amount (INR) *") },
                singleLine = true, modifier = Modifier.fillMaxWidth())
            SelectField("Balance side *", side, listOf("Debit" to "Debit — asset or amount owed to us", "Credit" to "Credit — liability or fund")) { side = it }
            if (needsParty) {
                val allowedTypes = if (accountType == "Receivable") listOf("Customer", "Employee") else listOf("Supplier", "Employee")
                SelectField("Party type *", partyType, allowedTypes.map { it to it }) {
                    partyType = it; party = ""; model.loadOpeningParties(it)
                }
                if (partyType.isNotBlank()) SelectField("Party *", party,
                    state.form.items("parties").map { it.text("value") to it.display("label") }) { party = it }
            }
            OutlinedTextField(source, { source = it }, label = { Text("Source reference *") },
                supportingText = { Text("For example, the 31 March closing trial balance or bank statement.") },
                modifier = Modifier.fillMaxWidth())
            if (attachments.isNotEmpty()) attachments.forEach { proof ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(proof.name, modifier = Modifier.weight(1f))
                    OutlinedButton(onClick = { attachments.remove(proof) }) { Text("Remove") }
                }
            }
            if (attachments.size < 3) OutlinedButton(onClick = { picker.launch(arrayOf("application/pdf", "image/png", "image/jpeg")) },
                modifier = Modifier.fillMaxWidth()) { Text("Attach proof (optional)") }
            val value = amount.toDoubleOrNull()
            if (account.isNotBlank() && value != null && value > 0) {
                LabelValue(side, "${selectedAccount?.display("account_name") ?: account} · ${money(value)}")
                LabelValue(if (side == "Debit") "Credit" else "Debit", "Temporary Opening · ${money(value)}")
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(confirmed, { confirmed = it })
                Text("I checked this amount, date and account against the source record.")
            }
            if (error.isNotBlank()) Text(error, color = Color(0xFF9B2D25))
            Button(onClick = {
                error = when {
                    account.isBlank() || date.isBlank() || source.isBlank() -> "Choose an account and date, and enter the source reference."
                    value == null || !value.isFinite() || value <= 0 -> "Enter a positive amount."
                    needsParty && (partyType.isBlank() || party.isBlank()) -> "Choose the party for this receivable or payable."
                    !confirmed -> "Confirm that you checked the source record."
                    else -> ""
                }
                if (error.isBlank()) {
                    val files = JSONArray()
                    attachments.forEach { files.put(JSONObject().put("file_name", it.name).put("content", it.base64)) }
                    model.recordOpeningBalance(JSONObject().put("account", account).put("opening_date", date)
                        .put("side", side).put("amount", value).put("party_type", if (needsParty) partyType else "")
                        .put("party", if (needsParty) party else "").put("source_reference", source)
                        .put("attachments", files))
                }
            }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Post opening balance") }
        } }
        item { Text("Opening amounts already recorded", fontWeight = FontWeight.Bold) }
        items(workspace.items("history")) { entry -> SectionCard {
            Text(entry.display("name"), fontWeight = FontWeight.SemiBold)
            LabelValue("Posting date", entry.display("posting_date"))
            entry.items("rows").forEach { row ->
                Text("${row.display("account")} · ${if (row.optDouble("debit_in_account_currency") > 0) "Debit ${money(row.optDouble("debit_in_account_currency"))}" else "Credit ${money(row.optDouble("credit_in_account_currency"))}"}")
            }
            entry.items("attachments").forEach { proof ->
                OutlinedButton(onClick = { model.openReceipt(proof.text("file_url"), Page.OPENING_BALANCES) }) { Text("Open ${proof.display("file_name")}") }
            }
        } }
    }
}
