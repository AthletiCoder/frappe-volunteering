package org.sevamrita.mobile.ui

import org.junit.Assert.*
import org.junit.Test
import org.sevamrita.mobile.reminders.ReminderEvent
import org.sevamrita.mobile.reminders.pendingReminders
import org.sevamrita.mobile.reminders.dueReminders

class ReminderPlanTest {
    private val now = 1_000_000_000L
    private fun event(key: String = "a", at: Long = now + 1000, kind: String = "Task") = ReminderEvent(key, "work", "kitchen", kind, "Confirm supplies", at)

    @Test fun duplicateSyncDoesNotCreateDuplicateAlerts() {
        assertEquals(1, pendingReminders(listOf(event(), event()), emptySet(), now).size)
        assertTrue(pendingReminders(listOf(event()), setOf("a"), now).isEmpty())
    }
    @Test fun missedReminderCanCatchUpButOldBacklogCannotSpam() {
        assertEquals(1, pendingReminders(listOf(event(at = now - 60_000)), emptySet(), now).size)
        assertTrue(pendingReminders(listOf(event(at = now - 13 * 60 * 60 * 1000L)), emptySet(), now).isEmpty())
    }
    @Test fun onlySupportedKindsAndValidItemsCanNotify() {
        assertTrue(pendingReminders(listOf(event(kind = "Event")), emptySet(), now).isEmpty())
        assertTrue(pendingReminders(listOf(event().copy(item = "")), emptySet(), now).isEmpty())
        assertEquals(1, pendingReminders(listOf(event(kind = "Tracker")), emptySet(), now).size)
    }
    @Test fun soonestRemindersAreScheduledWithinAndroidAlarmLimits() {
        val items = (1..200).map { event("$it", now + it * 1000) }.reversed()
        val result = pendingReminders(items, emptySet(), now)
        assertEquals(100, result.size)
        assertEquals("1", result.first().key)
        assertEquals("100", result.last().key)
    }
    @Test fun changedTimeReplacesItsPendingSchedule() {
        val edited = event(at = now + 60_000)
        assertEquals(edited.at, pendingReminders(listOf(edited), emptySet(), now).single().at)
        assertTrue(pendingReminders(emptyList(), emptySet(), now).isEmpty())
    }

    @Test fun sameTimeTasksBecomeOneBatchWithEachTaskRepresentedOnce() {
        val rows = listOf(event("a", now), event("b", now).copy(item = "other"), event("c", now).copy(item = "work"), event("later", now + 60_000))
        assertEquals(listOf("work", "other"), dueReminders(rows, emptySet(), now).map { it.item })
        assertTrue(dueReminders(rows, setOf("a", "b", "c"), now).isEmpty())
    }
    @Test fun longQuietHoursRetainDueRemindersWithoutRevivingOldBacklog() {
        val until = now + 15 * 60 * 60 * 1000L
        val rows = listOf(event("due", now), event("later", until + 1000).copy(item = "other"), event("expired", now - 13 * 60 * 60 * 1000L))
        val delayed = org.sevamrita.mobile.reminders.quietDeferrals(rows, emptySet(), now, until)
        assertEquals(mapOf("due" to until), delayed)
        val cached = rows.map { it.copy(at = delayed[it.key] ?: it.at) }
        assertEquals(listOf("due", "later"), dueReminders(cached, emptySet(), until).map { it.key })
        assertTrue(org.sevamrita.mobile.reminders.quietDeferrals(rows, setOf("due"), now, until).isEmpty())
    }
}
