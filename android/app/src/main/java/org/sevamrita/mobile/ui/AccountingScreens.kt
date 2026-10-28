package org.sevamrita.mobile.ui

import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
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
import org.sevamrita.mobile.ActionRow
import org.sevamrita.mobile.Heading
import org.sevamrita.mobile.LabelValue
import org.sevamrita.mobile.SectionCard
import org.sevamrita.mobile.data.display
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text
import org.sevamrita.mobile.money

private val accent = Color(0xFF08745E)

@Composable
fun ChartScreen(state: PortalState, model: PortalViewModel) {
    val accounts = state.data.items("accounts")
    val byName = remember(state.data) { accounts.associateBy { it.text("name") } }
    var query by remember { mutableStateOf("") }
    var expanded by remember(state.data) { mutableStateOf(setOf<String>()) }
    val visible = remember(accounts, query, expanded) {
        if (query.isNotBlank()) accounts.filter {
            it.text("account_name").contains(query.trim(), ignoreCase = true) ||
                it.text("name").contains(query.trim(), ignoreCase = true)
        } else accounts.filter { row ->
            var parent = row.text("parent_account")
            var shown = true
            while (parent.isNotBlank() && byName[parent] != null) {
                if (parent !in expanded) { shown = false; break }
                parent = byName[parent]?.text("parent_account").orEmpty()
            }
            shown
        }
    }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item { Heading("Chart of Accounts", "Choose a ledger to inspect its dated transactions") }
        if (state.data.optBoolean("can_manage")) item {
            Button(onClick = { model.openAccountForm() }, modifier = Modifier.fillMaxWidth()) { Text("Add account") }
        }
        item {
            OutlinedTextField(query, { query = it }, label = { Text("Find an account") },
                modifier = Modifier.fillMaxWidth(), singleLine = true)
        }
        if (accounts.isEmpty() && !state.busy) item { SectionCard { Text("No chart is available to this account.") } }
        items(visible, key = { it.text("name") }) { row ->
            val name = row.text("name")
            val isGroup = row.optInt("is_group") == 1
            SectionCard {
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                    if (isGroup && row.optInt("has_children") == 1) IconButton(onClick = {
                        expanded = if (name in expanded) expanded - name else expanded + name
                    }) {
                        Icon(if (name in expanded) Icons.Default.ExpandMore else Icons.Default.ChevronRight,
                            contentDescription = if (name in expanded) "Collapse ${row.text("account_name")}" else "Expand ${row.text("account_name")}")
                    }
                    Column(Modifier.weight(1f).clickable {
                        if (isGroup) model.openAccountForm(row) else model.openLedger(name)
                    }.padding(start = if (isGroup && row.optInt("has_children") == 1) 0.dp else 12.dp)) {
                        Text(row.display("account_name"), fontWeight = FontWeight.SemiBold)
                        Text("${row.display("root_type")} · ${if (isGroup) "Group" else "Ledger"}${if (row.optInt("disabled") == 1) " · Disabled" else ""}",
                            color = Color(0xFF637378))
                    }
                    TextButton(onClick = { if (isGroup) model.openAccountForm(row) else model.openLedger(name) }) {
                        Text(if (isGroup) "Details" else "Ledger")
                    }
                }
            }
        }
        item { Text("Groups organise the chart. Only ledgers receive posted entries.", color = Color(0xFF637378)) }
    }
}

private fun signedBalance(amount: Double) = when {
    amount > 0 -> "${money(amount)} Dr"
    amount < 0 -> "${money(-amount)} Cr"
    else -> money(0.0)
}

@Composable
fun LedgerScreen(state: PortalState, model: PortalViewModel) {
    val ledger = state.data
    val account = ledger.optJSONObject("account") ?: JSONObject()
    var from by remember(state.detailId, state.ledgerFrom) { mutableStateOf(state.ledgerFrom) }
    var to by remember(state.detailId, state.ledgerTo) { mutableStateOf(state.ledgerTo) }
    val entries = ledger.items("entries")
    val page = ledger.optInt("page", 1)
    val count = ledger.optInt("entry_count")
    val pageSize = ledger.optInt("page_size", 50)
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading(account.display("account_name", state.detailId), state.detailId) }
        item { SectionCard {
            DateField("From posting date", from) { from = it }
            DateField("To posting date", to) { to = it }
            Button(onClick = { model.loadLedger(from, to, 1) }, enabled = !state.busy,
                modifier = Modifier.fillMaxWidth()) { Text("Show entries") }
            Text("Posted entries only; cancelled entries are excluded.", color = Color(0xFF637378))
        } }
        if (ledger.has("opening_balance")) item { SectionCard {
            LabelValue("Opening balance", signedBalance(ledger.optDouble("opening_balance")))
            LabelValue("Debits", money(ledger.optDouble("total_debit")))
            LabelValue("Credits", money(ledger.optDouble("total_credit")))
            HorizontalDivider()
            LabelValue("Closing balance", signedBalance(ledger.optDouble("closing_balance")))
        } }
        item { Text("Transactions · $count", fontWeight = FontWeight.Bold, color = accent) }
        if (count == 0 && !state.busy) item { SectionCard { Text("No posted entries for the selected period.") } }
        items(entries, key = { it.text("name") }) { entry -> SectionCard {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(entry.display("posting_date"), color = Color(0xFF637378))
                Text(signedBalance(entry.optDouble("balance")), fontWeight = FontWeight.Bold)
            }
            Text("${entry.display("voucher_type")} · ${entry.display("voucher_no")}", fontWeight = FontWeight.SemiBold)
            if (entry.text("remarks").isNotBlank()) Text(entry.text("remarks"))
            if (entry.text("party").isNotBlank()) Text("${entry.display("party_type")}: ${entry.text("party")}")
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Debit ${if (entry.optDouble("debit") > 0) money(entry.optDouble("debit")) else "—"}")
                Text("Credit ${if (entry.optDouble("credit") > 0) money(entry.optDouble("credit")) else "—"}")
            }
        } }
        if (count > pageSize) item { Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            OutlinedButton(onClick = { model.loadLedger(from, to, page - 1) }, enabled = !state.busy && page > 1) { Text("Previous") }
            Text("Page $page", modifier = Modifier.align(Alignment.CenterVertically))
            OutlinedButton(onClick = { model.loadLedger(from, to, page + 1) }, enabled = !state.busy && page * pageSize < count) { Text("Next") }
        } }
        item { Spacer(Modifier.height(16.dp)) }
    }
}

