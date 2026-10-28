package org.sevamrita.mobile.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
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
import org.json.JSONObject
import org.sevamrita.mobile.Heading
import org.sevamrita.mobile.LabelValue
import org.sevamrita.mobile.SectionCard
import org.sevamrita.mobile.data.display
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text
import org.sevamrita.mobile.money

private val muted = Color(0xFF637378)
private val warning = Color(0xFF9B2D25)

@Composable
fun BankAccountScreen(state: PortalState, model: PortalViewModel) {
    val workspace = state.data
    val context = LocalContext.current
    var holder by remember(workspace) { mutableStateOf("") }
    var bank by remember(workspace) { mutableStateOf("") }
    var branch by remember(workspace) { mutableStateOf("") }
    var accountType by remember(workspace) { mutableStateOf("Savings") }
    var number by remember(workspace) { mutableStateOf("") }
    var confirmation by remember(workspace) { mutableStateOf("") }
    var ifsc by remember(workspace) { mutableStateOf("") }
    var swift by remember(workspace) { mutableStateOf("") }
    var proof by remember(workspace) { mutableStateOf<Evidence?>(null) }
    var ownership by remember(workspace) { mutableStateOf(false) }
    var error by remember(workspace) { mutableStateOf("") }
    var reviewRequest by remember { mutableStateOf<JSONObject?>(null) }
    var reviewAction by remember { mutableStateOf("") }
    var reviewComments by remember { mutableStateOf("") }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) runCatching { readEvidence(context, uri) }
            .onSuccess { proof = it; error = "" }
            .onFailure { error = it.message ?: "Unable to read bank proof." }
    }
    if (reviewRequest != null) AlertDialog(onDismissRequest = { reviewRequest = null },
        title = { Text("${reviewAction.replaceFirstChar { it.uppercase() }} bank details?") },
        text = { Column {
            Text("${reviewRequest?.display("employee_name")} · ${reviewRequest?.display("bank_name")}")
            OutlinedTextField(reviewComments, { reviewComments = it }, label = { Text("Review comments${if (reviewAction == "approve") " (optional)" else " *"}") },
                minLines = 2, modifier = Modifier.fillMaxWidth())
        } },
        confirmButton = { TextButton(onClick = {
            if (reviewAction != "approve" && reviewComments.isBlank()) error = "Enter a reason for return or rejection."
            else { model.reviewBankAccount(reviewRequest!!, reviewAction, reviewComments); reviewRequest = null; reviewComments = "" }
        }) { Text("Confirm") } },
        dismissButton = { TextButton(onClick = { reviewRequest = null }) { Text("Cancel") } })
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading("Reimbursement bank account", "Employees submit; Accounts Managers verify and approve") }
        val approved = workspace.optJSONObject("approved")
        if (approved != null) item { SectionCard {
            Text("Approved account", fontWeight = FontWeight.Bold)
            LabelValue("Bank", approved.display("bank_name"))
            LabelValue("Account", approved.display("account_number_masked"))
            LabelValue("IFSC", approved.display("ifsc"))
        } }
        if (workspace.optBoolean("can_submit")) item { SectionCard {
            Text("Submit new details", fontWeight = FontWeight.Bold)
            Text("A replacement stays pending until Accounts approves it. Bank proof is stored privately.", color = muted)
            if (workspace.items("requests").any { it.text("request_status") == "Pending" })
                Text("A request is already pending review.", color = warning)
            else {
                OutlinedTextField(holder, { holder = it }, label = { Text("Account holder *") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(bank, { bank = it }, label = { Text("Bank name *") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(branch, { branch = it }, label = { Text("Branch (optional)") }, modifier = Modifier.fillMaxWidth())
                SelectField("Account type *", accountType, listOf("Savings", "Current").map { it to it }) { accountType = it }
                OutlinedTextField(number, { number = it }, label = { Text("Account number *") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(confirmation, { confirmation = it }, label = { Text("Confirm account number *") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(ifsc, { ifsc = it.uppercase() }, label = { Text("IFSC *") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(swift, { swift = it.uppercase() }, label = { Text("SWIFT (optional)") }, modifier = Modifier.fillMaxWidth())
                OutlinedButton(onClick = { picker.launch(arrayOf("application/pdf", "image/png", "image/jpeg")) },
                    modifier = Modifier.fillMaxWidth()) { Text(proof?.name ?: "Attach private bank proof *") }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(ownership, { ownership = it })
                    Text("This is my account and the proof is correct.")
                }
                if (error.isNotBlank()) Text(error, color = warning)
                Button(onClick = {
                    error = when {
                        holder.isBlank() || bank.isBlank() || ifsc.isBlank() || number.isBlank() -> "Complete all required bank fields."
                        number.filterNot { it == ' ' || it == '-' } != confirmation.filterNot { it == ' ' || it == '-' } -> "Account numbers do not match."
                        proof == null -> "Attach bank proof."
                        !ownership -> "Confirm ownership of this account."
                        else -> ""
                    }
                    if (error.isBlank()) model.submitBankAccount(JSONObject()
                        .put("account_holder_name", holder).put("bank_name", bank).put("branch", branch)
                        .put("account_type", accountType).put("account_number", number)
                        .put("account_number_confirmation", confirmation).put("ifsc", ifsc).put("swift", swift)
                        .put("proof_filename", proof!!.name).put("proof_content", proof!!.base64)
                        .put("ownership_confirmed", 1))
                }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Submit for approval") }
            }
        } }
        if (workspace.items("requests").isNotEmpty()) {
            item { Text("Your request history", fontWeight = FontWeight.Bold) }
            items(workspace.items("requests")) { row -> SectionCard {
                Text("${row.display("bank_name")} · ${row.display("account_number_masked")}", fontWeight = FontWeight.SemiBold)
                LabelValue("Status", row.display("request_status"))
                if (row.text("review_comments").isNotBlank()) Text(row.text("review_comments"), color = muted)
            } }
        }
        if (workspace.optBoolean("can_review")) {
            item { Text("Pending Accounts review", fontWeight = FontWeight.Bold) }
            items(workspace.items("pending_requests")) { row -> SectionCard {
                Text(row.display("employee_name"), fontWeight = FontWeight.SemiBold)
                LabelValue("Bank", row.display("bank_name"))
                LabelValue("Account", row.display("account_number_masked"))
                LabelValue("IFSC", row.display("ifsc"))
                if (row.text("proof_url").isNotBlank()) TextButton(onClick = { model.openReceipt(row.text("proof_url"), Page.BANK_ACCOUNT) }) { Text("View private proof") }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("approve", "return", "reject").forEach { action ->
                        OutlinedButton(onClick = { reviewRequest = row; reviewAction = action }) { Text(action.replaceFirstChar { it.uppercase() }) }
                    }
                }
            } }
        }
    }
}

@Composable
fun OfficeAddressesScreen(state: PortalState, model: PortalViewModel) {
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading("Office addresses", state.data.display("company")) }
        if (state.data.optBoolean("can_manage")) item {
            Button(onClick = { model.openOfficeAddress() }, modifier = Modifier.fillMaxWidth()) { Text("Add office address") }
        }
        items(state.data.items("addresses")) { row -> SectionCard {
            Text(row.display("address_title"), fontWeight = FontWeight.Bold)
            Text(listOf("address_line1", "address_line2", "city", "county", "state", "pincode", "country")
                .map { row.text(it) }.filter { it.isNotBlank() }.joinToString(", "))
            Text("${row.display("address_type")}${if (row.optInt("is_primary_address") == 1) " · Registered/primary" else ""}", color = muted)
            if (state.data.optBoolean("can_manage")) TextButton(onClick = { model.openOfficeAddress(row) }) { Text("Edit address") }
        } }
        if (state.data.items("addresses").isEmpty() && !state.busy) item { SectionCard { Text("No office addresses found.") } }
    }
}

@Composable
fun OfficeAddressFormScreen(state: PortalState, model: PortalViewModel) {
    val original = state.form
    var title by remember(original) { mutableStateOf(original.text("address_title")) }
    var type by remember(original) { mutableStateOf(original.text("address_type").ifBlank { "Office" }) }
    var line1 by remember(original) { mutableStateOf(original.text("address_line1")) }
    var line2 by remember(original) { mutableStateOf(original.text("address_line2")) }
    var city by remember(original) { mutableStateOf(original.text("city")) }
    var county by remember(original) { mutableStateOf(original.text("county")) }
    var region by remember(original) { mutableStateOf(original.text("state")) }
    var country by remember(original) { mutableStateOf(original.text("country").ifBlank { "India" }) }
    var pin by remember(original) { mutableStateOf(original.text("pincode")) }
    var email by remember(original) { mutableStateOf(original.text("email_id")) }
    var phone by remember(original) { mutableStateOf(original.text("phone")) }
    var primary by remember(original) { mutableStateOf(original.optInt("is_primary_address") == 1) }
    var shipping by remember(original) { mutableStateOf(original.optInt("is_shipping_address") == 1) }
    var disabled by remember(original) { mutableStateOf(original.optInt("disabled") == 1) }
    var error by remember(original) { mutableStateOf("") }
    var deleting by remember(original) { mutableStateOf(false) }
    if (deleting) AlertDialog(onDismissRequest = { deleting = false },
        title = { Text("Delete office address?") },
        text = { Text("This removes the address from invoice choices. Existing documents keep their recorded address.") },
        confirmButton = { TextButton(onClick = { deleting = false; model.deleteOfficeAddress() }) { Text("Delete") } },
        dismissButton = { TextButton(onClick = { deleting = false }) { Text("Cancel") } })
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading(if (original.text("name").isBlank()) "Add office address" else "Edit office address") }
        item { SectionCard {
            OutlinedTextField(title, { title = it }, label = { Text("Address title *") }, modifier = Modifier.fillMaxWidth())
            SelectField("Type *", type, state.data.optJSONArray("address_types")?.let { values ->
                (0 until values.length()).map { values.optString(it) to values.optString(it) }
            }.orEmpty()) { type = it }
            OutlinedTextField(line1, { line1 = it }, label = { Text("Address line 1 *") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(line2, { line2 = it }, label = { Text("Address line 2") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(city, { city = it }, label = { Text("City/Town *") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(county, { county = it }, label = { Text("District (optional)") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(region, { region = it }, label = { Text("State") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(country, { country = it }, label = { Text("Country *") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(pin, { pin = it }, label = { Text("PIN code") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(email, { email = it }, label = { Text("Email (optional)") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(phone, { phone = it }, label = { Text("Phone (optional)") }, modifier = Modifier.fillMaxWidth())
            Row(verticalAlignment = Alignment.CenterVertically) { Checkbox(primary, { primary = it }); Text("Primary address") }
            Row(verticalAlignment = Alignment.CenterVertically) { Checkbox(shipping, { shipping = it }); Text("Shipping address") }
            Row(verticalAlignment = Alignment.CenterVertically) { Checkbox(disabled, { disabled = it }); Text("Disabled") }
            if (error.isNotBlank()) Text(error, color = warning)
            Button(onClick = {
                error = if (title.isBlank() || line1.isBlank() || city.isBlank() || country.isBlank()) "Complete the required address fields." else ""
                if (error.isBlank()) model.saveOfficeAddress(JSONObject()
                    .put("address_title", title).put("address_type", type).put("address_line1", line1)
                    .put("address_line2", line2).put("city", city).put("county", county).put("state", region)
                    .put("country", country).put("pincode", pin).put("email_id", email).put("phone", phone)
                    .put("is_primary_address", primary).put("is_shipping_address", shipping).put("disabled", disabled))
            }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Save address") }
            if (original.text("name").isNotBlank()) OutlinedButton(onClick = { deleting = true },
                enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Delete address") }
        } }
    }
}

@Composable
fun TeamScreen(state: PortalState, model: PortalViewModel) {
    var selected by remember { mutableStateOf<JSONObject?>(null) }
    var reason by remember { mutableStateOf("") }
    val target = selected
    if (target != null) AlertDialog(onDismissRequest = { selected = null },
        title = { Text(if (target.optJSONObject("advance_control")?.optBoolean("frozen") == true) "Unfreeze advances?" else "Freeze advances?") },
        text = { Column {
            Text("${target.display("employee_name")} · new requests only")
            OutlinedTextField(reason, { reason = it }, label = { Text("Reason *") }, minLines = 2)
        } },
        confirmButton = { TextButton(onClick = {
            if (reason.isNotBlank()) {
                model.setAdvanceFreeze(target.text("employee"), target.optJSONObject("advance_control")?.optBoolean("frozen") != true, reason)
                selected = null; reason = ""
            }
        }) { Text("Confirm") } },
        dismissButton = { TextButton(onClick = { selected = null }) { Text("Cancel") } })
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading("My team", "Direct reports, attendance and advance status") }
        items(state.data.items("team")) { row -> SectionCard {
            Text(row.display("employee_name"), fontWeight = FontWeight.Bold)
            Text(listOf(row.text("designation"), row.text("department"), row.text("grade")).filter { it.isNotBlank() }.joinToString(" · "), color = muted)
            val today = row.optJSONObject("attendance")?.optJSONObject("today")
            LabelValue("Attendance today", today?.display("status") ?: "Not marked")
            val requests = row.optJSONObject("requests")
            LabelValue("Pending people requests", "Leave ${requests?.optInt("leave_pending") ?: 0} · WFH ${requests?.optInt("wfh_pending") ?: 0} · Corrections ${requests?.optInt("attendance_fixes_pending") ?: 0}")
            val advances = row.items("advances")
            LabelValue("Recent advances", advances.size.toString())
            advances.take(3).forEach { advance -> Text("${advance.display("name")} · ${money(advance.optDouble("advance_amount"))} · ${advance.display("workflow_state")}") }
            val control = row.optJSONObject("advance_control")
            LabelValue("New advance requests", if (control?.optBoolean("frozen") == true) "Frozen" else "Allowed")
            if (control?.text("reason").orEmpty().isNotBlank()) Text(control!!.text("reason"), color = muted)
            OutlinedButton(onClick = { selected = row }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) {
                Text(if (control?.optBoolean("frozen") == true) "Unfreeze advance requests" else "Freeze advance requests")
            }
        } }
    }
}
