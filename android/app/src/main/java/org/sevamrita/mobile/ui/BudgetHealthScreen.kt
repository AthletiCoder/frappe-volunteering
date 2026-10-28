package org.sevamrita.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
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
fun BudgetHealthScreen(state: PortalState, model: PortalViewModel) {
    val rows = state.data.items("value")
    var filter by remember { mutableStateOf("") }
    val visible = rows.filter { it.text("project").contains(filter, true) }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Heading("Budget health", "Approved, committed and available by project") }
        item { OutlinedTextField(filter, { filter = it }, label = { Text("Find a project") }, modifier = Modifier.fillMaxWidth()) }
        if (visible.isEmpty() && !state.busy) item { Text("No matching projects are available.") }
        items(visible) { project -> SectionCard {
            Text(project.display("project"), fontWeight = FontWeight.Bold)
            LabelValue("Budget status", project.display("budget_status"))
            LabelValue("Approved", money(project.optDouble("allocated")))
            LabelValue("Committed", money(project.optDouble("consumed")))
            LabelValue("Available", if (project.optBoolean("has_project_budget")) money(project.optDouble("remaining")) else "No ceiling")
            LabelValue("Utilisation", "${project.optDouble("utilisation_pct").toInt()}%")
            project.items("accounts").forEach { account ->
                Text(account.display("expense_account"), fontWeight = FontWeight.Medium)
                LabelValue("Approved / Committed", "${money(account.optDouble("allocated"))} / ${money(account.optDouble("consumed"))}")
            }
        } }
    }
}
