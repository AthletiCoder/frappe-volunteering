package org.sevamrita.mobile.data

import org.junit.Assert.*
import org.junit.Test

class ChatCacheIdentityTest {
    @Test fun sameAccountAndServerFindTheirSavedScreens() {
        assertEquals(chatCacheIdentity("http://192.168.0.2:8001", "ravi"), chatCacheIdentity("http://192.168.0.2:8001", "ravi"))
    }
    @Test fun anotherAccountOrServerCannotReusePrivateScreens() {
        val ravi = chatCacheIdentity("server-one", "ravi")
        assertNotEquals(ravi, chatCacheIdentity("server-one", "arjun"))
        assertNotEquals(ravi, chatCacheIdentity("server-two", "ravi"))
    }
    @Test fun endpointAndUsernameBoundariesCannotCollide() {
        assertNotEquals(chatCacheIdentity("ab", "c"), chatCacheIdentity("a", "bc"))
    }
}
