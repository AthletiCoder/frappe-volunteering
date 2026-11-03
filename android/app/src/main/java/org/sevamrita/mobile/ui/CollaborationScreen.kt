package org.sevamrita.mobile.ui

import android.app.TimePickerDialog
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
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
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
private val workKinds = listOf("Task", "Tracker")
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
    var dialog by remember { mutableStateOf("") }
    var form by remember { mutableStateOf(JSONObject()) }
    var selected by remember { mutableStateOf(JSONObject()) }
    var history by remember { mutableStateOf(listOf<JSONObject>()) }
    var calendarDate by rememberSaveable { mutableStateOf(LocalDate.now().toString()) }
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
        form = JSONObject().put("title", "").put("space_kind", if (parent.isBlank()) "Workspace" else "Area")
            .put("parent_space", parent).put("members", JSONArray().put(JSONObject().put("user", state.user).put("access_level", "Owner")))
        dialog = "space"
    }
    fun newItem(kind: String, source: JSONObject? = null) {
        form = JSONObject().put("item_kind", kind).put("title", source?.text("body")?.take(160).orEmpty())
            .put("assignee", state.user).put("priority", "Medium").put("repeat_pattern", "None")
            .put("source_entry", source?.text("name")).put("participants", JSONArray())
            .put("item_data", when (kind) { "List" -> JSONObject().put("rows", JSONArray()); "Tracker" -> JSONObject().put("scale", "Percentage"); else -> JSONObject() })
        dialog = "item"
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
        form = config.copyJson().put("note", "").put("effective_at", LocalDateTime.now().withSecond(0).withNano(0).toString())
            .put("outcome", if (item.text("status") in listOf("Completed", "Failed")) item.text("status") else "Open")
        dialog = "progress"
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
    fun sendMessage() {
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
            if (!personalTrackers) item { SelectField("View", personalTab, choices(listOf("Today", "Open tasks"))) { personalTab = it } }
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
                TaskRow(task, !state.busy, { taskAction(task, it) }, if (task.optBoolean("can_edit")) { { form = task.copyJson(); dialog = "item" } } else null,
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
                    onUpdate = { progressFor(tracker) }, onConfigure = { form = tracker.copyJson(); dialog = "item" }, onHistory = { historyFor(tracker) }, onShare = if (tracker.optBoolean("can_share")) { { shareFor(tracker) } } else null)
            }
        }
        roomId.isBlank() -> ChatInbox(state.chatHome.items("spaces"), listState, model::openChatRoom, { newSpace() },
            search, { search = it }, showArchived, { showArchived = it })
        tab == "Chat" -> ChatThread(space, state.chatRoom.items("entries"), state.chatRoom.items("items"), state.user,
            state.busy, state.chatRoom.text("older_cursor").isNotBlank(), listState,
            ChatComposerData(draft, entryKind, reply, uploads), ChatThreadActions(
                back = { model.backInChat() }, tasks = model::showRoomTasks, trackers = model::showRoomTrackers,
                members = { form = space.copyJson(); dialog = if (space.optBoolean("can_manage")) "space" else "members" }, newArea = { newSpace(roomId) },
                refresh = model::refreshChat, signOut = model::logout, older = model::olderChatMessages,
                reply = { reply = it }, task = { newItem("Task", it) }, tracker = { newItem("Tracker", it) },
                edit = { selected = it; form = it.copyJson(); dialog = "message" },
                remove = { selected = it; dialog = "removeMessage" },
                openFile = { model.openReceipt(it, Page.COLLABORATION) }, body = { draft = it }, kind = { entryKind = it },
                attach = { picker.launch(arrayOf("application/pdf", "image/*", "text/*", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")) },
                removeFile = { uploads = uploads - it }, cancelReply = { reply = null }, send = ::sendMessage))
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
                edit = { form = item.copyJson(); dialog = "item" }, action = { taskAction(item, it) }, history = { historyFor(item) }, share = if (item.optBoolean("can_share")) { { shareFor(item) } } else null,
                openDetails = { model.openTask(roomId, item.text("name")) }) }
        }
    }
    if (canPost && !personal && (tab in listOf("Tasks", "Trackers") || trackerDetail)) {
        val kind = if (tab == "Tasks" && !trackerDetail) "Task" else "Tracker"
        WorkCreateButton("Create ${kind.lowercase()}", { newItem(kind) }, Modifier.align(Alignment.BottomEnd).padding(20.dp), enabled = !state.busy)
    }
    }
    if (dialog == "removeMessage") AlertDialog(onDismissRequest = { if (!state.busy) dialog = "" },
        title = { Text("Remove this message?") }, text = { Text("Its linked tasks will remain in the conversation.") },
        confirmButton = { TextButton(onClick = { model.chatCall("edit_entry", JSONObject().put("name", selected.text("name")).put("expected_modified", selected.text("modified")).put("remove", true)) { dialog = "" } }, enabled = !state.busy) { Text("Remove") } },
        dismissButton = { TextButton(onClick = { dialog = "" }, enabled = !state.busy) { Text("Cancel") } })
    val fullScreenTracker = dialog == "item" && form.text("item_kind") == "Tracker"
    if (dialog.isNotBlank() && dialog != "removeMessage") Dialog(onDismissRequest = { if (!state.busy) dialog = "" },
        properties = DialogProperties(usePlatformDefaultWidth = !fullScreenTracker, decorFitsSystemWindows = !fullScreenTracker)) {
        Surface(shape = if (fullScreenTracker) androidx.compose.ui.graphics.RectangleShape else MaterialTheme.shapes.large,
            modifier = (if (fullScreenTracker) Modifier.fillMaxSize() else Modifier.fillMaxWidth().fillMaxHeight(0.92f))
                .windowInsetsPadding(WindowInsets.safeDrawing).imePadding()) {
            Column(Modifier.padding(18.dp)) {
                if (fullScreenTracker) Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = { dialog = "" }, enabled = !state.busy) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
                    Text(if (form.text("name").isBlank()) "Create tracker" else "Edit tracker", style = MaterialTheme.typography.titleLarge)
                } else {
                Text(when (dialog) { "space" -> "Conversation settings"; "members" -> "Conversation members"; "item" -> if (form.text("item_kind") == "Tracker") "Tracker details" else "Task details"; "progress" -> "Record progress"; "history" -> "Activity history"; "share" -> "Share ${selected.text("item_kind").lowercase()}"; "message" -> "Edit message"; "date" -> "Schedule task"; else -> "Create from message" }, style = MaterialTheme.typography.titleLarge)
                }
                if (state.error.isNotBlank()) Text(state.error, color = MaterialTheme.colorScheme.error)
                Column(Modifier.weight(1f).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    Spacer(Modifier.height(2.dp))
                    when (dialog) {
                        "space" -> ChatSpaceForm(form, state.chatHome, space, state.user) { form = it }
                        "members" -> space.items("members").forEach { member -> Column {
                            Text(member.text("full_name"), fontWeight = FontWeight.SemiBold)
                            Text(member.text("access_level"), color = chatMuted)
                        } }
                        "share" -> WorkShareForm(form, state.chatHome.items("directory"), model) { form = it }
                        "item" -> ChatItemForm(form, space.items("members").filter { it.optBoolean("chat_enabled") }) { form = it }
                        "progress" -> ChatProgressForm(form, selected) { form = it }
                        "message" -> {
                            ChatText("Message", form.text("body")) { form = form.changed("body", it) }
                            TextButton(onClick = { model.chatCall("edit_entry", JSONObject().put("name", selected.text("name")).put("expected_modified", selected.text("modified")).put("remove", true)) { dialog = "" } }) { Text("Remove message") }
                        }
                        "date" -> {
                            Text(if (form.text("action") == "snooze") "Snooze within the task's action window." else "Move the action window to a later date. Its deadline stays unchanged.")
                            DateField("Date", form.text("date")) { form = form.changed("date", it) }
                            if (form.text("action") == "snooze") TextButton(onClick = { form = form.changed("date", "") }) { Text("Wake now") }
                        }
                        "fromMessage" -> workKinds.forEach { kind -> OutlinedButton(onClick = { newItem(kind, selected) }, modifier = Modifier.fillMaxWidth()) { Text("Create ${kind.lowercase()}") } }
                        "history" -> history.forEach { entry -> Column {
                            Text(entry.text("body")); Text("${entry.text("author_name")} · ${stamp(entry.optJSONObject("snapshot")?.text("effective_at").orEmpty().ifBlank { entry.text("creation") })}", color = chatMuted)

                            entry.optJSONObject("snapshot")?.takeIf { it.has("item_data") }?.let { TrackerSnapshot(it) }
                            Text("Recorded ${stamp(entry.text("creation"))}", color = chatMuted)
                            HorizontalDivider(Modifier.padding(vertical = 10.dp))
                        } }
                    }
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    TextButton(onClick = { dialog = "" }, enabled = !state.busy) { Text(if (fullScreenTracker) "Cancel" else "Close") }
                    if (dialog !in listOf("history", "fromMessage", "members")) Button(enabled = !state.busy, onClick = {
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
                            "message" -> model.chatCall("edit_entry", JSONObject().put("name", form.text("name")).put("body", form.text("body")).put("expected_modified", form.text("modified"))) { dialog = "" }
                            "date" -> model.chatCall("update_task", JSONObject().put("name", selected.text("name")).put("expected_modified", selected.text("modified")).put("action", form.text("action")).put("date", form.text("date").ifBlank { null })) { dialog = "" }
                        }
                    }) { Text(if (state.busy) "Saving…" else if (fullScreenTracker && form.text("name").isBlank()) "Create tracker" else "Save") }
                }
            }
        }
    }
}

