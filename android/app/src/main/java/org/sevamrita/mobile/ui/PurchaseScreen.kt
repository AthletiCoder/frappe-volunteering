package org.sevamrita.mobile.ui

import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import org.sevamrita.mobile.ActionRow
import org.sevamrita.mobile.Heading
import org.sevamrita.mobile.LabelValue
import org.sevamrita.mobile.SectionCard
import org.sevamrita.mobile.data.display
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.strings
import org.sevamrita.mobile.data.text
import org.sevamrita.mobile.money
import java.time.LocalDate
import java.util.UUID

internal fun purchaseTitle(view: String) = when (view) {
    "approvals" -> "Purchase approvals"
    "accounts" -> "Approved purchases"
    else -> "My purchase requests"
}

@Composable
internal fun PurchaseScreen(state: PortalState, model: PortalViewModel) {
    val workspace = state.purchaseWorkspace
    val order = state.data
    val caps = workspace.optJSONObject("capabilities") ?: JSONObject()
    val actions = order.optJSONObject("actions") ?: JSONObject()
    val today = workspace.text("today").ifBlank { LocalDate.now().toString() }
    val projectHint = state.form.text("project")
    var editor by remember(state.page, state.detailId, state.purchaseView, projectHint) { mutableStateOf("") }
    var query by remember { mutableStateOf("") }
    var reason by remember(state.detailId) { mutableStateOf("") }
    var confirmSetup by remember { mutableStateOf(false) }
    val detail = state.page == Page.PURCHASE
    LaunchedEffect(projectHint, caps.optBoolean("create")) {
        if (!detail && projectHint.isNotBlank() && caps.optBoolean("create")) editor = "order"
    }
    BackHandler(editor.isNotBlank() && !state.busy) { editor = "" }
    fun action(method: String, args: JSONObject) = model.purchaseAction(method, args) { editor = "" }
    fun updateOrder(method: String, details: JSONObject) = action(method,
        JSONObject().put("name", order.text("name")).put("details", details))
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        if (editor.isNotBlank()) {
            item { TextButton(onClick = { editor = "" }, enabled = !state.busy) { Text("Cancel") } }
            item {
                when (editor) {
                    "order" -> PurchaseOrderForm(order, workspace, projectHint, today, state.busy) { values, submit ->
                        action("save_purchase", JSONObject().put("details", values).put("submit", if (submit) 1 else 0)
                            .put("name", order.text("name").ifBlank { null }).put("modified", order.text("modified").ifBlank { null }))
                    }
                    "receive" -> PurchaseDeliveryForm(order, today, state.busy) { updateOrder("record_goods_received", it) }
                    "invoice" -> SupplierBillForm(order, workspace, today, state.busy) { updateOrder("record_supplier_invoice", it) }
                    "advance", "payment" -> VendorPaymentForm(order, workspace, today, editor == "advance", state.busy) { updateOrder("record_vendor_payment", it) }
                    "supplier", "item" -> PurchaseMasterForm(editor, workspace, state.busy) { values ->
                        action("create_purchase_master", JSONObject().put("kind", editor).put("details", values))
                    }
                }
            }
        } else if (!detail) {
            item { Heading(purchaseTitle(state.purchaseView), when (state.purchaseView) {
                "approvals" -> "Requests assigned to you for a decision"
                "accounts" -> "Record deliveries, supplier bills and payments"
                else -> "Raise purchase requests and follow their status"
            }) }
            if (caps.optBoolean("create")) item {
                Button(onClick = { editor = "order" }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("New purchase request") }
            }
            if (caps.optBoolean("manage_suppliers")) item { SectionCard {
                Text("Suppliers and items", fontWeight = FontWeight.SemiBold)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { editor = "supplier" }, enabled = !state.busy, modifier = Modifier.weight(1f)) { Text("Add supplier") }
                    OutlinedButton(onClick = { editor = "item" }, enabled = !state.busy, modifier = Modifier.weight(1f)) { Text("Add item") }
                }
                val setup = workspace.optJSONObject("advance_setup")
                if (setup?.optBoolean("can_configure") == true && !setup.optBoolean("ready")) {
                    TextButton(onClick = { confirmSetup = true }, enabled = !state.busy) { Text("Enable supplier advance accounting") }
                }
            } }
            item { PurchaseText("Find an order", query, { query = it }) }
            val orders = workspace.items("orders").filter { row ->
                listOf("name", "supplier_name", "project", "workflow_state").any { row.text(it).contains(query.trim(), true) }
            }
            if (orders.isEmpty() && !state.busy) item { SectionCard { Text("No purchases in this view.") } }
            items(orders, key = { it.text("name") }) { row ->
                ActionRow(row.display("supplier_name"), "${row.display("name")} · ${money(row.optDouble("grand_total", 0.0))} · ${row.display("workflow_state")}") {
                    if (!state.busy) model.openPurchases(state.purchaseView, row.text("name"))
                }
            }
        } else if (order.has("name")) {
            item { Heading(order.display("supplier_name"), "${order.display("project_name", order.text("project"))} · ${order.display("workflow_state")}") }
            item { SectionCard {
                LabelValue("Order total", money(order.optDouble("grand_total", 0.0)))
                LabelValue("Ordered", order.display("transaction_date"))
                LabelValue("Expected delivery", order.display("schedule_date"))
                LabelValue("Requested by", order.display("owner"))
                if (order.text("pending_approver").isNotBlank()) LabelValue("Approver", order.text("pending_approver"))
            } }
            item { SectionCard {
                Text("Order items", fontWeight = FontWeight.Bold)
                for (line in order.items("items")) {
                    LabelValue(line.display("item_name"), "${line.display("qty")} ${line.display("uom", "")} · ${money(line.optDouble("amount", 0.0))}")
                    Text("Received: ${line.display("received_qty", "0")}", style = MaterialTheme.typography.bodySmall)
                }
            } }
            val files = order.items("attachments")
            if (files.isNotEmpty()) item { SectionCard {
                Text("Supporting documents", fontWeight = FontWeight.SemiBold)
                for (file in files) TextButton(onClick = { model.openReceipt(file.text("file_url"), Page.PURCHASE) }, enabled = !state.busy) { Text(file.display("file_name")) }
            } }
            if (actions.optBoolean("edit")) item { PurchaseButton("Edit purchase request", state.busy) { editor = "order" } }
            if (actions.optBoolean("review")) item { SectionCard {
                Text("Review decision", fontWeight = FontWeight.Bold)
                PurchaseText("Review note", reason, { reason = it })
                val transitions = actions.strings("transitions")
                val flags = actions.optJSONObject("approval_flags")
                for (decision in listOf("Approve", "Reject", "Escalate")) {
                    if (decision in transitions || (decision == "Escalate" && flags?.optBoolean("can_escalate") == true)) {
                        Button(onClick = { action("review_purchase", JSONObject().put("name", order.text("name"))
                            .put("modified", order.text("modified")).put("action", decision).put("reason", reason)) },
                            enabled = !state.busy && (decision == "Approve" || reason.isNotBlank()), modifier = Modifier.fillMaxWidth()) { Text(decision) }
                    }
                }
            } }
            if (actions.optBoolean("receive")) item { PurchaseButton("Record goods received", state.busy) { editor = "receive" } }
            if (actions.optBoolean("invoice")) item { PurchaseButton("Record supplier bill", state.busy) { editor = "invoice" } }
            val invoices = order.items("invoices")
            if (actions.optBoolean("pay")) {
                if (invoices.isEmpty() && workspace.optJSONObject("advance_setup")?.optBoolean("ready") == true &&
                    order.optDouble("grand_total", 0.0) > order.optDouble("advance_paid", 0.0)) {
                    item { PurchaseButton("Record supplier advance", state.busy) { editor = "advance" } }
                }
                if (invoices.any { it.optDouble("outstanding_amount", 0.0) > 0 }) {
                    item { PurchaseButton("Record bill payment", state.busy) { editor = "payment" } }
                }
            }
            val receipts = order.items("receipts")
            if (receipts.isNotEmpty()) item { SectionCard {
                Text("Deliveries", fontWeight = FontWeight.Bold)
                for (receipt in receipts) LabelValue(receipt.display("name"), receipt.display("posting_date"))
            } }
            if (invoices.isNotEmpty()) item { SectionCard {
                Text("Supplier bills", fontWeight = FontWeight.Bold)
                for (bill in invoices) {
                    LabelValue(bill.display("bill_no"), "${bill.display("bill_date")} · ${money(bill.optDouble("grand_total", 0.0))}")
                    LabelValue("Outstanding", money(bill.optDouble("outstanding_amount", 0.0)))
                    bill.optJSONObject("tax_breakup")?.let { LabelValue("Included tax", money(it.optDouble("tax_total", 0.0))) }
                }
            } }
            if (order.items("payments").isNotEmpty()) item { SectionCard {
                Text("Recorded payments", fontWeight = FontWeight.Bold)
                for (payment in order.items("payments")) LabelValue(payment.display("posting_date"), money(payment.optDouble("paid_amount", 0.0)))
            } }
        }
    }
    if (confirmSetup) AlertDialog(onDismissRequest = { confirmSetup = false }, title = { Text("Enable supplier advance accounting?") },
        text = { Text("This will configure the Vendor Advances ledger for future payments.") },
        confirmButton = { TextButton(onClick = { confirmSetup = false; action("configure_vendor_advances", JSONObject()) }) { Text("Enable") } },
        dismissButton = { TextButton(onClick = { confirmSetup = false }) { Text("Cancel") } })
}

