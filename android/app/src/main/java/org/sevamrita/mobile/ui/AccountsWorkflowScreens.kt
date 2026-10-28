package org.sevamrita.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.HorizontalDivider
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
import androidx.compose.ui.text.font.FontWeight
import org.json.JSONArray
import org.json.JSONObject
import org.sevamrita.mobile.LabelValue
import org.sevamrita.mobile.SectionCard
import org.sevamrita.mobile.data.display
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text
import org.sevamrita.mobile.money

private val warning = Color(0xFF9B2D25)

@Composable
private fun PaymentInputs(
    accounts: List<JSONObject>, selected: String, select: (String) -> Unit,
    postingDate: String, setPostingDate: (String) -> Unit,
    reference: String, setReference: (String) -> Unit,
    referenceDate: String, setReferenceDate: (String) -> Unit,
    label: String
) {
    val selectedType = accounts.firstOrNull { it.text("value") == selected }?.text("type")
    SelectField(label, selected, accounts.map { it.text("value") to it.display("label") }) { select(it) }
    DateField("Posting date *", postingDate, setPostingDate)
    if (selectedType == "Bank") {
        OutlinedTextField(reference, setReference, label = { Text("Bank transaction reference *") },
            modifier = Modifier.fillMaxWidth(), singleLine = true)
        DateField("Transaction reference date *", referenceDate, setReferenceDate)
    }
}

@Composable
fun AdvanceDisbursementForm(item: JSONObject, busy: Boolean, submit: (JSONObject) -> Unit) {
    val options = item.optJSONObject("payment") ?: JSONObject()
    val accounts = options.items("accounts")
    var account by remember(item) { mutableStateOf("") }
    var amount by remember(item) { mutableStateOf(item.optDouble("outstanding_to_pay").toString()) }
    var postingDate by remember(item) { mutableStateOf(options.text("posting_date")) }
    var mode by remember(item) { mutableStateOf("") }
    var reference by remember(item) { mutableStateOf("") }
    var referenceDate by remember(item) { mutableStateOf(options.text("posting_date")) }
    var confirmed by remember(item) { mutableStateOf(false) }
    var error by remember(item) { mutableStateOf("") }
    SectionCard {
        Text("Disburse approved advance", fontWeight = FontWeight.Bold)
        LabelValue("Still to disburse", money(item.optDouble("outstanding_to_pay")))
        OutlinedTextField(amount, { amount = it }, label = { Text("Amount (INR) *") },
            modifier = Modifier.fillMaxWidth(), singleLine = true)
        PaymentInputs(accounts, account, { account = it; mode = "" }, postingDate, { postingDate = it },
            reference, { reference = it }, referenceDate, { referenceDate = it }, "Pay from *")
        val accountType = accounts.firstOrNull { it.text("value") == account }?.text("type")
        val modes = options.items("modes_of_payment").filter { it.text("type") == accountType }
        SelectField("Mode of payment (optional)", mode,
            listOf("" to "Not specified") + modes.map { it.text("name") to it.display("name") }) { mode = it }
        if (accounts.firstOrNull { it.text("value") == account }?.text("type") == "Bank" && options.optJSONObject("approved_bank") == null)
            Text("The employee needs an approved bank account for a bank payment.", color = warning)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(confirmed, { confirmed = it })
            Text("I confirm the funds were actually given or transferred.")
        }
        if (error.isNotBlank()) Text(error, color = warning)
        Button(onClick = {
            val value = amount.toDoubleOrNull()
            val bank = accounts.firstOrNull { it.text("value") == account }?.text("type") == "Bank"
            error = when {
                account.isBlank() || postingDate.isBlank() -> "Choose the payment ledger and posting date."
                value == null || !value.isFinite() || value <= 0 || value > item.optDouble("outstanding_to_pay") -> "Enter an amount no greater than the approved balance."
                bank && (reference.isBlank() || referenceDate.isBlank()) -> "Enter the bank transaction reference and date."
                !confirmed -> "Confirm that the funds were actually disbursed."
                else -> ""
            }
            if (error.isBlank()) submit(JSONObject().put("amount", value).put("paid_from", account)
                .put("posting_date", postingDate).put("mode_of_payment", mode)
                .put("reference_no", if (bank) reference.trim() else "")
                .put("reference_date", if (bank) referenceDate else JSONObject.NULL))
        }, enabled = !busy, modifier = Modifier.fillMaxWidth()) { Text("Record disbursement") }
    }
}

