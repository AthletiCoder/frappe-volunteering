package org.sevamrita.mobile.ui

import android.app.DatePickerDialog
import android.os.Build
import android.widget.NumberPicker
import android.view.ViewGroup
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject
import org.sevamrita.mobile.SectionCard
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.UUID

data class WorkLogItemDraft(
    val key: String = UUID.randomUUID().toString(),
    val title: String = "",
    val project: String = "",
    val projectName: String = "",
    val description: String = "",
    val hours: String = "",
    val output: String = ""
)

data class WorkLogDraft(val date: String, val notes: String, val items: List<WorkLogItemDraft>, val exception: String = "") {
    val total: Double get() = items.sumOf { it.hours.toDoubleOrNull()?.takeIf(Double::isFinite) ?: 0.0 }
    fun payload(log: JSONObject): JSONObject = JSONObject()
        .put("name", log.text("name")).put("modified", log.text("modified"))
        .put("employee", log.text("employee")).put("hr_exception_reason", exception).put("date", date).put("notes", notes).put("items", JSONArray().apply {
            items.forEach { item -> put(JSONObject().put("task_title", item.title).put("project", item.project)
                .put("description", item.description).put("time_spent_hours", item.hours).put("output_link", item.output)) }
        })

    companion object {
        fun from(log: JSONObject) = WorkLogDraft(log.text("date").take(10), log.text("notes"),
            log.items("items").map { WorkLogItemDraft(title = it.text("task_title"), project = it.text("project"),
                projectName = it.text("project_name"), description = it.text("description"),
                hours = it.text("time_spent_hours"), output = it.text("output_link")) })
    }
}

private fun workLogDate(value: String) = runCatching {
    LocalDate.parse(value.take(10)).format(DateTimeFormatter.ofPattern("d MMM yyyy"))
}.getOrDefault(value)

@Composable
private fun WorkLogStatus(status: String) {
    val colors = MaterialTheme.colorScheme
    val background = when (status) {
        "Submitted" -> colors.secondaryContainer
        "Reviewed" -> colors.primaryContainer
        "Cancelled" -> colors.errorContainer
        else -> colors.surfaceVariant
    }
    Surface(color = background, shape = MaterialTheme.shapes.small) {
        Text(status, Modifier.padding(horizontal = 10.dp, vertical = 5.dp), style = MaterialTheme.typography.labelMedium)
    }
}

