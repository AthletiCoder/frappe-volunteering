package org.sevamrita.mobile.ui

import org.junit.Assert.*
import org.junit.Test

class TrackerStageEditingTest {
    private val steps = listOf(
        TrackerStage("draft", "Draft", 20.0, "Ravi", "ravi@example.com"),
        TrackerStage("review", "Review", 60.0, "Arjun", "arjun@example.com"),
        TrackerStage("issue", "Issue", 100.0, "Ravi", "ravi@example.com"))
    private val added = TrackerStage("check", "Check evidence", assigneeName = "Dev", assigneeUser = "dev@example.com")

    @Test fun statusCanBeInsertedAfterEveryRowWithoutChangingExistingKeysOrAssignments() {
        for ((index, step) in steps.withIndex()) {
            val result = insertTrackerStage(steps, step.key, added, "Status")
            assertEquals(added.key, result[index + 1].key)
            assertEquals(steps, result.filter { it.key != added.key })
            assertNull(result[index + 1].percent)
        }
    }
    @Test fun percentageStageUsesTheGapBetweenItsTwoNeighbours() {
        val result = insertTrackerStage(steps, "draft", added, "Stages")
        assertEquals(listOf("draft", "check", "review", "issue"), result.map { it.key })
        assertEquals(40.0, result[1].percent!!, 0.0)
        assertEquals(steps, result.filter { it.key != added.key })
    }
    @Test fun insertionKeepsCurrentStageIdentityAndTheResponsiblePerson() {
        val before = TrackerDisplay("Status", stage = "review", stages = steps)
        val after = before.copy(stages = insertTrackerStage(steps, "draft", added, "Status"))
        assertEquals(before.label, after.label)
        assertEquals(before.currentIndex + 1, after.currentIndex)
        assertEquals(before.pendingWith("Open", "Stages", TrackerAssignee(), TrackerAssignee()),
            after.pendingWith("Open", "Stages", TrackerAssignee(), TrackerAssignee()))
    }
    @Test fun appendingAfterOneHundredLeavesRoomAndKeepsTheLastMilestoneAtOneHundred() {
        val result = insertTrackerStage(steps, "issue", added, "Stages")
        assertEquals(80.0, result[2].percent!!, 0.0)
        assertEquals(100.0, result.last().percent!!, 0.0)
        assertEquals(steps.take(2), result.take(2))
        assertEquals(steps[2].assigneeUser, result[2].assigneeUser)
    }
    @Test fun repeatedInsertionsAndTightlySpacedLegacyPositionsStayStrictlyIncreasing() {
        var result = listOf(TrackerStage("a", "A", 1.0), TrackerStage("b", "B", Math.nextUp(1.0)))
        repeat(28) { index -> result = insertTrackerStage(result, "a", added.copy(key = "added-$index"), "Stages") }
        assertEquals(30, result.size)
        assertTrue(result.zipWithNext().all { (left, right) -> left.percent!! < right.percent!! })
        assertTrue(result.all { it.percent!! in 0.0..100.0 })
    }
    @Test fun invalidAnchorsDuplicateKeysAndMoreThanThirtyStagesAreRejected() {
        assertThrows(IllegalArgumentException::class.java) { insertTrackerStage(steps, "missing", added, "Status") }
        assertThrows(IllegalArgumentException::class.java) { insertTrackerStage(steps, "draft", added.copy(key = "review"), "Status") }
        assertThrows(IllegalArgumentException::class.java) { insertTrackerStage(steps, "draft", added, "Percentage") }
        assertThrows(IllegalArgumentException::class.java) { insertTrackerStage((1..30).map { added.copy(key = "$it") }, "1", added, "Status") }
    }
    @Test fun firstStageCanBeCreatedAndAMiddleStageCanBeEditedWithoutMovingProgress() {
        assertEquals(100.0, insertTrackerStage(emptyList(), null, added, "Stages").single().percent!!, 0.0)
        val edited = editTrackerStage(steps, "review", "  Verify bills  ", "ravi@example.com", "Ravi")
        assertEquals(steps.map { it.key }, edited.map { it.key })
        assertEquals(steps.map { it.percent }, edited.map { it.percent })
        assertEquals("Verify bills", edited[1].label)
        assertEquals("ravi@example.com", edited[1].assigneeUser)
        assertEquals(steps[0], edited[0]); assertEquals(steps[2], edited[2])
        assertEquals("Review", steps[1].label)
    }
    @Test fun emptyNamesAndUnknownEditTargetsAreRejected() {
        assertThrows(IllegalArgumentException::class.java) { editTrackerStage(steps, "review", " ", "", "") }
        assertThrows(IllegalArgumentException::class.java) { editTrackerStage(steps, "missing", "Check", "", "") }
    }
}
