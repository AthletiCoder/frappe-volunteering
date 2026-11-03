package org.sevamrita.mobile.data

import org.junit.Assert.*
import org.junit.Test

class DemoLoginTest {
    @Test fun demoLoginRequiresLocalOnlyDebugBuild() {
        for (server in Server.entries) {
            assertFalse(allowsDemoLogin(false, true, server))
            assertFalse(allowsDemoLogin(true, false, server))
        }
        assertTrue(allowsDemoLogin(true, true, Server.LOCAL))
        assertFalse(allowsDemoLogin(true, true, Server.PRODUCTION))
        assertFalse(allowsDemoLogin(true, true, Server.STAGING))
    }

    @Test fun selectorNeverSuppliesRemoteServerCredentials() {
        for (server in listOf(Server.PRODUCTION, Server.STAGING)) {
            assertTrue(DemoLogins.accounts(server).isEmpty())
            assertNull(DemoLogins.password("demo.chat.ravi@sevamrita.local", server))
        }
    }

    @Test fun cannotUseDemoLoginToImpersonateAnArbitraryAccount() {
        assertNull(DemoLogins.password("Administrator", Server.LOCAL))
        assertNull(DemoLogins.password("another.user@example.com", Server.LOCAL))
    }
}
