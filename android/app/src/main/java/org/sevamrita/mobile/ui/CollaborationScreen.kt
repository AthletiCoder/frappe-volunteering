package org.sevamrita.mobile.ui

import android.provider.OpenableColumns
import android.util.Base64
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PersonRemove
import androidx.activity.compose.BackHandler
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import org.sevamrita.mobile.Heading
import org.sevamrita.mobile.SectionCard
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text
import java.time.LocalDate
import java.time.LocalDateTime
import java.io.ByteArrayOutputStream
import java.util.UUID

private val chatGreen = Color(0xFF08745E)
private val chatMuted = Color(0xFF637378)
private val importance = listOf("Very low", "Low", "Medium", "High", "Very high")
private val formSaver = Saver<JSONObject, String>(save = { it.toString() }, restore = { JSONObject(it) })
private val editorSaver = Saver<String, String>(
    save = { it.takeIf { kind -> kind in setOf("item", "space", "progress") }.orEmpty() },
    restore = { it }
)
private fun JSONObject.copyJson() = JSONObject(toString())
private fun JSONObject.changed(key: String, value: Any?): JSONObject = copyJson().put(key, value ?: JSONObject.NULL)
private fun choices(values: List<String>) = values.map { it to it }
private fun JSONObject.strings(key: String): List<String> = optJSONArray(key)?.let { a -> (0 until a.length()).map { a.optString(it) } }.orEmpty()
private fun stamp(value: String) = value.replace('T', ' ').take(16)
private fun trackerValue(item: JSONObject): String = trackerDisplay(item.optJSONObject("item_data") ?: JSONObject()).label

