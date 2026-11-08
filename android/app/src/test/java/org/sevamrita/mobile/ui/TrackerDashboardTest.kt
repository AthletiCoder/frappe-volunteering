package org.sevamrita.mobile.ui

import org.junit.Assert.*
import org.junit.Test

class TrackerDashboardTest {
    @Test fun actionNeededNeverIncludesCompletedOrFailedTrackers() {
        assertTrue(trackerInScope(TrackerScope.MINE, "Open", true))
        assertTrue(trackerInScope(TrackerScope.MINE, "In progress", true))
        listOf("Completed", "Failed", "Cancelled").forEach { assertFalse(trackerInScope(TrackerScope.MINE, it, true)) }
        assertFalse(trackerInScope(TrackerScope.MINE, "Open", false))
    }
    @Test fun waitingFilterRetainsOpenItemsWithoutMyResponsibility() {
        assertTrue(trackerInScope(TrackerScope.OTHERS, "Open", false))
        assertFalse(trackerInScope(TrackerScope.OTHERS, "Open", true))
        assertFalse(trackerInScope(TrackerScope.OTHERS, "Completed", false))
    }
    @Test fun allIncludesFailedHistoryAndCompletedFilterIsExplicit() {
        assertTrue(trackerInScope(TrackerScope.ALL, "Failed", false))
        assertTrue(trackerInScope(TrackerScope.COMPLETED, "Completed", false))
        assertFalse(trackerInScope(TrackerScope.COMPLETED, "In progress", true))
    }
}
