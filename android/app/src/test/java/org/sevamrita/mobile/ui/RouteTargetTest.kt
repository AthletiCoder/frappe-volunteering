package org.sevamrita.mobile.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class RouteTargetTest {
    @Test fun homeRoutesStayNative() {
        assertEquals(Page.HOME, routeTarget("/volunteering/home")?.first)
        assertEquals(Page.PROJECT, routeTarget("/volunteering/projects?project=PROJ-0001")?.first)
        assertEquals(Page.PROPOSAL_FORM, routeTarget("/volunteering/projects?new=1")?.first)
        assertEquals(Page.PROPOSALS, routeTarget("/volunteering/projects?view=mine")?.first)
        assertEquals(Page.PROPOSALS, routeTarget("/volunteering/project-proposals/review")?.first)
        assertEquals("PROJ-0001", routeTarget("/volunteering/projects?project=PROJ-0001")?.second)
        assertEquals(Page.CLAIM, routeTarget("/volunteering/expense-claims?claim=HR-EXP-0001")?.first)
        assertEquals(Page.ADVANCE_REVIEW, routeTarget("/volunteering/advance-workflow?advance=HR-EAD-0001")?.first)
        assertEquals(Page.CLAIM_REVIEW, routeTarget("/volunteering/expense-claim-workflow?claim=HR-EXP-0001")?.first)
    }

    @Test fun deskAndUnknownRoutesNeverOpen() {
        assertNull(routeTarget("/desk/project"))
        assertNull(routeTarget("/app/expense-claim"))
        assertNull(routeTarget("https://example.org/desk"))
        assertNull(routeTarget("/volunteering/chart-of-accounts"))
    }
}
