package org.sevamrita.mobile.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Reply
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.currentStateAsState
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONObject
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text

private val emerald = Color(0xFF08745E)
private val messageInk = Color(0xFF172B2B)
private val greyInk = Color(0xFF687778)
private val chatPaper = Color(0xFFF2EEE7)
private val avatarTints = listOf(0xFFD8EEE7, 0xFFDDE8F6, 0xFFF1E2EF, 0xFFF9E8D0, 0xFFE7E4F7, 0xFFDDECEC)

@Composable
internal fun ChatAvatar(title: String, modifier: Modifier = Modifier) {
    val colour = Color(avatarTints[Math.floorMod(title.lowercase().hashCode(), avatarTints.size)])
    Box(modifier.size(50.dp).background(colour, CircleShape).clearAndSetSemantics {}, contentAlignment = Alignment.Center) {
        Text(chatInitials(title), color = emerald, fontWeight = FontWeight.SemiBold, fontSize = 17.sp)
    }
}

@Composable
internal fun ChatInbox(
    rooms: List<JSONObject>, state: LazyListState, onOpen: (String) -> Unit, onNew: () -> Unit,
    search: String, onSearch: (String) -> Unit, archived: Boolean, onArchived: (Boolean) -> Unit
) {
    var filter by rememberSaveable { mutableStateOf("All") }
    var expanded by rememberSaveable { mutableStateOf(emptyList<String>()) }
    val summaries = rooms.map { room ->
        val last = room.optJSONObject("last_entry")
        ChatSummary(room.text("name"), room.text("title"), room.text("space_kind"), room.text("parent_space"),
            chatPreview(last?.text("body").orEmpty()).ifBlank { if (last == null) "" else "Message removed" }, last?.text("creation").orEmpty().ifBlank { room.text("modified") },
            room.optInt("unread"), room.optBoolean("archived"))
    }
    val rows = chatInboxRows(summaries, expanded.toSet(), search, filter, archived)
    Box(Modifier.fillMaxSize().background(Color.White)) {
        Column {
            TextField(search, onSearch, modifier = Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 6.dp),
                placeholder = { Text("Search chats") }, singleLine = true, shape = RoundedCornerShape(28.dp),
                leadingIcon = { Icon(Icons.Default.Search, null, tint = greyInk) },
                trailingIcon = if (search.isNotBlank()) ({ IconButton(onClick = { onSearch("") }) { Icon(Icons.Default.Close, "Clear search") } }) else null,
                colors = TextFieldDefaults.colors(focusedContainerColor = Color(0xFFF0F3F2), unfocusedContainerColor = Color(0xFFF0F3F2),
                    focusedIndicatorColor = Color.Transparent, unfocusedIndicatorColor = Color.Transparent))
            LazyRow(contentPadding = PaddingValues(horizontal = 14.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(listOf("All", "Unread", "Groups", "Direct")) { label -> FilterChip(selected = filter == label, onClick = { filter = label },
                    label = { Text(label) }, shape = RoundedCornerShape(20.dp),
                    colors = FilterChipDefaults.filterChipColors(selectedContainerColor = Color(0xFFD9EFE4), selectedLabelColor = emerald)) }
                item { FilterChip(selected = archived, onClick = { onArchived(!archived) }, label = { Text("Archived") }, shape = RoundedCornerShape(20.dp)) }
            }
            LazyColumn(Modifier.weight(1f).fillMaxWidth(), state = state, contentPadding = PaddingValues(top = 4.dp, bottom = 94.dp)) {
                items(rows, key = { it.chat.id }) { row ->
                    val room = row.chat
                    Column(Modifier.padding(start = (row.depth * 12).dp)) {
                        Row(Modifier.fillMaxWidth().clickable { onOpen(room.id) }.heightIn(min = 72.dp).padding(horizontal = 14.dp, vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically) {
                            ChatAvatar(room.title, Modifier.size(44.dp))
                            Spacer(Modifier.width(12.dp))
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(room.title, Modifier.weight(1f), fontSize = 16.sp, fontWeight = if (room.unread > 0) FontWeight.Bold else FontWeight.SemiBold,
                                        color = messageInk, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                    Text(chatListTime(room.timestamp), Modifier.padding(start = 8.dp), color = if (room.unread > 0) emerald else greyInk, fontSize = 11.sp)
                                }
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(if (search.isNotBlank() && room.parent.isNotBlank()) row.path else room.preview.ifBlank { "Start a conversation" },
                                        Modifier.weight(1f), color = greyInk, fontSize = 14.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                    if (room.unread > 0) Box(Modifier.padding(start = 8.dp).sizeIn(minWidth = 22.dp, minHeight = 22.dp).background(emerald, CircleShape).padding(horizontal = 5.dp), contentAlignment = Alignment.Center) {
                                        Text(if (room.unread > 99) "99+" else room.unread.toString(), color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                                    }
                                }
                                if (row.childCount > 0 || room.archived) Text(if (room.archived) "Archived" else "${row.childCount} subareas", color = greyInk, fontSize = 11.sp)
                            }
                            if (row.childCount > 0 && filter == "All" && search.isBlank()) IconButton(onClick = { expanded = if (room.id in expanded) expanded - room.id else expanded + room.id }) {
                                Icon(if (room.id in expanded) Icons.Default.ExpandMore else Icons.Default.ChevronRight,
                                    "${if (room.id in expanded) "Collapse" else "Expand"} ${room.title} subareas", tint = greyInk)
                            }
                        }
                        HorizontalDivider(Modifier.padding(start = 77.dp), color = Color(0xFFEEF1EF))
                    }
                }
                if (rows.isEmpty()) item { Column(Modifier.fillMaxWidth().padding(36.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(Icons.Default.Forum, null, Modifier.size(42.dp), tint = emerald)
                    Text(if (search.isBlank()) "No chats in this view" else "No matching conversations", Modifier.padding(top = 14.dp), fontWeight = FontWeight.SemiBold)
                    Text("Start a chat with a person or your team.", color = greyInk, fontSize = 13.sp)
                } }
            }
        }
        FloatingActionButton(onClick = onNew, modifier = Modifier.align(Alignment.BottomEnd).padding(20.dp), containerColor = emerald, contentColor = Color.White) {
            Icon(Icons.Default.AddComment, "New chat")
        }
    }
}

internal data class ChatComposerData(
    val body: String, val kind: String, val reply: JSONObject?, val files: List<JSONObject>, val editing: Boolean
)
internal data class ChatThreadActions(
    val back: () -> Unit, val tasks: () -> Unit, val trackers: () -> Unit, val members: () -> Unit, val newArea: () -> Unit,
    val refresh: () -> Unit, val signOut: () -> Unit, val older: () -> Unit,
    val reply: (JSONObject) -> Unit, val task: (JSONObject) -> Unit, val tracker: (JSONObject) -> Unit, val edit: (JSONObject) -> Unit,
    val remove: (JSONObject) -> Unit, val info: (JSONObject) -> Unit, val seen: (JSONObject) -> Unit,
    val openTracker: (String) -> Unit, val openFile: (String) -> Unit,
    val body: (String) -> Unit, val kind: (String) -> Unit, val attach: () -> Unit,
    val removeFile: (JSONObject) -> Unit, val cancelReply: () -> Unit, val cancelEdit: () -> Unit, val send: () -> Unit
)

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class, ExperimentalLayoutApi::class)
@Composable
internal fun ChatThread(
    data: JSONObject, user: String, busy: Boolean, canMarkSeen: Boolean,
    listState: LazyListState, composer: ChatComposerData, actions: ChatThreadActions
) {
    val space = data.optJSONObject("space") ?: JSONObject()
    val entries = data.items("entries")
    val work = data.items("items")
    val currentProgress = data.optJSONObject("current_progress")
    val receiptThrough = data.optJSONObject("receipt_through")
    val scope = rememberCoroutineScope()
    val clipboard = LocalClipboardManager.current
    val focus = remember { FocusRequester() }
    val keyboard = LocalSoftwareKeyboardController.current
    var options by remember { mutableStateOf<JSONObject?>(null) }
    var menu by remember { mutableStateOf(false) }
    var kindMenu by remember { mutableStateOf(false) }
    val canPost = space.optBoolean("can_post")
    val members = space.items("members")
    val items = work.associateBy { it.text("name") }
    val messages = entries.filter { entry -> entry.text("entry_kind") != "System" ||
        items[entry.text("item")]?.text("item_kind").let { it == null || it in listOf("Task", "Tracker") } }.asReversed()
    val messageMap = entries.associateBy { it.text("name") }
    val lifecycle by LocalLifecycleOwner.current.lifecycle.currentStateAsState()
    val visibleIncoming by remember(data, listState, user) { derivedStateOf {
        listState.layoutInfo.visibleItemsInfo.asSequence()
            .mapNotNull { messageMap[it.key as? String] }
            .filter { it.text("owner") != user }
            .maxByOrNull { it.text("creation") }
    } }
    LaunchedEffect(composer.editing, canPost) {
        if (composer.editing && canPost) {
            focus.requestFocus()
            keyboard?.show()
        }
    }
    LaunchedEffect(data, visibleIncoming, lifecycle, canMarkSeen, options) {
        val entry = visibleIncoming ?: return@LaunchedEffect
        if (canMarkSeen && options == null && lifecycle == Lifecycle.State.RESUMED &&
            data.has("seen_through") && entry.text("creation") > data.text("seen_through")) {
            delay(300)
            actions.seen(entry)
        }
    }
    Column(Modifier.fillMaxSize().background(chatPaper)) {
        Row(Modifier.fillMaxWidth().background(Color.White).padding(end = 4.dp).heightIn(min = 66.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = actions.back) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back", tint = emerald) }
            ChatAvatar(space.text("title").ifBlank { "Chat" }, Modifier.size(39.dp))
            Column(Modifier.weight(1f).padding(start = 10.dp, end = 4.dp).clickable(onClick = actions.members)) {
                Text(space.text("title").ifBlank { "Loading chat…" }, fontSize = 17.sp, fontWeight = FontWeight.SemiBold, color = messageInk, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(if (space.optBoolean("archived")) "Archived conversation" else if (space.text("space_kind") == "Direct") "Direct conversation" else members.joinToString(", ") { it.text("full_name").substringBefore(' ') },
                    fontSize = 12.sp, color = greyInk, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            IconButton(onClick = actions.tasks) { Icon(Icons.Default.Checklist, "Conversation tasks", tint = emerald) }
            IconButton(onClick = actions.trackers) { Icon(Icons.Default.Timeline, "Conversation trackers", tint = emerald) }
            Box {
                IconButton(onClick = { menu = true }) { Icon(Icons.Default.MoreVert, "Chat options", tint = greyInk) }
                DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                    DropdownMenuItem(text = { Text("Tasks") }, onClick = { menu = false; actions.tasks() })
                    DropdownMenuItem(text = { Text("Trackers") }, onClick = { menu = false; actions.trackers() })
                    if (canPost && !composer.editing) DropdownMenuItem(text = { Text("Message type") }, onClick = { menu = false; kindMenu = true })
                    if (space.optBoolean("can_manage")) DropdownMenuItem(text = { Text("Members & settings") }, onClick = { menu = false; actions.members() })
                    else DropdownMenuItem(text = { Text("Conversation members") }, onClick = { menu = false; actions.members() })
                    if (space.optBoolean("can_manage") && canPost) DropdownMenuItem(text = { Text("New subarea") }, onClick = { menu = false; actions.newArea() })
                    DropdownMenuItem(text = { Text("Refresh") }, onClick = { menu = false; actions.refresh() })
                    DropdownMenuItem(text = { Text("Switch user") }, onClick = { menu = false; actions.signOut() })
                }
                DropdownMenu(expanded = kindMenu, onDismissRequest = { kindMenu = false }) {
                    listOf("Message", "Note", "Decision", "Blocker", "Milestone").forEach { kind ->
                        DropdownMenuItem(text = { Text(kind) }, onClick = { kindMenu = false; actions.kind(kind) })
                    }
                }
            }
        }
        HorizontalDivider(color = Color(0xFFE6EBE7))
        Box(Modifier.weight(1f).fillMaxWidth()) {
        LazyColumn(Modifier.fillMaxSize(), state = listState, reverseLayout = true,
            contentPadding = PaddingValues(horizontal = 10.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            itemsIndexed(messages, key = { _, entry -> entry.text("name") }) { index, entry ->
                val older = messages.getOrNull(index + 1)
                Column {
                    if (older == null || older.text("creation").take(10) != entry.text("creation").take(10)) Box(Modifier.fillMaxWidth().padding(vertical = 10.dp), contentAlignment = Alignment.Center) {
                        Surface(color = Color(0xFFFAF8F3), shape = RoundedCornerShape(9.dp), shadowElevation = 0.5.dp) { Text(chatDay(entry.text("creation")), Modifier.padding(horizontal = 12.dp, vertical = 6.dp), fontSize = 11.sp, color = greyInk) }
                    }
                    if (entry.text("entry_kind") == "System") Box(Modifier.fillMaxWidth().padding(horizontal = 22.dp, vertical = 6.dp), contentAlignment = Alignment.Center) {
                        Surface(onClick = if (items[entry.text("item")]?.text("item_kind") == "Tracker") actions.trackers else actions.tasks,
                            color = Color(0xFFFAF8F3), shape = RoundedCornerShape(8.dp)) { Text(entry.text("body"), Modifier.padding(horizontal = 10.dp, vertical = 6.dp), fontSize = 11.sp, color = greyInk) }
                    } else BoxWithConstraints(Modifier.fillMaxWidth()) {
                        val mine = entry.text("owner") == user
                        val progress = entry.text("entry_kind") == "Progress"
                        val latestProgress = currentProgress?.text(entry.text("item")).orEmpty()
                        val earlier = progress && latestProgress.isNotBlank() && latestProgress != entry.text("name")
                        val deleted = entry.optBoolean("is_deleted")
                        val quoted = messageMap[entry.text("source_entry")]
                        val linked = work.filter { it.text("item_kind") in listOf("Task", "Tracker") && it.text("source_entry") == entry.text("name") }
                        val plain = entry.text("entry_kind") == "Message" && entry.text("source_entry").isBlank() &&
                            entry.items("attachments").isEmpty() && linked.isEmpty()
                        Surface(modifier = Modifier.align(if (mine) Alignment.CenterEnd else Alignment.CenterStart).widthIn(min = 62.dp, max = minOf(maxWidth * .86f, 560.dp))
                            .combinedClickable(onClick = {}, onLongClick = { if (!entry.optBoolean("is_deleted")) options = entry }),
                            color = when { earlier -> Color(0xFFEAE9E5); mine -> Color(0xFFE0F4DB); else -> Color.White },
                            shadowElevation = 0.5.dp,
                            shape = RoundedCornerShape(topStart = 13.dp, topEnd = 13.dp, bottomEnd = if (mine) 3.dp else 13.dp, bottomStart = if (mine) 13.dp else 3.dp)) {
                            Column(Modifier.padding(start = 10.dp, end = 10.dp, top = 7.dp, bottom = 5.dp)) {
                                if (!mine && space.text("space_kind") != "Direct" && (older?.text("owner") != entry.text("owner") || older?.text("entry_kind") == "System" || older?.text("creation")?.take(10) != entry.text("creation").take(10)))
                                    Text(entry.text("author_name"), color = emerald, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(bottom = 4.dp))
                                if (entry.text("source_entry").isNotBlank()) QuotePreview(quoted?.text("author_name") ?: "Earlier message", quoted?.text("body") ?: "Linked message", onClose = null) {
                                    val target = messages.indexOfFirst { it.text("name") == entry.text("source_entry") }
                                    if (target >= 0) scope.launch { listState.animateScrollToItem(target) }
                                }
                                if (entry.text("entry_kind") !in listOf("Message", "System", "Progress")) Text(entry.text("entry_kind"), color = emerald, fontSize = 11.sp, fontWeight = FontWeight.Medium)
                                val metadata: @Composable () -> Unit = { ChatMessageMeta(entry, receiptThrough.takeIf { mine && !deleted }) }
                                if (plain) FlowRow(Modifier.align(Alignment.End),
                                    horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End),
                                    itemVerticalAlignment = Alignment.Bottom) {
                                    Text(entry.text("body"), color = if (deleted) greyInk else messageInk, fontSize = 15.sp, lineHeight = 20.sp)
                                    metadata()
                                } else {
                                    Text(entry.text("body"), color = if (earlier || deleted) greyInk else messageInk, fontSize = 15.sp, lineHeight = 20.sp)
                                }
                                if (progress) entry.optJSONObject("snapshot")?.let {
                                    TrackerSnapshot(it, earlier = earlier, recordedAt = entry.text("creation"),
                                        onOpen = { actions.openTracker(entry.text("item")) })
                                }
                                entry.items("attachments").forEach { file -> Row(Modifier.fillMaxWidth().padding(top = 8.dp).background(Color(0x221C7556), RoundedCornerShape(9.dp)).clickable { actions.openFile(file.text("file_url")) }.padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
                                    Icon(Icons.Default.Description, null, Modifier.size(24.dp), tint = emerald)
                                    Text(file.text("file_name"), Modifier.weight(1f).padding(start = 8.dp), fontSize = 13.sp, color = messageInk, maxLines = 2, overflow = TextOverflow.Ellipsis)
                                    Icon(Icons.Default.Download, "Open attachment", Modifier.size(18.dp), tint = emerald)
                                } }
                                linked.forEach { task -> Row(Modifier.fillMaxWidth().padding(top = 8.dp).background(Color(0x18107050), RoundedCornerShape(8.dp)).clickable(onClick = if (task.text("item_kind") == "Tracker") actions.trackers else actions.tasks).padding(9.dp), verticalAlignment = Alignment.CenterVertically) {
                                    Icon(if (task.text("item_kind") == "Tracker") Icons.Default.Timeline else if (task.text("status") == "Completed") Icons.Default.CheckCircle else Icons.Default.RadioButtonUnchecked, null, Modifier.size(18.dp), tint = emerald)
                                    Text(task.text("title"), Modifier.padding(start = 7.dp), fontSize = 13.sp, fontWeight = FontWeight.Medium, color = messageInk)
                                } }
                                if (!plain) Box(Modifier.align(Alignment.End).padding(top = 3.dp)) { metadata() }
                            }
                        }
                    }
                }
            }
            if (data.text("older_cursor").isNotBlank()) item { Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) { TextButton(onClick = actions.older, enabled = !busy) { Text("Load earlier messages") } } }
            if (messages.isEmpty()) item { Box(Modifier.fillMaxWidth().padding(36.dp), contentAlignment = Alignment.Center) { Text("Start the conversation", color = greyInk) } }
        }
        if (listState.firstVisibleItemIndex > 2) SmallFloatingActionButton(onClick = { scope.launch { listState.animateScrollToItem(0) } },
            modifier = Modifier.align(Alignment.BottomEnd).padding(12.dp), containerColor = Color.White, contentColor = emerald) {
            Icon(Icons.Default.KeyboardArrowDown, "Jump to latest messages")
        }
        }
        if (canPost) Column(Modifier.fillMaxWidth().padding(horizontal = 7.dp, vertical = 7.dp)) {
            if (composer.editing) Row(Modifier.fillMaxWidth().padding(start = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Edit, null, Modifier.size(18.dp), tint = emerald)
                Text("Editing message", Modifier.weight(1f).padding(start = 8.dp), color = emerald, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                IconButton(onClick = actions.cancelEdit, enabled = !busy) { Icon(Icons.Default.Close, "Cancel edit", tint = greyInk) }
            }
            if (!composer.editing) composer.reply?.let { QuotePreview(it.text("author_name"), it.text("body"), actions.cancelReply) {} }
            if (!composer.editing && composer.files.isNotEmpty()) LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp), contentPadding = PaddingValues(bottom = 6.dp)) {
                items(composer.files) { file -> InputChip(selected = true, onClick = {}, label = { Text(file.text("filename"), maxLines = 1) }, trailingIcon = { IconButton(onClick = { actions.removeFile(file) }, modifier = Modifier.size(24.dp)) { Icon(Icons.Default.Close, "Remove attachment", Modifier.size(16.dp)) } }) }
            }
            if (!composer.editing && composer.kind != "Message") Row(verticalAlignment = Alignment.CenterVertically) { Text("${composer.kind} ·", color = emerald, fontSize = 12.sp); TextButton(onClick = { actions.kind("Message") }) { Text("Send as message") } }
            Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                TextField(composer.body, actions.body, modifier = Modifier.weight(1f).heightIn(min = 51.dp).focusRequester(focus), placeholder = { Text("Message", color = greyInk) },
                    shape = RoundedCornerShape(27.dp), maxLines = 5, enabled = !composer.editing || !busy,
                    trailingIcon = if (composer.editing) null else { { IconButton(onClick = actions.attach, enabled = !busy && composer.files.size < 5) { Icon(Icons.Default.AttachFile, "Attach file", tint = greyInk) } } },
                    colors = TextFieldDefaults.colors(focusedContainerColor = Color.White, unfocusedContainerColor = Color.White,
                        focusedIndicatorColor = Color.Transparent, unfocusedIndicatorColor = Color.Transparent))
                FilledIconButton(onClick = actions.send, enabled = !busy && composer.body.isNotBlank(), modifier = Modifier.size(51.dp),
                    colors = IconButtonDefaults.filledIconButtonColors(containerColor = emerald, contentColor = Color.White)) {
                    Icon(if (composer.editing) Icons.Default.Check else Icons.AutoMirrored.Filled.Send,
                        if (composer.editing) "Save message edit" else "Send message", Modifier.size(23.dp))
                }
            }
        } else Box(Modifier.fillMaxWidth().background(Color.White).padding(15.dp), contentAlignment = Alignment.Center) {
            Text(if (space.optBoolean("archived")) "This conversation is archived" else "You have viewing access", color = greyInk, fontSize = 13.sp)
        }
    }
    options?.let { entry -> ModalBottomSheet(onDismissRequest = { options = null }, containerColor = Color.White) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 8.dp)) {
            Text(entry.text("body").take(140), color = greyInk, maxLines = 2, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(bottom = 12.dp))
            fun act(action: () -> Unit) { options = null; action() }
            if (canPost) {
                ListItem(headlineContent = { Text("Reply") }, leadingContent = { Icon(Icons.AutoMirrored.Filled.Reply, null) }, modifier = Modifier.clickable { act { actions.reply(entry) } })
                ListItem(headlineContent = { Text("Create task") }, leadingContent = { Icon(Icons.Default.AddTask, null) }, modifier = Modifier.clickable { act { actions.task(entry) } })
                ListItem(headlineContent = { Text("Create tracker") }, leadingContent = { Icon(Icons.Default.Timeline, null) }, modifier = Modifier.clickable { act { actions.tracker(entry) } })
            }
            ListItem(headlineContent = { Text("Copy text") }, leadingContent = { Icon(Icons.Default.ContentCopy, null) }, modifier = Modifier.clickable { act { clipboard.setText(AnnotatedString(entry.text("body"))) } })
            if (entry.text("owner") == user && receiptThrough != null)
                ListItem(headlineContent = { Text("Message info") }, leadingContent = { Icon(Icons.Default.Info, null) }, modifier = Modifier.clickable { act { actions.info(entry) } })
            if (canPost && entry.optBoolean("can_edit") && entry.text("owner") == user) {
                ListItem(headlineContent = { Text("Edit message") }, leadingContent = { Icon(Icons.Default.Edit, null) }, modifier = Modifier.clickable { act { actions.edit(entry) } })
            }
            if (canPost && entry.optBoolean("can_remove", entry.optBoolean("can_edit"))) {
                ListItem(headlineContent = { Text("Remove message", color = MaterialTheme.colorScheme.error) }, leadingContent = { Icon(Icons.Default.DeleteOutline, null) }, modifier = Modifier.clickable { act { actions.remove(entry) } })
            }
            Spacer(Modifier.height(18.dp))
        }
    } }
}