@Composable
fun AdvanceReturnForm(item: JSONObject, busy: Boolean, submit: (JSONObject) -> Unit) {
    val options = item.optJSONObject("return_options") ?: JSONObject()
    val accounts = options.items("accounts")
    var account by remember(item) { mutableStateOf("") }
    var amount by remember(item) { mutableStateOf("") }
    var postingDate by remember(item) { mutableStateOf(options.text("posting_date")) }
    var reference by remember(item) { mutableStateOf("") }
    var referenceDate by remember(item) { mutableStateOf(options.text("posting_date")) }
    var confirmed by remember(item) { mutableStateOf(false) }
    var error by remember(item) { mutableStateOf("") }
    SectionCard {
        Text("Record unused advance returned", fontWeight = FontWeight.Bold)
        LabelValue("Maximum available to return", money(options.optDouble("maximum")))
        if (item.items("pending_claims").isNotEmpty()) Text("Resolve pending claims against this advance before recording a return.", color = warning)
        OutlinedTextField(amount, { amount = it }, label = { Text("Returned amount (INR) *") },
            modifier = Modifier.fillMaxWidth(), singleLine = true)
        PaymentInputs(accounts, account, { account = it }, postingDate, { postingDate = it },
            reference, { reference = it }, referenceDate, { referenceDate = it }, "Received into *")
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(confirmed, { confirmed = it })
            Text("I confirm the funds were actually received back.")
        }
        if (error.isNotBlank()) Text(error, color = warning)
        Button(onClick = {
            val value = amount.toDoubleOrNull()
            val bank = accounts.firstOrNull { it.text("value") == account }?.text("type") == "Bank"
            error = when {
                item.items("pending_claims").isNotEmpty() -> "Resolve pending expense claims first."
                account.isBlank() || postingDate.isBlank() -> "Choose the receiving ledger and posting date."
                value == null || !value.isFinite() || value <= 0 || value > options.optDouble("maximum") -> "Enter an amount within the remaining advance."
                bank && (reference.isBlank() || referenceDate.isBlank()) -> "Enter the bank receipt reference and date."
                !confirmed -> "Confirm that the returned funds were actually received."
                else -> ""
            }
            if (error.isBlank()) submit(JSONObject().put("amount", value).put("received_into", account)
                .put("posting_date", postingDate).put("reference_no", if (bank) reference.trim() else "")
                .put("reference_date", if (bank) referenceDate else JSONObject.NULL))
        }, enabled = !busy && item.items("pending_claims").isEmpty(), modifier = Modifier.fillMaxWidth()) { Text("Post advance return") }
    }
}

private class SplitInput(accountValue: String = "", amountValue: String = "") {
    var account by mutableStateOf(accountValue)
    var amount by mutableStateOf(amountValue)
}

