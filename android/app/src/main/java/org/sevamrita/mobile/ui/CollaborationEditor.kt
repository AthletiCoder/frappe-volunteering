package org.sevamrita.mobile.ui

import android.app.DatePickerDialog
import android.app.TimePickerDialog
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CalendarToday
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.compose.ui.window.DialogWindowProvider
import androidx.core.view.WindowCompat
import java.time.LocalDate
import java.time.LocalTime
import java.time.format.DateTimeFormatter

@Composable
internal fun CollaborationEditor(
    title: String,
    contextLabel: String,
    action: String,
    saving: Boolean,
    dirty: Boolean,
    error: String,
    canSave: Boolean,
    onClose: () -> Unit,
    onSave: () -> Unit,
    content: @Composable ColumnScope.() -> Unit
) {
    var confirmDiscard by rememberSaveable { mutableStateOf(false) }
    fun close() {
        if (saving) return
        if (dirty) confirmDiscard = true else onClose()
    }

    Dialog(onDismissRequest = ::close, properties = DialogProperties(
        dismissOnClickOutside = false, usePlatformDefaultWidth = false, decorFitsSystemWindows = false
    )) {
        val view = LocalView.current
        val window = (view.parent as? DialogWindowProvider)?.window
        SideEffect {
            if (window != null) WindowCompat.getInsetsController(window, view).apply {
                isAppearanceLightStatusBars = true
                isAppearanceLightNavigationBars = true
            }
        }
        Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
            Column(Modifier.fillMaxSize().safeDrawingPadding().imePadding()) {
                Surface(color = MaterialTheme.colorScheme.surface) {
                    Row(Modifier.fillMaxWidth().heightIn(min = 64.dp).padding(end = 18.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        IconButton(onClick = ::close, enabled = !saving) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back")
                        }
                        Column(Modifier.weight(1f)) {
                            Text(title, Modifier.semantics { heading() }, style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.SemiBold)
                            if (contextLabel.isNotBlank()) Text(contextLabel, style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1,
                                overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis)
                        }
                    }
                }
                HorizontalDivider()
                Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.TopCenter) {
                    Column(Modifier.widthIn(max = 600.dp).fillMaxWidth().fillMaxHeight()
                        .verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 14.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp), content = content)
                }
                HorizontalDivider()
                Surface(color = MaterialTheme.colorScheme.surface) {
                    Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                        Column(Modifier.widthIn(max = 600.dp).fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            if (error.isNotBlank()) Text(error, Modifier.heightIn(max = 96.dp).verticalScroll(rememberScrollState()),
                                color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                            Button(onClick = onSave, enabled = canSave && !saving,
                                modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                                Text(if (saving) "Saving…" else action)
                            }
                        }
                    }
                }
            }
        }
        if (confirmDiscard) AlertDialog(
            onDismissRequest = { confirmDiscard = false },
            title = { Text("Discard changes?") },
            text = { Text("Your edits to this form will be lost.") },
            confirmButton = { TextButton(onClick = { confirmDiscard = false; onClose() }) { Text("Discard") } },
            dismissButton = { TextButton(onClick = { confirmDiscard = false }) { Text("Keep editing") } }
        )
    }
}