@Composable
private fun ChatText(label: String, value: String, multiline: Boolean = false, set: (String) -> Unit) {
    OutlinedTextField(value, set, label = { Text(label) }, modifier = Modifier.fillMaxWidth(), minLines = if (multiline) 3 else 1, singleLine = !multiline)
}

@Composable
private fun CheckOption(label: String, checked: Boolean, set: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth()) { Checkbox(checked, set); Text(label, Modifier.padding(top = 12.dp)) }
}

@Composable
private fun ChatDateTime(label: String, value: String, set: (String) -> Unit) {
    val context = LocalContext.current
    val time = runCatching { LocalDateTime.parse(value.replace(' ', 'T')) }.getOrDefault(LocalDateTime.now().withSecond(0).withNano(0))
    DateField("$label date", value.take(10)) { set("${it}T${time.toLocalTime()}") }
    OutlinedButton(onClick = { TimePickerDialog(context, { _, hour, minute -> set(time.withHour(hour).withMinute(minute).toString()) }, time.hour, time.minute, true).show() }, modifier = Modifier.fillMaxWidth()) { Text("$label time · ${time.toLocalTime()}") }
}

@Composable
private fun ChatSpaceForm(form: JSONObject, home: JSONObject, currentSpace: JSONObject, user: String, set: (JSONObject) -> Unit) {
    val directory = home.items("directory")
    val isNew = form.text("name").isBlank()
    val isArea = form.text("parent_space").isNotBlank()
    if (isNew && !isArea) SelectField("Conversation type", form.text("space_kind"), choices(listOf("Direct", "Group", "Workspace"))) { set(form.changed("space_kind", it)) }
    if (form.text("space_kind") == "Direct") {
        SelectField("Person", form.text("person"), directory.filter { it.text("name") != user }.map { it.text("name") to "${it.text("full_name")} · ${it.text("name")}" }) { set(form.changed("person", it)) }
        return
    }
    ChatText("Title *", form.text("title")) { set(form.changed("title", it)) }

    if (isArea) Text("Members and access are inherited from the parent workspace.", color = chatMuted)
    else {
        Text("Members and access", fontWeight = FontWeight.Bold)
        val members = form.items("members")
        members.forEachIndexed { index, member ->
            val label = directory.firstOrNull { it.text("name") == member.text("user") }?.text("full_name") ?: member.text("user")
            SelectField(label, member.text("access_level"), choices(listOf("Owner", "Manager", "Member", "Viewer"))) { level ->
                set(form.changed("members", JSONArray(members.mapIndexed { i, m -> if (i == index) m.changed("access_level", level) else m })))
            }
            TextButton(onClick = { set(form.changed("members", JSONArray(members.filterIndexed { i, _ -> i != index }))) }) { Text("Remove $label") }
        }
        var add by remember { mutableStateOf("") }
        SelectField("Add person", add, directory.filter { d -> members.none { it.text("user") == d.text("name") } }.map { it.text("name") to it.text("full_name") }) { add = it }
        OutlinedButton(onClick = { set(form.changed("members", JSONArray(members + JSONObject().put("user", add).put("access_level", "Member")))); add = "" }, enabled = add.isNotBlank()) { Text("Add member") }
        Text("Owner: membership and settings. Manager: organise work. Member: chat and contribute. Viewer: read only.", color = chatMuted)
    }
    if (!isNew && currentSpace.text("access_level") == "Owner") CheckOption("Archive conversation", form.optBoolean("archived")) { set(form.changed("archived", it)) }
}