@Composable
fun ClaimClassificationForm(item: JSONObject, busy: Boolean, submit: (JSONArray, String) -> Unit) {
    val classification = item.optJSONObject("classification") ?: JSONObject()
    val rows = classification.items("items")
    val accounts = classification.items("accounts")
    val splits = remember(item) { rows.associate { row ->
        val existing = row.items("allocations")
        row.text("expense_detail") to mutableStateListOf<SplitInput>().apply {
            if (existing.isEmpty()) add(SplitInput("", row.optDouble("required_amount").toString()))
            else existing.forEach { add(SplitInput(it.text("expense_account"), it.optDouble("amount").toString())) }
        }
    } }
    var note by remember(item) { mutableStateOf("") }
    var confirmed by remember(item) { mutableStateOf(false) }
    var error by remember(item) { mutableStateOf("") }
    SectionCard {
        Text("Accounts classification", fontWeight = FontWeight.Bold)
        Text("Allocate each sanctioned item across one or more expense ledgers. This posts the approved claim.")
        for (row in rows) {
            HorizontalDivider()
            Text(row.display("label"), fontWeight = FontWeight.SemiBold)
            LabelValue("Amount to classify", money(row.optDouble("required_amount")))
            val detail = row.text("expense_detail")
            val inputs = splits[detail].orEmpty()
            inputs.forEachIndexed { index, input ->
                SelectField("Expense ledger ${index + 1}", input.account,
                    accounts.map { it.text("value") to it.display("label") }) { input.account = it }
                OutlinedTextField(input.amount, { input.amount = it }, label = { Text("Allocated amount (INR)") },
                    modifier = Modifier.fillMaxWidth(), singleLine = true)
                if (inputs.size > 1) OutlinedButton(onClick = { splits[detail]?.remove(input) }) { Text("Remove this split") }
            }
            OutlinedButton(onClick = { splits[detail]?.add(SplitInput()) }, modifier = Modifier.fillMaxWidth()) {
                Text("Add another ledger")
            }
        }
        OutlinedTextField(note, { note = it }, label = { Text("Classification note (optional)") },
            modifier = Modifier.fillMaxWidth(), minLines = 2)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(confirmed, { confirmed = it })
            Text("I reviewed the receipts and ledger allocations.")
        }
        if (error.isNotBlank()) Text(error, color = warning)
        Button(onClick = {
            val output = JSONArray()
            error = ""
            for (row in rows) {
                val detail = row.text("expense_detail")
                val inputs = splits[detail].orEmpty()
                val chosen = inputs.map { it.account }
                val amounts = inputs.map { it.amount.toDoubleOrNull() }
                if (inputs.isEmpty() || chosen.any { it.isBlank() } || chosen.distinct().size != chosen.size ||
                    amounts.any { it == null || !it.isFinite() || it <= 0 } ||
                    kotlin.math.abs(amounts.filterNotNull().sum() - row.optDouble("required_amount")) >= 0.005) {
                    error = "Each item needs distinct ledgers whose amounts add up exactly to its sanctioned amount."
                    break
                }
                val allocations = JSONArray()
                inputs.forEachIndexed { index, input -> allocations.put(JSONObject()
                    .put("expense_account", input.account).put("amount", amounts[index])) }
                output.put(JSONObject().put("expense_detail", detail).put("allocations", allocations))
            }
            if (error.isBlank() && !confirmed) error = "Confirm the ledger allocation before posting."
            if (error.isBlank()) submit(output, note)
        }, enabled = !busy, modifier = Modifier.fillMaxWidth()) { Text("Finalise accounts and post claim") }
    }
}

@Composable
fun ClaimReimbursementForm(item: JSONObject, busy: Boolean, submit: (JSONObject) -> Unit) {
    val options = item.optJSONObject("payment") ?: JSONObject()
    val accounts = options.items("accounts")
    var account by remember(item) { mutableStateOf("") }
    var postingDate by remember(item) { mutableStateOf(options.text("posting_date")) }
    var mode by remember(item) { mutableStateOf("") }
    var reference by remember(item) { mutableStateOf("") }
    var referenceDate by remember(item) { mutableStateOf(options.text("posting_date")) }
    var confirmed by remember(item) { mutableStateOf(false) }
    var error by remember(item) { mutableStateOf("") }
    SectionCard {
        Text("Accounts reimbursement", fontWeight = FontWeight.Bold)
        LabelValue("Approved amount", money(item.optDouble("sanctioned_amount")))
        Text("This creates a Payment Entry. It does not initiate a bank transfer.")
        PaymentInputs(accounts, account, { account = it }, postingDate, { postingDate = it },
            reference, { reference = it }, referenceDate, { referenceDate = it }, "Pay from *")
        SelectField("Mode of payment (optional)", mode,
            listOf("" to "Not specified") + options.items("modes_of_payment")
                .map { it.text("name") to it.display("name") }) { mode = it }
        if (accounts.firstOrNull { it.text("value") == account }?.text("type") == "Bank" && options.optJSONObject("approved_bank") == null)
            Text("The employee needs an approved bank account for bank reimbursement.", color = warning)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(confirmed, { confirmed = it })
            Text("I confirm the reimbursement was actually paid.")
        }
        if (error.isNotBlank()) Text(error, color = warning)
        Button(onClick = {
            val bank = accounts.firstOrNull { it.text("value") == account }?.text("type") == "Bank"
            error = when {
                account.isBlank() || postingDate.isBlank() -> "Choose the payment ledger and posting date."
                bank && (reference.isBlank() || referenceDate.isBlank()) -> "Enter the bank transaction reference and date."
                !confirmed -> "Confirm that the reimbursement was actually paid."
                else -> ""
            }
            if (error.isBlank()) submit(JSONObject().put("paid_from", account).put("posting_date", postingDate)
                .put("mode_of_payment", mode)
                .put("reference_no", if (bank) reference.trim() else "")
                .put("reference_date", if (bank) referenceDate else JSONObject.NULL))
        }, enabled = !busy, modifier = Modifier.fillMaxWidth()) { Text("Create and submit Payment Entry") }
    }
}
