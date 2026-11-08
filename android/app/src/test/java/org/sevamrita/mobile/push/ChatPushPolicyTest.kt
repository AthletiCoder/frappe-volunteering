package org.sevamrita.mobile.push

import org.junit.Assert.*
import org.junit.Test

class ChatPushPolicyTest {
    private val session = "a".repeat(64)
    @Test fun onlyTheCurrentlyRegisteredSessionCanReceivePush() {
        assertTrue(validPush("message-123", session, session, session))
        assertFalse(validPush("message-123", session, null, session))
        assertFalse(validPush("message-123", session, session, null))
        assertFalse(validPush("message-123", "b".repeat(64), session, session))
        assertFalse(validPush("message-123", session, "new-session", session))
    }
    @Test fun invalidEntryIdsCannotBecomePortalOrNavigationRequests() {
        listOf("", "../files/receipt", "https://other.test", "a".repeat(141)).forEach { assertFalse(validPush(it, session, session, session)) }
    }
}
