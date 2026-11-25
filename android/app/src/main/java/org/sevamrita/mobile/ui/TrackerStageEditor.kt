package org.sevamrita.mobile.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.text.font.FontWeight
import org.json.JSONArray
import org.json.JSONObject
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text
import java.util.UUID

internal fun trackerStagesJson(stages: List<TrackerStage>) = JSONArray().apply {
    stages.forEach { stage -> put(JSONObject().put("key", stage.key).put("label", stage.label)
        .put("position", stage.percent ?: JSONObject.NULL).put("assignee", stage.assigneeUser.ifBlank { null })
        .put("assignee_name", stage.assigneeName)) }
}

internal fun trackerStageForm(item: JSONObject, key: String, edit: Boolean): JSONObject {
    val config = item.optJSONObject("item_data") ?: JSONObject()
    val stage = config.items("stages").first { it.text("key") == key }
    return JSONObject().put("editing", edit).put("anchor", key).put("anchor_label", stage.text("label"))
        .put("key", if (edit) key else UUID.randomUUID().toString())
        .put("label", if (edit) stage.text("label") else "")
        .put("assignee", if (edit) stage.text("assignee") else "")
}

internal fun trackerStageConfig(item: JSONObject, form: JSONObject, members: List<JSONObject>): JSONObject {
    val config = JSONObject(item.optJSONObject("item_data")?.toString() ?: "{}")
    val display = trackerDisplay(config)
    val person = if (config.text("assignment_mode") == "Stages") form.text("assignee") else ""
    val personName = members.firstOrNull { it.text("user") == person }?.text("full_name").orEmpty()
    require(config.text("assignment_mode") != "Stages" || person.isNotBlank()) { "Choose a responsible person." }
    val label = form.text("label").trim()
    require(label.isNotBlank() && label.length <= 100) { "Enter a stage name of up to 100 characters." }
    val stages = if (form.optBoolean("editing")) editTrackerStage(display.stages, form.text("anchor"), label, person, personName)
    else insertTrackerStage(display.stages, form.text("anchor"), TrackerStage(form.text("key"), label, assigneeName = personName, assigneeUser = person), display.scale)
    return config.put("stages", trackerStagesJson(stages))
}

@Composable
internal fun TrackerStageForm(item: JSONObject, form: JSONObject, members: List<JSONObject>, set: (JSONObject) -> Unit) {
    val config = item.optJSONObject("item_data") ?: JSONObject()
    val display = trackerDisplay(config)
    val editing = form.optBoolean("editing")
    val noun = if (display.scale == "Status") "Status" else "Stage"
    fun change(key: String, value: String) = set(JSONObject(form.toString()).put(key, value))
    EditorSection(if (editing) "Edit ${noun.lowercase()}" else "Insert after ${form.text("anchor_label")}") {
        EditorText("$noun name *", form.text("label")) { change("label", it) }
        if (config.text("assignment_mode") == "Stages") EditorSelect("Responsible person *", form.text("assignee"),
            listOf("" to "Choose a person") + members.filter { it.text("access_level") != "Viewer" || it.text("user") == form.text("assignee") }
                .map { it.text("user") to it.text("full_name").ifBlank { it.text("user") } }) { change("assignee", it) }
        else Text("Responsibility stays with the person assigned to this tracker.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    val anchor = display.stages.indexOfFirst { it.key == form.text("anchor") }
    val next = display.stages.getOrNull(anchor + 1)
    if (!editing) EditorSection("Position in workflow") {
        Text(form.text("anchor_label"), style = MaterialTheme.typography.bodyMedium)
        Text("↓  ${form.text("label").trim().ifBlank { "New ${noun.lowercase()}" }}", fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.primary)
        if (next != null) Text("↓  ${next.label}", style = MaterialTheme.typography.bodyMedium)
        if (item.text("status") in listOf("Completed", "Failed", "Cancelled")) Text("This tracker stays ${item.text("status").lowercase()}. Use Update / reopen tracker if more work is needed.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        else if (anchor < display.currentIndex) Text("This goes before the current stage, ${display.label}. It will appear as passed until you move progress back to it.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        else Text("The current stage stays unchanged.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
