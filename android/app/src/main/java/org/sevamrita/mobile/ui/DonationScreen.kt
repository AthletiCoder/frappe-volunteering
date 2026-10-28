package org.sevamrita.mobile.ui

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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
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
import java.util.UUID

@Composable
fun DonationScreen(state: PortalState, model: PortalViewModel) {
    val workspace = state.data
    val settings = workspace.optJSONObject("settings") ?: JSONObject()
    val accounts = workspace.optJSONObject("accounts") ?: JSONObject()
    val donors = workspace.items("donors")
    val signatories = workspace.items("signatories")
    var type by remember(workspace) { mutableStateOf("General") }
    var donorName by remember(workspace) { mutableStateOf("") }
    var donorId by remember(workspace) { mutableStateOf("") }
    var donorType by remember(workspace) { mutableStateOf("Individual") }
    var address by remember(workspace) { mutableStateOf("") }
    var pan by remember(workspace) { mutableStateOf("") }
    var phone by remember(workspace) { mutableStateOf("") }
    var email by remember(workspace) { mutableStateOf("") }
    var amount by remember(workspace) { mutableStateOf("") }
    var date by remember(workspace) { mutableStateOf(workspace.text("today")) }
    var method by remember(workspace) { mutableStateOf("Online") }
    var reference by remember(workspace) { mutableStateOf("") }
    var receivedInto by remember(workspace) { mutableStateOf("") }
    var cleared by remember(workspace) { mutableStateOf(false) }
    var signatory by remember(workspace) { mutableStateOf("") }
    var want80g by remember(workspace) { mutableStateOf(false) }
    val donorSignature = remember(workspace) { SignatureState() }
    var error by remember(workspace) { mutableStateOf("") }
    val requestKey = remember(workspace) { UUID.randomUUID().toString() }
    var showSettings by remember { mutableStateOf(false) }
    var showSignatory by remember { mutableStateOf(false) }
    var organisation by remember(settings) { mutableStateOf(settings.text("organisation_name")) }
    var registeredAddress by remember(settings) { mutableStateOf(settings.text("registered_address")) }
    var contact by remember(settings) { mutableStateOf(settings.text("contact_email")) }
    var cin by remember(settings) { mutableStateOf(settings.text("cin")) }
    var orgPan by remember(settings) { mutableStateOf(settings.text("organisation_pan")) }
    var reg80g by remember(settings) { mutableStateOf(settings.text("eighty_g_number")) }
    var regValidUntil by remember(settings) { mutableStateOf(settings.text("eighty_g_valid_until")) }
    var newSignatory by remember { mutableStateOf("") }
    var designation by remember { mutableStateOf("") }
    val orgSignature = remember { SignatureState() }
    val creditRow = accounts.optJSONObject("donation_credit_by_type")?.optJSONObject(type)
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading("Register a donation", "Record money received; General donations issue a private PDF receipt") }
        item { SectionCard {
            SelectField("Donation type *", type, listOf("General" to "General donation", "CSR" to "CSR donation")) {
                type = it; donorId = ""; donorName = ""; donorType = if (it == "CSR") "Organisation" else "Individual"; want80g = false
            }
            Text(if (type == "CSR") "CSR donations post to the CSR income ledger and do not issue a receipt." else "General donations post to the general donation income ledger and issue a receipt.", color = Color(0xFF637378))
        } }
        item { SectionCard {
            Text("Donor", fontWeight = FontWeight.Bold)
            OutlinedTextField(donorName, { text ->
                donorName = text
                if (donors.firstOrNull { it.text("name") == donorId }?.text("donor_name") != text) donorId = ""
            }, label = { Text("Name *") }, modifier = Modifier.fillMaxWidth())
            donors.filter { donorName.isNotBlank() && it.text("donor_name").contains(donorName, true) }
                .take(5).forEach { row ->
                    TextButton(onClick = {
                        donorId = row.text("name"); donorName = row.text("donor_name")
                        donorType = row.text("donor_type"); address = row.text("address")
                        pan = row.text("pan"); phone = row.text("mobile_number"); email = row.text("email")
                    }) { Text("Use ${row.display("donor_name")} · ${row.display("pan")}") }
                }
            if (donorId.isNotBlank()) Text("Saved donor selected. To change details, update the donor record first.", color = Color(0xFF637378))
            SelectField("Donor type *", donorType,
                (if (type == "CSR") listOf("Organisation") else listOf("Individual", "Organisation")).map { it to it }) { donorType = it; donorId = "" }
            OutlinedTextField(address, { address = it; donorId = "" }, label = { Text("Full postal address *") },
                minLines = 2, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(pan, { pan = it.uppercase(); donorId = "" }, label = { Text("PAN *") },
                singleLine = true, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(phone, { phone = it; donorId = "" }, label = { Text(if (type == "General") "Phone number *" else "Phone number (optional)") },
                singleLine = true, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(email, { email = it; donorId = "" }, label = { Text("Email (optional)") }, modifier = Modifier.fillMaxWidth())
        } }
        item { SectionCard {
            Text("Donation and payment", fontWeight = FontWeight.Bold)
            OutlinedTextField(amount, { amount = it }, label = { Text("Amount received (INR) *") },
                singleLine = true, modifier = Modifier.fillMaxWidth())
            DateField("Date received *", date) { date = it }
            SelectField("Payment method *", method, listOf("Online", "Bank Transfer", "UPI", "Cash", "Cheque").map { it to it }) {
                method = it; receivedInto = ""
            }
            if (method != "Cash") OutlinedTextField(reference, { reference = it },
                label = { Text("Cheque/transaction reference *") }, modifier = Modifier.fillMaxWidth())
            if (method == "Cheque") Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(cleared, { cleared = it }); Text("Cheque has cleared in the bank")
            }
            SelectField("Money received into *", receivedInto,
                accounts.items("received_into").filter { it.text("account_type") == if (method == "Cash") "Cash" else "Bank" }
                    .map { it.text("name") to it.display("account_name") }) { receivedInto = it }
            LabelValue("Donation credit ledger", creditRow?.display("account_name", "Not configured") ?: "Not configured")
            if (type == "General") {
                SelectField("Authorised Sevamrita signatory *", signatory,
                    signatories.map { it.text("name") to "${it.display("signatory_name")} · ${it.display("designation")}" }) { signatory = it }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(want80g, { want80g = it }); Text("Include verified 80G registration on this receipt")
                }
                if (method == "Cash") SignaturePad("Cash donor signature *", donorSignature)
            }
            if (error.isNotBlank()) Text(error, color = Color(0xFF9B2D25))
            Button(onClick = {
                val value = amount.toDoubleOrNull()
                val signed = if (type == "General" && method == "Cash") donorSignature.imageData() else null
                error = when {
                    donorName.isBlank() || address.isBlank() || pan.isBlank() -> "Enter donor name, address and PAN."
                    type == "General" && phone.isBlank() -> "Enter the donor phone number."
                    value == null || !value.isFinite() || value <= 0 -> "Enter a positive donation amount."
                    date.isBlank() || receivedInto.isBlank() -> "Enter the received date and destination ledger."
                    method != "Cash" && reference.isBlank() -> "Enter the bank/cheque transaction reference."
                    method == "Cheque" && !cleared -> "Only register a cheque after it has cleared."
                    type == "General" && signatory.isBlank() -> "Choose a registered authorised signatory."
                    type == "General" && method == "Cash" && signed == null -> "Ask the donor to sign on screen."
                    creditRow == null -> "The donation credit ledger is not configured."
                    else -> ""
                }
                if (error.isBlank()) {
                    val payload = JSONObject().put("request_key", requestKey).put("donation_purpose", type)
                        .put("donor_name", donorName).put("donor_type", donorType).put("address", address)
                        .put("pan", pan).put("mobile_number", phone).put("email", email)
                        .put("amount", value).put("received_on", date).put("payment_method", method)
                        .put("payment_reference", if (method == "Cash") "" else reference)
                        .put("cheque_cleared", if (method == "Cheque") cleared else false)
                        .put("received_into_account", receivedInto)
                    if (donorId.isNotBlank()) payload.put("donor", donorId)
                    if (type == "General") payload.put("receipt_signatory", signatory)
                        .put("want_80g", want80g).put("donor_signature_data", signed ?: "")
                    model.registerDonation(payload)
                }
            }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Post donation${if (type == "General") " and issue receipt" else ""}") }
        } }
        item { OutlinedButton(onClick = { showSettings = !showSettings }, modifier = Modifier.fillMaxWidth()) {
            Text(if (showSettings) "Hide receipt identity" else "Set receipt identity")
        } }
        if (showSettings) item { SectionCard {
            Text("Receipt identity", fontWeight = FontWeight.Bold)
            OutlinedTextField(organisation, { organisation = it }, label = { Text("Organisation name *") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(registeredAddress, { registeredAddress = it }, label = { Text("Registered address *") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(contact, { contact = it }, label = { Text("Contact email *") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(cin, { cin = it }, label = { Text("CIN") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(orgPan, { orgPan = it.uppercase() }, label = { Text("Organisation PAN") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(reg80g, { reg80g = it }, label = { Text("80G registration number") }, modifier = Modifier.fillMaxWidth())
            DateField("80G valid until", regValidUntil) { regValidUntil = it }
            Button(onClick = { model.saveDonationSettings(JSONObject().put("organisation_name", organisation)
                .put("registered_address", registeredAddress).put("contact_email", contact).put("cin", cin)
                .put("organisation_pan", orgPan).put("eighty_g_number", reg80g)
                .put("eighty_g_valid_until", regValidUntil)) }, enabled = !state.busy,
                modifier = Modifier.fillMaxWidth()) { Text("Save receipt identity") }
        } }
        item { OutlinedButton(onClick = { showSignatory = !showSignatory }, modifier = Modifier.fillMaxWidth()) {
            Text(if (showSignatory) "Hide signatory registration" else "Register an authorised signatory")
        } }
        if (showSignatory) item { SectionCard {
            OutlinedTextField(newSignatory, { newSignatory = it }, label = { Text("Signatory name *") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(designation, { designation = it }, label = { Text("Designation *") }, modifier = Modifier.fillMaxWidth())
            SignaturePad("Authorised signature *", orgSignature)
            Button(onClick = {
                val image = orgSignature.imageData()
                if (newSignatory.isBlank() || designation.isBlank() || image == null) error = "Enter name, designation and draw the signature."
                else model.saveDonationSignatory(newSignatory, designation, image)
            }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Save signatory") }
        } }
        item { Text("Recent donations", fontWeight = FontWeight.Bold) }
        items(workspace.items("history")) { row -> SectionCard {
            Text(row.display("full_name"), fontWeight = FontWeight.SemiBold)
            LabelValue("Received", "${money(row.optDouble("amount"))} · ${row.display("received_on")}")
            Text(row.display("donation_purpose"), color = Color(0xFF637378))
            if (row.text("receipt_number").isNotBlank()) LabelValue("Receipt", row.text("receipt_number"))
            if (row.text("receipt_file").isNotBlank()) TextButton(onClick = { model.openReceipt(row.text("receipt_file"), Page.DONATIONS) }) { Text("Open private receipt") }
        } }
    }
}
