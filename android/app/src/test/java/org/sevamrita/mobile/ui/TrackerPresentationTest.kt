package org.sevamrita.mobile.ui

import org.junit.Assert.*
import org.junit.Test

class TrackerPresentationTest {
    @Test fun percentageShowsZeroAndFullProgress() {
        assertEquals("0%", TrackerDisplay("Percentage", 0.0).label)
        assertEquals(0f, TrackerDisplay("Percentage", 0.0).fraction!!, .0001f)
        assertEquals("100%", TrackerDisplay("Percentage", 100.0).label)
        assertEquals(1f, TrackerDisplay("Percentage", 100.0).fraction!!, .0001f)
    }

    @Test fun unsetValueIsNotShownAsZero() {
        assertEquals("Not started", TrackerDisplay("Percentage").label)
        assertNull(TrackerDisplay("Percentage").fraction)
    }

    @Test fun numberUsesItsActualRangeAndUnit() {
        val tracker = TrackerDisplay("Number", 60.0, 10.0, 110.0, "meals")
        assertEquals("60 meals", tracker.label)
        assertEquals(.5f, tracker.fraction!!, .0001f)
    }

    @Test fun decimalsStayReadable() {
        assertEquals("12.5%", TrackerDisplay("Percentage", 12.5).label)
        assertEquals("12.5 km", TrackerDisplay("Number", 12.5, unit = "km").label)
        assertEquals("12.5%", TrackerStage("partial", "First milestone", 12.5).percentLabel)
    }

    @Test fun stagesUseConfiguredWeights() {
        val tracker = TrackerDisplay("Stages", stage = "supplies", stages = listOf(
            TrackerStage("plan", "Plan agreed", 10.0), TrackerStage("supplies", "Supplies arranged", 45.0),
            TrackerStage("cooked", "Meals prepared", 85.0), TrackerStage("served", "Meals served", 100.0)))
        assertEquals("Supplies arranged", tracker.label)
        assertEquals(.45f, tracker.fraction!!, .0001f)
    }

    @Test fun openEndedStatusDoesNotInventPercentage() {
        val tracker = TrackerDisplay("Status", stage = "blocked", stages = listOf(
            TrackerStage("active", "Active"), TrackerStage("blocked", "Awaiting vendor")))
        assertEquals("Awaiting vendor", tracker.label)
        assertNull(tracker.fraction)
    }

    @Test fun unknownOrClearedStageIsNotStarted() {
        assertEquals("Not started", TrackerDisplay("Stages", stage = "missing", stages = listOf(TrackerStage("one", "Ready", 50.0))).label)
        assertNull(TrackerDisplay("Stages").fraction)
    }

    @Test fun malformedNumbersDoNotProduceInvalidProgressBars() {
        assertNull(TrackerDisplay("Number", 5.0, 10.0, 10.0).fraction)
        assertNull(TrackerDisplay("Number", Double.NaN).fraction)
        assertEquals("Not started", TrackerDisplay("Percentage", Double.POSITIVE_INFINITY).label)
        assertEquals(1f, TrackerDisplay("Percentage", 101.0).fraction!!, .0001f)
    }

    @Test fun displayingHistoricalSnapshotPreservesItsOwnValue() {
        val historical = TrackerDisplay("Percentage", 20.0)
        val current = historical.copy(value = 80.0)
        assertEquals("20%", historical.label)
        assertEquals("80%", current.label)
    }

    @Test fun orderedDotsDistinguishDoneCurrentAndUpcoming() {
        val display = TrackerDisplay("Stages", stage = "b", stages = listOf(TrackerStage("a", "Plan", 20.0), TrackerStage("b", "Prepare", 60.0), TrackerStage("c", "Deliver", 100.0)))
        assertEquals(listOf(MilestoneState.DONE, MilestoneState.CURRENT, MilestoneState.UPCOMING), (0..2).map { display.milestoneState(it) })
        assertEquals(listOf(.2f, .6f, 1f), display.milestonePositions)
    }

    @Test fun statusDotsDoNotInventNumericProgress() {
        val display = TrackerDisplay("Status", stage = "waiting", stages = listOf(TrackerStage("new", "Requested"), TrackerStage("waiting", "Awaiting response"), TrackerStage("done", "Confirmed")))
        assertNull(display.fraction)
        assertEquals(listOf(0f, .5f, 1f), display.milestonePositions)
        assertEquals(1, display.currentIndex)
        assertEquals(MilestoneState.CURRENT, display.milestoneState(1))
    }

    @Test fun notStartedLeavesEveryDotAhead() {
        val display = TrackerDisplay("Status", stages = listOf(TrackerStage("one", "Requested"), TrackerStage("two", "Confirmed")))
        assertEquals(-1, display.currentIndex)
        assertTrue(display.stages.indices.all { display.milestoneState(it) == MilestoneState.UPCOMING })
    }

    @Test fun completedOutcomeFillsEveryDot() {
        val display = TrackerDisplay("Stages", stage = "b", stages = listOf(TrackerStage("a", "Plan", 30.0), TrackerStage("b", "Ready", 100.0)))
        assertTrue(display.stages.indices.all { display.milestoneState(it, "Completed") == MilestoneState.DONE })
    }

    @Test fun oneStatusNeverDividesByZero() {
        assertEquals(listOf(1f), TrackerDisplay("Status", stages = listOf(TrackerStage("one", "Ready"))).milestonePositions)
    }

    @Test fun unknownStageHasNoCurrentDot() {
        val display = TrackerDisplay("Status", stage = "removed", stages = listOf(TrackerStage("new", "New")))
        assertEquals(MilestoneState.UPCOMING, display.milestoneState(0))
    }

    @Test fun invalidWeightFallsBackToAStableDotPosition() {
        val display = TrackerDisplay("Stages", stages = listOf(TrackerStage("a", "One", Double.NaN), TrackerStage("b", "Two", 100.0)))
        assertEquals(listOf(0f, 1f), display.milestonePositions)
    }
}
