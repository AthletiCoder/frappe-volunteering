package org.sevamrita.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject
import org.sevamrita.mobile.Heading
import org.sevamrita.mobile.LabelValue
import org.sevamrita.mobile.SectionCard
import org.sevamrita.mobile.data.display
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.strings
import org.sevamrita.mobile.data.text

private val muted = Color(0xFF637378)
private val warning = Color(0xFF9B2D25)

@Composable
fun HRManagementScreen(state: PortalState, model: PortalViewModel) {
    var query by remember { mutableStateOf("") }
    val employees = state.data.items("employees").filter { query.isBlank() ||
        it.text("employee_name").contains(query, true) || it.text("name").contains(query, true) }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Heading("Employees", "HR management for Sevamrita") }
        item { Button(onClick = { model.openManagedEmployee() }, modifier = Modifier.fillMaxWidth()) { Text("Add employee") } }
        item { OutlinedTextField(query, { query = it }, label = { Text("Find an employee") }, modifier = Modifier.fillMaxWidth()) }
        items(employees) { row -> SectionCard {
            Text(row.display("employee_name"), fontWeight = FontWeight.Bold)
            Text(row.display("name"), color = muted)
            LabelValue("Status", row.display("status"))
            LabelValue("Department", row.display("department"))
            LabelValue("Linked user", row.display("user_id", "No login yet"))
            TextButton(onClick = { model.openManagedEmployee(row.text("name")) }) { Text("View or edit employee") }
        } }
    }
}

