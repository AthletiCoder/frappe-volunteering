package org.sevamrita.mobile.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
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
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text

private val detailInk: Color @Composable get() = appColor(0xFF182C3A)
private val detailMuted: Color @Composable get() = appColor(0xFF677781)
private val detailBlue: Color @Composable get() = appColor(0xFF2E6CCD)
private val detailRed: Color @Composable get() = appColor(0xFFA52E42)

@Composable
internal fun TrackerDetailScreen(item: JSONObject, roomTitle: String, user: String, canUpdate: Boolean, canConfigure: Boolean,
    onUpdate: () -> Unit, onConfigure: () -> Unit, onShare: (() -> Unit)?, onHistory: () -> Unit,
    loadHistory: ((List<JSONObject>) -> Unit) -> Unit, onFile: (String) -> Unit,
    loadFiles: (String?, (JSONObject?) -> Unit) -> Unit, onAddFiles: (() -> Unit)?, comments: (@Composable () -> Unit)? = null) {
    var tab by rememberSaveable(item.text("name")) { mutableStateOf("Workflow") }
    var expandedDescription by rememberSaveable(item.text("name")) { mutableStateOf(true) }
    var history by remember(item.text("name")) { mutableStateOf(emptyList<JSONObject>()) }
    var options by remember { mutableStateOf(false) }
    LaunchedEffect(item.text("name"), item.text("modified")) { loadHistory { history = it } }
    val config = item.optJSONObject("item_data") ?: JSONObject()
    val display = trackerDisplay(config)
    val outcome = item.text("status")
    val phase = display.phase(outcome)
    val pending = trackerPendingWith(item)
    val mine = pending?.isMe(user) == true
    var files by remember(item.text("name")) { mutableStateOf(emptyList<JSONObject>()) }
    var fileCursor by remember(item.text("name")) { mutableStateOf<String?>(null) }
    var filesLoading by remember(item.text("name")) { mutableStateOf(false) }
    var filesLoaded by remember(item.text("name")) { mutableStateOf(false) }
    var filesError by remember(item.text("name")) { mutableStateOf(false) }
    var filesRestricted by remember(item.text("name")) { mutableStateOf(false) }
    fun fetchFiles(before: String? = null) {
        filesLoading = true; filesError = false
        loadFiles(before) { result ->
            filesLoading = false
            if (result == null) filesError = true
            else {
                files = ((if (before == null) emptyList() else files) + result.items("files")).distinctBy { it.text("name") }
                fileCursor = result.text("next_cursor").ifBlank { null }
                filesRestricted = result.optBoolean("restricted")
                filesLoaded = true
            }
        }
    }
    LaunchedEffect(item.text("name"), item.text("modified"), tab) { if (tab == "Files") fetchFiles() }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(start = 18.dp, end = 18.dp, top = 10.dp, bottom = 100.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item(key = "identity") {
            Text(roomTitle.ifBlank { item.text("space_title") }, color = detailMuted, fontSize = 13.sp)
            Row(verticalAlignment = Alignment.Top) {
                Text(item.text("title"), Modifier.weight(1f).padding(top = 5.dp, bottom = 12.dp), color = detailInk,
                    fontSize = 27.sp, lineHeight = 33.sp, fontWeight = FontWeight.Bold)
                Box {
                    IconButton(onClick = { options = true }) { Icon(Icons.Default.MoreVert, "Tracker actions", tint = detailMuted) }
                    DropdownMenu(options, onDismissRequest = { options = false }) {
                        if (canConfigure) DropdownMenuItem(text = { Text("Configure tracker") }, onClick = { options = false; onConfigure() })
                        if (onShare != null) DropdownMenuItem(text = { Text("Share tracker") }, onClick = { options = false; onShare() })
                        DropdownMenuItem(text = { Text("Full activity history") }, onClick = { options = false; onHistory() })
                    }
                }
            }
            TrackerPhaseBadge(phase, outcome)
        }
        item(key = "progress") {
            DetailPanel {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Progress", color = detailMuted, fontSize = 12.sp)
                        Text(if (display.stages.isNotEmpty()) when {
                            outcome == "Completed" -> "${display.stages.size} / ${display.stages.size} complete"
                            display.currentIndex >= 0 -> "Step ${display.currentIndex + 1} / ${display.stages.size}"
                            else -> "Not started"
                        } else display.label, color = detailInk, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                        TrackerBar(display, outcome, phase.ink)
                    }
                    VerticalDivider(Modifier.height(72.dp), color = appColor(0xFFE5EAED))
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Responsibility", color = detailMuted, fontSize = 12.sp)
                        Icon(if (mine) Icons.Default.PersonOutline else Icons.Default.PeopleOutline, null, Modifier.size(20.dp), tint = if (mine) detailRed else phase.ink)
                        Text(if (pending == null) outcome else if (mine) "Pending with you" else "Pending with ${pending.displayName}", color = if (mine) detailRed else detailInk,
                            fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                    }
                }
            }
        }
        item(key = "tabs") {
            TabRow(selectedTabIndex = (listOf("Workflow", "Details", "Updates", "Files") + if(comments!=null) listOf("Comments") else emptyList()).indexOf(tab),
                containerColor = Color.Transparent, divider = { HorizontalDivider(color = appColor(0xFFE4E9EC)) }) {
                (listOf("Workflow", "Details", "Updates", "Files") + if(comments!=null) listOf("Comments") else emptyList()).forEach { label ->
                    Tab(selected = label == tab, onClick = { tab = label }) {
                        Text(label, modifier = Modifier.padding(horizontal = 2.dp, vertical = 16.dp), style = MaterialTheme.typography.labelMedium, maxLines = 1)
                    }
                }
            }
        }
        when (tab) {
            "Comments" -> item(key="comments"){comments?.invoke()}
            "Workflow" -> {
                item(key = "workflow") { DetailPanel {
                    Text(if (display.stages.isEmpty()) "Current progress" else "${if (display.scale == "Status") "Statuses" else "Stages"} (${display.stages.size})",
                        fontSize = 19.sp, fontWeight = FontWeight.Bold, color = detailInk)
                    if (display.stages.isEmpty()) {
                        Text(display.label, fontSize = 24.sp, fontWeight = FontWeight.Bold, color = phase.ink)
                        if (canUpdate) Button(onClick = onUpdate, modifier = Modifier.fillMaxWidth()) { Text("Update progress") }
                    } else display.stages.forEachIndexed { index, stage ->
                        val milestone = display.milestoneState(index, outcome)
                        val current = milestone == MilestoneState.CURRENT || display.currentIndex < 0 && index == 0 && pending != null
                        val person = stage.assigneeName.ifBlank { pending?.displayName.orEmpty().takeIf { current }.orEmpty() }
                        Row(Modifier.fillMaxWidth().background(if (current) appColor(0xFFEDF2FF) else Color.Transparent, RoundedCornerShape(16.dp)).padding(12.dp),
                            horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Box(Modifier.size(27.dp).background(when { milestone == MilestoneState.DONE -> appColor(0xFF39A65E); current -> detailBlue; else -> appColor(0xFFE8ECEF) }, CircleShape), contentAlignment = Alignment.Center) {
                                    if (milestone == MilestoneState.DONE) Icon(Icons.Default.Check, null, Modifier.size(18.dp), tint = MaterialTheme.colorScheme.surface)
                                    else if (current) Box(Modifier.size(9.dp).background(MaterialTheme.colorScheme.surface, CircleShape))
                                }
                                if (index < display.stages.lastIndex) Box(Modifier.width(2.dp).height(39.dp).background(appColor(0xFFDCE3E8)))
                            }
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                                Text(stage.label, fontWeight = FontWeight.SemiBold, color = detailInk, fontSize = 16.sp)
                                Text(when { milestone == MilestoneState.DONE -> "Passed"; current && mine -> "Pending with you"; current -> "Current stage"; else -> "Not started" },
                                    color = if (current && mine) detailRed else detailMuted, fontSize = 12.sp)
                                if (person.isNotBlank() && !(current && mine)) Text(person, color = detailMuted, fontSize = 12.sp)
                                if (current && canUpdate) TextButton(onClick = onUpdate, contentPadding = PaddingValues(0.dp)) { Text("Take action →", fontWeight = FontWeight.SemiBold) }
                            }
                        }
                    }
                    if (canUpdate && (display.currentIndex < 0 || outcome in listOf("Completed", "Failed"))) OutlinedButton(onClick = onUpdate, modifier = Modifier.fillMaxWidth()) {
                        Text(if (outcome in listOf("Completed", "Failed")) "Update / reopen tracker" else "Record progress")
                    }
                    HorizontalDivider(color = appColor(0xFFE8ECEF))
                    val dates = workDates(config.text("attention_date"), config.text("attention_until"), item.text("deadline"), "Attention")
                    if (dates.isEmpty()) Text("No dates set", color = detailMuted, fontSize = 12.sp)
                    else dates.forEach { Text(it, color = detailMuted, fontSize = 12.sp) }
                    if (config.text("next_action").isNotBlank()) Text("Next: ${config.text("next_action")}", fontWeight = FontWeight.Medium, fontSize = 14.sp)
                } }
                item { DetailPanel {
                    TextButton(onClick = { expandedDescription = !expandedDescription }, contentPadding = PaddingValues(0.dp), modifier = Modifier.fillMaxWidth()) {
                        Text("Description", Modifier.weight(1f), color = detailInk, fontWeight = FontWeight.Bold, fontSize = 17.sp)
                        Icon(if (expandedDescription) Icons.Default.ExpandLess else Icons.Default.ExpandMore, null)
                    }
                    if (expandedDescription) Text(item.text("description").ifBlank { "No description added." }, color = detailMuted, fontSize = 14.sp)
                } }
            }
            "Details" -> item { DetailPanel {
                listOf("Measurement" to display.scale, "Priority" to item.text("priority"), "Responsibility" to (if (config.text("assignment_mode") == "Stages") "Assigned by stage" else "One person"),
                    "Assigned to" to item.text("assignee_name"), "Updated" to item.text("modified").replace('T', ' ').take(16)).filter { it.second.isNotBlank() }.forEach { (label, value) ->
                    Text(label, color = detailMuted, fontSize = 12.sp); Text(value, color = detailInk, fontSize = 15.sp)
                }
                if (canConfigure) OutlinedButton(onClick = onConfigure) { Text("Configure tracker") }
                if (onShare != null) TextButton(onClick = onShare) { Text("Share tracker") }
            } }
            "Updates" -> {
                if (history.isEmpty()) item { Text("No updates loaded yet. You can open the full history from Tracker actions.", color = detailMuted) }
                items(history, key = { it.text("name") }) { entry -> DetailPanel {
                    Text(entry.text("author_name"), fontWeight = FontWeight.SemiBold, color = detailInk)
                    Text(entry.text("creation").take(16), fontSize = 11.sp, color = detailMuted)
                    if (entry.text("entry_kind") == "Progress") entry.optJSONObject("snapshot")?.let { TrackerSnapshot(it, recordedAt = entry.text("creation"), user = user) }
                    Text(entry.text("body"), color = detailInk, fontSize = 14.sp)
                    entry.items("attachments").forEach { file -> TextButton(onClick = { onFile(file.text("file_url")) }) {
                        Icon(Icons.Default.AttachFile, null, Modifier.size(18.dp)); Text(file.text("file_name"))
                    } }
                } }
            }
            "Files" -> {
                item(key = "files-heading") { DetailPanel {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                            Text("Tracker files", fontWeight = FontWeight.Bold, fontSize = 18.sp, color = detailInk)
                            Text("Private to this conversation", fontSize = 12.sp, color = detailMuted)
                        }
                        if (onAddFiles != null) FilledTonalButton(onClick = onAddFiles) { Icon(Icons.Default.Add, null, Modifier.size(18.dp)); Text("Add files") }
                    }
                    if (filesRestricted) Text("Files are available only to members of the conversation.", color = detailMuted)
                    else if (filesLoading && !filesLoaded) Text("Loading files…", color = detailMuted)
                    else if (!filesError && files.isEmpty()) Text("No files yet. Add supporting documents here or with a progress update.", color = detailMuted)
                    if (filesError) {
                        Text("Files could not be loaded. Check your connection and try again.", color = MaterialTheme.colorScheme.error)
                        OutlinedButton(onClick = { fetchFiles(if (filesLoaded) fileCursor else null) }, enabled = !filesLoading) { Text("Try again") }
                    }
                } }
                items(files, key = { "file:${it.text("name")}" }) { file -> Surface(shape = RoundedCornerShape(18.dp), color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, appColor(0xFFE5E9EE)),
                    onClick = { onFile(file.text("file_url")) }) {
                    Row(Modifier.fillMaxWidth().padding(16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.Top) {
                        Icon(Icons.Default.Description, null, Modifier.size(25.dp), tint = detailBlue)
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                            Text(file.text("file_name"), fontWeight = FontWeight.SemiBold, color = detailInk)
                            Text("${trackerAttachmentSize(file.optLong("file_size"))} · ${file.text("uploaded_by_name")}", fontSize = 12.sp, color = detailMuted)
                            Text(file.text("creation").replace('T', ' ').take(16), fontSize = 11.sp, color = detailMuted)
                            if (file.text("note").isNotBlank()) Text(file.text("note"), fontSize = 13.sp, color = detailMuted, maxLines = 3,
                                overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis)
                        }
                        Icon(Icons.Default.ChevronRight, "Open file", tint = detailMuted)
                    }
                } }
                if (fileCursor != null && !filesError) item(key = "more-files") { OutlinedButton(onClick = { fetchFiles(fileCursor) }, enabled = !filesLoading, modifier = Modifier.fillMaxWidth()) { Text(if (filesLoading) "Loading files…" else "Load older files") } }
            }
        }
    }
}

@Composable
private fun DetailPanel(content: @Composable ColumnScope.() -> Unit) {
    Surface(shape = RoundedCornerShape(22.dp), color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, appColor(0xFFE5E9EE))) {
        Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp), content = content)
    }
}
