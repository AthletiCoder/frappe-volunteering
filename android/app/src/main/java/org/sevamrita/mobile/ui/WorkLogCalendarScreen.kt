package org.sevamrita.mobile.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject
import org.sevamrita.mobile.SectionCard
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text
import java.time.LocalDate
import java.time.YearMonth
import java.time.format.DateTimeFormatter
import java.util.Locale

internal fun workLogMonthDates(month: YearMonth): List<LocalDate?> {
    val dates = MutableList<LocalDate?>(month.atDay(1).dayOfWeek.value - 1) { null }
    dates.addAll((1..month.lengthOfMonth()).map { month.atDay(it) })
    while (dates.size % 7 != 0) dates.add(null)
    return dates
}

private fun calendarHours(value: Double) = String.format(Locale.US, "%.2f", value).trimEnd('0').trimEnd('.')
private val workLogDateFormat = DateTimeFormatter.ofPattern("d MMM yyyy", Locale.ENGLISH)

@Composable
private fun calendarColors(status: String): Pair<Color, Color> {
    val dark = MaterialTheme.colorScheme.surface.luminance() < 0.5f
    return when (status) {
        "Not filled" -> if (dark) Color(0xFF482626) to Color(0xFFFFB4AB) else Color(0xFFFFEDEB) to Color(0xFF96372E)
        "Draft" -> if (dark) Color(0xFF443818) to Color(0xFFFFDF94) else Color(0xFFFFF2D2) to Color(0xFF765600)
        "Submitted" -> if (dark) Color(0xFF1E334E) to Color(0xFFB5D0FF) else Color(0xFFE7EFFF) to Color(0xFF224F94)
        "Reviewed" -> if (dark) Color(0xFF153B2E) to Color(0xFFA5E8C4) else Color(0xFFDCF3E6) to Color(0xFF165E3C)
        else -> MaterialTheme.colorScheme.surfaceVariant to MaterialTheme.colorScheme.onSurfaceVariant
    }
}

@Composable
fun WorkLogNavigation(state: PortalState, model: PortalViewModel) {
    val access = state.workLogList.takeIf { it.has("can_review_team") }
        ?: state.chatHome.optJSONObject("work_logging") ?: JSONObject()
    if (!access.optBoolean("can_review_team")) return
    NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
        if (access.optBoolean("can_create")) NavigationBarItem(
            selected = state.workLogView == "mine",
            onClick = { if (!state.busy) model.openWorkLogs(view = "mine", employee = "") },
            icon = { Icon(Icons.Default.CalendarMonth, null) }, label = { Text("My logs") })
        NavigationBarItem(
            selected = state.workLogView == "team",
            onClick = { if (!state.busy) model.openWorkLogs(view = "team", employee = "") },
            icon = { Icon(Icons.Default.Groups, null) }, label = { Text("Team review") })
    }
}