@Composable
fun ManagedEmployeeFormScreen(state: PortalState, model: PortalViewModel) {
    val original = state.form
    val options = state.data.optJSONObject("options") ?: JSONObject()
    var first by remember(original) { mutableStateOf(original.text("first_name")) }
    var middle by remember(original) { mutableStateOf(original.text("middle_name")) }
    var last by remember(original) { mutableStateOf(original.text("last_name")) }
    var status by remember(original) { mutableStateOf(original.text("status").ifBlank { "Active" }) }
    var gender by remember(original) { mutableStateOf(original.text("gender")) }
    var dob by remember(original) { mutableStateOf(original.text("date_of_birth")) }
    var joining by remember(original) { mutableStateOf(original.text("date_of_joining")) }
    var relieving by remember(original) { mutableStateOf(original.text("relieving_date")) }
    var user by remember(original) { mutableStateOf(original.text("user_id")) }
    var department by remember(original) { mutableStateOf(original.text("department")) }
    var designation by remember(original) { mutableStateOf(original.text("designation")) }
    var grade by remember(original) { mutableStateOf(original.text("grade")) }
    var employment by remember(original) { mutableStateOf(original.text("employment_type")) }
    var manager by remember(original) { mutableStateOf(original.text("reports_to")) }
    var mobile by remember(original) { mutableStateOf(original.text("cell_number")) }
    var companyEmail by remember(original) { mutableStateOf(original.text("company_email")) }
    var personalEmail by remember(original) { mutableStateOf(original.text("personal_email")) }
    var error by remember(original) { mutableStateOf("") }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading(if (original.text("name").isBlank()) "New employee" else original.display("employee_name")) }
        item { SectionCard {
            OutlinedTextField(first, { first = it }, label = { Text("First name *") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(middle, { middle = it }, label = { Text("Middle name") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(last, { last = it }, label = { Text("Last name") }, modifier = Modifier.fillMaxWidth())
            SelectField("Status *", status, options.strings("statuses").map { it to it }) { status = it }
            SelectField("Gender *", gender, options.strings("genders").map { it to it }) { gender = it }
            DateField("Date of birth *", dob) { dob = it }
            DateField("Date of joining *", joining) { joining = it }
            if (status == "Left") DateField("Relieving date *", relieving) { relieving = it }
        } }
        item { SectionCard {
            Text("Organisation", fontWeight = FontWeight.Bold)
            LabelValue("Company", options.display("company"))
            SelectField("Department", department, listOf("" to "Not set") + options.strings("departments").map { it to it }) { department = it }
            SelectField("Designation", designation, listOf("" to "Not set") + options.strings("designations").map { it to it }) { designation = it }
            SelectField("Grade", grade, listOf("" to "Not set") + options.strings("grades").map { it to it }) { grade = it }
            SelectField("Employment type", employment, listOf("" to "Not set") + options.strings("employment_types").map { it to it }) { employment = it }
            SelectField("Reports to", manager, listOf("" to "No reporting manager") + options.items("reporting_managers")
                .filter { it.text("name") != original.text("name") }.map { it.text("name") to it.display("employee_name") }) { manager = it }
            SelectField("Linked login user", user, listOf("" to "No login account") + options.items("users")
                .filter { !it.optBoolean("linked") || it.text("name") == original.text("user_id") }
                .map { it.text("name") to it.display("full_name", it.text("name")) }) { user = it }
        } }
        item { SectionCard {
            Text("Contact", fontWeight = FontWeight.Bold)
            OutlinedTextField(mobile, { mobile = it }, label = { Text("Mobile") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(companyEmail, { companyEmail = it }, label = { Text("Company email") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(personalEmail, { personalEmail = it }, label = { Text("Personal email") }, modifier = Modifier.fillMaxWidth())
            if (error.isNotBlank()) Text(error, color = warning)
            Button(onClick = {
                error = when {
                    first.isBlank() || gender.isBlank() || dob.isBlank() || joining.isBlank() -> "Enter name, gender, birth date and joining date."
                    status == "Left" && relieving.isBlank() -> "Enter the relieving date."
                    else -> ""
                }
                if (error.isBlank()) model.saveManagedEmployee(JSONObject()
                    .put("first_name", first).put("middle_name", middle).put("last_name", last)
                    .put("status", status).put("gender", gender).put("date_of_birth", dob)
                    .put("date_of_joining", joining).put("relieving_date", relieving)
                    .put("user_id", user).put("department", department).put("designation", designation)
                    .put("grade", grade).put("employment_type", employment).put("reports_to", manager)
                    .put("cell_number", mobile).put("company_email", companyEmail).put("personal_email", personalEmail))
            }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Save employee") }
        } }
    }
}

@Composable
fun SystemManagementScreen(state: PortalState, model: PortalViewModel) {
    var query by remember { mutableStateOf("") }
    var reset by remember { mutableStateOf("") }
    if (reset.isNotBlank()) AlertDialog(onDismissRequest = { reset = "" },
        title = { Text("Send password-reset email?") },
        text = { Text("A one-time link will be emailed to $reset. This requires outgoing mail to be configured on the server.") },
        confirmButton = { TextButton(onClick = { model.sendManagedPasswordReset(reset); reset = "" }) { Text("Send link") } },
        dismissButton = { TextButton(onClick = { reset = "" }) { Text("Cancel") } })
    val users = state.data.items("users").filter { query.isBlank() ||
        it.text("full_name").contains(query, true) || it.text("name").contains(query, true) }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Heading("System users", "Create login accounts, assign roles and send reset links") }
        item { Button(onClick = { model.openManagedUser() }, modifier = Modifier.fillMaxWidth()) { Text("Add user") } }
        item { OutlinedTextField(query, { query = it }, label = { Text("Find a user") }, modifier = Modifier.fillMaxWidth()) }
        items(users) { row -> SectionCard {
            Text(row.display("full_name", row.text("name")), fontWeight = FontWeight.Bold)
            Text(row.display("name"), color = muted)
            LabelValue("Access", "${row.display("user_type")} · ${if (row.optInt("enabled") == 1) "Enabled" else "Disabled"}")
            row.optJSONObject("employee")?.let { LabelValue("Employee", it.display("employee_name")) }
            TextButton(onClick = { model.openManagedUser(row.text("name")) }) { Text("View or edit roles") }
            if (row.optInt("enabled") == 1) TextButton(onClick = { reset = row.text("name") }) { Text("Send password reset") }
        } }
    }
}

@Composable
fun ManagedUserFormScreen(state: PortalState, model: PortalViewModel) {
    val original = state.form
    val workspace = state.data
    var first by remember(original) { mutableStateOf(original.text("first_name")) }
    var middle by remember(original) { mutableStateOf(original.text("middle_name")) }
    var last by remember(original) { mutableStateOf(original.text("last_name")) }
    var email by remember(original) { mutableStateOf(original.text("name")) }
    var type by remember(original) { mutableStateOf(original.text("user_type").ifBlank { "System User" }) }
    var enabled by remember(original) { mutableStateOf(original.optInt("enabled", 1) == 1) }
    var welcome by remember(original) { mutableStateOf(false) }
    var mode by remember(original) { mutableStateOf(if (original.strings("role_profiles").isNotEmpty()) "profiles" else "roles") }
    var chosenRoles by remember(original) { mutableStateOf(original.strings("roles").toSet()) }
    var chosenProfiles by remember(original) { mutableStateOf(original.strings("role_profiles").toSet()) }
    var roleQuery by remember { mutableStateOf("") }
    var error by remember(original) { mutableStateOf("") }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { Heading(if (original.text("name").isBlank()) "New user" else original.display("full_name")) }
        item { SectionCard {
            if (original.text("name").isBlank()) OutlinedTextField(email, { email = it }, label = { Text("Login email *") }, modifier = Modifier.fillMaxWidth())
            else LabelValue("Login", original.display("name"))
            OutlinedTextField(first, { first = it }, label = { Text("First name *") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(middle, { middle = it }, label = { Text("Middle name") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(last, { last = it }, label = { Text("Last name") }, modifier = Modifier.fillMaxWidth())
            SelectField("User type *", type, workspace.strings("user_types").map { it to it }) { type = it }
            Row { Checkbox(enabled, { enabled = it }); Text("Enabled") }
            if (original.text("name").isBlank()) Row { Checkbox(welcome, { welcome = it }); Text("Send welcome email") }
        } }
        item { SectionCard {
            Text("Access", fontWeight = FontWeight.Bold)
            SelectField("Access mode", mode, listOf("roles" to "Direct roles", "profiles" to "Role profiles")) { mode = it }
            if (mode == "roles") {
                OutlinedTextField(roleQuery, { roleQuery = it }, label = { Text("Find a role") }, modifier = Modifier.fillMaxWidth())
                workspace.items("roles").filter { roleQuery.isBlank() || it.text("name").contains(roleQuery, true) }
                    .forEach { row ->
                        val role = row.text("name")
                        Row { Checkbox(role in chosenRoles, { checked ->
                            chosenRoles = if (checked) chosenRoles + role else chosenRoles - role
                        }); Text(role) }
                    }
            } else workspace.items("role_profiles").forEach { row ->
                val profile = row.text("name")
                Row { Checkbox(profile in chosenProfiles, { checked ->
                    chosenProfiles = if (checked) chosenProfiles + profile else chosenProfiles - profile
                }); Text(profile) }
            }
            if (error.isNotBlank()) Text(error, color = warning)
            Button(onClick = {
                error = if (first.isBlank() || (original.text("name").isBlank() && email.isBlank())) "Enter the first name and login email." else ""
                if (error.isBlank()) {
                    val roles = JSONArray(); chosenRoles.sorted().forEach { roles.put(it) }
                    val profiles = JSONArray(); chosenProfiles.sorted().forEach { profiles.put(it) }
                    model.saveManagedUser(JSONObject().put("email", email).put("first_name", first)
                        .put("middle_name", middle).put("last_name", last).put("user_type", type)
                        .put("enabled", if (enabled) 1 else 0).put("send_welcome_email", if (welcome) 1 else 0)
                        .put("role_mode", mode).put("roles", roles).put("role_profiles", profiles))
                }
            }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Save user") }
        } }
    }
}
