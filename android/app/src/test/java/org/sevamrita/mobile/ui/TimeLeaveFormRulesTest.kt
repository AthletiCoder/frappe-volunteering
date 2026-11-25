package org.sevamrita.mobile.ui

import org.junit.Assert.*
import org.junit.Test

class TimeLeaveFormRulesTest {
    @Test fun ordinaryLeaveKeepsTheChosenMedicalCategory() {
        for (type in listOf("Privilege Leave", "Compensatory Leave", "Leave Without Pay")) {
            assertTrue(timeLeaveHasCategory(type))
            assertEquals("Medical", timeLeaveCategory(type, "Medical"))
        }
    }
    @Test fun parentalAndOptionalLeaveCannotInheritAMedicalCategory() {
        for (type in listOf("Maternity Leave", "Paternity Leave", "Optional Holiday")) {
            assertFalse(timeLeaveHasCategory(type))
            assertEquals("Normal", timeLeaveCategory(type, "Medical"))
        }
    }
}