/** Compose-only collaboration. All actions use the same guarded APIs as Home on the web. */
@Composable
fun CollaborationScreen(state: PortalState, model: PortalViewModel) {
    val scope = rememberCoroutineScope()
    val listState = rememberLazyListState()
    val context = LocalContext.current
    val space = state.chatRoom.optJSONObject("space") ?: JSONObject()
    val roomId = state.chatNavigation.current.room
    val canPost = space.optBoolean("can_post")
    val personalTrackers = state.chatNavigation.current.view == ChatView.MY_TRACKERS
    val personal = state.chatNavigation.current.view in listOf(ChatView.MY_TASKS, ChatView.MY_TRACKERS)
    val trackerDetail = state.chatNavigation.current.view == ChatView.TRACKER
    val taskDetail = state.chatNavigation.current.view == ChatView.TASK
    val tab = when (state.chatNavigation.current.view) { ChatView.TASKS -> "Tasks"; ChatView.TRACKERS -> "Trackers"; else -> "Chat" }
    var personalTab by rememberSaveable { mutableStateOf("Today") }
    var search by rememberSaveable { mutableStateOf("") }
    var showArchived by rememberSaveable { mutableStateOf(false) }
    var draft by rememberSaveable(state.user, roomId) { mutableStateOf("") }
    var sendKey by rememberSaveable(state.user, roomId) { mutableStateOf(UUID.randomUUID().toString()) }
    var entryKind by rememberSaveable(roomId) { mutableStateOf("Message") }
    var reply by remember(roomId) { mutableStateOf<JSONObject?>(null) }
    var uploads by remember(roomId) { mutableStateOf(listOf<JSONObject>()) }
    var editTarget by remember(state.user, roomId) { mutableStateOf<JSONObject?>(null) }
    var editBody by rememberSaveable(state.user, roomId) { mutableStateOf("") }
    var messageInfo by remember(state.user, roomId) { mutableStateOf<List<JSONObject>?>(null) }
    var dialog by rememberSaveable(stateSaver = editorSaver) { mutableStateOf("") }
    var form by rememberSaveable(stateSaver = formSaver) { mutableStateOf(JSONObject()) }
    var selected by rememberSaveable(stateSaver = formSaver) { mutableStateOf(JSONObject()) }
    var originalForm by rememberSaveable { mutableStateOf("") }
    fun openEditor(kind: String, initial: JSONObject) {
        model.dismissMessage()
        form = initial
        originalForm = initial.toString()
        dialog = kind
    }
    var history by remember { mutableStateOf(listOf<JSONObject>()) }
    var openedMessages by rememberSaveable(roomId) { mutableStateOf(false) }
    val latestMessage = state.chatRoom.items("entries").lastOrNull()?.text("name")
    LaunchedEffect(roomId, latestMessage, tab) {
        if (roomId.isNotBlank() && tab == "Chat" && latestMessage != null) {
            if (!openedMessages || listState.firstVisibleItemIndex <= 1) {
                openedMessages = true
                listState.animateScrollToItem(0)
            }
        }
    }
    fun newSpace(parent: String = "") {
        openEditor("space", JSONObject().put("title", "").put("space_kind", if (parent.isBlank()) "Workspace" else "Area")
            .put("parent_space", parent).put("members", JSONArray().put(JSONObject().put("user", state.user).put("access_level", "Owner"))))
    }
    fun newItem(kind: String, source: JSONObject? = null) {
        openEditor("item", JSONObject().put("item_kind", kind).put("title", source?.text("body")?.take(160).orEmpty())
            .put("assignee", state.user).put("priority", "Medium").put("repeat_pattern", "None")
            .put("source_entry", source?.text("name")).put("participants", JSONArray())
            .put("item_data", if (kind == "Tracker") JSONObject().put("scale", "Percentage") else JSONObject()))
    }
    fun historyFor(item: JSONObject) {
        model.chatCall("get_item_history", JSONObject().put("name", item.text("name"))) {
            history = it.items("history"); selected = item; dialog = "history"
        }
    }
    fun taskAction(item: JSONObject, action: String) {
        selected = item
        if (action in listOf("snooze", "postpone")) {
            form = JSONObject().put("action", action).put("date", item.text("from_date").ifBlank { LocalDate.now().toString() })
            dialog = "date"
        } else model.chatCall("update_task", JSONObject().put("name", item.text("name")).put("action", action).put("expected_modified", item.text("modified")))
    }
    fun shareFor(item: JSONObject) {
        selected = item
        form = JSONObject().put("shares", item.optJSONArray("shares") ?: JSONArray())
        dialog = "share"
    }
    fun progressFor(item: JSONObject) {
        if (!item.optBoolean("can_update", canPost)) { historyFor(item); return }
        selected = item
        val config = item.optJSONObject("item_data") ?: JSONObject()
        openEditor("progress", config.copyJson().put("note", "").put("effective_at", LocalDateTime.now().withSecond(0).withNano(0).toString())
            .put("outcome", if (item.text("status") in listOf("Completed", "Failed")) item.text("status") else "Open"))
    }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) scope.launch {
            runCatching { withContext(Dispatchers.IO) {
                val name = context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
                    if (cursor.moveToFirst()) cursor.getString(cursor.getColumnIndexOrThrow(OpenableColumns.DISPLAY_NAME)) else "attachment"
                } ?: "attachment"
                val bytes = context.contentResolver.openInputStream(uri)?.use { stream ->
                    val output = ByteArrayOutputStream()
                    val buffer = ByteArray(8192)
                    val limit = 10 * 1024 * 1024 + 1
                    while (output.size() < limit) {
                        val count = stream.read(buffer, 0, minOf(buffer.size, limit - output.size()))
                        if (count < 0) break
                        output.write(buffer, 0, count)
                    }
                    output.toByteArray()
                } ?: error("Unable to open file")
                require(bytes.isNotEmpty() && bytes.size <= 10 * 1024 * 1024) { "Choose a non-empty file up to 10 MB." }
                JSONObject().put("filename", name).put("content", Base64.encodeToString(bytes, Base64.NO_WRAP))
            } }.onSuccess { if (uploads.size < 5) uploads = uploads + it else model.error("Use at most five attachments.") }
                .onFailure { model.error(it.message ?: "Unable to read attachment") }
        }
    }
    LaunchedEffect(roomId) {
        while (true) { delay(15_000); if (dialog.isBlank() && !model.state.value.busy) model.refreshChat() }
    }
    BackHandler(editTarget != null && tab == "Chat" && !trackerDetail && !taskDetail && dialog.isBlank()) {
        if (!state.busy) editTarget = null
    }
    fun sendMessage() {
        editTarget?.let { target ->
            val args = JSONObject().put("name", target.text("name")).put("body", editBody)
                .put("expected_modified", target.text("modified"))
            model.chatCall("edit_entry", args) { editTarget = null }
            return
        }
        val args = JSONObject().put("payload", JSONObject().put("space", roomId).put("body", draft).put("entry_kind", entryKind)
            .put("request_key", sendKey).put("source_entry", reply?.text("name")).put("attachments", JSONArray(uploads)))
        model.chatCall("send_message", args) { draft = ""; uploads = emptyList(); reply = null; sendKey = UUID.randomUUID().toString(); openedMessages = false }
    }
    Box(Modifier.fillMaxSize()) {
    when {
        roomId.isNotBlank() && !space.has("access_level") -> Column(Modifier.fillMaxWidth().padding(24.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            if (state.chatLoading) Text("Opening…", color = chatMuted)
            else {
                Text("This page could not be loaded.")
                OutlinedButton(onClick = model::refreshChat) { Text("Try again") }
                TextButton(onClick = { model.backInChat() }) { Text("Go back") }
            }
        }
        personal -> LazyColumn(Modifier.fillMaxSize(), state = listState, contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (!personalTrackers) item {
                val views = listOf("Today", "Open tasks")
                SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                    views.forEachIndexed { index, label ->
                        SegmentedButton(selected = personalTab == label, onClick = { personalTab = label },
                            shape = SegmentedButtonDefaults.itemShape(index, views.size), label = { Text(label) })
                    }
                }
            }
            val work = if (personalTrackers) state.chatWork.items("trackers").filter { trackerMatchesFilter(it.text("status"), state.trackerFilter) }
                else state.chatWork.items(if (personalTab == "Today") "today" else "open_progress").filter { it.text("item_kind") == "Task" }
            if (work.isEmpty()) item { SectionCard { Text(if (personalTrackers) "No trackers in this view." else "No tasks in this view.") } }
            if (personalTrackers) {
                groupTrackersByChat(work, { it.text("space") }, { it.text("space_title") }).forEach { group ->
                    item(key = "chat-heading:${group.chatId}") {
                        Row(Modifier.fillMaxWidth().padding(start = 2.dp, end = 2.dp, top = 12.dp, bottom = 2.dp),
                            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Text(group.title, Modifier.weight(1f).semantics { heading() }, color = chatGreen,
                                style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                            Text("${group.trackers.size}", color = chatMuted, style = MaterialTheme.typography.labelMedium)
                        }
                    }
                    items(group.trackers, key = { it.text("name") }) { item ->
                        TrackerRow(item) { model.openTracker(item.text("space"), item.text("name")) }
                    }
                }
            } else items(work, key = { it.text("name") }) { item ->
                TaskRow(item, !state.busy, action = { taskAction(item, it) }, edit = null,
                    history = { historyFor(item) }, share = if (item.optBoolean("can_share")) { { shareFor(item) } } else null,
                    openDetails = { model.openTask(item.text("space"), item.text("name")) })
            }
        }
        taskDetail -> LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            val task = state.chatRoom.items("items").firstOrNull { it.text("name") == state.chatNavigation.current.item }
            if (task == null) item { Text(if (state.busy) "Loading task…" else "This task is unavailable.") }
            else item {
                TaskRow(task, !state.busy, { taskAction(task, it) }, if (task.optBoolean("can_edit")) { { openEditor("item", task.copyJson()) } } else null,
                    { historyFor(task) }, share = if (task.optBoolean("can_share")) { { shareFor(task) } } else null)
                if (task.text("description").isNotBlank()) Text(task.text("description"), Modifier.padding(14.dp))
            }
        }
        trackerDetail -> LazyColumn(Modifier.fillMaxSize(), state = listState, contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 16.dp, bottom = 96.dp)) {
            val tracker = state.chatRoom.items("items").firstOrNull { it.text("name") == state.chatNavigation.current.item && it.text("item_kind") == "Tracker" }
            if (tracker == null) item { Text(if (state.busy) "Loading tracker…" else "This tracker is unavailable. Go back and refresh the list.", Modifier.padding(12.dp)) }
            else item {
                val canConfigure = canPost && tracker.optBoolean("can_edit") && (space.text("access_level") in listOf("Owner", "Manager") || tracker.text("owner") == state.user)
                TrackerCard(tracker, tracker.optBoolean("can_update", canPost) && !state.busy, canConfigure && !state.busy,
                    onUpdate = { progressFor(tracker) }, onConfigure = { openEditor("item", tracker.copyJson()) }, onHistory = { historyFor(tracker) }, onShare = if (tracker.optBoolean("can_share")) { { shareFor(tracker) } } else null)
            }
        }
        roomId.isBlank() -> ChatInbox(state.chatHome.items("spaces"), listState, model::openChatRoom, { newSpace() },
            search, { search = it }, showArchived, { showArchived = it })
        tab == "Chat" -> ChatThread(state.chatRoom, state.user,
            state.busy, dialog.isBlank() && messageInfo == null, listState,
            ChatComposerData(if (editTarget == null) draft else editBody, entryKind, reply, uploads, editTarget != null), ChatThreadActions(
                back = { if (editTarget != null && !state.busy) editTarget = null else model.backInChat() },
                tasks = model::showRoomTasks, trackers = model::showRoomTrackers,
                members = { if (space.optBoolean("can_manage")) openEditor("space", space.copyJson()) else dialog = "members" }, newArea = { newSpace(roomId) },
                refresh = model::refreshChat, signOut = model::logout, older = model::olderChatMessages,
                reply = { reply = it }, task = { newItem("Task", it) }, tracker = { newItem("Tracker", it) },
                edit = { editTarget = it; editBody = it.text("body") },
                remove = { selected = it; dialog = "removeMessage" },
                info = { entry -> model.chatCall("get_message_info", JSONObject().put("name", entry.text("name"))) {
                    if (model.state.value.chatNavigation.current == ChatRoute(ChatView.CHAT, roomId)) messageInfo = it.items("recipients")
                } },
                seen = { model.markChatSeen(roomId, it) },
                openTracker = { model.openTracker(roomId, it) },
                openFile = { model.openReceipt(it, Page.COLLABORATION) },
                body = { if (editTarget == null) draft = it else editBody = it }, kind = { entryKind = it },
                attach = { picker.launch(arrayOf("application/pdf", "image/*", "text/*", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")) },
                removeFile = { uploads = uploads - it }, cancelReply = { reply = null }, cancelEdit = { editTarget = null }, send = ::sendMessage))
        tab == "Trackers" -> LazyColumn(Modifier.fillMaxSize(), state = listState, contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 16.dp, bottom = 96.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            val trackers = state.chatRoom.items("items").filter { it.text("item_kind") == "Tracker" && trackerMatchesFilter(it.text("status"), state.trackerFilter) }
            if (trackers.isEmpty()) item { SectionCard { Text("No trackers in this view.") } }
            items(trackers, key = { it.text("name") }) { tracker ->
                TrackerRow(tracker) { model.openTracker(roomId, tracker.text("name")) }
            }
        }
        else -> LazyColumn(Modifier.fillMaxSize(), state = listState, contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 16.dp, bottom = 96.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            val tasks = state.chatRoom.items("items").filter { it.text("item_kind") == "Task" }
            if (tasks.isEmpty()) item { SectionCard { Text("No tasks in this conversation yet.") } }
            items(tasks, key = { it.text("name") }) { item -> TaskRow(item, !state.busy,
                edit = { openEditor("item", item.copyJson()) }, action = { taskAction(item, it) }, history = { historyFor(item) }, share = if (item.optBoolean("can_share")) { { shareFor(item) } } else null,
                openDetails = { model.openTask(roomId, item.text("name")) }) }
        }
    }
    messageInfo?.let { MessageInfoDialog(it) { messageInfo = null } }
    if (canPost && !personal && (tab in listOf("Tasks", "Trackers") || trackerDetail)) {
        val kind = if (tab == "Tasks" && !trackerDetail) "Task" else "Tracker"
        WorkCreateButton("Create ${kind.lowercase()}", { newItem(kind) }, Modifier.align(Alignment.BottomEnd).padding(20.dp), enabled = !state.busy)
    }
    }
    if (dialog == "removeMessage") AlertDialog(onDismissRequest = { if (!state.busy) dialog = "" },
        title = { Text("Remove this message?") }, text = { Text("Its linked tasks will remain in the conversation.") },
        confirmButton = { TextButton(onClick = { model.chatCall("edit_entry", JSONObject().put("name", selected.text("name")).put("expected_modified", selected.text("modified")).put("remove", true)) { dialog = "" } }, enabled = !state.busy) { Text("Remove") } },
        dismissButton = { TextButton(onClick = { dialog = "" }, enabled = !state.busy) { Text("Cancel") } })
    fun saveForm() {
        when (dialog) {
            "space" -> {
                if (form.text("space_kind") == "Direct") model.chatCall("start_direct", JSONObject().put("user", form.text("person"))) { dialog = ""; model.openChatRoom(it.text("name")) }
                else {
                    val payload = JSONObject()
                    listOf("title", "space_kind", "parent_space", "project", "archived").forEach { key -> if (form.has(key)) payload.put(key, form.opt(key)) }
                    if (form.text("parent_space").isBlank()) payload.put("members", JSONArray(form.items("members").map { JSONObject().put("user", it.text("user")).put("access_level", it.text("access_level")) }))
                    model.chatCall("save_space", JSONObject().put("payload", payload).put("name", form.text("name").ifBlank { null }).put("expected_modified", form.text("modified"))) { dialog = ""; model.openChatRoom(it.text("name")) }
                }
            }
            "item" -> {
                val payload = JSONObject()
                listOf("title", "item_kind", "description", "source_entry", "assignee", "priority", "from_date", "until_date", "deadline", "repeat_pattern", "repeat_until", "start_at", "end_at", "location", "participants", "item_data").forEach { key -> if (form.has(key)) payload.put(key, form.opt(key)) }
                val creatingTracker = form.text("item_kind") == "Tracker" && form.text("name").isBlank()
                model.chatCall("save_item", JSONObject().put("space", roomId).put("payload", payload).put("name", form.text("name").ifBlank { null }).put("expected_modified", form.text("modified"))) {
                    dialog = ""
                    if (creatingTracker) model.openTracker(roomId, it.text("name"))
                }
            }
            "share" -> model.chatCall("share_item", JSONObject().put("name", selected.text("name")).put("expected_modified", selected.text("modified")).put("shares", form.optJSONArray("shares") ?: JSONArray())) { dialog = "" }
            "progress" -> {
                val plan = JSONObject(); listOf("next_action", "attention_date", "attention_until").forEach { plan.put(it, form.opt(it)) }
                val args = JSONObject().put("name", selected.text("name")).put("expected_modified", selected.text("modified")).put("note", form.text("note"))
                    .put("value", form.text("value").ifBlank { null }).put("stage", form.text("stage")).put("outcome", form.text("outcome"))
                    .put("effective_at", form.text("effective_at")).put("plan", plan)
                model.chatCall("record_progress", args) { dialog = "" }
            }
            "date" -> model.chatCall("update_task", JSONObject().put("name", selected.text("name")).put("expected_modified", selected.text("modified")).put("action", form.text("action")).put("date", form.text("date").ifBlank { null })) { dialog = "" }
        }
    }
    fun closeForm() {
        dialog = ""
        model.dismissMessage()
    }

    val members = space.items("members").filter { it.optBoolean("chat_enabled") }
    val existing = form.text("name").isNotBlank()
    val kind = form.text("item_kind").lowercase()
    val roomTitle = space.text("title")
    when (dialog) {
        "item", "progress", "space" -> {
            val title = when (dialog) {
                "item" -> if (existing) "Edit $kind" else "New $kind"
                "progress" -> "Update progress"
                else -> if (existing) "Conversation settings" else if (form.text("parent_space").isNotBlank()) "New subarea" else "New conversation"
            }
            val action = when {
                dialog == "progress" -> "Post update"
                existing -> "Save changes"
                dialog == "item" -> "Create $kind"
                form.text("space_kind") == "Direct" -> "Open chat"
                else -> "Create conversation"
            }
            val ready = when {
                dialog == "progress" -> form.text("note").isNotBlank()
                dialog == "space" && form.text("space_kind") == "Direct" -> form.text("person").isNotBlank()
                else -> form.text("title").isNotBlank()
            }
            key(dialog) {
                CollaborationEditor(title, if (dialog == "progress") selected.text("title") else roomTitle,
                    action, state.busy, form.toString() != originalForm, state.error, ready, ::closeForm, ::saveForm) {
                    when (dialog) {
                        "item" -> ChatItemForm(form, members) { form = it }
                        "space" -> ChatSpaceForm(form, state.chatHome, space, state.user) { form = it }
                        "progress" -> ChatProgressForm(form, selected) { form = it }
                    }
                }
            }
        }
        "date", "share", "members", "history" -> Dialog(onDismissRequest = { if (!state.busy) closeForm() }) {
            Surface(shape = MaterialTheme.shapes.large, modifier = Modifier.fillMaxWidth().fillMaxHeight(0.82f).imePadding()) {
                Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    val title = when (dialog) {
                        "date" -> "Schedule task"
                        "share" -> "Share ${selected.text("item_kind").lowercase()}"
                        "members" -> "Conversation members"
                        else -> "Activity history"
                    }
                    Text(title, style = MaterialTheme.typography.titleLarge)
                    if (state.error.isNotBlank()) Text(state.error, color = MaterialTheme.colorScheme.error)
                    Column(Modifier.weight(1f).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        when (dialog) {
                            "members" -> space.items("members").forEach { member -> Column {
                                Text(member.text("full_name"), fontWeight = FontWeight.SemiBold)
                                Text(member.text("access_level"), color = chatMuted)
                            } }
                            "share" -> WorkShareForm(form, state.chatHome.items("directory"), model) { form = it }
                            "date" -> {
                                val snooze = form.text("action") == "snooze"
                                Text(if (snooze) "Snooze within the task's action window." else "Move the action window to a later date. Its deadline stays unchanged.")
                                EditorDate(if (snooze) "Snooze until" else "New start date", form.text("date")) { form = form.changed("date", it) }
                                if (snooze) TextButton(onClick = { form = form.changed("date", "") }) { Text("Wake now") }
                            }
                            "history" -> history.forEach { entry ->
                                Text(entry.text("body"), fontWeight = FontWeight.Medium)
                                Text("${entry.text("author_name")} · ${stamp(entry.text("creation"))}", color = chatMuted,
                                    style = MaterialTheme.typography.bodySmall)
                                entry.optJSONObject("snapshot")?.takeIf { it.has("item_data") }?.let { TrackerSnapshot(it) }
                                HorizontalDivider()
                            }
                        }
                    }
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                        TextButton(onClick = ::closeForm, enabled = !state.busy) { Text("Close") }
                        if (dialog in listOf("date", "share")) Button(onClick = ::saveForm, enabled = !state.busy) { Text("Save") }
                    }
                }
            }
        }
    }
}

