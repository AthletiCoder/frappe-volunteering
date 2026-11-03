package org.sevamrita.mobile.data

import org.junit.Assert.*
import org.junit.Test
import java.util.concurrent.CancellationException

class OptionalBackgroundWorkTest {
    @Test fun reminderSecurityFailureCannotAbortTheSuccessfulSignInPath() {
        val events = mutableListOf("login succeeded", "session saved", "home opened")
        val started = runOptionalBackgroundWork({ throw SecurityException("ACCESS_NETWORK_STATE permission missing") },
            { events.add("reminders unavailable") })
        events.add("open tracker")
        assertFalse(started)
        assertEquals(listOf("login succeeded", "session saved", "home opened", "reminders unavailable", "open tracker"), events)
    }

    @Test fun successfulBackgroundStartupDoesNotReportAnError() {
        var executed = false
        assertTrue(runOptionalBackgroundWork({ executed = true }, { fail("No warning expected") }))
        assertTrue(executed)
    }

    @Test fun cancellationAndFatalErrorsAreNotHidden() {
        assertThrows(CancellationException::class.java) { runOptionalBackgroundWork({ throw CancellationException() }) }
        assertThrows(AssertionError::class.java) { runOptionalBackgroundWork({ throw AssertionError() }) }
    }
}
