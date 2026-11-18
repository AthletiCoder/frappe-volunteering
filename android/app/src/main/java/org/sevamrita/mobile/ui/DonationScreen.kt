package org.sevamrita.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
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
    val donorSignature = remember(workspace) { SignatureState() }
    var error by remember(workspace) { mutableStateOf("") }
    val requestKey = remember(workspace) { UUID.randomUUID().toString() }
    var view by remember { mutableStateOf("list") }
    var showSettings by remember { mutableStateOf(false) }
    var showSignatory by remember { mutableStateOf(false) }
    var issuing by remember { mutableStateOf("") }
    var signatory by remember(issuing) { mutableStateOf("") }
    var want80g by remember(issuing) { mutableStateOf(false) }
    val list = state.donationList
    val filter = list.text("filter").ifBlank { "all" }
    val page = list.optInt("page", 1)
    val filters = listOf("all" to "All donations", "pending" to "Pending receipt", "issued" to "Receipt issued")
    val listState = rememberLazyListState()
    val ready = workspace.has("accounts")
    LaunchedEffect(ready) {
        if (ready && !list.has("rows")) model.loadDonations()
    }
    LaunchedEffect(view, filter, page) {
        listState.scrollToItem(0)
        issuing = ""
    }
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
    val creditRow = accounts.optJSONObject("donation_credit_by_type")?.optJSONObject("General")
    LazyColumn(Modifier.fillMaxSize(), state = listState, contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading("Donations", "Record money received and issue receipts when ready") }
        if (ready) item {
            SelectField("Donations view", view, listOf("list" to "Donations list", "record" to "Record a donation", "setup" to "Receipt setup")) {
                error = ""
                view = it
            }
        }
        if (ready && view == "list") {
            item {
                SelectField("Receipt status", filter, filters) {
                    if (!state.busy && it != filter) model.loadDonations(it)
                }
            }
            if (list.has("rows") && list.items("rows").isEmpty()) item { Text("No donations match this view.") }
            if (!list.has("rows") && !state.busy) item {
                OutlinedButton(onClick = { model.loadDonations(filter) }) { Text("Load donations") }
            }
            items(list.items("rows"), key = { it.text("name") }) { row -> SectionCard {
                Text(row.display("full_name"), fontWeight = FontWeight.SemiBold)
                LabelValue("Received", "${money(row.optDouble("amount"))} · ${row.display("received_on")}")
                if (row.text("payment_method").isNotBlank()) LabelValue("Method", row.text("payment_method"))
                if (row.text("journal_entry").isNotBlank()) LabelValue("Journal Entry", row.text("journal_entry"))
                when (row.text("receipt_status")) {
                    "issued" -> {
                        LabelValue("Receipt", row.text("receipt_number"))
                        TextButton(onClick = { model.openReceipt(row.text("receipt_file"), Page.DONATIONS) }, enabled = !state.busy) {
                            Text("Open private receipt")
                        }
                    }
                    "pending" -> {
                        Text("Pending receipt")
                        if (issuing != row.text("name")) {
                            OutlinedButton(onClick = { issuing = row.text("name") }, enabled = !state.busy) { Text("Issue receipt") }
                        } else if (signatories.isEmpty()) {
                            Text("Register an authorised signature in Receipt setup first.")
                            TextButton(onClick = { view = "setup" }) { Text("Open Receipt setup") }
                        } else {
                            SelectField("Authorised Sevamrita signatory *", signatory,
                                signatories.map { it.text("name") to "${it.display("signatory_name")} · ${it.display("designation")}" }
                            ) { signatory = it }
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Checkbox(want80g, { want80g = it }, enabled = !state.busy)
                                Text("Include verified 80G registration on this acknowledgement")
                            }
                            Button(
                                onClick = { model.issueDonationReceipt(row.text("name"), signatory, want80g) },
                                enabled = !state.busy && signatory.isNotBlank(),
                                modifier = Modifier.fillMaxWidth()
                            ) { Text("Issue signed PDF") }
                            TextButton(onClick = { issuing = "" }, enabled = !state.busy) { Text("Cancel") }
                        }
                    }
                    else -> Text(if (row.text("donation_purpose") == "CSR") "Historical CSR · no receipt expected" else "Receipt unavailable")
                }
            } }
            if (page > 1 || list.optBoolean("has_more")) item {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    TextButton(onClick = { model.loadDonations(filter, page - 1) }, enabled = page > 1 && !state.busy) { Text("Previous") }
                    Text("Page $page")
                    TextButton(onClick = { model.loadDonations(filter, page + 1) }, enabled = list.optBoolean("has_more") && !state.busy) { Text("Next") }
                }
            }
        }
        if (ready && view == "record") {
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
                    listOf("Individual", "Organisation").map { it to it }) { donorType = it; donorId = "" }
                OutlinedTextField(address, { address = it; donorId = "" }, label = { Text("Full postal address *") },
                    minLines = 2, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(pan, { pan = it.uppercase(); donorId = "" }, label = { Text("PAN *") },
                    singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(phone, { phone = it; donorId = "" }, label = { Text("Phone number (optional)") },
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
                if (method == "Cash") SignaturePad("Cash donor signature *", donorSignature)
                Text("You can issue a signed receipt later from the donations list.", color = Color(0xFF637378))
                if (error.isNotBlank()) Text(error, color = Color(0xFF9B2D25))
                Button(onClick = {
                    val value = amount.toDoubleOrNull()
                    val signed = if (method == "Cash") donorSignature.imageData() else null
                    error = when {
                        donorName.isBlank() || address.isBlank() || pan.isBlank() -> "Enter donor name, address and PAN."
                        value == null || !value.isFinite() || value <= 0 -> "Enter a positive donation amount."
                        date.isBlank() || receivedInto.isBlank() -> "Enter the received date and destination ledger."
                        method != "Cash" && reference.isBlank() -> "Enter the bank/cheque transaction reference."
                        method == "Cheque" && !cleared -> "Only register a cheque after it has cleared."
                        method == "Cash" && signed == null -> "Ask the donor to sign on screen."
                        creditRow == null -> "The donation credit ledger is not configured."
                        else -> ""
                    }
                    if (error.isBlank()) {
                        val payload = JSONObject().put("request_key", requestKey)
                            .put("donor_name", donorName).put("donor_type", donorType).put("address", address)
                            .put("pan", pan).put("mobile_number", phone).put("email", email)
                            .put("amount", value).put("received_on", date).put("payment_method", method)
                            .put("payment_reference", if (method == "Cash") "" else reference)
                            .put("cheque_cleared", if (method == "Cheque") cleared else false)
                            .put("received_into_account", receivedInto)
                        if (donorId.isNotBlank()) payload.put("donor", donorId)
                        if (signed != null) payload.put("donor_signature_data", signed)
                        model.registerDonation(payload) { view = "list" }
                    }
                }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Record donation") }
            } }
        }
        if (ready && view == "setup") {
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
            if (error.isNotBlank()) item { Text(error, color = Color(0xFF9B2D25)) }
        }
    }
}