@Composable
private fun CheckOption(label: String, checked: Boolean, set: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth()) { Checkbox(checked, set); Text(label, Modifier.padding(top = 12.dp)) }
}

@Composable
private fun ChatDateTime(label: String, value: String, set: (String) -> Unit) {
    val time = runCatching { LocalDateTime.parse(value.replace(' ', 'T')) }.getOrDefault(LocalDateTime.now().withSecond(0).withNano(0))
    EditorDate("$label date", value.take(10), canClear = false) { set("${it}T${time.toLocalTime()}") }
    EditorTime("$label time", time.toLocalTime()) { set(time.toLocalDate().atTime(it).toString()) }
}

@Composable
private fun ChatSpaceForm(form: JSONObject, home: JSONObject, currentSpace: JSONObject, user: String, set: (JSONObject) -> Unit) {
    val directory = home.items("directory")
    val isNew = form.text("name").isBlank()
    val isArea = form.text("parent_space").isNotBlank()
    val direct = form.text("space_kind") == "Direct"
    EditorSection("Details") {
        if (isNew && !isArea) EditorSelect("Conversation type", form.text("space_kind"),
            choices(listOf("Direct", "Group", "Workspace"))) { set(form.changed("space_kind", it)) }
        if (direct) EditorSelect("Person", form.text("person"), directory.filter { it.text("name") != user }
            .map { it.text("name") to "${it.text("full_name")} · ${it.text("name")}" }) { set(form.changed("person", it)) }
        else EditorText("Title *", form.text("title")) { set(form.changed("title", it)) }
    }
    if (direct) return

    if (isArea) Text("Members and access are inherited from the parent workspace.", color = chatMuted)
    else EditorSection("Members and access") {
        val members = form.items("members")
        members.forEachIndexed { index, member ->
            val label = directory.firstOrNull { it.text("name") == member.text("user") }?.text("full_name") ?: member.text("user")
            key(member.text("user")) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.weight(1f)) {
                        EditorSelect(label, member.text("access_level"), choices(listOf("Owner", "Manager", "Member", "Viewer"))) { level ->
                            set(form.changed("members", JSONArray(members.mapIndexed { i, m ->
                                if (i == index) m.changed("access_level", level) else m
                            })))
                        }
                    }
                    IconButton(onClick = { set(form.changed("members", JSONArray(members.filterIndexed { i, _ -> i != index }))) }) {
                        Icon(Icons.Default.PersonRemove, "Remove $label", tint = chatMuted)
                    }
                }
            }
        }
        var add by remember { mutableStateOf("") }
        EditorSelect("Add person", add, directory.filter { d -> members.none { it.text("user") == d.text("name") } }.map { it.text("name") to "${it.text("full_name")} · ${it.text("name")}" }) { add = it }
        OutlinedButton(onClick = { set(form.changed("members", JSONArray(members + JSONObject().put("user", add).put("access_level", "Member")))); add = "" }, enabled = add.isNotBlank()) { Text("Add member") }
        Text("Owner: membership and settings. Manager: organise work. Member: chat and contribute. Viewer: read only.", color = chatMuted)
    }
    if (!isNew && currentSpace.text("access_level") == "Owner") CheckOption("Archive conversation", form.optBoolean("archived")) { set(form.changed("archived", it)) }
}