@Composable
internal fun EditorSection(title: String, content: @Composable ColumnScope.() -> Unit) {
    Surface(shape = RoundedCornerShape(16.dp), color = MaterialTheme.colorScheme.surface) {
        Column(Modifier.fillMaxWidth().padding(14.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
            Text(title, Modifier.semantics { heading() }, style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.SemiBold)
            content()
        }
    }
}

@Composable
internal fun EditorDisclosure(title: String, summary: String, initiallyExpanded: Boolean = false, content: @Composable ColumnScope.() -> Unit) {
    var open by rememberSaveable { mutableStateOf(initiallyExpanded) }
    Column(Modifier.fillMaxWidth()) {
        Surface(onClick = { open = !open }, shape = RoundedCornerShape(10.dp),
            color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = .45f)) {
            Row(Modifier.fillMaxWidth().heightIn(min = 48.dp).padding(horizontal = 12.dp, vertical = 7.dp),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Column(Modifier.weight(1f)) {
                    Text(title, style = MaterialTheme.typography.labelLarge)
                    if (!open && summary.isNotBlank()) Text(summary, style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Icon(if (open) Icons.Default.ExpandLess else Icons.Default.ExpandMore, if (open) "Collapse" else "Expand")
            }
        }
        AnimatedVisibility(open) {
            Column(Modifier.padding(top = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp), content = content)
        }
    }
}

@Composable
internal fun EditorText(
    label: String, value: String, multiline: Boolean = false,
    keyboard: KeyboardType = KeyboardType.Text, set: (String) -> Unit
) {
    OutlinedTextField(value, set, label = { Text(label) }, modifier = Modifier.fillMaxWidth(),
        minLines = if (multiline) 2 else 1, maxLines = if (multiline) 5 else 1, singleLine = !multiline,
        shape = RoundedCornerShape(12.dp), textStyle = MaterialTheme.typography.bodyMedium,
        keyboardOptions = KeyboardOptions(keyboardType = keyboard, imeAction = if (multiline) ImeAction.Default else ImeAction.Next))
}

@Composable
private fun EditorField(label: String, value: String, onClick: () -> Unit, trailing: @Composable () -> Unit) {
    Surface(shape = RoundedCornerShape(10.dp), color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = .32f)) {
        Row(Modifier.fillMaxWidth().heightIn(min = 56.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f).clickable(onClick = onClick).heightIn(min = 56.dp).padding(horizontal = 12.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.Center) {
                Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
            }
            trailing()
        }
    }
}

@Composable
internal fun EditorTime(label: String, time: LocalTime, display: String = time.toString(), reset: (() -> Unit)? = null, set: (LocalTime) -> Unit) {
    val context = LocalContext.current
    val pick = {
        TimePickerDialog(context, { _, hour, minute -> set(LocalTime.of(hour, minute)) },
            time.hour, time.minute, true).show()
    }
    EditorField(label, display, onClick = pick) {
        if (reset == null) IconButton(onClick = pick) { Icon(Icons.Default.Schedule, "Choose ${label.lowercase()}") }
        else IconButton(onClick = reset) { Icon(Icons.Default.Close, "Reset ${label.lowercase()}") }
    }
}

@Composable
internal fun EditorSelect(label: String, selected: String, options: List<Pair<String, String>>, choose: (String) -> Unit) {
    var open by remember { mutableStateOf(false) }
    var query by remember { mutableStateOf("") }
    val display = options.firstOrNull { it.first == selected }?.second ?: "Choose…"
    val showMenu = { query = ""; open = true }
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        EditorField(label, display, onClick = showMenu) {
            IconButton(onClick = showMenu) { Icon(Icons.Default.ExpandMore, "Choose ${label.lowercase()}") }
        }
        DropdownMenu(open, onDismissRequest = { open = false }, modifier = Modifier.width(maxWidth).heightIn(max = 360.dp)) {
            if (options.size > 8) OutlinedTextField(query, { query = it }, singleLine = true,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 4.dp),
                label = { Text("Search") }, leadingIcon = { Icon(Icons.Default.Search, null) })
            val visible = options.filter { (id, name) -> name.contains(query, ignoreCase = true) || id.contains(query, ignoreCase = true) }
            if (visible.isEmpty()) DropdownMenuItem(text = { Text(if (options.isEmpty()) "No options available" else "No matches") },
                onClick = {}, enabled = false)
            visible.forEach { (id, name) ->
                DropdownMenuItem(text = { Text(name) }, onClick = { open = false; choose(id) },
                    trailingIcon = if (id == selected) { { Icon(Icons.Default.Check, "Selected") } } else null)
            }
        }
    }
}

@Composable
internal fun EditorDate(label: String, value: String, canClear: Boolean = true, set: (String) -> Unit) {
    val context = LocalContext.current
    val parsed = remember(value) { runCatching { LocalDate.parse(value) }.getOrNull() }
    val display = parsed?.format(DateTimeFormatter.ofPattern("d MMM yyyy")) ?: value.ifBlank { "Choose date" }
    val pick = {
        val date = parsed ?: LocalDate.now()
        DatePickerDialog(context, { _, year, month, day ->
            set(LocalDate.of(year, month + 1, day).toString())
        }, date.year, date.monthValue - 1, date.dayOfMonth).show()
    }
    EditorField(label, display, onClick = pick) {
        if (value.isBlank() || !canClear) IconButton(onClick = pick) { Icon(Icons.Default.CalendarToday, "Choose ${label.lowercase()}") }
        else IconButton(onClick = { set("") }) { Icon(Icons.Default.Close, "Clear ${label.lowercase()}") }
    }
}
