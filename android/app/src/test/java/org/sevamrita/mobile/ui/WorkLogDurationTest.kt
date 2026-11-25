package org.sevamrita.mobile.ui

import org.junit.Assert.*
import org.junit.Test

class WorkLogDurationTest {
    @Test fun minuteDurationsRoundTripWithoutLosingMinutes() {
        for (minutes in listOf(1, 15, 59, 60, 90, 359, 360, 1439, 1440)) {
            assertEquals(minutes, workLogMinutes(workLogDurationHours(minutes / 60, minutes % 60)))
        }
    }
    @Test fun invalidPickerDurationsAreRejected() {
        for ((hours, minutes) in listOf(-1 to 0, 25 to 0, 0 to 60, 0 to -1, 24 to 1)) {
            assertThrows(IllegalArgumentException::class.java) { workLogDurationHours(hours, minutes) }
        }
    }
    @Test fun invalidServerValuesCannotCrashDurationFormatting() {
        for (value in listOf("", "NaN", "Infinity", "-1", "1E1000")) assertNull(workLogMinutes(value))
    }
    @Test fun labelsSupportMinutesAndMonthlyTotals() {
        assertEquals("0 min", workLogDurationLabel("0"))
        assertEquals("1 min", workLogDurationLabel("0.016666667"))
        assertEquals("2 h 30 min", workLogDurationLabel("2.5"))
        assertEquals("37 h", workLogDurationLabel("37"))
        assertEquals("24", workLogDurationHours(24, 0))
    }
    @Test fun headingsIdentifyWhoseLogIsBeingShown() {
        assertEquals("My work log", workLogTitle(false))
        assertEquals("Team work log", workLogTitle(true))
    }
    @Test fun historicalOutputLinksRemainVisibleInDetailsWithoutDuplication() {
        val link = "https://example.org/lesson-plan"
        assertEquals("Prepared materials.\n\n$link", workLogDetails("Prepared materials.", link))
        assertEquals("Prepared materials: $link", workLogDetails("Prepared materials: $link", link))
        assertEquals("Prepared materials.", workLogDetails("Prepared materials.", ""))
    }
}