@Composable
private fun ChatItemForm(form: JSONObject, members: List<JSONObject>, set: (JSONObject) -> Unit) {
    val kind = form.text("item_kind")
    val config = form.optJSONObject("item_data") ?: JSONObject()
    val people = members.filter { it.text("access_level") != "Viewer" }.map { it.text("user") to it.text("full_name") }
    EditorSection("Details") {
        EditorText("Title *", form.text("title")) { set(form.changed("title", it)) }
        EditorText("Description", form.text("description"), multiline = true) { set(form.changed("description", it)) }
        if (kind == "Task") EditorSelect("Assigned to", form.text("assignee"), people) { set(form.changed("assignee", it)) }
        EditorSelect("Priority", form.text("priority").ifBlank { "Medium" }, choices(importance)) { set(form.changed("priority", it)) }
    }
    when (kind) {
        "Task" -> EditorSection("Schedule") {
            val repeat = form.text("repeat_pattern").ifBlank { "None" }
            val start = form.text("from_date")
            val end = form.text("until_date")
            val reminder = config.text("reminder_time")
            val scheduled = start.isNotBlank() || end.isNotBlank() || repeat != "None" || reminder.isNotBlank()
            EditorDate("Deadline", form.text("deadline")) { set(form.changed("deadline", it)) }
            EditorDisclosure("Action window, repeat and reminders",
                if (scheduled) (workDates(start, end, "") + repeat.takeIf { it != "None" }.orEmpty() + reminder)
                    .filter(String::isNotBlank).joinToString(" · ") else "Optional", initiallyExpanded = scheduled) {
                EditorDate("Start date", start) { set(form.changed("from_date", it)) }
                EditorDate("End date", end) { set(form.changed("until_date", it)) }
                EditorSelect("Repeat", repeat, choices(listOf("None", "Daily", "Weekly", "Monthly"))) {
                    val updated = form.changed("repeat_pattern", it)
                    if (it == "None") updated.put("repeat_until", JSONObject.NULL)
                    set(updated)
                }
                if (repeat != "None") EditorDate("Repeat until", form.text("repeat_until")) { set(form.changed("repeat_until", it)) }
                ReminderTimeField(reminder) { set(form.changed("item_data", config.changed("reminder_time", it))) }
                if (scheduled) TextButton(onClick = {
                    set(form.changed("from_date", null).put("until_date", JSONObject.NULL).put("repeat_pattern", "None")
                        .put("repeat_until", JSONObject.NULL).put("item_data", config.changed("reminder_time", "")))
                }) { Text("Reset optional schedule") }
            }
        }
        "Event" -> {
            ChatDateTime("Starts *", form.text("start_at")) { set(form.changed("start_at", it)) }
            ChatDateTime("Ends *", form.text("end_at")) { set(form.changed("end_at", it)) }
            EditorText("Location", form.text("location")) { set(form.changed("location", it)) }
            members.forEach { member -> CheckOption(member.text("full_name"), member.text("user") in form.strings("participants")) { checked ->
                val people = form.strings("participants").toMutableSet(); if (checked) people.add(member.text("user")) else people.remove(member.text("user")); set(form.changed("participants", JSONArray(people.toList())))
            } }
            Text("No selected participants means the whole workspace. Times use the portal's local time.", color = chatMuted)
        }
        "List" -> {
            val config = form.optJSONObject("item_data") ?: JSONObject()
            val rows = config.items("rows")
            fun changeRows(values: List<JSONObject>) { set(form.changed("item_data", JSONObject().put("rows", JSONArray(values)))) }
            rows.forEachIndexed { index, row ->
                HorizontalDivider()
                EditorText("Entry ${index + 1}", row.text("content")) { content -> changeRows(rows.mapIndexed { i, r -> if (i == index) r.changed("content", content) else r }) }
                CheckOption("Completed", row.optBoolean("completed")) { checked -> changeRows(rows.mapIndexed { i, r -> if (i == index) r.changed("completed", checked) else r }) }
                EditorSelect("Parent entry", row.text("parent_id"), listOf("" to "Top level") + rows.filter { it.text("id") != row.text("id") }.map { it.text("id") to it.text("content").ifBlank { "Untitled" } }) { parent -> changeRows(rows.mapIndexed { i, r -> if (i == index) r.changed("parent_id", parent) else r }) }
                EditorSelect("Entry importance", row.text("priority").ifBlank { "Medium" }, choices(importance)) { value -> changeRows(rows.mapIndexed { i, r -> if (i == index) r.changed("priority", value) else r }) }
                Row {
                    TextButton(onClick = { if (index > 0) { val list = rows.toMutableList(); java.util.Collections.swap(list, index, index - 1); changeRows(list) } }) { Text("Move up") }
                    TextButton(onClick = { if (index < rows.lastIndex) { val list = rows.toMutableList(); java.util.Collections.swap(list, index, index + 1); changeRows(list) } }) { Text("Down") }
                    TextButton(onClick = { changeRows(rows.filterIndexed { i, _ -> i != index }.map { if (it.text("parent_id") == row.text("id")) it.changed("parent_id", "") else it }) }) { Text("Remove") }
                }
            }
            OutlinedButton(onClick = { changeRows(rows + JSONObject().put("id", UUID.randomUUID().toString()).put("content", "").put("priority", "Medium")) }) { Text("Add list entry") }
        }
        "Tracker" -> {
            EditorSection("Assignment") {
                TrackerAssignmentChoice(form, set)
                if (config.text("assignment_mode") != "Stages")
                    EditorSelect("Assigned to", form.text("assignee"), people) { set(form.changed("assignee", it)) }
            }
            fun configChange(key: String, value: Any?) { set(form.changed("item_data", config.changed(key, value))) }
            EditorSection("Tracking scale") {
                EditorSelect("Measure progress by", config.text("scale"), choices(if (config.text("assignment_mode") == "Stages") listOf("Stages", "Status") else listOf("Percentage", "Number", "Stages", "Status"))) { scale ->
                    val updated = config.changed("scale", scale)
                    if (scale != config.text("scale")) updated.put("value", JSONObject.NULL).put("stage", JSONObject.NULL)
                    set(form.changed("item_data", updated))
                }
                if (config.text("scale") == "Number") {
                    EditorText("Minimum", config.text("minimum").ifBlank { "0" }) { configChange("minimum", it) }
                    EditorText("Maximum", config.text("maximum").ifBlank { "100" }) { configChange("maximum", it) }
                    EditorText("Unit (for example, meals)", config.text("unit")) { configChange("unit", it) }
                }
                if (config.text("scale") in listOf("Stages", "Status")) {
                    val stages = config.items("stages")
                    stages.forEachIndexed { index, stage ->
                        Text("Stage ${index + 1}", fontWeight = FontWeight.Bold, color = chatGreen)
                        EditorText("Stage name *", stage.text("label")) { label -> configChange("stages", JSONArray(stages.mapIndexed { i, s -> if (i == index) s.changed("label", label) else s })) }
                        if (config.text("assignment_mode") == "Stages") EditorSelect("Responsible person *", stage.text("assignee"),
                            people) { person ->
                            configChange("stages", JSONArray(stages.mapIndexed { i, s -> if (i == index) s.changed("assignee", person) else s }))
                        }
                        if (config.text("scale") == "Stages") EditorText("Stage position (%)", stage.text("position"), keyboard = KeyboardType.Decimal) { position -> configChange("stages", JSONArray(stages.mapIndexed { i, s -> if (i == index) s.changed("position", position) else s })) }
                        TextButton(onClick = {
                            val updated = config.changed("stages", JSONArray(stages.filterIndexed { i, _ -> i != index }))
                            if (config.text("stage") == stage.text("key")) updated.put("stage", JSONObject.NULL)
                            set(form.changed("item_data", updated))
                        }) { Text("Remove stage") }
                    }
                    OutlinedButton(onClick = {
                        val existing = stages.mapIndexed { index, stage ->
                            if (config.text("scale") == "Stages" && index == stages.lastIndex && stage.optDouble("position", 100.0) >= 100)
                                stage.changed("position", ((stages.getOrNull(index - 1)?.optDouble("position") ?: 0.0) + 100) / 2)
                            else stage
                        }
                        configChange("stages", JSONArray(existing + JSONObject().put("key", UUID.randomUUID().toString()).put("label", "").put("position", 100)))
                    }) { Text("Add stage / status") }
                }
            }
            EditorSection("Follow-up") {
                EditorText("Next action", config.text("next_action")) { configChange("next_action", it) }
                ReminderTimeField(config.text("reminder_time")) { configChange("reminder_time", it) }
                EditorDate("Attention from", config.text("attention_date")) { configChange("attention_date", it) }
                EditorDate("Attention until", config.text("attention_until")) { configChange("attention_until", it) }
                EditorDate("Deadline", form.text("deadline")) { set(form.changed("deadline", it)) }
            }
        }
    }
}

