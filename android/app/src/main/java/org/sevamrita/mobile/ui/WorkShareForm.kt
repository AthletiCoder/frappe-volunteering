package org.sevamrita.mobile.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import org.json.JSONArray
import org.json.JSONObject
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text
import java.time.LocalTime

@Composable
internal fun WorkShareForm(form: JSONObject, initialPeople: List<JSONObject>, model: PortalViewModel, set: (JSONObject) -> Unit) {
    var query by remember { mutableStateOf("") }
    var people by remember { mutableStateOf(initialPeople) }
    val shares = form.items("shares")
    Text("Chat members can already see this. Share this item with other people without adding them to the chat.", style = MaterialTheme.typography.bodyMedium)
    Text("Only people with web or app chat access can be selected. View only is the default.", style = MaterialTheme.typography.bodySmall)
    shares.forEachIndexed { index, row ->
        HorizontalDivider()
        Text(row.text("full_name").ifBlank { initialPeople.firstOrNull { it.text("name") == row.text("user") }?.text("full_name") ?: row.text("user") }, fontWeight = FontWeight.Medium)
        SelectField("Permission", row.text("access").ifBlank { "View" }, listOf("View" to "Can view", "Update" to "Can update status / progress")) { access ->
            set(JSONObject(form.toString()).put("shares", JSONArray(shares.mapIndexed { i, existing -> if (i == index) JSONObject(existing.toString()).put("access", access) else existing })))
        }
        TextButton(onClick = { set(JSONObject(form.toString()).put("shares", JSONArray(shares.filterIndexed { i, _ -> i != index }))) }) { Text("Remove access") }
    }
    OutlinedTextField(query, { query = it }, label = { Text("Find a person to share with") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
    LaunchedEffect(query) {
        if (query.isBlank()) people = initialPeople
        else {
            val requested = query
            delay(350)
            model.chatCall("get_directory", JSONObject().put("query", requested)) { if (query == requested) people = it.items("value") }
        }
    }
    people.filter { p -> p.text("name") != model.state.value.user && shares.none { it.text("user") == p.text("name") } }.take(15).forEach { person ->
        OutlinedButton(onClick = { set(JSONObject(form.toString()).put("shares", JSONArray(shares + JSONObject().put("user", person.text("name")).put("full_name", person.text("full_name")).put("access", "View")))) }, modifier = Modifier.fillMaxWidth()) {
            Text("+ ${person.text("full_name")}")
        }
    }
}

@Composable
internal fun ReminderTimeField(value: String, set: (String) -> Unit) {
    val time = runCatching { LocalTime.parse(value) }.getOrDefault(LocalTime.of(9, 0))
    EditorTime("Reminder time", time, if (value.isBlank()) "09:00 · morning default" else "$time · portal time",
        reset = if (value.isNotBlank()) { { set("") } } else null) { set(it.toString()) }
    Text("On scheduled days, or on the deadline. Times follow the portal's time zone.", style = MaterialTheme.typography.bodySmall)
}
