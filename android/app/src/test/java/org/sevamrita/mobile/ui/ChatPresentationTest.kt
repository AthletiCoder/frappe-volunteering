package org.sevamrita.mobile.ui

import org.junit.Assert.*
import org.junit.Test
import java.time.LocalDate

class ChatPresentationTest {
    @Test fun receiptUsesTheLeastAdvancedRecipientAndDoesNotReadFutureMessages() {
        val stamp = "2026-11-04 13:46:12.000001"
        assertEquals(ChatReceipt.SENT, chatReceipt(stamp, "", ""))
        assertEquals(ChatReceipt.DELIVERED, chatReceipt(stamp, stamp, "2026-11-04 13:46:12"))
        assertEquals(ChatReceipt.READ, chatReceipt(stamp, stamp, stamp))
    }

    private val today = LocalDate.of(2026, 11, 2)
    private val kitchen = ChatSummary("kitchen", "Pune Community Kitchen", "Workspace", timestamp = "2026-11-02 11:05:00")
    private val area = ChatSummary("area", "Meal delivery", "Area", parent = "kitchen", timestamp = "2026-11-02 13:00:00", unread = 2)
    private val direct = ChatSummary("direct", "Arjun Sharma", "Direct", timestamp = "2026-11-02 12:45:01", unread = 1)

    @Test fun latestChatAppearsFirst() {
        assertEquals(listOf("direct", "kitchen"), chatInboxRows(listOf(kitchen, direct), emptySet(), "", "All", false).map { it.chat.id })
    }
    @Test fun subareaStaysCollapsedUntilRequested() {
        val rooms = listOf(area, kitchen, direct)
        val closed = chatInboxRows(rooms, emptySet(), "", "All", false)
        assertFalse(closed.any { it.chat.id == "area" })
        assertEquals(1, closed.first { it.chat.id == "kitchen" }.childCount)
        val opened = chatInboxRows(rooms, setOf("kitchen"), "", "All", false)
        assertEquals(1, opened.first { it.chat.id == "area" }.depth)
    }
    @Test fun searchFindsCollapsedChildrenAndTheirParentPath() {
        val rows = chatInboxRows(listOf(area, kitchen, direct), emptySet(), "meal", "All", false)
        assertEquals("area", rows.single().chat.id)
        assertEquals("Pune Community Kitchen / Meal delivery", rows.single().path)
    }
    @Test fun unreadAndConversationTypeFiltersAreIndependentOfExpansion() {
        val rooms = listOf(kitchen, area, direct)
        assertEquals(setOf("area", "direct"), chatInboxRows(rooms, emptySet(), "", "Unread", false).map { it.chat.id }.toSet())
        assertEquals(listOf("direct"), chatInboxRows(rooms, emptySet(), "", "Direct", false).map { it.chat.id })
        assertTrue(chatInboxRows(rooms, emptySet(), "", "Groups", false).none { it.chat.kind == "Direct" })
    }
    @Test fun archivedChatsRequireExplicitOptIn() {
        val archive = direct.copy(archived = true)
        assertTrue(chatInboxRows(listOf(archive), emptySet(), "", "All", false).isEmpty())
        assertEquals(1, chatInboxRows(listOf(archive), emptySet(), "", "All", true).size)
    }
    @Test fun listTimestampsUseTodayYesterdayAndOlderDates() {
        assertEquals("12:45", chatListTime("2026-11-02 12:45:01.123456", today))
        assertEquals("Yesterday", chatListTime("2026-11-01 12:45:00", today))
        assertEquals("31 Oct", chatListTime("2026-10-31 12:45:00", today))
        assertEquals("2 Nov 25", chatListTime("2025-11-02 12:45:00", today))
    }
    @Test fun daySeparatorsAndBubbleTimesRemainReadable() {
        assertEquals("Today", chatDay("2026-11-02 09:05:00", today))
        assertEquals("Yesterday", chatDay("2026-11-01 09:05:00", today))
        assertEquals("31 October 2026", chatDay("2026-10-31 09:05:00", today))
        assertEquals("09:05", chatTime("2026-11-02T09:05:00"))
    }
    @Test fun previewsAreOneLineAndNamesMakeStableInitials() {
        assertEquals("Vendor confirmed delivery", chatPreview("  Vendor\nconfirmed\t delivery  "))
        assertEquals("AS", chatInitials("  Arjun  Sharma "))
        assertEquals("S", chatInitials(" "))
        assertTrue(chatPreview("a".repeat(250)).length <= 180)
    }
    @Test fun malformedOrMissingTimesDoNotCrashConversationList() {
        assertEquals("", chatTime(""))
        assertEquals("", chatDay("invalid", today))
        assertEquals("", chatListTime("invalid", today))
    }
}
