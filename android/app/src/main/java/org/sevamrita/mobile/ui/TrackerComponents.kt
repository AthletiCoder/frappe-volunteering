package org.sevamrita.mobile.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject
import org.sevamrita.mobile.SectionCard
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text

internal fun trackerDisplay(config: JSONObject): TrackerDisplay = TrackerDisplay(
    config.text("scale"), if (config.isNull("value")) null else config.optDouble("value").takeIf { it.isFinite() },
    config.optDouble("minimum", 0.0), config.optDouble("maximum", 100.0), config.text("unit"), config.text("stage"),
    config.items("stages").map { TrackerStage(it.text("key"), it.text("label"), if (it.isNull("position")) null else it.optDouble("position").takeIf { v -> v.isFinite() }, it.text("assignee_name")) }
)

internal val TrackerPhase.tileColor: Color get() = when (this) {
    TrackerPhase.WAITING -> Color(0xFFFCF5E7)
    TrackerPhase.ACTIVE -> Color(0xFFEAF2FD)
    TrackerPhase.COMPLETE -> Color(0xFFE4F4EA)
    TrackerPhase.CLOSED -> Color(0xFFF9EDEB)
}

internal val TrackerPhase.ink: Color get() = when (this) {
    TrackerPhase.WAITING -> Color(0xFF76531F)
    TrackerPhase.ACTIVE -> Color(0xFF275FAD)
    TrackerPhase.COMPLETE -> Color(0xFF0B694F)
    TrackerPhase.CLOSED -> Color(0xFF973D34)
}

@Composable
internal fun TrackerPhaseBadge(phase: TrackerPhase, outcome: String) {
    val label = when (phase) {
        TrackerPhase.WAITING -> "Not started"
        TrackerPhase.ACTIVE -> "In progress"
        else -> outcome
    }
    Surface(color = phase.ink.copy(alpha = .09f), shape = RoundedCornerShape(8.dp)) {
        Text(label, Modifier.padding(horizontal = 7.dp, vertical = 4.dp), color = phase.ink, fontSize = 11.sp)
    }
}

@Composable
internal fun TrackerCard(item: JSONObject, canUpdate: Boolean, canConfigure: Boolean, onUpdate: () -> Unit, onConfigure: () -> Unit, onHistory: () -> Unit, onShare: (() -> Unit)? = null) {
    val config = item.optJSONObject("item_data") ?: JSONObject()
    val display = trackerDisplay(config)
    val status = item.text("status")
    val phase = display.phase(status)
    SectionCard(color = phase.tileColor) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(display.scale.uppercase(), color = Color(0xFF687778), fontSize = 11.sp, modifier = Modifier.weight(1f))
            TrackerPhaseBadge(phase, status)
        }
        Text(item.text("title"), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        if (item.text("description").isNotBlank()) Text(item.text("description"), color = Color(0xFF687778))
        Text(display.label, color = phase.ink, fontSize = 24.sp, fontWeight = FontWeight.Bold)
        TrackerBar(display, status, phase.ink)
        if (display.scale == "Number") Text("Range: ${config.opt("minimum")}–${config.opt("maximum")}", color = Color(0xFF687778), fontSize = 12.sp)
        if (display.stages.isNotEmpty()) TrackerTimeline(display, onSelect = null, outcome = status)
        if (item.text("assignee_name").isNotBlank()) Text("Assigned to ${item.text("assignee_name")}", fontSize = 12.sp, color = Color(0xFF687778))
        if (config.text("next_action").isNotBlank()) Text("Next: ${config.text("next_action")}")
        workDates(config.text("attention_date"), config.text("attention_until"), item.text("deadline"), "Attention").forEach {
            Text(it, color = Color(0xFF687778), fontSize = 12.sp)
        }
        if (canUpdate) Button(onClick = onUpdate, modifier = Modifier.fillMaxWidth()) { Text(if (status in listOf("Completed", "Failed")) "Update / reopen tracker" else "Update progress") }
        Row {
            if (canConfigure) TextButton(onClick = onConfigure) { Text("Configure") }
            TextButton(onClick = onHistory) { Text("History") }
            if (onShare != null) TextButton(onClick = onShare) { Text("Share") }
        }
    }
}