private class PurchaseLine(row: JSONObject = JSONObject()) {
    var item by mutableStateOf(row.text("item_code"))
    var description by mutableStateOf(plainPurchaseText(row.text("description")))
    var qty by mutableStateOf(row.text("qty").ifBlank { "1" })
    var rate by mutableStateOf(row.text("rate"))
    var warehouse by mutableStateOf(row.text("warehouse"))
}

@Composable
private fun PurchaseOrderForm(order: JSONObject, workspace: JSONObject, projectHint: String, today: String, busy: Boolean,
    save: (JSONObject, Boolean) -> Unit) {
    val requestKey = remember { UUID.randomUUID().toString() }
    var project by remember { mutableStateOf(order.text("project").ifBlank { projectHint }) }
    var supplier by remember { mutableStateOf(order.text("supplier")) }
    var date by remember { mutableStateOf(order.text("transaction_date").ifBlank { today }) }
    var delivery by remember { mutableStateOf(order.text("schedule_date").ifBlank { today }) }
    var terms by remember { mutableStateOf(plainPurchaseText(order.text("terms"))) }
    var proof by remember { mutableStateOf<Evidence?>(null) }
    var reading by remember { mutableStateOf(false) }
    val lines = remember { mutableStateListOf<PurchaseLine>().apply {
        addAll(order.items("items").map { PurchaseLine(it) }.ifEmpty { listOf(PurchaseLine()) })
    } }
    val masters = workspace.items("items")
    val legacyTax = order.has("prices_include_tax") && !order.optBoolean("prices_include_tax")
    SectionCard {
        Heading(if (order.has("name")) "Edit purchase request" else "New purchase request")
        PurchaseSelect("Project", project, workspace.options("projects", "label", "value")) { project = it }
        PurchaseSelect("Supplier", supplier, workspace.options("suppliers", "supplier_name")) { supplier = it }
        DateField("Order date", date) { date = it }
        DateField("Expected delivery", delivery) { delivery = it }
        PurchaseText("Terms or notes (optional)", terms, { terms = it })
    }
    Spacer(Modifier.height(12.dp))
    for ((index, line) in lines.withIndex()) key(line) {
        SectionCard {
            Text("Item ${index + 1}", fontWeight = FontWeight.Bold)
            PurchaseSelect("Purchase item", line.item, workspace.options("items", "item_name")) { picked ->
                line.item = picked
                line.warehouse = ""
            }
            PurchaseText("Description (optional)", line.description, { line.description = it })
            PurchaseText("Quantity", line.qty, { line.qty = it }, numeric = true)
            PurchaseText(if (legacyTax) "Unit price" else "Unit price including taxes (INR)", line.rate, { line.rate = it }, numeric = true)
            if (masters.firstOrNull { it.text("name") == line.item }?.optInt("is_stock_item") == 1) {
                PurchaseSelect("Receiving warehouse", line.warehouse, workspace.options("warehouses", "warehouse_name")) { line.warehouse = it }
            }
            if (lines.size > 1) TextButton(onClick = { lines.remove(line) }, enabled = !busy) { Text("Remove item") }
        }
        Spacer(Modifier.height(10.dp))
    }
    SectionCard {
        TextButton(onClick = { lines.add(PurchaseLine()) }, enabled = !busy && lines.size < 50) { Text("Add item") }
        LabelValue(if (legacyTax) "Items total" else "Total including taxes", money(lines.sumOf { (it.qty.toDoubleOrNull() ?: 0.0) * (it.rate.toDoubleOrNull() ?: 0.0) }))
        PurchaseProof("Quotation (optional)", proof, busy, { proof = it }, { reading = it })
        val ready = project.isNotBlank() && supplier.isNotBlank() && delivery >= date && lines.all {
            it.item.isNotBlank() && positive(it.qty) && positive(it.rate) &&
                (masters.firstOrNull { row -> row.text("name") == it.item }?.optInt("is_stock_item") != 1 || it.warehouse.isNotBlank())
        }
        fun send(submit: Boolean) = save(JSONObject().put("request_key", requestKey).put("project", project).put("supplier", supplier)
            .put("transaction_date", date).put("schedule_date", delivery).put("terms", terms).put("proof", proof?.json())
            .put("items", JSONArray(lines.map { JSONObject().put("item_code", it.item).put("description", it.description)
                .put("qty", it.qty.toDouble()).put("rate", it.rate.toDouble()).put("warehouse", it.warehouse) })), submit)
        OutlinedButton(onClick = { send(false) }, enabled = ready && !busy && !reading, modifier = Modifier.fillMaxWidth()) { Text("Save draft") }
        Button(onClick = { send(true) }, enabled = ready && !busy && !reading, modifier = Modifier.fillMaxWidth()) { Text("Submit for approval") }
    }
}

