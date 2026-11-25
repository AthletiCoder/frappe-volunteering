package org.sevamrita.mobile.ui

import org.junit.Assert.*
import org.junit.Test
import java.time.LocalDate
import java.time.YearMonth

class WorkLogCalendarTest {
    @Test fun sundayStartUsesSixLeadingBlanksAndCompleteWeeks() {
        val dates = workLogMonthDates(YearMonth.of(2026, 11))
        assertEquals(42, dates.size)
        assertTrue(dates.take(6).all { it == null })
        assertEquals(LocalDate.of(2026, 11, 1), dates[6])
        assertEquals(30, dates.filterNotNull().size)
    }
    @Test fun leapFebruaryIncludesTwentyNineDaysWithoutDuplicates() {
        val dates = workLogMonthDates(YearMonth.of(2024, 2))
        assertEquals(35, dates.size)
        assertEquals(29, dates.filterNotNull().toSet().size)
        assertEquals(LocalDate.of(2024, 2, 29), dates[31])
    }
    @Test fun mondayStartFebruaryUsesExactlyFourWeeks() {
        val dates = workLogMonthDates(YearMonth.of(2021, 2))
        assertEquals(28, dates.size)
        assertEquals(LocalDate.of(2021, 2, 1), dates.first())
    }
    @Test fun allMonthsHaveExactlyTheirOwnDatesInChronologicalOrder() {
        for (year in listOf(2024, 2026, 2027)) for (month in 1..12) {
            val ym = YearMonth.of(year, month)
            val dates = workLogMonthDates(ym)
            assertEquals(0, dates.size % 7)
            assertEquals((1..ym.lengthOfMonth()).map { ym.atDay(it) }, dates.filterNotNull())
        }
    }
}
