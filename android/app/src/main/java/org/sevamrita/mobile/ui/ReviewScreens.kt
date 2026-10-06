package org.sevamrita.mobile.ui

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.pdf.PdfRenderer
import android.os.ParcelFileDescriptor
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import org.sevamrita.mobile.ActionRow
import org.sevamrita.mobile.Heading
import org.sevamrita.mobile.LabelValue
import org.sevamrita.mobile.SectionCard
import org.sevamrita.mobile.data.display
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text
import org.sevamrita.mobile.money
import java.io.File

@Composable
fun AdvanceQueueScreen(state: PortalState, model: PortalViewModel) {
    val queues = state.data.optJSONObject("queues") ?: JSONObject()
    val approvals = queues.items("approval")
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Heading("Advance approvals", "Requests assigned to you") }
        if (approvals.isEmpty() && !state.busy) item { SectionCard { Text("No advances await your decision.") } }
        items(approvals) { row -> ActionRow(row.display("employee_name"), "${row.display("name")} · ${money(row.optDouble("amount"))}") {
            model.open(Page.ADVANCE_REVIEW, row.text("name"))
        } }
        if (queues.items("disbursement").isNotEmpty() || queues.items("return").isNotEmpty()) item {
            SectionCard { Text("Accounts disbursement and advance returns need dedicated mobile controls and are not available in this build.") }
        }
    }
}