@Composable
private fun PurchaseDeliveryForm(order: JSONObject, today: String, busy: Boolean, save: (JSONObject) -> Unit) {
    val requestKey = remember { UUID.randomUUID().toString() }
    val lines = order.items("items").filter { it.optDouble("qty", 0.0) > it.optDouble("received_qty", 0.0) }
    val remaining = lines.associate { it.text("name") to it.optDouble("qty", 0.0) - it.optDouble("received_qty", 0.0) }
    val quantities = remember { mutableStateMapOf<String, String>() }
    var date by remember { mutableStateOf(today) }
    var note by remember { mutableStateOf("") }
    var proof by remember { mutableStateOf<Evidence?>(null) }
    var reading by remember { mutableStateOf(false) }
    SectionCard {
        Heading("Record goods received")
        DateField("Date received", date) { date = it }
        PurchaseText("Delivery note number (optional)", note, { note = it })
        for (line in lines) {
            val id = line.text("name")
            PurchaseText("${line.display("item_name")} · up to ${remaining[id]}", quantities[id].orEmpty(), { quantities[id] = it }, numeric = true)
        }
        PurchaseProof("Delivery proof (optional)", proof, busy, { proof = it }, { reading = it })
        val ready = quantities.values.any(::positive) && quantities.all { (id, value) ->
            value.isBlank() || value.toDoubleOrNull()?.let { it >= 0 && it <= remaining.getValue(id) } == true
        }
        Button(onClick = { save(JSONObject().put("request_key", requestKey).put("posting_date", date)
            .put("delivery_note", note).put("proof", proof?.json()).put("items", JSONArray(quantities.filterValues(::positive).map { (id, qty) ->
                JSONObject().put("order_item", id).put("qty", qty.toDouble())
            }))) }, enabled = ready && !busy && !reading, modifier = Modifier.fillMaxWidth()) { Text("Post goods receipt") }
    }
}

