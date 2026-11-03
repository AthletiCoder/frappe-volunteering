package org.sevamrita.mobile.ui

import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

internal const val DEFAULT_TRACKER_FILTER = "Open"
internal val TRACKER_FILTERS = listOf("Open", "All", "Completed", "Failed")
internal val TASK_STATUSES = listOf("Open", "In progress", "Completed", "Failed")

internal data class TrackerChatGroup<T>(val chatId: String, val title: String, val trackers: List<T>)

/** Use chat identity, since two different chats can have the same display name. */
internal fun <T> groupTrackersByChat(trackers: List<T>, chatId: (T) -> String, chatTitle: (T) -> String): List<TrackerChatGroup<T>> =
    trackers.groupBy(chatId).map { (id, items) ->
        TrackerChatGroup(id, items.firstNotNullOfOrNull { chatTitle(it).takeIf(String::isNotBlank) } ?: "Shared trackers", items)
    }

internal fun taskStatusAction(status: String): String? = when (status) {
    "Open" -> "reopen"
    "In progress" -> "start"
    "Completed" -> "complete"
    "Failed" -> "fail"
    else -> null
}

internal fun trackerMatchesFilter(status: String, filter: String): Boolean = when (filter) {
    "All" -> true
    "Open" -> status == "Open" || status == "In progress"
    else -> status == filter
}

internal fun workDates(from: String, until: String, deadline: String, windowLabel: String = "Scheduled"): List<String> {
    fun date(value: String): String = runCatching {
        LocalDate.parse(value.take(10)).format(DateTimeFormatter.ofPattern("d MMM yyyy", Locale.ENGLISH))
    }.getOrDefault(value)
    return buildList {
        if (from.isNotBlank()) add("$windowLabel ${date(from)}" + if (until.isNotBlank() && until != from) " – ${date(until)}" else "")
        else if (until.isNotBlank()) add("$windowLabel until ${date(until)}")
        if (deadline.isNotBlank()) add("Deadline ${date(deadline)}")
    }
}