@Composable
private fun ChatMessageMeta(entry: JSONObject, receiptThrough: JSONObject?) {
    val creation = entry.text("creation")
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(3.dp)) {
        Text((if (entry.text("edited_at").isNotBlank() && !entry.optBoolean("is_deleted")) "Edited · " else "") + chatTime(creation),
            color = greyInk, fontSize = 10.sp, lineHeight = 14.sp)
        if (receiptThrough != null) {
            val receipt = chatReceipt(creation, receiptThrough.text("delivered_through"), receiptThrough.text("seen_through"))
            Icon(if (receipt == ChatReceipt.SENT) Icons.Default.Check else Icons.Default.DoneAll,
                receipt.label, Modifier.size(15.dp), tint = if (receipt == ChatReceipt.READ) Color(0xFF006BA8) else greyInk)
        }
    }
}

@Composable
internal fun MessageInfoDialog(recipients: List<JSONObject>, close: () -> Unit) {
    AlertDialog(onDismissRequest = close, title = { Text("Message info") }, text = {
        Column(Modifier.heightIn(max = 360.dp).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (recipients.isEmpty()) Text("There are no other recipients in this conversation.", color = greyInk)
            for ((status, label) in listOf(3 to "Read by", 2 to "Delivered to", 1 to "Awaiting delivery")) {
                val people = recipients.filter { it.optInt("status") == status }
                if (people.isEmpty()) continue
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                    val ink = if (status == 3) Color(0xFF006BA8) else greyInk
                    Icon(if (status == 1) Icons.Default.Check else Icons.Default.DoneAll, null, Modifier.size(18.dp), tint = ink)
                    Text(label, fontWeight = FontWeight.SemiBold, color = ink)
                }
                people.forEach { person ->
                    Text(person.text("full_name"), Modifier.padding(start = 25.dp), color = messageInk)
                }
            }
        }
    }, confirmButton = { TextButton(onClick = close) { Text("Done") } })
}

@Composable
private fun QuotePreview(name: String, body: String, onClose: (() -> Unit)?, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(bottom = 6.dp).background(Color(0x14167350), RoundedCornerShape(8.dp)).clickable(onClick = onClick).heightIn(min = 45.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.width(3.dp).height(42.dp).background(emerald))
        Column(Modifier.weight(1f).padding(horizontal = 9.dp, vertical = 7.dp)) {
            Text(name, color = emerald, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
            Text(chatPreview(body), fontSize = 12.sp, color = greyInk, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
        if (onClose != null) IconButton(onClick = onClose) { Icon(Icons.Default.Close, "Cancel reply", Modifier.size(18.dp)) }
    }
}