private val taxFields = listOf("cgst" to "CGST", "sgst" to "SGST", "igst" to "IGST", "other_tax" to "Other tax")

@Composable
private fun SupplierBillForm(order: JSONObject, workspace: JSONObject, today: String, busy: Boolean, save: (JSONObject) -> Unit) {
    val requestKey = remember { UUID.randomUUID().toString() }
    val receipts = order.items("receipts").filter { receipt -> receipt.items("items").any(::unbilled) }
    var receipt by remember { mutableStateOf(receipts.firstOrNull()?.text("name").orEmpty()) }
    val lines = receipts.firstOrNull { it.text("name") == receipt }?.items("items").orEmpty().filter(::unbilled)
    val accounts = remember(receipt) { mutableStateMapOf<String, String>().apply { lines.forEach { put(it.text("name"), it.text("expense_account")) } } }
    val taxes = remember(receipt) { mutableStateMapOf<Pair<String, String>, String>() }
    var taxBreakup by remember { mutableStateOf(false) }
    var number by remember { mutableStateOf("") }
    var date by remember { mutableStateOf(today) }
    var due by remember { mutableStateOf(today) }
    var proof by remember { mutableStateOf<Evidence?>(null) }
    var reading by remember { mutableStateOf(false) }
    SectionCard {
        Heading("Record supplier bill")
        PurchaseSelect("Goods receipt", receipt, receipts.map { it.text("name") to it.display("name") }) { receipt = it }
        PurchaseText("Supplier invoice number", number, { number = it })
        DateField("Invoice date", date) { date = it }
        DateField("Payment due date", due) { due = it }
        PurchaseProof("Supplier bill", proof, busy, { proof = it }, { reading = it })
        if (order.optBoolean("prices_include_tax")) Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(taxBreakup, { taxBreakup = it })
            Text("Record included tax breakup (optional)")
        }
        for (line in lines) {
            val id = line.text("name")
            Text(line.display("item_name"), fontWeight = FontWeight.SemiBold)
            PurchaseSelect("Expense ledger", accounts[id].orEmpty(), workspace.options("expense_accounts", "account_name")) { accounts[id] = it }
            if (taxBreakup) for ((field, label) in taxFields) PurchaseText("$label (INR)", taxes[id to field].orEmpty(), { taxes[id to field] = it }, numeric = true)
        }
        val ready = number.isNotBlank() && due >= date && proof != null && lines.isNotEmpty() && accounts.values.all { it.isNotBlank() }
        Button(onClick = {
            val details = JSONObject().put("request_key", requestKey).put("receipt", receipt).put("bill_no", number)
                .put("bill_date", date).put("due_date", due).put("proof", proof?.json())
                .put("items", JSONArray(accounts.map { (id, ledger) -> JSONObject().put("receipt_item", id).put("expense_account", ledger) }))
            if (taxBreakup) details.put("tax_breakup", JSONArray(lines.map { row ->
                JSONObject().put("receipt_item", row.text("name")).apply {
                    for ((field, _) in taxFields) put(field, taxes[row.text("name") to field].orEmpty())
                }
            }))
            save(details)
        }, enabled = ready && !busy && !reading, modifier = Modifier.fillMaxWidth()) { Text("Post supplier bill") }
    }
}