@Composable
internal fun TrackerTimeline(display: TrackerDisplay, onSelect: ((String) -> Unit)?, outcome: String = "Open") {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        display.stages.forEachIndexed { index, stage ->
            val selected = display.stage == stage.key
            val done = display.milestoneState(index, outcome) == MilestoneState.DONE
            Row(Modifier.fillMaxWidth().background(if (selected) Color(0xFFE0F1E8) else Color.Transparent, RoundedCornerShape(9.dp))
                .then(if (onSelect != null) Modifier.clickable { onSelect(stage.key) } else Modifier).padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(22.dp).background(if (done || selected) Color(0xFF08745E) else Color(0xFFE7ECE8), CircleShape), contentAlignment = Alignment.Center) {
                    if (done) Icon(Icons.Default.Check, null, Modifier.size(15.dp), tint = Color.White)
                    else if (selected) Box(Modifier.size(8.dp).background(Color.White, CircleShape))
                }
                Column(Modifier.weight(1f).padding(start = 10.dp)) {
                    Text(stage.label, fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal)
                    if (stage.assigneeName.isNotBlank()) Text(stage.assigneeName, fontSize = 12.sp, color = Color(0xFF687778))
                }
                if (selected && !done) Text("Current", color = Color(0xFF08745E), fontSize = 11.sp, modifier = Modifier.padding(end = 8.dp))
                if (display.scale == "Stages" && stage.percent != null) Text(stage.percentLabel, color = Color(0xFF687778), fontSize = 12.sp)
            }
        }
    }
}

@Composable
internal fun TrackerMilestoneBar(display: TrackerDisplay, outcome: String = "Open", ink: Color = Color(0xFF08745E)) {
    val upcoming = ink.copy(alpha = .27f)
    val positions = display.milestonePositions
    if (positions.isEmpty()) return
    Canvas(Modifier.fillMaxWidth().height(30.dp).semantics {
        contentDescription = if (outcome == "Completed") "All ${positions.size} steps completed"
            else if (display.currentIndex < 0) "Not started, ${positions.size} steps ahead"
            else "Current: ${display.label}, step ${display.currentIndex + 1} of ${positions.size}"
    }) {
        val inset = 9.dp.toPx()
        val width = (size.width - 2 * inset).coerceAtLeast(0f)
        val y = size.height / 2
        drawLine(upcoming, Offset(inset, y), Offset(inset + width, y), 3.dp.toPx(), StrokeCap.Round)
        val reached = if (outcome == "Completed") 1f else positions.getOrNull(display.currentIndex) ?: 0f
        if (reached > 0f) drawLine(ink, Offset(inset, y), Offset(inset + width * reached, y), 3.dp.toPx(), StrokeCap.Round)
        positions.forEachIndexed { index, position ->
            val center = Offset(inset + width * position, y)
            when (display.milestoneState(index, outcome)) {
                MilestoneState.DONE -> { drawCircle(Color.White, 6.dp.toPx(), center); drawCircle(ink, 4.dp.toPx(), center) }
                MilestoneState.CURRENT -> { drawCircle(Color.White, 9.dp.toPx(), center); drawCircle(ink, 7.dp.toPx(), center); drawCircle(Color.White, 3.dp.toPx(), center) }
                MilestoneState.UPCOMING -> { drawCircle(Color.White, 6.dp.toPx(), center); drawCircle(upcoming, 4.dp.toPx(), center); drawCircle(Color.White, 2.dp.toPx(), center) }
            }
        }
    }
}

@Composable
internal fun TrackerBar(display: TrackerDisplay, outcome: String, ink: Color) {
    if (display.stages.isNotEmpty()) TrackerMilestoneBar(display, outcome, ink)
    else LinearProgressIndicator(progress = { display.fraction ?: 0f },
        modifier = Modifier.fillMaxWidth().height(5.dp), color = ink, trackColor = ink.copy(alpha = .18f), gapSize = 0.dp)
}

@Composable
internal fun TrackerSnapshot(snapshot: JSONObject, earlier: Boolean = false, recordedAt: String = "", onOpen: (() -> Unit)? = null) {
    val config = snapshot.optJSONObject("item_data") ?: return
    val display = trackerDisplay(config)
    val status = snapshot.text("status")
    val ink = if (earlier) Color(0xFF596361) else Color(0xFF096651)
    val effective = snapshot.text("effective_at").replace('T', ' ').take(16)
    Column(Modifier.fillMaxWidth().padding(top = 5.dp).background(ink.copy(alpha = .08f), RoundedCornerShape(8.dp))
        .then(if (onOpen != null) Modifier.clickable(onClickLabel = "Open tracker", onClick = onOpen) else Modifier)
        .padding(horizontal = 9.dp, vertical = 7.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        if (snapshot.text("title").isNotBlank()) Text(snapshot.text("title"), fontSize = 12.sp, lineHeight = 16.sp, fontWeight = FontWeight.SemiBold, color = ink)
        Text(listOfNotNull(display.label, status.takeIf { it in listOf("Completed", "Failed") }).joinToString(" · "),
            fontSize = 13.sp, lineHeight = 17.sp, fontWeight = FontWeight.Medium, color = ink)
        TrackerBar(display, status, ink)
        if (earlier || effective.isNotBlank() && effective != recordedAt.replace('T', ' ').take(16))
            Text(listOfNotNull("Earlier update".takeIf { earlier }, "As of $effective".takeIf {
                effective.isNotBlank() && effective != recordedAt.replace('T', ' ').take(16)
            }).joinToString(" · "), fontSize = 10.sp, lineHeight = 14.sp, color = ink)
    }
}
