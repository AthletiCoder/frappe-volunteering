package org.sevamrita.mobile.ui

import android.util.Base64
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

private class InvoiceLine {
    var description by mutableStateOf("")
    var hsn by mutableStateOf("")
    var unit by mutableStateOf("Nos")
    var quantity by mutableStateOf("1")
    var rate by mutableStateOf("")
}

@Composable
fun InvoiceScreen(state: PortalState, model: PortalViewModel, integrated: Boolean = false) {
    val defaults = state.data
    val claimedExpense = state.form.optJSONArray("expenses")?.optJSONObject(0) ?: JSONObject()
    val supplierOptions = defaults.items("vendor_addresses")
    val officeOptions = defaults.items("office_addresses")
    var invoiceType by remember(defaults) { mutableStateOf("NON_GST") }
    var invoiceDate by remember(defaults) { mutableStateOf(if (integrated) claimedExpense.text("expense_date") else defaults.text("invoice_date")) }
    var office by remember(defaults) { mutableStateOf(defaults.text("default_office_address")) }
    var supplierName by remember(defaults) { mutableStateOf("") }
    var savedSupplier by remember(defaults) { mutableStateOf("") }
    var supplierAddress by remember(defaults) { mutableStateOf("") }
    var supplierState by remember(defaults) { mutableStateOf("") }
    var supplierPin by remember(defaults) { mutableStateOf("") }
    var supplierPan by remember(defaults) { mutableStateOf("") }
    var supplierGstin by remember(defaults) { mutableStateOf("") }
    var bankName by remember(defaults) { mutableStateOf("") }
    var bankBranch by remember(defaults) { mutableStateOf("") }
    var bankAccountName by remember(defaults) { mutableStateOf("") }
    var bankNumber by remember(defaults) { mutableStateOf("") }
    var bankIfsc by remember(defaults) { mutableStateOf("") }
    var bankSwift by remember(defaults) { mutableStateOf("") }
    var bankUpi by remember(defaults) { mutableStateOf("") }
    var transport by remember(defaults) { mutableStateOf("0") }
    var other by remember(defaults) { mutableStateOf("0") }
    var gst by remember(defaults) { mutableStateOf("0") }
    var buyerOrder by remember(defaults) { mutableStateOf("") }
    var buyerDate by remember(defaults) { mutableStateOf("") }
    var supplierReference by remember(defaults) { mutableStateOf("") }
    var dispatch by remember(defaults) { mutableStateOf("") }
    var deliveryDate by remember(defaults) { mutableStateOf("") }
    var vendorWillSign by remember(defaults) { mutableStateOf(false) }
    var vendorSigner by remember(defaults) { mutableStateOf("") }
    var reuseVolunteer by remember(defaults) { mutableStateOf(false) }
    val volunteerSignature = remember(defaults) { SignatureState() }
    val vendorSignature = remember(defaults) { SignatureState() }
    val lines = remember(defaults) { mutableStateListOf(InvoiceLine().apply {
        if (integrated) { description = claimedExpense.text("description"); rate = claimedExpense.optDouble("amount").toString() }
    }) }
    var error by remember(defaults) { mutableStateOf("") }
    val detailsKey = listOf(invoiceType, invoiceDate, office, supplierName, supplierAddress, supplierState,
        supplierPin, supplierPan, supplierGstin, bankName, bankBranch, bankAccountName, bankNumber,
        bankIfsc, bankSwift, bankUpi, transport, other, gst, buyerOrder, buyerDate,
        supplierReference, dispatch, deliveryDate, vendorWillSign.toString(), vendorSigner,
        lines.joinToString("|") { "${it.description}/${it.hsn}/${it.unit}/${it.quantity}/${it.rate}" }).joinToString("\u001f")
    LaunchedEffect(detailsKey) {
        if (reuseVolunteer || volunteerSignature.strokes.isNotEmpty() || vendorSignature.strokes.isNotEmpty()) {
            reuseVolunteer = false
            volunteerSignature.clear()
            vendorSignature.clear()
            error = "Invoice details changed. Please sign the final version again."
        }
    }
    fun payload(): JSONObject? {
        val volunteerSign = if (reuseVolunteer) defaults.text("saved_volunteer_signature") else volunteerSignature.imageData()
        val vendorSign = if (vendorWillSign) vendorSignature.imageData() else null
        error = when {
            office.isBlank() -> "Choose a Sevamrita office."
            invoiceDate.isBlank() || supplierName.isBlank() || supplierAddress.isBlank() || supplierState.isBlank() -> "Complete invoice date and supplier details."
            invoiceType == "GST" && supplierGstin.isBlank() -> "A GST supplier needs a GSTIN."
            lines.isEmpty() || lines.any { it.description.isBlank() || it.unit.isBlank() || it.quantity.toDoubleOrNull()?.let { n -> n > 0 } != true || it.rate.toDoubleOrNull()?.let { n -> n > 0 } != true } -> "Complete each item with description, unit, positive quantity and rate."
            volunteerSign.isNullOrBlank() -> "Sign as the volunteer or choose your saved signature."
            vendorWillSign && vendorSign.isNullOrBlank() -> "Ask the vendor to sign or turn off vendor signing."
            else -> ""
        }
        if (error.isNotBlank()) return null
        val items = JSONArray()
        lines.forEach { items.put(JSONObject().put("description", it.description).put("hsn_sac", it.hsn)
            .put("unit", it.unit).put("quantity", it.quantity.toDouble()).put("rate", it.rate.toDouble())) }
        val consignee = officeOptions.firstOrNull { it.text("name") == office }?.optJSONObject("party") ?: defaults.optJSONObject("consignee") ?: JSONObject()
        return JSONObject().put("invoice_type", invoiceType).put("invoice_date", invoiceDate)
            .put("consignee_address_name", office).put("consignee", consignee)
            .put("supplier", JSONObject().put("name", supplierName).put("address", supplierAddress)
                .put("state", supplierState).put("pin_code", supplierPin)
                .put("pan", supplierPan).put("gstin", supplierGstin))
            .put("bank", JSONObject().put("bank_name", bankName).put("branch", bankBranch)
                .put("account_name", bankAccountName).put("account_number", bankNumber)
                .put("ifsc", bankIfsc).put("swift", bankSwift).put("upi_id", bankUpi))
            .put("items", items).put("transportation_charges", transport.toDoubleOrNull() ?: 0.0)
            .put("other_charges", other.toDoubleOrNull() ?: 0.0)
            .put("gst_amount", if (invoiceType == "GST") gst.toDoubleOrNull() ?: 0.0 else 0.0)
            .put("buyer_order_number", buyerOrder).put("buyer_order_date", buyerDate)
            .put("supplier_reference", supplierReference).put("dispatch_document_number", dispatch)
            .put("delivery_note_date", deliveryDate).put("vendor_will_sign", vendorWillSign)
            .put("authorised_signatory", if (vendorWillSign) vendorSigner else "")
            .put("volunteer_signature_data", volunteerSign).put("vendor_signature_data", vendorSign ?: "")
    }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading(if (integrated) "Prepare signed invoice" else "Prepare an invoice",
            if (integrated) "The signed PDF will attach directly to this expense claim; no download is offered in this flow."
            else "Fill supplier details, sign on screen, then choose PDF or Word") }
        item { SectionCard {
            SelectField("Invoice type *", invoiceType, listOf("NON_GST" to "Non-GST invoice", "GST" to "GST tax invoice")) { invoiceType = it }
            if (integrated) LabelValue("Invoice date", invoiceDate)
            else DateField("Invoice date *", invoiceDate) { invoiceDate = it }
            SelectField("Sevamrita buyer and consignee office *", office,
                officeOptions.map { it.text("name") to it.display("label") }) { office = it }
        } }
        item { SectionCard {
            Text("Supplier", fontWeight = FontWeight.Bold)
            SelectField("Saved supplier (optional)", savedSupplier, listOf("" to "Enter a new supplier") + supplierOptions.map { it.text("name") to it.display("label") }) { selected ->
                savedSupplier = selected
                val row = supplierOptions.firstOrNull { it.text("name") == selected }
                val party = row?.optJSONObject("party") ?: JSONObject()
                val bank = row?.optJSONObject("bank") ?: JSONObject()
                supplierName = party.text("name"); supplierAddress = party.text("address")
                supplierState = party.text("state"); supplierPin = party.text("pin_code")
                supplierPan = party.text("pan"); supplierGstin = party.text("gstin")
                bankName = bank.text("bank_name"); bankBranch = bank.text("branch")
                bankAccountName = bank.text("account_name"); bankNumber = bank.text("account_number")
                bankIfsc = bank.text("ifsc"); bankSwift = bank.text("swift"); bankUpi = bank.text("upi_id")
            }
            OutlinedTextField(supplierName, { supplierName = it }, label = { Text("Supplier name *") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(supplierAddress, { supplierAddress = it }, label = { Text("Supplier address *") }, minLines = 2, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(supplierState, { supplierState = it }, label = { Text("State *") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(supplierPin, { supplierPin = it }, label = { Text("PIN code") }, modifier = Modifier.fillMaxWidth())
            if (invoiceType == "GST") OutlinedTextField(supplierGstin, { supplierGstin = it.uppercase() }, label = { Text("Supplier GSTIN *") }, modifier = Modifier.fillMaxWidth())
            else OutlinedTextField(supplierPan, { supplierPan = it.uppercase() }, label = { Text("Supplier PAN (optional)") }, modifier = Modifier.fillMaxWidth())
        } }
        item { SectionCard {
            Text("Supplier bank details (optional)", fontWeight = FontWeight.Bold)
            Text("When supplied, these appear on the invoice. Your reimbursement bank account is separate.", color = Color(0xFF637378))
            OutlinedTextField(bankName, { bankName = it }, label = { Text("Bank name") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(bankBranch, { bankBranch = it }, label = { Text("Branch") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(bankAccountName, { bankAccountName = it }, label = { Text("Account name") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(bankNumber, { bankNumber = it }, label = { Text("Account number") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(bankIfsc, { bankIfsc = it.uppercase() }, label = { Text("IFSC") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(bankSwift, { bankSwift = it.uppercase() }, label = { Text("SWIFT") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(bankUpi, { bankUpi = it }, label = { Text("UPI ID") }, modifier = Modifier.fillMaxWidth())
        } }
        item { Text("Items on the bill", fontWeight = FontWeight.Bold) }
        items(lines) { line -> SectionCard {
            Text("Item ${lines.indexOf(line) + 1}", fontWeight = FontWeight.SemiBold)
            OutlinedTextField(line.description, { line.description = it }, label = { Text("Description *") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(line.hsn, { line.hsn = it }, label = { Text("HSN/SAC (optional)") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(line.unit, { line.unit = it }, label = { Text("Unit *") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(line.quantity, { line.quantity = it }, label = { Text("Quantity *") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(line.rate, { line.rate = it }, label = { Text("Rate (INR) *") }, modifier = Modifier.fillMaxWidth())
            val lineTotal = (line.quantity.toDoubleOrNull() ?: 0.0) * (line.rate.toDoubleOrNull() ?: 0.0)
            LabelValue("Amount", money(lineTotal))
            if (lines.size > 1) TextButton(onClick = { lines.remove(line) }) { Text("Remove item") }
        } }
        item { OutlinedButton(onClick = { lines.add(InvoiceLine()) }, modifier = Modifier.fillMaxWidth()) { Text("Add item") } }
        item { SectionCard {
            OutlinedTextField(transport, { transport = it }, label = { Text("Transportation charges") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(other, { other = it }, label = { Text("Other charges") }, modifier = Modifier.fillMaxWidth())
            if (invoiceType == "GST") OutlinedTextField(gst, { gst = it }, label = { Text("GST amount") }, modifier = Modifier.fillMaxWidth())
            val total = lines.sumOf { (it.quantity.toDoubleOrNull() ?: 0.0) * (it.rate.toDoubleOrNull() ?: 0.0) } +
                (transport.toDoubleOrNull() ?: 0.0) + (other.toDoubleOrNull() ?: 0.0) +
                (if (invoiceType == "GST") gst.toDoubleOrNull() ?: 0.0 else 0.0)
            LabelValue("Total", money(total))
        } }
        item { SectionCard {
            Text("Optional fields, if available", fontWeight = FontWeight.Bold)
            OutlinedTextField(buyerOrder, { buyerOrder = it }, label = { Text("Buyer order number") }, modifier = Modifier.fillMaxWidth())
            DateField("Buyer order date", buyerDate) { buyerDate = it }
            OutlinedTextField(supplierReference, { supplierReference = it }, label = { Text("Supplier reference") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(dispatch, { dispatch = it }, label = { Text("Dispatch document number") }, modifier = Modifier.fillMaxWidth())
            DateField("Delivery note date", deliveryDate) { deliveryDate = it }
        } }
        item { SectionCard {
            Text("Signatures", fontWeight = FontWeight.Bold)
            Text("The volunteer confirms payment and requests reimbursement. Changing any detail before generation requires signing the final version.")
            if (defaults.text("saved_volunteer_signature").isNotBlank()) Row {
                Checkbox(reuseVolunteer, { reuseVolunteer = it }); Text("Reuse my saved signature")
            }
            if (!reuseVolunteer) SignaturePad("Volunteer signature *", volunteerSignature)
            Row { Checkbox(vendorWillSign, { vendorWillSign = it }); Text("Vendor will also sign") }
            if (vendorWillSign) {
                OutlinedTextField(vendorSigner, { vendorSigner = it }, label = { Text("Vendor signatory name") }, modifier = Modifier.fillMaxWidth())
                SignaturePad("Vendor signature *", vendorSignature)
            }
            if (error.isNotBlank()) Text(error, color = Color(0xFF9B2D25))
            if (integrated) Button(onClick = {
                payload()?.let { details ->
                    val expected = claimedExpense.optDouble("amount")
                    val actual = lines.sumOf { (it.quantity.toDoubleOrNull() ?: 0.0) * (it.rate.toDoubleOrNull() ?: 0.0) } +
                        (transport.toDoubleOrNull() ?: 0.0) + (other.toDoubleOrNull() ?: 0.0) +
                        (if (invoiceType == "GST") gst.toDoubleOrNull() ?: 0.0 else 0.0)
                    if (kotlin.math.abs(expected - actual) >= 0.01) error = "Invoice total must match the expense amount ${money(expected)}."
                    else model.submitGeneratedInvoice(details)
                }
            }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Submit signed invoice and expense for review") }
            else {
                Button(onClick = { payload()?.let { model.generateInvoice(it, "pdf") } }, enabled = !state.busy,
                    modifier = Modifier.fillMaxWidth()) { Text("Generate PDF") }
                OutlinedButton(onClick = { payload()?.let { model.generateInvoice(it, "docx") } }, enabled = !state.busy,
                    modifier = Modifier.fillMaxWidth()) { Text("Generate Word") }
            }
        } }
    }
}

@Composable
fun InvoiceResultScreen(state: PortalState, model: PortalViewModel) {
    val result = state.data
    val context = LocalContext.current
    val pdf = result.optJSONObject("pdf")
    val docx = result.optJSONObject("docx")
    var saveError by remember(result) { mutableStateOf("") }
    val pdfSaver = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/pdf")) { uri ->
        if (uri != null && pdf != null) runCatching {
            context.contentResolver.openOutputStream(uri)?.use { it.write(Base64.decode(pdf.text("content_base64"), Base64.DEFAULT)) }
                ?: error("Cannot open destination file.")
        }.onFailure { saveError = it.message ?: "Could not save PDF." }
    }
    val wordSaver = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/vnd.openxmlformats-officedocument.wordprocessingml.document")) { uri ->
        if (uri != null && docx != null) runCatching {
            context.contentResolver.openOutputStream(uri)?.use { it.write(Base64.decode(docx.text("content_base64"), Base64.DEFAULT)) }
                ?: error("Cannot open destination file.")
        }.onFailure { saveError = it.message ?: "Could not save Word document." }
    }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading("Invoice ready", result.display("invoice_number")) }
        item { SectionCard {
            LabelValue("Supplier", result.display("supplier_name"))
            LabelValue("Total", money(result.optDouble("grand_total")))
            LabelValue("Style", result.display("invoice_style"))
            if (saveError.isNotBlank()) Text(saveError, color = Color(0xFF9B2D25))
            if (pdf != null) {
                Button(onClick = model::previewGeneratedInvoice, modifier = Modifier.fillMaxWidth()) { Text("Preview PDF") }
                OutlinedButton(onClick = { pdfSaver.launch(pdf.display("filename")) }, modifier = Modifier.fillMaxWidth()) { Text("Save PDF") }
            }
            if (docx != null) OutlinedButton(onClick = { wordSaver.launch(docx.display("filename")) }, modifier = Modifier.fillMaxWidth()) { Text("Save Word document") }
            val other = if (pdf != null) "docx" else "pdf"
            OutlinedButton(onClick = { model.generateInvoice(state.form, other, result.text("generation_reference")) },
                enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Generate same invoice as ${if (other == "pdf") "PDF" else "Word"}") }
            Text("Save the file to the device before leaving. The generated document is not an Expense Claim.", color = Color(0xFF637378))
        } }
    }
}