@Composable
fun AdvanceReviewScreen(state: PortalState, model: PortalViewModel) {
    val item = state.data
    val flags = item.optJSONObject("approval_flags") ?: JSONObject()
    var reason by remember(item) { mutableStateOf("") }
    var error by remember { mutableStateOf("") }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading(item.display("employee_name", "Advance request"), item.display("name")) }
        item { SectionCard {
            LabelValue("Requested", money(item.optDouble("requested_amount")))
            LabelValue("Project", item.display("project_name"))
            LabelValue("Purpose", item.display("purpose"))
            LabelValue("Needed by", item.display("required_by_date"))
            LabelValue("Expected settlement", item.display("expected_settlement_date"))
            if (item.text("additional_note").isNotBlank()) LabelValue("Note", item.text("additional_note"))
            if (item.text("supporting_document").startsWith("/private/files/")) TextButton(onClick = {
                model.openReceipt(item.text("supporting_document"), Page.ADVANCE_REVIEW)
            }) { Text("Open supporting document") }
        } }
        if (flags.optBoolean("is_pending_approver")) {
            item { SectionCard {
                Text("Your decision", fontWeight = FontWeight.SemiBold)
                OutlinedTextField(reason, { reason = it }, label = { Text("Note / reason") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
                if (error.isNotBlank()) Text(error, color = androidx.compose.material3.MaterialTheme.colorScheme.error)
                if (flags.optBoolean("can_approve")) Button(onClick = { model.decideAdvance("approve", reason) }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Approve") }
                if (flags.optBoolean("can_escalate")) OutlinedButton(onClick = {
                    if (reason.isBlank()) error = "Give a reason for escalation." else model.decideAdvance("escalate", reason)
                }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Escalate to next manager") }
                if (flags.optBoolean("can_reject")) OutlinedButton(onClick = {
                    if (reason.isBlank()) error = "Give a reason for rejection." else model.decideAdvance("reject", reason)
                }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Reject") }
            } }
        }
    }
}

@Composable
fun ClaimQueueScreen(state: PortalState, model: PortalViewModel) {
    val queues = state.data.optJSONObject("queues") ?: JSONObject()
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Heading("Expense review", "Items assigned to your role") }
        for ((key, title) in listOf("receipt_review" to "Receipt review", "approval" to "Manager approval")) {
            val rows = queues.items(key)
            if (rows.isNotEmpty()) {
                item { Text(title, fontWeight = FontWeight.Bold) }
                items(rows) { row -> ActionRow(row.display("employee_name"), "${row.display("name")} · ${money(row.optDouble("amount"))}") {
                    model.open(Page.CLAIM_REVIEW, row.text("name"))
                } }
            }
        }
        if (queues.items("receipt_review").isEmpty() && queues.items("approval").isEmpty() && !state.busy) item {
            SectionCard { Text("No expense claims await your review.") }
        }
        if (queues.items("classification").isNotEmpty() || queues.items("reimbursement").isNotEmpty()) item {
            SectionCard { Text("Accounts classification and reimbursement need dedicated mobile controls and are not available in this build.") }
        }
    }
}

@Composable
fun ClaimReviewScreen(state: PortalState, model: PortalViewModel) {
    val item = state.data
    val access = item.optJSONObject("access") ?: JSONObject()
    val flags = item.optJSONObject("approval_flags") ?: JSONObject()
    var notes by remember(item) { mutableStateOf("") }
    var reason by remember(item) { mutableStateOf("") }
    var error by remember { mutableStateOf("") }
    val rows = item.items("expenses")
    val amounts = remember(item) { rows.associate { it.text("name") to mutableStateOf(it.optDouble("amount").toString()) } }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading(item.display("employee_name", "Expense claim"), item.display("name")) }
        item { SectionCard {
            LabelValue("Project", item.display("project_name"))
            LabelValue("Status", item.display("workflow_state"))
            LabelValue("Claimed", money(item.optDouble("claimed_amount")))
            LabelValue("Approval basis", money(item.optDouble("approval_basis")))
            LabelValue("Paid with", item.display("source"))
            if (item.text("remark").isNotBlank()) LabelValue("Purpose", item.text("remark"))
        } }
        item { Heading("Expenses and receipts", "Open every receipt before deciding") }
        items(rows) { row -> SectionCard {
            Text(row.display("description"), fontWeight = FontWeight.SemiBold)
            LabelValue("Invoice date", row.display("expense_date"))
            LabelValue("Supplier", row.display("supplier_name"))
            LabelValue("Category", row.display("category"))
            LabelValue("Claimed", money(row.optDouble("amount")))
            if (row.text("receipt_attachment").startsWith("/private/files/")) TextButton(onClick = {
                model.openReceipt(row.text("receipt_attachment"), Page.CLAIM_REVIEW)
            }) { Text("Open private receipt") }
            else Text("No private receipt attached")
            if (access.optBoolean("approval")) OutlinedTextField(
                amounts[row.text("name")]?.value ?: "", { amounts[row.text("name")]?.value = it },
                label = { Text("Sanctioned amount (INR)") }, modifier = Modifier.fillMaxWidth(), singleLine = true
            )
        } }
        if (access.optBoolean("receipt_review")) item { SectionCard {
            Text("Receipt review", fontWeight = FontWeight.SemiBold)
            OutlinedTextField(notes, { notes = it }, label = { Text("Review notes") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
            if (error.isNotBlank()) Text(error, color = androidx.compose.material3.MaterialTheme.colorScheme.error)
            Button(onClick = { model.reviewClaimReceipt("verify", notes) }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Verify receipts") }
            OutlinedButton(onClick = {
                if (notes.isBlank()) error = "Explain what the employee must correct."
                else model.reviewClaimReceipt("request_correction", notes)
            }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Request correction") }
        } }
        if (access.optBoolean("approval")) item { SectionCard {
            Text("Manager decision", fontWeight = FontWeight.SemiBold)
            OutlinedTextField(reason, { reason = it }, label = { Text("Reason / note") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
            if (error.isNotBlank()) Text(error, color = androidx.compose.material3.MaterialTheme.colorScheme.error)
            if (flags.optBoolean("can_approve")) Button(onClick = {
                val output = JSONObject()
                var valid = true
                rows.forEach { row ->
                    val requested = row.optDouble("amount")
                    val value = amounts[row.text("name")]?.value?.toDoubleOrNull()
                    if (value == null || !value.isFinite() || value < 0 || value > requested) valid = false
                    else output.put(row.text("name"), value)
                }
                if (!valid) error = "Each sanctioned amount must be between zero and the claimed amount."
                else model.decideClaim("approve", reason, output)
            }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Approve sanctioned amounts") }
            if (flags.optBoolean("can_escalate")) OutlinedButton(onClick = {
                if (reason.isBlank()) error = "Give a reason for escalation."
                else model.decideClaim("escalate", reason, JSONObject())
            }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Escalate") }
            if (flags.optBoolean("can_reject")) OutlinedButton(onClick = {
                if (reason.isBlank()) error = "Give a reason for rejection."
                else model.decideClaim("reject", reason, JSONObject())
            }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Reject") }
        } }
    }
}

@Composable
fun ReceiptScreen(state: PortalState) {
    val bytes = state.receiptBytes ?: return
    val context = LocalContext.current
    var page by remember(bytes) { mutableIntStateOf(0) }
    val isPdf = state.receiptName.lowercase().endsWith(".pdf") || bytes.take(4).toByteArray().contentEquals("%PDF".toByteArray())
    val temp = remember(bytes) {
        if (!isPdf) null else File.createTempFile("sevamrita-receipt-", ".pdf", context.cacheDir).apply { writeBytes(bytes) }
    }
    DisposableEffect(temp) { onDispose { temp?.delete() } }
    val rendered = remember(bytes, page) {
        runCatching {
            if (temp == null) BitmapFactory.decodeByteArray(bytes, 0, bytes.size) to 1
            else {
                ParcelFileDescriptor.open(temp, ParcelFileDescriptor.MODE_READ_ONLY).use { descriptor ->
                    PdfRenderer(descriptor).use { renderer ->
                        val count = renderer.pageCount
                        renderer.openPage(page.coerceIn(0, count - 1)).use { pdfPage ->
                            val scale = minOf(1600f / pdfPage.width, 2600f / pdfPage.height, 3f)
                            val bitmap = Bitmap.createBitmap((pdfPage.width * scale).toInt(), (pdfPage.height * scale).toInt(), Bitmap.Config.ARGB_8888)
                            bitmap.eraseColor(android.graphics.Color.WHITE)
                            pdfPage.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
                            bitmap to count
                        }
                    }
                }
            }
        }.getOrNull()
    }
    Column(Modifier.fillMaxSize().padding(12.dp)) {
        if (rendered?.first == null) Text("This receipt could not be rendered. It may be damaged or unsupported.")
        else {
            if (rendered.second > 1) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                TextButton(onClick = { page-- }, enabled = page > 0) { Text("Previous") }
                Text("Page ${page + 1} of ${rendered.second}")
                TextButton(onClick = { page++ }, enabled = page < rendered.second - 1) { Text("Next") }
            }
            Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
                Image(rendered.first.asImageBitmap(), contentDescription = "Private receipt page ${page + 1}",
                    contentScale = ContentScale.FillWidth, modifier = Modifier.fillMaxWidth())
            }
        }
    }
}
