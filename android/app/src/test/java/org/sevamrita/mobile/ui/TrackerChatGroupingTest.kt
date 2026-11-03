package org.sevamrita.mobile.ui

import org.junit.Assert.*
import org.junit.Test

class TrackerChatGroupingTest {
    private data class Work(val id: String, val chat: String, val title: String, val status: String = "Open")
    private fun groups(items: List<Work>) = groupTrackersByChat(items, { it.chat }, { it.title })

    @Test fun interleavedTrackersStayTogetherWithoutLosingTheirOrder() {
        val input = listOf(Work("kit", "school", "School Support"), Work("venue", "camp", "Health Camp"), Work("consent", "school", "School Support"))
        val result = groups(input)
        assertEquals(listOf("school", "camp"), result.map { it.chatId })
        assertEquals(listOf("kit", "consent"), result[0].trackers.map { it.id })
        assertEquals(listOf("venue"), result[1].trackers.map { it.id })
    }

    @Test fun identicalChatNamesDoNotMergePrivateContexts() {
        val result = groups(listOf(Work("one", "room-a", "Volunteer Team"), Work("two", "room-b", "Volunteer Team")))
        assertEquals(2, result.size)
        assertEquals(listOf("room-a", "room-b"), result.map { it.chatId })
    }

    @Test fun openFilterDoesNotLeaveEmptyHeadingsOrIncludeClosedTrackers() {
        val input = listOf(Work("done", "camp", "Health Camp", "Completed"), Work("active", "school", "School Support", "In progress"))
        val result = groups(input.filter { trackerMatchesFilter(it.status, DEFAULT_TRACKER_FILTER) })
        assertEquals(listOf("school"), result.map { it.chatId })
        assertEquals(1, result.single().trackers.size)
    }

    @Test fun emptyResultsHaveNoHeadings() { assertTrue(groups(emptyList()).isEmpty()) }

    @Test fun missingFirstTitleUsesTheAvailableChatName() {
        assertEquals("School Support", groups(listOf(Work("one", "school", ""), Work("two", "school", "School Support"))).single().title)
    }
}
