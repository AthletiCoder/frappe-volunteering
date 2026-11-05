package org.sevamrita.mobile.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.FilterList
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.PersonOutline
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject
import org.sevamrita.mobile.data.text
import androidx.compose.foundation.BorderStroke

private val workGreen = Color(0xFF08745E)
private val workMuted = Color(0xFF637378)
private val pendingRed = Color(0xFFA22C35)

@Composable
internal fun TrackerPendingSummary(trackers: List<JSONObject>, user: String, archived: Boolean = false) {
    val mine = if (archived) 0 else trackers.count { trackerPendingWith(it)?.isMe(user) == true }
    Row(Modifier.fillMaxWidth().padding(horizontal = 2.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Surface(color = if (mine > 0) Color(0xFFFCE4E5) else Color(0xFFEDF0F0), shape = RoundedCornerShape(12.dp)) {
            Text(mine.toString(), Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                color = if (mine > 0) pendingRed else workMuted, fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.titleMedium)
        }
        Column(Modifier.weight(1f)) {
            Text("Pending with me", fontWeight = FontWeight.SemiBold, color = if (mine > 0) pendingRed else workMuted)
            Text("${trackers.size} trackers in this view", color = workMuted, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
internal fun TrackerFilter(value: String, onChange: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        TextButton(onClick = { expanded = true }, contentPadding = PaddingValues(horizontal = 8.dp)) {
            Icon(Icons.Default.FilterList, "Filter trackers", Modifier.size(20.dp))
            Text(value, Modifier.padding(start = 5.dp))
            Icon(Icons.Default.ExpandMore, null, Modifier.size(18.dp))
        }
        DropdownMenu(expanded, onDismissRequest = { expanded = false }) {
            TRACKER_FILTERS.forEach { filter -> DropdownMenuItem(
                text = { Text(filter, fontWeight = if (filter == value) FontWeight.Bold else FontWeight.Normal) },
                onClick = { expanded = false; onChange(filter) }) }
        }
    }
}

@Composable
internal fun WorkCreateButton(label: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    FloatingActionButton(onClick = { if (enabled) onClick() }, modifier = modifier, containerColor = workGreen, contentColor = Color.White) {
        Icon(Icons.Default.Add, contentDescription = label)
    }
}

@Composable
internal fun WorkStatus(status: String, change: ((String) -> Unit)? = null, enabled: Boolean = true) {
    var expanded by remember { mutableStateOf(false) }
    val color = when (status) { "Failed" -> Color(0xFFA23C35); "In progress" -> Color(0xFF275FAD); else -> workGreen }
    Box {
        if (change != null) TextButton(onClick = { expanded = true }, enabled = enabled,
            colors = ButtonDefaults.textButtonColors(contentColor = color), contentPadding = PaddingValues(horizontal = 8.dp)) {
            Text(status, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
            Icon(Icons.Default.ExpandMore, null, Modifier.size(18.dp))
        } else Surface(color = color.copy(alpha = 0.09f), shape = RoundedCornerShape(8.dp)) {
            Text(status, Modifier.padding(horizontal = 8.dp, vertical = 5.dp), color = color, fontSize = 12.sp)
        }
        DropdownMenu(expanded && change != null, onDismissRequest = { expanded = false }) {
            TASK_STATUSES.forEach { next -> DropdownMenuItem(text = { Text(next) }, enabled = next != status,
                onClick = { expanded = false; change?.invoke(next) }) }
        }
    }
}

@Composable
internal fun TaskRow(item: JSONObject, enabled: Boolean, action: (String) -> Unit, edit: (() -> Unit)?, history: () -> Unit,
    openConversation: (() -> Unit)? = null, share: (() -> Unit)? = null, openDetails: (() -> Unit)? = null) {
    var expanded by remember { mutableStateOf(false) }
    val canEdit = item.optBoolean("can_edit")
    val canUpdate = item.optBoolean("can_update", canEdit)
    Surface(shape = RoundedCornerShape(16.dp), color = Color.White, tonalElevation = 0.dp) {
        Column(Modifier.fillMaxWidth().then(if (openDetails != null) Modifier.clickable(onClick = openDetails) else Modifier).padding(start = 14.dp, end = 8.dp, top = 6.dp, bottom = 12.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            if (item.text("space_title").isNotBlank()) Text(item.text("space_title"), color = workGreen, fontSize = 12.sp, modifier = Modifier.padding(top = 5.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(item.text("title"), Modifier.weight(1f), style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                WorkStatus(item.text("status"), if (canUpdate) { next -> taskStatusAction(next)?.let(action) } else null, enabled)
                Box {
                    IconButton(onClick = { expanded = true }, modifier = Modifier.size(48.dp)) { Icon(Icons.Default.MoreVert, "Task options", tint = workMuted) }
                    DropdownMenu(expanded, onDismissRequest = { expanded = false }) {
                        if (canEdit && edit != null) DropdownMenuItem(text = { Text("Edit task") }, enabled = enabled, onClick = { expanded = false; edit() })
                        if (canUpdate && item.text("status") in listOf("Open", "In progress")) {
                            DropdownMenuItem(text = { Text("Postpone") }, enabled = enabled, onClick = { expanded = false; action("postpone") })
                            DropdownMenuItem(text = { Text("Snooze / wake") }, enabled = enabled, onClick = { expanded = false; action("snooze") })
                        }
                        DropdownMenuItem(text = { Text("History") }, enabled = enabled, onClick = { expanded = false; history() })
                        if (share != null) DropdownMenuItem(text = { Text("Share") }, enabled = enabled, onClick = { expanded = false; share() })
                        if (openConversation != null) DropdownMenuItem(text = { Text("Open conversation") }, onClick = { expanded = false; openConversation() })
                    }
                }
            }
            val meta = listOf(item.text("assignee_name"), item.text("priority").takeIf { it != "Medium" }.orEmpty()).filter(String::isNotBlank)
            if (meta.isNotEmpty()) Text(meta.joinToString(" · "), color = workMuted, fontSize = 12.sp)
            workDates(item.text("from_date"), item.text("until_date"), item.text("deadline")).forEach { Text(it, color = workMuted, fontSize = 12.sp) }
            if (item.text("snoozed_until").isNotBlank()) Text("Snoozed until ${item.text("snoozed_until")}", fontSize = 12.sp, color = workMuted)
        }
    }
}

@Composable
internal fun TrackerRow(item: JSONObject, user: String, archived: Boolean = false, onClick: () -> Unit) {
    val config = item.optJSONObject("item_data") ?: JSONObject()
    val display = trackerDisplay(config)
    val outcome = item.text("status")
    val phase = display.phase(outcome)
    val pending = if (archived) null else trackerPendingWith(item)
    val mine = pending?.isMe(user) == true
    val accent = if (mine) pendingRed else phase.ink
    Surface(onClick = onClick, shape = RoundedCornerShape(16.dp),
        color = if (mine) Color(0xFFFFEEEF) else phase.tileColor,
        border = if (mine) BorderStroke(1.dp, Color(0xFFE8B7BC)) else null) {
        Column(Modifier.fillMaxWidth().padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(item.text("title"), Modifier.weight(1f), fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.titleMedium)
                TrackerPhaseBadge(phase, outcome)
                Icon(Icons.Default.ChevronRight, null, Modifier.size(18.dp), tint = workMuted)
            }
            if (pending != null) Row(verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                Icon(Icons.Default.PersonOutline, null, Modifier.size(16.dp), tint = if (mine) pendingRed else workMuted)
                Text(if (mine) "Pending with you" else if (pending.user.isBlank()) "Pending · unassigned" else "Pending with ${pending.displayName}",
                    color = if (mine) pendingRed else workMuted, fontSize = 12.sp,
                    fontWeight = if (mine) FontWeight.SemiBold else FontWeight.Normal)
            }
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text((if (display.stages.isNotEmpty() && display.currentIndex >= 0) "Current: " else "") + display.label,
                    Modifier.weight(1f), color = accent, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium)
                if (display.currentIndex >= 0) Text("${display.currentIndex + 1} / ${display.stages.size}", color = workMuted, style = MaterialTheme.typography.labelSmall)
            }
            TrackerBar(display, outcome, accent)
            workDates(config.text("attention_date"), config.text("attention_until"), item.text("deadline"), "Attention").forEach { Text(it, color = workMuted, fontSize = 12.sp) }
        }
    }
}