@Composable
private fun VendorPaymentForm(order: JSONObject, workspace: JSONObject, today: String, advance: Boolean, busy: Boolean, save: (JSONObject) -> Unit) {
    val requestKey = remember { UUID.randomUUID().toString() }
    val invoices = order.items("invoices").filter { it.optDouble("outstanding_amount", 0.0) > 0 }
    var invoice by remember { mutableStateOf(if (advance) "" else invoices.firstOrNull()?.text("name").orEmpty()) }
    val maximum = if (advance) order.optDouble("grand_total", 0.0) - order.optDouble("advance_paid", 0.0)
        else invoices.firstOrNull { it.text("name") == invoice }?.optDouble("outstanding_amount", 0.0) ?: 0.0
    var amount by remember(invoice) { mutableStateOf(if (advance) "" else maximum.toString()) }
    var ledger by remember { mutableStateOf("") }
    var mode by remember { mutableStateOf("") }
    var posting by remember { mutableStateOf(today) }
    var reference by remember { mutableStateOf("") }
    var referenceDate by remember { mutableStateOf(today) }
    var confirmed by remember { mutableStateOf(false) }
    val bank = workspace.items("payment_accounts").any { it.text("name") == ledger && it.text("account_type") == "Bank" }
    SectionCard {
        Heading(if (advance) "Record supplier advance" else "Record bill payment")
        if (!advance) PurchaseSelect("Supplier bill", invoice, invoices.map { it.text("name") to it.display("bill_no") }) { invoice = it }
        LabelValue("Amount available to pay", money(maximum))
        PurchaseText("Amount (INR)", amount, { amount = it }, numeric = true)
        PurchaseSelect("Pay from", ledger, workspace.options("payment_accounts", "account_name")) { ledger = it }
        PurchaseSelect("Mode of payment (optional)", mode, listOf("" to "Not specified") + workspace.options("modes", "name")) { mode = it }
        DateField("Posting date", posting) { posting = it }
        if (bank) {
            PurchaseText("Bank transaction reference", reference, { reference = it })
            DateField("Bank transaction date", referenceDate) { referenceDate = it }
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(confirmed, { confirmed = it })
            Text("I confirm the supplier has been paid.")
        }
        Button(onClick = { save(JSONObject().put("request_key", requestKey).put("invoice", invoice).put("amount", amount.toDouble())
            .put("paid_from", ledger).put("posting_date", posting).put("mode_of_payment", mode)
            .put("reference_no", if (bank) reference else "").put("reference_date", if (bank) referenceDate else null)) },
            enabled = confirmed && !busy && ledger.isNotBlank() && positive(amount) && (amount.toDoubleOrNull() ?: 0.0) <= maximum && (!bank || reference.isNotBlank()),
            modifier = Modifier.fillMaxWidth()) { Text("Post payment entry") }
    }
}