@Composable
private fun ChatItemForm(form: JSONObject, members: List<JSONObject>, set: (JSONObject) -> Unit) {
    val kind = form.text("item_kind")
    Text(if (kind == "Tracker") "Progress tracker" else "Task", fontWeight = FontWeight.Bold)
    ChatText("Title *", form.text("title")) { set(form.changed("title", it)) }
    ChatText("Description", form.text("description"), true) { set(form.changed("description", it)) }
    if (kind == "Tracker") TrackerAssignmentChoice(form, set)
    if (kind == "Task" || kind == "Tracker" && form.optJSONObject("item_data")?.text("assignment_mode") != "Stages") SelectField("Assigned to", form.text("assignee"), members.filter { it.text("access_level") != "Viewer" }.map { it.text("user") to it.text("full_name") }) { set(form.changed("assignee", it)) }
    SelectField("Importance", form.text("priority").ifBlank { "Medium" }, choices(importance)) { set(form.changed("priority", it)) }
    when (kind) {
        "Task" -> {
            DateField("Action window starts", form.text("from_date")) { set(form.changed("from_date", it)) }
            DateField("Action window ends (optional)", form.text("until_date")) { set(form.changed("until_date", it)) }
            val config = form.optJSONObject("item_data") ?: JSONObject()
            ReminderTimeField(config.text("reminder_time")) { set(form.changed("item_data", config.changed("reminder_time", it))) }
            DateField("Deadline (optional)", form.text("deadline")) { set(form.changed("deadline", it)) }
            SelectField("Repeat", form.text("repeat_pattern").ifBlank { "None" }, choices(listOf("None", "Daily", "Weekly", "Monthly"))) { set(form.changed("repeat_pattern", it)) }
            if (form.text("repeat_pattern") != "None") DateField("Repeat until (optional)", form.text("repeat_until")) { set(form.changed("repeat_until", it)) }
            TextButton(onClick = { set(form.changed("from_date", null).put("until_date", JSONObject.NULL).put("deadline", JSONObject.NULL).put("repeat_pattern", "None").put("repeat_until", JSONObject.NULL)) }) { Text("Clear schedule") }
        }
        "Event" -> {
            ChatDateTime("Starts *", form.text("start_at")) { set(form.changed("start_at", it)) }
            ChatDateTime("Ends *", form.text("end_at")) { set(form.changed("end_at", it)) }
            ChatText("Location", form.text("location")) { set(form.changed("location", it)) }
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
                ChatText("Entry ${index + 1}", row.text("content")) { content -> changeRows(rows.mapIndexed { i, r -> if (i == index) r.changed("content", content) else r }) }
                CheckOption("Completed", row.optBoolean("completed")) { checked -> changeRows(rows.mapIndexed { i, r -> if (i == index) r.changed("completed", checked) else r }) }
                SelectField("Parent entry", row.text("parent_id"), listOf("" to "Top level") + rows.filter { it.text("id") != row.text("id") }.map { it.text("id") to it.text("content").ifBlank { "Untitled" } }) { parent -> changeRows(rows.mapIndexed { i, r -> if (i == index) r.changed("parent_id", parent) else r }) }
                SelectField("Entry importance", row.text("priority").ifBlank { "Medium" }, choices(importance)) { value -> changeRows(rows.mapIndexed { i, r -> if (i == index) r.changed("priority", value) else r }) }
                Row {
                    TextButton(onClick = { if (index > 0) { val list = rows.toMutableList(); java.util.Collections.swap(list, index, index - 1); changeRows(list) } }) { Text("Move up") }
                    TextButton(onClick = { if (index < rows.lastIndex) { val list = rows.toMutableList(); java.util.Collections.swap(list, index, index + 1); changeRows(list) } }) { Text("Down") }
                    TextButton(onClick = { changeRows(rows.filterIndexed { i, _ -> i != index }.map { if (it.text("parent_id") == row.text("id")) it.changed("parent_id", "") else it }) }) { Text("Remove") }
                }
            }
            OutlinedButton(onClick = { changeRows(rows + JSONObject().put("id", UUID.randomUUID().toString()).put("content", "").put("priority", "Medium")) }) { Text("Add list entry") }
        }
        "Tracker" -> {
            val config = form.optJSONObject("item_data") ?: JSONObject().put("scale", "Percentage")
            fun configChange(key: String, value: Any?) { set(form.changed("item_data", config.changed(key, value))) }
            SelectField("Tracking scale", config.text("scale"), choices(if (config.text("assignment_mode") == "Stages") listOf("Stages", "Status") else listOf("Percentage", "Number", "Stages", "Status"))) { scale ->
                val updated = config.changed("scale", scale)
                if (scale != config.text("scale")) updated.put("value", JSONObject.NULL).put("stage", JSONObject.NULL)
                set(form.changed("item_data", updated))
            }
            if (config.text("scale") == "Number") {
                ChatText("Minimum", config.text("minimum").ifBlank { "0" }) { configChange("minimum", it) }
                ChatText("Maximum", config.text("maximum").ifBlank { "100" }) { configChange("maximum", it) }
                ChatText("Unit (for example, meals)", config.text("unit")) { configChange("unit", it) }
            }
            if (config.text("scale") in listOf("Stages", "Status")) {
                val stages = config.items("stages")
                stages.forEachIndexed { index, stage ->
                    Text("Stage ${index + 1}", fontWeight = FontWeight.Bold, color = chatGreen)
                    ChatText("Stage name *", stage.text("label")) { label -> configChange("stages", JSONArray(stages.mapIndexed { i, s -> if (i == index) s.changed("label", label) else s })) }
                    if (config.text("assignment_mode") == "Stages") SelectField("Responsible person *", stage.text("assignee"),
                        members.filter { it.text("access_level") != "Viewer" }.map { it.text("user") to it.text("full_name") }) { person ->
                        configChange("stages", JSONArray(stages.mapIndexed { i, s -> if (i == index) s.changed("assignee", person) else s }))
                    }
                    if (config.text("scale") == "Stages") ChatText("Stage position (%)", stage.text("position")) { position -> configChange("stages", JSONArray(stages.mapIndexed { i, s -> if (i == index) s.changed("position", position) else s })) }
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
            ChatText("Next action", config.text("next_action")) { configChange("next_action", it) }
            ReminderTimeField(config.text("reminder_time")) { configChange("reminder_time", it) }
            DateField("Attention from", config.text("attention_date")) { configChange("attention_date", it) }
            DateField("Attention until", config.text("attention_until")) { configChange("attention_until", it) }
            TextButton(onClick = { set(form.changed("item_data", config.changed("attention_date", null).put("attention_until", JSONObject.NULL))) }) { Text("Clear attention dates") }
            DateField("Deadline", form.text("deadline")) { set(form.changed("deadline", it)) }
            if (form.text("deadline").isNotBlank()) TextButton(onClick = { set(form.changed("deadline", null)) }) { Text("Clear deadline") }
        }
    }
}

@Composable
private fun ChatProgressForm(form: JSONObject, item: JSONObject, set: (JSONObject) -> Unit) {
    Text(item.text("title"), fontWeight = FontWeight.Bold)
    Text("Current: ${trackerValue(item)}", color = chatGreen)
    if (form.text("scale") in listOf("Percentage", "Number")) {
        ChatText("New value", form.text("value")) { set(form.changed("value", it)) }
        Text("Leave blank to keep the current value.", color = chatMuted)
    } else {
        val display = trackerDisplay(form)
        SelectField(if (display.scale == "Status") "Status" else "Stage", form.text("stage"),
            listOf("" to "Not started") + display.stages.map { it.key to it.label }) { set(form.changed("stage", it)) }
        TrackerMilestoneBar(display)
        TrackerTimeline(display, onSelect = { set(form.changed("stage", it)) })
    }
    SelectField("Outcome", form.text("outcome"), choices(listOf("Open", "Completed", "Failed"))) { set(form.changed("outcome", it)) }
    ChatDateTime("Effective", form.text("effective_at")) { set(form.changed("effective_at", it)) }
    ChatText("Progress note *", form.text("note"), true) { set(form.changed("note", it)) }
    ChatText("Next action", form.text("next_action")) { set(form.changed("next_action", it)) }
    DateField("Attention from", form.text("attention_date")) { set(form.changed("attention_date", it)) }
    DateField("Attention until", form.text("attention_until")) { set(form.changed("attention_until", it)) }
    TextButton(onClick = { set(form.changed("attention_date", null).put("attention_until", JSONObject.NULL)) }) { Text("Clear attention dates") }
    Text("A dated snapshot appears in chat. Backdated updates keep newer progress unchanged. Completing this tracker does not complete tasks.", color = chatMuted)
}