@Composable
fun WorkLogsScreen(state: PortalState, model: PortalViewModel) {
    val data = state.workLogList
    val team = state.workLogView == "team"
    val people = team && state.workLogEmployee.isBlank()
    val access = if (data.has("can_create")) data else state.chatHome.optJSONObject("work_logging") ?: JSONObject()
    var search by remember(state.workLogPeopleQuery) { mutableStateOf(state.workLogPeopleQuery) }
    val scroll = remember(state.workLogView, state.workLogEmployee) { LazyListState() }
    LazyColumn(Modifier.fillMaxSize(), state = scroll, contentPadding = PaddingValues(horizontal = if (people) 16.dp else 6.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        if (people) {
            item { Text("Select a person to view their monthly calendar and review their work.", color = MaterialTheme.colorScheme.onSurfaceVariant) }
            if (data.text("month").isNotBlank()) item { Text(YearMonth.parse(data.text("month")).format(DateTimeFormatter.ofPattern("MMMM yyyy", Locale.ENGLISH)), fontWeight = FontWeight.Medium) }
            item {
                OutlinedTextField(search, { search = it }, singleLine = true,
                    label = { Text("Search team") }, modifier = Modifier.fillMaxWidth(),
                    trailingIcon = { IconButton(onClick = { model.openWorkLogs(view = "team", employee = "", query = search) }, enabled = !state.busy) { Icon(Icons.Default.Search, "Search team members") } })
            }
            if (state.workLogLoading && !data.has("people")) item { Text("Loading team…") }
            if (!state.workLogLoading && data.has("people") && data.items("people").isEmpty()) item { SectionCard { Text("No employees match this view.") } }
            items(data.items("people"), key = { it.text("name") }) { person ->
                Surface(onClick = { model.openWorkLogs(view = "team", employee = person.text("name")) },
                    enabled = !state.busy, shape = RoundedCornerShape(18.dp), color = MaterialTheme.colorScheme.surface,
                    border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
                    Row(Modifier.fillMaxWidth().padding(18.dp), horizontalArrangement = Arrangement.spacedBy(14.dp), verticalAlignment = Alignment.CenterVertically) {
                        Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = CircleShape) {
                            Box(Modifier.size(44.dp), contentAlignment = Alignment.Center) { Text(person.text("employee_name").take(1), fontWeight = FontWeight.Bold) }
                        }
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                            Text(person.text("employee_name"), fontWeight = FontWeight.SemiBold)
                            Text(person.text("designation").ifBlank { person.text("name") }, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            val pending = person.optInt("submitted")
                            Text(if (pending > 0) "$pending awaiting review · ${calendarHours(person.optDouble("total_hours", 0.0))} h" else "${calendarHours(person.optDouble("total_hours", 0.0))} h recorded",
                                style = MaterialTheme.typography.bodySmall, color = if (pending > 0) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null)
                    }
                }
            }
            if (data.optInt("page", 1) > 1 || data.optBoolean("has_more")) item {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    TextButton(onClick = { model.openWorkLogs(view = "team", employee = "", page = data.optInt("page") - 1) }, enabled = !state.busy && data.optInt("page", 1) > 1) { Text("Previous") }
                    TextButton(onClick = { model.openWorkLogs(view = "team", employee = "", page = data.optInt("page") + 1) }, enabled = !state.busy && data.optBoolean("has_more")) { Text("Next") }
                }
            }
        } else {
            if (state.workLogLoading && !data.has("days")) item { Text("Loading calendar…") }
            if (data.has("days")) {
                if (team) item {
                    Row(Modifier.fillMaxWidth().padding(horizontal = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(data.optJSONObject("calendar_employee")?.text("employee_name").orEmpty(), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                        if (team) TextButton(onClick = { model.openWorkLogs(view = "team", employee = "") }, enabled = !state.busy) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, null, Modifier.size(18.dp)); Spacer(Modifier.width(8.dp)); Text("Back to team")
                        }
                    }
                }
                item { MonthlyWorkLogCalendar(data, !state.busy, { month -> model.openWorkLogs(month = month) }) { day ->
                    if (day.text("name").isNotBlank()) model.openWorkLog(day.text("name")) else model.openWorkLog(date = day.text("date"), employee = state.workLogEmployee)
                } }
                item {
                    val summary = data.optJSONObject("summary") ?: JSONObject()
                    Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        val pending = summary.optInt("awaiting_review", summary.optInt("Submitted"))
                        val submitted = summary.optInt("submitted_total", pending + summary.optInt("Reviewed"))
                        for ((value, label) in listOf(workLogDurationLabel(summary.optDouble("total_hours", 0.0).toString()) to "Total time", submitted.toString() to "Submitted", pending.toString() to "Awaiting review", summary.optInt("Reviewed").toString() to "Reviewed")) {
                            Column(Modifier.weight(1f).padding(vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text(value, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleSmall)
                                Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun MonthlyWorkLogCalendar(data: JSONObject, enabled: Boolean, onMonth: (String) -> Unit, onOpen: (JSONObject) -> Unit) {
    val month = YearMonth.parse(data.text("month"))
    val today = LocalDate.parse(data.text("today"))
    val dates = remember(month) { workLogMonthDates(month) }
    val days = data.items("days").associateBy { it.text("date") }
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = { onMonth(month.minusMonths(1).toString()) }, enabled = enabled && month.year > 1) { Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, "Previous month") }
            Text(month.format(DateTimeFormatter.ofPattern("MMMM yyyy", Locale.ENGLISH)), fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
            TextButton(onClick = { onMonth(YearMonth.from(today).toString()) }, enabled = enabled, contentPadding = PaddingValues(horizontal = 8.dp)) { Text("Today", style = MaterialTheme.typography.labelMedium) }
            IconButton(onClick = { onMonth(month.plusMonths(1).toString()) }, enabled = enabled && month < YearMonth.from(today)) { Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, "Next month") }
        }
        Row(Modifier.fillMaxWidth()) {
            for (day in listOf("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")) Box(Modifier.weight(1f), contentAlignment = Alignment.Center) { Text(day, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
        for (week in dates.chunked(7)) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            for (date in week) {
                if (date == null) Spacer(Modifier.weight(1f).height(64.dp))
                else {
                    val day = days[date.toString()] ?: JSONObject()
                    val status = day.text("status")
                    val (background, foreground) = calendarColors(status)
                    val hours = if (day.isNull("total_hours")) (if (status == "Holiday") "Off" else if (status == "On leave") "Leave" else "—") else calendarHours(day.optDouble("total_hours", 0.0)) + " h"
                    val description = "${date.format(workLogDateFormat)}, $status, ${day.text("day_note")}" + if (!day.isNull("total_hours")) ", ${calendarHours(day.optDouble("total_hours", 0.0))} hours" else ""
                    Surface(Modifier.weight(1f).heightIn(min = 64.dp).semantics(mergeDescendants = true) { contentDescription = description }
                        .clickable(enabled = enabled && day.optBoolean("can_open"), role = Role.Button) { onOpen(day) },
                        color = background, contentColor = foreground, shape = RoundedCornerShape(8.dp),
                        border = if (date == today) BorderStroke(2.dp, MaterialTheme.colorScheme.primary) else null) {
                        Column(Modifier.padding(vertical = 8.dp), verticalArrangement = Arrangement.SpaceBetween, horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(date.dayOfMonth.toString(), fontWeight = FontWeight.SemiBold, fontSize = 16.sp, lineHeight = 22.sp)
                            Text(hours, fontSize = 12.sp, lineHeight = 16.sp, maxLines = 1, overflow = TextOverflow.Clip)
                        }
                    }
                }
            }
        }
        Row(Modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 6.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            for (status in listOf("Not filled", "Draft", "Submitted", "Reviewed")) Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                val (background, foreground) = calendarColors(status)
                Surface(Modifier.size(8.dp), color = background, shape = CircleShape, border = BorderStroke(1.dp, foreground)) {}
                Text(status, fontSize = 10.sp, lineHeight = 14.sp)
            }
        }
    }
}