@Composable
private fun PurchaseMasterForm(kind: String, workspace: JSONObject, busy: Boolean, save: (JSONObject) -> Unit) {
    var name by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var address by remember { mutableStateOf("") }
    var pan by remember { mutableStateOf("") }
    var gstin by remember { mutableStateOf("") }
    var uom by remember { mutableStateOf("") }
    val supplier = kind == "supplier"
    SectionCard {
        Heading(if (supplier) "Add supplier" else "Add purchase item")
        PurchaseText("Name", name, { name = it })
        if (supplier) {
            PurchaseText("Phone", phone, { phone = it })
            PurchaseText("Address", address, { address = it })
            PurchaseText("PAN", pan, { pan = it })
            PurchaseText("GSTIN (optional)", gstin, { gstin = it })
        } else PurchaseSelect("Unit of measure", uom, workspace.strings("uoms").map { it to it }) { uom = it }
        val ready = name.isNotBlank() && if (supplier) listOf(phone, address, pan).all { it.isNotBlank() } else uom.isNotBlank()
        Button(onClick = {
            val details = JSONObject().put("name", name)
            if (supplier) details.put("phone", phone).put("address", address).put("pan", pan).put("gstin", gstin)
            else details.put("uom", uom)
            save(details)
        }, enabled = ready && !busy, modifier = Modifier.fillMaxWidth()) { Text("Save") }
    }
}