@Composable
fun WorkLogScreen(state: PortalState, model: PortalViewModel) {
    val workspace = state.workLogData
    val log = workspace.optJSONObject("log") ?: JSONObject()
    val draft = state.workLogDraft
    val context = LocalContext.current
    var confirmSubmit by remember { mutableStateOf(false) }
    var pendingDate by remember { mutableStateOf<String?>(null) }
    var durationKey by remember { mutableStateOf<String?>(null) }
    var showNotes by remember(log.text("name")) { mutableStateOf(draft?.notes?.isNotBlank() == true) }
    var remarks by remember(log.text("name"), log.text("modified")) { mutableStateOf(log.text("manager_remarks")) }
    if (draft == null) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text(if (state.workLogLoading) "Loading work log…" else "Open a work log to continue.") }
        return
    }
    val editable = log.optBoolean("can_edit")
    val enabled = editable && !state.busy
    Column(Modifier.fillMaxSize()) {
        LazyColumn(Modifier.weight(1f).fillMaxWidth(), contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                if (!log.optBoolean("is_own", editable)) Text(log.text("employee_name"), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(bottom = 8.dp))
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    if (editable && log.text("name").isBlank()) OutlinedButton(onClick = {
                        val date = runCatching { LocalDate.parse(draft.date) }.getOrDefault(LocalDate.now())
                        DatePickerDialog(context, { _, year, month, day ->
                            val nextDate = LocalDate.of(year, month + 1, day).toString()
                            if (nextDate != draft.date) {
                                if (draft != state.workLogOriginal && (draft.notes.isNotBlank() || draft.items.any { it.title.isNotBlank() || it.description.isNotBlank() || it.hours.isNotBlank() })) pendingDate = nextDate
                                else model.openWorkLog(date = nextDate)
                            }
                        }, date.year, date.monthValue - 1, date.dayOfMonth).apply {
                            val zone = java.time.ZoneId.systemDefault()
                            datePicker.maxDate = LocalDate.parse(workspace.text("today")).atStartOfDay(zone).toInstant().toEpochMilli()
                            datePicker.minDate = LocalDate.parse(if (workspace.optBoolean("can_override")) "2000-01-01" else workspace.text("earliest_date")).atStartOfDay(zone).toInstant().toEpochMilli()
                        }.show()
                    }, enabled = enabled, contentPadding = PaddingValues(horizontal = 10.dp, vertical = 6.dp), modifier = Modifier.semantics { contentDescription = "Change work date" }) {
                        Icon(Icons.Default.CalendarMonth, null, Modifier.size(16.dp)); Spacer(Modifier.width(6.dp)); Text(workLogDate(draft.date), style = MaterialTheme.typography.labelMedium)
                    } else Text(workLogDate(draft.date), style = MaterialTheme.typography.labelLarge, modifier = Modifier.weight(1f))
                    WorkLogStatus(log.text("status"))
                    if (editable && log.text("name").isBlank()) Spacer(Modifier.weight(1f))
                }
                if (log.optBoolean("is_wfh")) Text("Approved work from home", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
            }
            items(draft.items, key = { it.key }) { item ->
                Surface(shape = RoundedCornerShape(16.dp), color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(if (editable) "Activity ${draft.items.indexOf(item) + 1}" else item.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                            if (editable) OutlinedButton(onClick = { durationKey = item.key }, enabled = enabled, contentPadding = PaddingValues(horizontal = 10.dp, vertical = 6.dp), modifier = Modifier.semantics { contentDescription = "Time spent on activity ${draft.items.indexOf(item) + 1}" }) {
                                Icon(Icons.Default.Schedule, null, Modifier.size(16.dp)); Spacer(Modifier.width(6.dp)); Text(if ((workLogMinutes(item.hours) ?: 0) > 0) workLogDurationLabel(item.hours) else "Set time", style = MaterialTheme.typography.labelMedium)
                            } else Text(workLogDurationLabel(item.hours), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                            if (editable && draft.items.size > 1) IconButton(onClick = { model.editWorkLog { it.copy(items = it.items.filterNot { row -> row.key == item.key }) } }, enabled = enabled, modifier = Modifier.size(36.dp)) { Icon(Icons.Default.Close, "Remove activity ${draft.items.indexOf(item) + 1}", Modifier.size(18.dp)) }
                        }
                        if (editable) {
                            OutlinedTextField(item.title, { value -> model.editWorkLogItem(item.key) { it.copy(title = value) } }, label = { Text("Activity *") }, placeholder = { Text("What did you work on?") }, singleLine = true, enabled = enabled, modifier = Modifier.fillMaxWidth())
                            val projects = workspace.items("projects").map { it.text("name") to it.text("project_name") }.toMutableList()
                            if (item.project.isNotBlank() && projects.none { it.first == item.project }) projects.add(item.project to item.projectName.ifBlank { item.project })
                            WorkLogProjectField(item.project, listOf("" to "General work") + projects, enabled) { value -> model.editWorkLogItem(item.key) { it.copy(project = value) } }
                            OutlinedTextField(workLogDetails(item.description, item.output), { value -> model.editWorkLogItem(item.key) { it.copy(description = value, output = "") } }, label = { Text("Details *") }, minLines = 2, maxLines = 6, enabled = enabled, modifier = Modifier.fillMaxWidth())
                        } else {
                            Text(workLogDetails(item.description, item.output), style = MaterialTheme.typography.bodyMedium)
                            Text(item.projectName.ifBlank { "General work" }, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)

                        }
                    }
                }
            }
            if (editable && workspace.optBoolean("can_override")) item {
                OutlinedTextField(draft.exception, { value -> model.editWorkLog { it.copy(exception = value) } }, label = { Text("HR exception reason") }, supportingText = { Text("Required for late or on-behalf entries") }, minLines = 2, enabled = enabled, modifier = Modifier.fillMaxWidth())
            }
            if (editable) item {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    TextButton(onClick = { model.editWorkLog { it.copy(items = it.items + WorkLogItemDraft()) } }, enabled = enabled && draft.items.size < 100) { Icon(Icons.Default.Add, null, Modifier.size(18.dp)); Text("Add activity") }
                    if (!showNotes) TextButton(onClick = { showNotes = true }, enabled = enabled) { Text("Add notes") }
                }
            }
            if (editable) item { AnimatedVisibility(showNotes) {
                OutlinedTextField(draft.notes, { value -> model.editWorkLog { it.copy(notes = value) } }, label = { Text("Notes (optional)") }, enabled = enabled, minLines = 2, modifier = Modifier.fillMaxWidth())
            } } else if (draft.notes.isNotBlank()) item {
                Text("Notes", style = MaterialTheme.typography.labelLarge)
                Text(draft.notes, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (log.optBoolean("can_review")) item {
                Text("Manager review", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                OutlinedTextField(remarks, { remarks = it }, label = { Text("Private review notes") }, supportingText = { Text("Visible to managers and HR") }, enabled = !state.busy, minLines = 2, modifier = Modifier.fillMaxWidth())
            } else if (log.text("manager_remarks").isNotBlank()) item {
                Text("Private review notes", fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.labelLarge)
                Text(log.text("manager_remarks"), style = MaterialTheme.typography.bodyMedium)
            }
        }
        Surface(tonalElevation = 2.dp) {
            Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("${draft.items.size} ${if (draft.items.size == 1) "activity" else "activities"} · ${workLogDurationLabel(draft.total.toString())}", style = MaterialTheme.typography.labelLarge)
                if (editable) Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    OutlinedButton(onClick = { model.saveWorkLog(false) }, enabled = enabled, modifier = Modifier.weight(1f)) { Text("Save draft") }
                    Button(onClick = { confirmSubmit = true }, enabled = enabled, modifier = Modifier.weight(1f)) { Text("Submit log") }
                } else if (log.optBoolean("can_review")) Button(onClick = { model.reviewWorkLog(remarks) }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Mark as reviewed") }
            }
        }
    }
    durationKey?.let { key -> draft.items.firstOrNull { it.key == key }?.let { item ->
        WorkLogDurationDialog(item.hours, onDismiss = { durationKey = null }) { hours, minutes ->
            val originalMinutes = workLogMinutes(item.hours)
            model.editWorkLogItem(key) { it.copy(hours = if (originalMinutes == hours * 60 + minutes && item.hours.isNotBlank()) item.hours else workLogDurationHours(hours, minutes)) }
            durationKey = null
        }
    } }
    pendingDate?.let { date -> WorkLogDiscardDialog(onDismiss = { pendingDate = null }, onDiscard = { pendingDate = null; model.openWorkLog(date = date) }) }
    if (confirmSubmit) AlertDialog(onDismissRequest = { confirmSubmit = false }, title = { Text("Submit work log?") }, text = { Text("Submitted logs are available for manager review and update attendance.") }, confirmButton = { TextButton(onClick = { confirmSubmit = false; model.saveWorkLog(true) }) { Text("Submit") } }, dismissButton = { TextButton(onClick = { confirmSubmit = false }) { Text("Cancel") } })
}

