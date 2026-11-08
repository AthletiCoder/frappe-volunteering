package org.sevamrita.mobile.reminders

internal data class ReminderEvent(val key: String, val item: String, val room: String, val kind: String, val title: String, val at: Long)

/** Limit outstanding alarms; periodic sync fills the window as reminders are delivered. */
internal fun pendingReminders(events: List<ReminderEvent>, delivered: Set<String>, now: Long): List<ReminderEvent> =
    events.filter { it.key !in delivered && it.at >= now - 12 * 60 * 60 * 1000L && it.kind in listOf("Task", "Tracker") && it.item.isNotBlank() }
        .distinctBy { it.key }.sortedBy { it.at }.take(100)

/** A sync/alarm race may wake several receivers. Consume every due occurrence together. */
internal fun dueReminders(events: List<ReminderEvent>, delivered: Set<String>, now: Long): List<ReminderEvent> =
    pendingReminders(events, delivered, now).filter { it.at <= now + 1000 }.distinctBy { it.item }