@Composable
fun AccountFormScreen(state: PortalState, model: PortalViewModel) {
    val original = state.form
    val workspace = state.data
    val existing = original.text("name").isNotBlank()
    val root = original.optBoolean("is_root")
    val canManage = workspace.optBoolean("can_manage")
    var name by remember(original) { mutableStateOf(original.text("account_name")) }
    var number by remember(original) { mutableStateOf(original.text("account_number")) }
    var parent by remember(original) { mutableStateOf(original.text("parent_account")) }
    var isGroup by remember(original) { mutableStateOf(original.optInt("is_group") == 1) }
    var type by remember(original) { mutableStateOf(original.text("account_type")) }
    var currency by remember(original) { mutableStateOf(original.text("account_currency")) }
    var disabled by remember(original) { mutableStateOf(original.optInt("disabled") == 1) }
    var deletionPrompt by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }
    val parents = workspace.items("parent_accounts").filter { it.text("name") != original.text("name") }
    val types = workspace.optJSONArray("account_types")?.let { values ->
        (0 until values.length()).map { values.optString(it) }
    }.orEmpty()
    val currencies = workspace.optJSONArray("currencies")?.let { values ->
        (0 until values.length()).map { values.optString(it) }
    }.orEmpty()
    if (deletionPrompt) AlertDialog(onDismissRequest = { deletionPrompt = false },
        title = { Text("Delete this account?") },
        text = { Text("Only an unused account can be deleted. Posted ledger entries cannot be deleted here.") },
        confirmButton = { TextButton(onClick = { deletionPrompt = false; model.deleteAccount() }) { Text("Delete") } },
        dismissButton = { TextButton(onClick = { deletionPrompt = false }) { Text("Keep account") } })
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading(if (existing) name else "Add account", original.display("name", "Sevamrita Foundation")) }
        if (!canManage || root) item { SectionCard {
            LabelValue("Account", original.display("name"))
            LabelValue("Parent", original.display("parent_account", "Root account"))
            LabelValue("Type", original.display("account_type", if (isGroup) "Group" else "Ledger"))
            Text(if (root) "Root accounts are protected." else "Your role can view this account but not change it.")
        } }
        else item { SectionCard {
            OutlinedTextField(name, { name = it }, label = { Text("Account name *") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(number, { number = it }, label = { Text("Account number (optional)") }, modifier = Modifier.fillMaxWidth())
            SelectField("Parent group *", parent, parents.map { it.text("name") to it.display("label") }) { parent = it }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Group account", modifier = Modifier.weight(1f))
                Switch(isGroup, { isGroup = it }, enabled = !existing)
            }
            if (!isGroup) {
                SelectField("Account type", type, listOf("" to "Normal ledger") + types.map { it to it }) { type = it }
                SelectField("Currency", currency, listOf("" to "Company default") + currencies.map { it to it }) { currency = it }
            }
            if (existing) Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Disabled", modifier = Modifier.weight(1f))
                Checkbox(disabled, { disabled = it })
            }
            if (error.isNotBlank()) Text(error, color = Color(0xFF9B2D25))
            Button(onClick = {
                if (name.isBlank() || parent.isBlank()) error = "Enter an account name and choose a parent group."
                else model.saveAccount(JSONObject().put("account_name", name.trim())
                    .put("account_number", number.trim()).put("parent_account", parent)
                    .put("is_group", if (isGroup) 1 else 0).put("account_type", if (isGroup) "" else type)
                    .put("account_currency", if (isGroup) "" else currency).put("disabled", if (disabled) 1 else 0)
                    .put("balance_must_be", original.text("balance_must_be"))
                    .put("include_in_gross", original.optInt("include_in_gross"))
                    .put("tax_rate", original.optDouble("tax_rate")))
            }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Save account") }
            if (existing) OutlinedButton(onClick = { deletionPrompt = true }, enabled = !state.busy,
                modifier = Modifier.fillMaxWidth()) { Text("Delete unused account") }
        } }
    }
}