@Composable
private fun WorkLogProjectField(value: String, options: List<Pair<String, String>>, enabled: Boolean, onChange: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    val name = options.firstOrNull { it.first == value }?.second.orEmpty()
    Box {
        OutlinedButton(onClick = { expanded = true }, enabled = enabled, contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp), modifier = Modifier.fillMaxWidth().semantics { contentDescription = "Project: $name" }) {
            Icon(Icons.Default.FolderOpen, null, Modifier.size(16.dp)); Spacer(Modifier.width(8.dp)); Text(name, modifier = Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis); Icon(Icons.Default.ExpandMore, null, Modifier.size(18.dp))
        }
        DropdownMenu(expanded, { expanded = false }, modifier = Modifier.heightIn(max = 300.dp)) {
            options.forEach { (id, label) -> DropdownMenuItem(text = { Text(label) }, onClick = { onChange(id); expanded = false }) }
        }
    }
}

@Composable
private fun WorkLogDurationDialog(value: String, onDismiss: () -> Unit, onConfirm: (Int, Int) -> Unit) {
    val initial = (workLogMinutes(value) ?: 0).coerceIn(0, 1440)
    var hours by remember { mutableIntStateOf(initial / 60) }
    var minutes by remember { mutableIntStateOf(initial % 60) }
    val dark = MaterialTheme.colorScheme.surface.luminance() < 0.5f
    val foreground = MaterialTheme.colorScheme.onSurface.toArgb()
    AlertDialog(onDismissRequest = onDismiss, title = { Text("Time spent") }, text = {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                for (isHours in listOf(true, false)) Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(if (isHours) "Hours" else "Minutes", style = MaterialTheme.typography.labelLarge)
                    AndroidView(factory = { ctx -> NumberPicker(android.view.ContextThemeWrapper(ctx, if (dark) android.R.style.Theme_DeviceDefault_Dialog else android.R.style.Theme_DeviceDefault_Light_Dialog)).apply {
                        minValue = 0; maxValue = if (isHours) 24 else 59; wrapSelectorWheel = !isHours
                        descendantFocusability = ViewGroup.FOCUS_BLOCK_DESCENDANTS
                        contentDescription = if (isHours) "Hours" else "Minutes"
                        if (Build.VERSION.SDK_INT >= 29) setTextColor(foreground)
                        setOnValueChangedListener { _, _, next -> if (isHours) { hours = next; if (next == 24) minutes = 0 } else minutes = next }
                    } }, update = { picker ->
                        val selected = if (isHours) hours else minutes
                        if (picker.value != selected) picker.value = selected
                        picker.isEnabled = isHours || hours < 24
                    }, modifier = Modifier.width(96.dp).height(136.dp))
                }
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                for (total in listOf(15, 30, 60)) SuggestionChip(onClick = { hours = total / 60; minutes = total % 60 }, label = { Text(if (total == 60) "1 h" else "$total min") })
            }
        }
    }, confirmButton = { TextButton(onClick = { onConfirm(hours, minutes) }, enabled = hours * 60 + minutes > 0) { Text("Set time") } }, dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } })
}

@Composable
fun WorkLogDiscardDialog(onDismiss: () -> Unit, onDiscard: () -> Unit) {
    AlertDialog(onDismissRequest = onDismiss, title = { Text("Discard unsaved changes?") }, text = { Text("Save the draft to keep your work before leaving.") }, confirmButton = { TextButton(onClick = onDiscard) { Text("Discard") } }, dismissButton = { TextButton(onClick = onDismiss) { Text("Keep editing") } })
}
