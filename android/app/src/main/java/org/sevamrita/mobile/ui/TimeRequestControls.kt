package org.sevamrita.mobile.ui

import android.app.DatePickerDialog
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

@Composable
internal fun TimeRequestSelect(
    label: String,
    value: String,
    options: List<Pair<String, String>>,
    enabled: Boolean,
    choose: (String) -> Unit
) {
    var expanded by remember { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Box {
            OutlinedButton(
                onClick = { expanded = true }, enabled = enabled,
                modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp),
                shape = RoundedCornerShape(10.dp),
                contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.onSurface)
            ) {
                Text(options.firstOrNull { it.first == value }?.second ?: "Choose…",
                    modifier = Modifier.weight(1f), textAlign = TextAlign.Start,
                    style = MaterialTheme.typography.bodyMedium, maxLines = 2)
                Icon(Icons.Default.ExpandMore, contentDescription = null, modifier = Modifier.size(20.dp))
            }
            DropdownMenu(expanded = expanded && enabled, onDismissRequest = { expanded = false },
                modifier = Modifier.widthIn(min = 220.dp, max = 340.dp)) {
                options.forEach { (key, title) ->
                    DropdownMenuItem(text = { Text(title) }, onClick = { expanded = false; choose(key) })
                }
            }
        }
    }
}

@Composable
internal fun TimeRequestDate(label: String, value: String, enabled: Boolean, choose: (String) -> Unit) {
    val context = LocalContext.current
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        OutlinedButton(
            onClick = {
                val date = runCatching { LocalDate.parse(value) }.getOrDefault(LocalDate.now())
                DatePickerDialog(context, { _, year, month, day ->
                    choose(LocalDate.of(year, month + 1, day).toString())
                }, date.year, date.monthValue - 1, date.dayOfMonth).show()
            }, enabled = enabled,
            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp),
            shape = RoundedCornerShape(10.dp),
            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
            colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.onSurface)
        ) {
            Text(if (value.isBlank()) "Choose date" else runCatching {
                LocalDate.parse(value).format(DateTimeFormatter.ofPattern("dd MMM yyyy", Locale.ENGLISH))
            }.getOrDefault(value), style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.weight(1f), textAlign = TextAlign.Start, maxLines = 2)
            Icon(Icons.Default.CalendarMonth, contentDescription = null, modifier = Modifier.size(18.dp))
        }
    }
}

@Composable
internal fun TimeRequestDates(
    startLabel: String, start: String, endLabel: String?, end: String,
    enabled: Boolean, changeStart: (String) -> Unit, changeEnd: (String) -> Unit
) {
    val fontScale = LocalDensity.current.fontScale
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        if (endLabel == null || maxWidth < 300.dp || fontScale > 1.25f) {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                TimeRequestDate(startLabel, start, enabled, changeStart)
                if (endLabel != null) TimeRequestDate(endLabel, end, enabled, changeEnd)
            }
        } else {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.Top) {
                Box(Modifier.weight(1f)) { TimeRequestDate(startLabel, start, enabled, changeStart) }
                Box(Modifier.weight(1f)) { TimeRequestDate(endLabel, end, enabled, changeEnd) }
            }
        }
    }
}

@Composable
internal fun TimeRequestCategory(value: String, medicalAvailable: Boolean, enabled: Boolean, choose: (String) -> Unit) {
    val options = listOf("Normal", "Emergency") + if (medicalAvailable) listOf("Medical") else emptyList()
    Column {
        Text("Leave category", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            options.forEach { option ->
                FilterChip(selected = value == option, onClick = { choose(option) }, enabled = enabled,
                    modifier = Modifier.weight(1f), shape = RoundedCornerShape(10.dp),
                    label = { Text(option, style = MaterialTheme.typography.labelLarge,
                        fontWeight = if (value == option) FontWeight.SemiBold else FontWeight.Normal) })
            }
        }
    }
}
