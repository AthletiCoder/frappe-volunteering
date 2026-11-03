package org.sevamrita.mobile.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text
import java.util.UUID

@Composable
internal fun TrackerAssignmentChoice(form: JSONObject, set: (JSONObject) -> Unit) {
    val config = form.optJSONObject("item_data") ?: JSONObject().put("scale", "Percentage")
    val mode = config.text("assignment_mode").ifBlank { "Single" }
    Text("Who is responsible?", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
    listOf("Single" to ("One person" to "Assign the entire tracker to one person"),
        "Stages" to ("Divide by stage" to "Choose a responsible person for each stage")).forEach { (value, labels) ->
        Surface(color = if (mode == value) Color(0xFFE4F2EC) else Color(0xFFF5F7F7), shape = RoundedCornerShape(12.dp)) {
            Row(Modifier.fillMaxWidth().clickable {
                val updated = JSONObject(config.toString()).put("assignment_mode", value)
                if (value == "Stages" && config.text("scale") !in listOf("Stages", "Status")) {
                    updated.put("scale", "Stages").put("value", JSONObject.NULL).put("stage", JSONObject.NULL)
                    if (config.items("stages").isEmpty()) updated.put("stages", JSONArray(listOf("Planning", "Execution", "Completion").mapIndexed { index, title ->
                        JSONObject().put("key", UUID.randomUUID().toString()).put("label", title).put("position", listOf(30, 70, 100)[index]) }))
                }
                set(JSONObject(form.toString()).put("item_data", updated))
            }.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                RadioButton(selected = mode == value, onClick = null)
                Column(Modifier.padding(start = 12.dp)) {
                    Text(labels.first, fontWeight = FontWeight.Medium)
                    Text(labels.second, style = MaterialTheme.typography.bodySmall, color = Color(0xFF637378))
                }
            }
        }
    }
}
