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
        assertEquals(Page.CHART, routeTarget("/volunteering/chart-of-accounts")?.first)
        assertEquals(Page.OPENING_BALANCES, routeTarget("/volunteering/opening-balances")?.first)
        assertEquals(Page.BANK_ACCOUNT, routeTarget("/volunteering/bank-account?queue=1")?.first)
        assertEquals(Page.OFFICE_ADDRESSES, routeTarget("/volunteering/office-addresses")?.first)
        assertEquals(Page.TEAM, routeTarget("/volunteering/team")?.first)
        assertEquals(Page.PROJECT_MAPPING, routeTarget("/volunteering/project-account-mapping")?.first)
        assertEquals(Page.CLAIM_LIMITS, routeTarget("/volunteering/expense-approval-limits")?.first)
        assertEquals(Page.FISCAL_YEARS, routeTarget("/volunteering/fiscal-years")?.first)
        assertEquals(Page.DONATIONS, routeTarget("/volunteering/donations")?.first)
        assertEquals(Page.INVOICE, routeTarget("/volunteering/invoice-generator")?.first)
        assertEquals(Page.MULTI_CLAIM, routeTarget("/volunteering/expense-claim/multiple")?.first)
        assertEquals(Page.COMBINED_START, routeTarget("/volunteering/invoice-expense-claim")?.first)
        assertEquals(Page.BUDGET_HEALTH, routeTarget("/volunteering/budget-health")?.first)
        assertEquals(Page.HR_MANAGEMENT, routeTarget("/volunteering/hr-management")?.first)
        assertEquals(Page.SYSTEM_MANAGEMENT, routeTarget("/volunteering/system-management")?.first)
    }

    @Test fun deskAndUnknownRoutesNeverOpen() {
        assertNull(routeTarget("/desk/project"))
        assertNull(routeTarget("/desk/leave-application/new"))
        assertNull(routeTarget("/desk/daily-work-log/new"))
        assertNull(routeTarget("/app/expense-claim"))
        assertNull(routeTarget("https://example.org/desk"))
    }

    @Test fun homeActionRoutesHaveNativeTargets() {
        val paths = listOf(
            "/volunteering/home", "/volunteering/todos", "/volunteering/projects?view=approved",
            "/volunteering/projects?view=mine", "/volunteering/projects?new=1",
            "/volunteering/project-proposals/review", "/volunteering/advances?new=1",
            "/volunteering/advance-workflow?view=disbursement", "/volunteering/advance-workflow?view=return",
            "/volunteering/expense-claim", "/volunteering/expense-claim/multiple",
            "/volunteering/invoice-expense-claim", "/volunteering/invoice-generator",
            "/volunteering/expense-claim-workflow?view=classification",
            "/volunteering/expense-claim-workflow?view=reimbursement",
            "/volunteering/bank-account?queue=1", "/volunteering/chart-of-accounts",
            "/volunteering/donations", "/volunteering/project-account-mapping",
            "/volunteering/expense-approval-limits", "/volunteering/opening-balances",
            "/volunteering/fiscal-years", "/volunteering/hr-management",
            "/volunteering/system-management", "/volunteering/office-addresses",
            "/volunteering/team", "/volunteering/profile", "/volunteering/budget-health"
        )
        paths.forEach { path -> requireNotNull(routeTarget(path)) { "Missing native route: $path" } }
    }
}
