package org.sevamrita.mobile.ui

import org.junit.Assert.*
import org.junit.Test

class TrackerPresentationTest {
    private val ravi = TrackerAssignee("ravi@example.com", "Ravi Menon")
    private val arjun = TrackerAssignee("arjun@example.com", "Arjun Sharma")

    @Test fun aSingleAssignmentIsPendingWithTheAssigneeRatherThanTheCreator() {
        val pending = TrackerDisplay("Percentage", 30.0).pendingWith("Open", "Single", arjun, ravi)
        assertEquals(arjun, pending)
        assertFalse(pending!!.isMe(ravi.user))
        assertTrue(pending.isMe(arjun.user))
    }

    @Test fun aStageTrackerFollowsTheCurrentStageAndTheFirstStageBeforeItStarts() {
        val display = TrackerDisplay("Status", stages = listOf(
            TrackerStage("plan", "Plan", assigneeUser = ravi.user, assigneeName = ravi.name),
            TrackerStage("ready", "Ready", assigneeUser = arjun.user, assigneeName = arjun.name)))
        assertEquals(ravi, display.pendingWith("Open", "Stages", TrackerAssignee(), arjun))
        assertEquals(arjun, display.copy(stage = "ready").pendingWith("Open", "Stages", TrackerAssignee(), ravi))
    }

    @Test fun closedTrackersHaveNoPendingAssignee() {
        for (status in listOf("Completed", "Failed", "Cancelled")) {
            assertNull(TrackerDisplay("Percentage", 100.0).pendingWith(status, "Single", ravi, ravi))
            assertNull(TrackerDisplay("Status", stages = listOf(TrackerStage("one", "Requested", assigneeUser = ravi.user)))
                .pendingWith(status, "Stages", ravi, ravi))
        }
    }

    @Test fun legacySingleAssignmentsUseTheOwnerWhenNoAssigneeWasRecorded() {
        assertEquals(ravi, TrackerDisplay("Number", 10.0).pendingWith("In progress", "", TrackerAssignee(), ravi))
    }

    @Test fun missingStageAssignmentsRemainUnassignedInsteadOfFallingBackToTheCreator() {
        val display = TrackerDisplay("Stages", stages = listOf(TrackerStage("one", "Requested", 10.0)))
        val pending = display.pendingWith("Open", "Stages", arjun, ravi)
        assertEquals("Unassigned", pending!!.displayName)
        assertFalse(pending.isMe(ravi.user))
        assertFalse(pending.isMe(""))
    }

    @Test fun pendingIdentityUsesTheUserIdWhenPeopleShareADisplayName() {
        val sameName = arjun.copy(name = ravi.name)
        assertFalse(sameName.isMe(ravi.user))
        assertTrue(sameName.isMe(arjun.user))
    }

    @Test fun tilePhaseUsesActualProgressAndExplicitOutcomes() {
        val empty = TrackerDisplay("Percentage", 0.0)
        assertEquals(TrackerPhase.WAITING, empty.phase("Open"))
        assertEquals(TrackerPhase.ACTIVE, empty.copy(value = 50.0).phase("Open"))
        assertEquals(TrackerPhase.WAITING, TrackerDisplay("Number", 10.0, minimum = 10.0).phase("Open"))
        assertEquals(TrackerPhase.ACTIVE, TrackerDisplay("Status", stage = "one",
            stages = listOf(TrackerStage("one", "Requested"))).phase("Open"))
        assertEquals(TrackerPhase.COMPLETE, empty.phase("Completed"))
        assertEquals(TrackerPhase.CLOSED, empty.copy(value = 50.0).phase("Failed"))
    }

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
