package org.sevamrita.mobile.ui

import org.junit.Assert.*
import org.junit.Test

class WorkPresentationTest {
    @Test fun inProgressUsesTheStartActionWithoutCompletingTheTask() {
        assertEquals("start", taskStatusAction("In progress"))
        assertEquals("complete", taskStatusAction("Completed"))
        assertEquals("reopen", taskStatusAction("Open"))
        assertEquals("fail", taskStatusAction("Failed"))
        assertNull(taskStatusAction("Unknown"))
    }

    @Test fun openTrackersAreTheDefaultAndIncludeInProgress() {
        assertEquals("Open", DEFAULT_TRACKER_FILTER)
        assertTrue(trackerMatchesFilter("Open", DEFAULT_TRACKER_FILTER))
        assertTrue(trackerMatchesFilter("In progress", DEFAULT_TRACKER_FILTER))
        assertFalse(trackerMatchesFilter("Completed", DEFAULT_TRACKER_FILTER))
        assertFalse(trackerMatchesFilter("Failed", DEFAULT_TRACKER_FILTER))
    }

    @Test fun outcomeFiltersDoNotLeakOtherOutcomes() {
        assertTrue(trackerMatchesFilter("Completed", "Completed"))
        assertFalse(trackerMatchesFilter("Open", "Completed"))
        assertTrue(trackerMatchesFilter("Failed", "All"))
        assertFalse(trackerMatchesFilter("Completed", "Failed"))
    }

    @Test fun deadlineIsDistinctFromActionWindow() {
        assertEquals(listOf("Scheduled 2 Nov 2026 – 4 Nov 2026", "Deadline 6 Nov 2026"),
            workDates("2026-11-02", "2026-11-04", "2026-11-06"))
    }

    @Test fun singleDayIsNotRepeatedAndMissingDatesAreOmitted() {
        assertEquals(listOf("Scheduled 2 Nov 2026"), workDates("2026-11-02", "2026-11-02", ""))
        assertEquals(listOf("Deadline 6 Nov 2026"), workDates("", "", "2026-11-06"))
        assertTrue(workDates("", "", "").isEmpty())
    }

    @Test fun yearBoundaryAndTrackerAttentionRangeAreUnambiguous() {
        assertEquals(listOf("Attention 31 Dec 2026 – 2 Jan 2027"), workDates("2026-12-31", "2027-01-02", "", "Attention"))
        assertEquals(listOf("Scheduled until 2 Jan 2027"), workDates("", "2027-01-02", ""))
    }
}