@Composable
private fun PurchaseSelect(label: String, selected: String, options: List<Pair<String, String>>, change: (String) -> Unit) {
    var open by remember { mutableStateOf(false) }
    var query by remember { mutableStateOf("") }
    Column {
        Text(label, style = MaterialTheme.typography.labelMedium)
        OutlinedButton(onClick = { query = ""; open = true }, modifier = Modifier.fillMaxWidth()) {
            Text(options.firstOrNull { it.first == selected }?.second ?: selected.ifBlank { "Choose ${label.lowercase()}" })
        }
    }
    if (open) AlertDialog(onDismissRequest = { open = false }, title = { Text(label) }, text = {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            PurchaseText("Search", query, { query = it })
            val matches = options.filter { it.second.contains(query.trim(), true) || it.first.contains(query.trim(), true) }
            if (matches.isEmpty()) Text("No matching options.")
            else LazyColumn(Modifier.fillMaxWidth().heightIn(max = 280.dp)) {
                items(matches) { (value, text) ->
                    Text(text, Modifier.fillMaxWidth().clickable { change(value); open = false }.padding(vertical = 12.dp))
                }
            }
        }
    }, confirmButton = { TextButton(onClick = { open = false }) { Text("Close") } })
}

@Composable
private fun PurchaseProof(label: String, proof: Evidence?, busy: Boolean, onFile: (Evidence?) -> Unit, onReading: (Boolean) -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var error by remember { mutableStateOf("") }
    var reading by remember { mutableStateOf(false) }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) scope.launch {
            error = ""
            reading = true
            onReading(true)
            try { onFile(withContext(Dispatchers.IO) { readEvidence(context, uri) }) }
            catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                error = e.message ?: "Could not read the document."
            } finally { reading = false; onReading(false) }
        }
    }
    Text(label, fontWeight = FontWeight.SemiBold)
    OutlinedButton(onClick = { picker.launch(arrayOf("application/pdf", "image/png", "image/jpeg")) }, enabled = !busy && !reading,
        modifier = Modifier.fillMaxWidth()) { Text(if (reading) "Reading document…" else proof?.name ?: "Choose PDF or image") }
    if (proof != null) TextButton(onClick = { onFile(null) }, enabled = !busy && !reading) { Text("Remove document") }
    if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
}

@Composable
private fun PurchaseText(label: String, value: String, change: (String) -> Unit, numeric: Boolean = false) {
    OutlinedTextField(value, change, label = { Text(label) }, singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = if (numeric) KeyboardType.Decimal else KeyboardType.Text), modifier = Modifier.fillMaxWidth())
}

@Composable
private fun PurchaseButton(label: String, busy: Boolean, action: () -> Unit) {
    OutlinedButton(onClick = action, modifier = Modifier.fillMaxWidth(), enabled = !busy) { Text(label) }
}

private fun JSONObject.options(field: String, label: String, value: String = "name") =
    items(field).map { it.text(value) to it.display(label, it.text(value)) }
private fun Evidence.json() = JSONObject().put("file_name", name).put("content", base64)
private fun positive(value: String) = value.toDoubleOrNull()?.let { it.isFinite() && it > 0 } == true
private fun unbilled(line: JSONObject) = line.optDouble("billed_amt", 0.0) + 0.005 < line.optDouble("amount", 0.0)
private fun plainPurchaseText(html: String) = android.text.Html.fromHtml(html, android.text.Html.FROM_HTML_MODE_LEGACY).toString().trim()
