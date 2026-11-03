package org.sevamrita.mobile.ui

import java.time.LocalDate
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

internal data class ChatSummary(
    val id: String, val title: String, val kind: String, val parent: String = "",
    val preview: String = "", val timestamp: String = "", val unread: Int = 0, val archived: Boolean = false
)
internal data class ChatListRow(val chat: ChatSummary, val depth: Int, val childCount: Int, val path: String)

internal fun chatInitials(name: String): String = name.trim().split(Regex("\\s+")).filter { it.isNotEmpty() }
    .take(2).map { it.take(1).uppercase(Locale.ROOT) }.joinToString("").ifBlank { "S" }

internal fun chatPreview(text: String): String = text.replace(Regex("\\s+"), " ").trim().take(180)

internal fun chatTime(timestamp: String): String = runCatching {
    LocalDateTime.parse(timestamp.replace(' ', 'T')).format(DateTimeFormatter.ofPattern("HH:mm", Locale.ENGLISH))
}.getOrDefault("")

internal fun chatListTime(timestamp: String, today: LocalDate = LocalDate.now()): String = runCatching {
    val time = LocalDateTime.parse(timestamp.replace(' ', 'T'))
    when (time.toLocalDate()) {
        today -> chatTime(timestamp)
        today.minusDays(1) -> "Yesterday"
        else -> time.format(DateTimeFormatter.ofPattern(if (time.year == today.year) "d MMM" else "d MMM yy", Locale.ENGLISH))
    }
}.getOrDefault("")

internal fun chatDay(timestamp: String, today: LocalDate = LocalDate.now()): String = runCatching {
    val day = LocalDate.parse(timestamp.take(10))
    when (day) {
        today -> "Today"
        today.minusDays(1) -> "Yesterday"
        else -> day.format(DateTimeFormatter.ofPattern("d MMMM yyyy", Locale.ENGLISH))
    }
}.getOrDefault("")

internal fun chatInboxRows(rooms: List<ChatSummary>, expanded: Set<String>, query: String, filter: String, archived: Boolean): List<ChatListRow> {
    val byId = rooms.associateBy { it.id }
    val children = rooms.groupBy { it.parent }
    val order = compareByDescending<ChatSummary> { it.timestamp }.thenBy { it.title.lowercase(Locale.ROOT) }.thenBy { it.id }
    fun path(item: ChatSummary): String {
        val names = mutableListOf(item.title)
        val seen = mutableSetOf(item.id)
        var parent = byId[item.parent]
        while (parent != null && seen.add(parent.id)) { names.add(0, parent.title); parent = byId[parent.parent] }
        return names.joinToString(" / ")
    }
    fun matches(item: ChatSummary): Boolean = (archived || !item.archived) && when (filter) {
        "Unread" -> item.unread > 0
        "Groups" -> item.kind != "Direct"
        "Direct" -> item.kind == "Direct"
        else -> true
    }
    if (query.isNotBlank() || filter != "All") return rooms.filter { matches(it) && path(it).contains(query.trim(), true) }
        .sortedWith(order).map { ChatListRow(it, 0, children[it.id].orEmpty().size, path(it)) }
    val output = mutableListOf<ChatListRow>()
    val seen = mutableSetOf<String>()
    fun visit(item: ChatSummary, depth: Int) {
        if (!seen.add(item.id) || !matches(item)) return
        output.add(ChatListRow(item, depth.coerceAtMost(4), children[item.id].orEmpty().size, path(item)))
        if (item.id in expanded) children[item.id].orEmpty().sortedWith(order).forEach { visit(it, depth + 1) }
    }
    rooms.filter { it.parent.isBlank() || it.parent !in byId }.sortedWith(order).forEach { visit(it, 0) }
    return output
}
