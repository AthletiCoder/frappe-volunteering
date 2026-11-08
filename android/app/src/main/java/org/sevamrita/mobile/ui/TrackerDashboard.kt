package org.sevamrita.mobile.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject
import org.sevamrita.mobile.data.text

internal enum class TrackerScope(val label: String) { OPEN("Open"), MINE("My actions"), OTHERS("Waiting on others"), COMPLETED("Completed"), ALL("All") }

internal fun trackerInScope(scope: TrackerScope, status: String, mine: Boolean): Boolean = when (scope) {
    TrackerScope.ALL -> true
    TrackerScope.OPEN -> status in listOf("Open", "In progress")
    TrackerScope.MINE -> mine && status in listOf("Open", "In progress")
    TrackerScope.OTHERS -> !mine && status in listOf("Open", "In progress")
    TrackerScope.COMPLETED -> status == "Completed"
}

@Composable
internal fun TrackerDashboard(trackers: List<JSONObject>, user: String, filter: String, onFilter: (String) -> Unit,
    listState: LazyListState, hasMore: Boolean, onOpen: (JSONObject) -> Unit) {
    var scopeName by rememberSaveable { mutableStateOf(TrackerScope.OPEN.name) }
    var search by rememberSaveable { mutableStateOf("") }
    var searching by rememberSaveable { mutableStateOf(false) }
    val scope = when (filter) { "Completed" -> TrackerScope.COMPLETED; "All", "Failed" -> TrackerScope.ALL; else -> TrackerScope.valueOf(scopeName).takeUnless { it in listOf(TrackerScope.COMPLETED, TrackerScope.ALL) } ?: TrackerScope.OPEN }
    fun choose(next: TrackerScope) { scopeName = next.name; onFilter(when (next) { TrackerScope.ALL -> "All"; TrackerScope.COMPLETED -> "Completed"; else -> "Open" }) }
    val pending = trackers.filter { trackerPendingWith(it)?.isMe(user) == true }
    val complete = trackers.count { it.text("status") == "Completed" }
    val visible = trackers.filter { item ->
        trackerInScope(scope, item.text("status"), trackerPendingWith(item)?.isMe(user) == true) &&
            trackerMatchesFilter(item.text("status"), filter) &&
            (search.isBlank() || listOf(item.text("title"), item.text("space_title"), trackerPendingWith(item)?.displayName.orEmpty()).any { it.contains(search, true) })
    }
    val attention = if (scope == TrackerScope.OPEN && search.isBlank()) pending.take(1) else emptyList()
    val grouped = visible.filterNot { item -> attention.isNotEmpty() && trackerPendingWith(item)?.isMe(user) == true }
    LazyColumn(Modifier.fillMaxSize(), state = listState, contentPadding = PaddingValues(start = 18.dp, end = 18.dp, top = 12.dp, bottom = 90.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(9.dp)) {
                TrackerStat("All trackers", trackers.size, appColor(0xFFEEF1FF), appColor(0xFF315EB7), Icons.Default.Layers, Modifier.weight(1f)) { choose(TrackerScope.ALL) }
                TrackerStat("My actions", pending.size, appColor(0xFFFFEEF0), appColor(0xFFA42E40), Icons.Default.PersonOutline, Modifier.weight(1f)) { choose(TrackerScope.MINE) }
                TrackerStat("Completed", complete, appColor(0xFFE5F5ED), appColor(0xFF08745E), Icons.Default.CheckCircleOutline, Modifier.weight(1f)) { choose(TrackerScope.COMPLETED) }
            }
            if (hasMore) Text("Counts show the trackers currently loaded.", Modifier.padding(top = 8.dp), style = MaterialTheme.typography.bodySmall, color = appColor(0xFF687778))
        }
        if (attention.isNotEmpty()) {
            item {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Needs your attention", Modifier.weight(1f), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    TextButton(onClick = { choose(TrackerScope.MINE) }) { Text("View all ${pending.size}") }
                }
            }
            items(attention, key = { "attention:${it.text("name")}" }) { item -> TrackerRow(item, user, showChat = true) { onOpen(item) } }
        }
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(if (attention.isNotEmpty()) "Other trackers" else "Your trackers", Modifier.weight(1f), fontSize = 20.sp, fontWeight = FontWeight.Bold)
                IconButton(onClick = { searching = !searching; if (!searching) search = "" }) { Icon(Icons.Default.Search, "Search trackers") }
            }
            if (searching) OutlinedTextField(search, { search = it }, modifier = Modifier.fillMaxWidth(), singleLine = true,
                placeholder = { Text("Title, chat or person") }, shape = RoundedCornerShape(16.dp), trailingIcon = {
                    IconButton(onClick = { search = ""; searching = false }) { Icon(Icons.Default.Close, "Close search") }
                })
            LazyRow(horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                items(TrackerScope.entries) { next -> FilterChip(selected = scope == next, onClick = { choose(next) }, label = { Text(next.label) }, shape = RoundedCornerShape(20.dp)) }
            }
        }
        if (grouped.isEmpty()) item {
            Surface(shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, appColor(0xFFE6EAED))) {
                Text(if (attention.isNotEmpty()) "You're seeing your pending work above. Choose a filter to explore more." else "No trackers match this view.", Modifier.padding(20.dp), color = appColor(0xFF687778))
            }
        }
        groupTrackersByChat(grouped, { it.text("space") }, { it.text("space_title") }).forEach { group ->
            item(key = "group:${group.chatId}") { Text(group.title, Modifier.padding(top = 8.dp), color = appColor(0xFF52636A), style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold) }
            items(group.trackers, key = { it.text("name") }) { item -> TrackerRow(item, user) { onOpen(item) } }
        }
    }
}

@Composable
private fun TrackerStat(label: String, count: Int, background: Color, ink: Color, icon: androidx.compose.ui.graphics.vector.ImageVector,
    modifier: Modifier, onClick: () -> Unit) {
    Surface(onClick = onClick, modifier = modifier, shape = RoundedCornerShape(20.dp), color = background) {
        Column(Modifier.padding(horizontal = 12.dp, vertical = 16.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
            Icon(icon, null, tint = ink, modifier = Modifier.size(24.dp))
            Text(count.toString(), fontSize = 28.sp, color = appColor(0xFF172A38), fontWeight = FontWeight.Bold)
            Text(label, fontSize = 12.sp, lineHeight = 16.sp, color = ink)
        }
    }
}