@Composable
private fun ChatProgressForm(form: JSONObject, item: JSONObject, set: (JSONObject) -> Unit) {
    EditorSection("Progress") {
        Text("Current: ${trackerValue(item)}", color = chatGreen, style = MaterialTheme.typography.bodySmall)
        if (form.text("scale") in listOf("Percentage", "Number")) {
            val keyboard = if (form.text("scale") == "Percentage") KeyboardType.Decimal else KeyboardType.Text
            EditorText("New value", form.text("value"), keyboard = keyboard) { set(form.changed("value", it)) }
            Text("Leave empty to keep the current value.", color = chatMuted, style = MaterialTheme.typography.bodySmall)
            TrackerBar(trackerDisplay(form), form.text("outcome"), chatGreen)
        } else {
            val display = trackerDisplay(form)
            EditorSelect(if (display.scale == "Status") "Status" else "Stage", form.text("stage"),
                listOf("" to "Not started") + display.stages.map { it.key to it.label }) { set(form.changed("stage", it)) }
            TrackerMilestoneBar(display, form.text("outcome"))
            EditorDisclosure("Stage list", "${display.stages.size} stages") {
                TrackerTimeline(display, onSelect = { set(form.changed("stage", it)) }, outcome = form.text("outcome"))
            }
        }
        EditorSelect("Outcome", form.text("outcome"), choices(listOf("Open", "Completed", "Failed"))) { set(form.changed("outcome", it)) }
        EditorText("Progress note *", form.text("note"), multiline = true) { set(form.changed("note", it)) }
    }
    EditorSection("Timing and follow-up") {
        EditorDisclosure("Effective date and next action", stamp(form.text("effective_at"))) {
            ChatDateTime("Effective", form.text("effective_at")) { set(form.changed("effective_at", it)) }
            EditorText("Next action", form.text("next_action")) { set(form.changed("next_action", it)) }
            EditorDate("Attention from", form.text("attention_date")) { set(form.changed("attention_date", it)) }
            EditorDate("Attention until", form.text("attention_until")) { set(form.changed("attention_until", it)) }
        }
    }
}
