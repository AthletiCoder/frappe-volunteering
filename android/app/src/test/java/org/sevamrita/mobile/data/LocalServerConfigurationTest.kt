package org.sevamrita.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.sevamrita.mobile.BuildConfig

class LocalServerConfigurationTest {
    @Test fun localTestBuildHasPrivateDefaultAndCannotSelectRemoteServers() {
        if (!BuildConfig.DEBUG) {
            assertEquals(listOf(Server.PRODUCTION), Server.available())
            assertEquals("SF Tasks", BuildConfig.APP_NAME)
            assertTrue(DemoLogins.accounts(Server.PRODUCTION).isEmpty())
            return
        }
        assertTrue(isPrivateIpv4(BuildConfig.DEFAULT_LOCAL_HOST))
        if (BuildConfig.LOCAL_PORTAL_ONLY) assertEquals("SF testing", BuildConfig.APP_NAME)
        if (BuildConfig.LOCAL_PORTAL_ONLY) assertEquals(listOf(Server.LOCAL), Server.available())
        else assertEquals(listOf(Server.LOCAL, Server.PRODUCTION, Server.STAGING), Server.available())
    }

    @Test fun releaseCannotEnableLocalHttpEvenWithLocalOnlyFlag() {
        assertEquals(listOf(Server.PRODUCTION), Server.available(debug = false, localOnly = true))
        assertEquals(listOf(Server.PRODUCTION), Server.available(debug = false, localOnly = false))
    }
}
