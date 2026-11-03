package org.sevamrita.mobile.data

import org.junit.Assert.*
import org.junit.Test

class ChatAccessResponseTest {
    private val api = "volunteering.volunteering.collaboration_mobile."

    @Test fun revokedGlobalRoleRemovesCachedLogin() {
        assertTrue(isChatAccessRevoked(api + "get_collaboration_home", 403))
        assertTrue(isChatAccessRevoked(api + "get_my_work", 403))
    }

    @Test fun lostChatMembershipDoesNotInvalidateOtherConversations() {
        for (method in listOf("get_space", "get_work_item", "record_progress", "get_item_history"))
            assertFalse(isChatAccessRevoked(api + method, 403))
    }

    @Test fun temporaryFailuresKeepTheSavedLogin() {
        for (status in listOf(200, 400, 429, 500, 502, 503))
            assertFalse(isChatAccessRevoked(api + "get_collaboration_home", status))
    }
}
