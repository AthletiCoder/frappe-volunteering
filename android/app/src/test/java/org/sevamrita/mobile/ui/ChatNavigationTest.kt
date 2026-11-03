package org.sevamrita.mobile.ui

import org.junit.Assert.*
import org.junit.Test

class ChatNavigationTest {
    @Test fun backReturnsThroughScreensInVisitedOrder() {
        val root = ChatNavigation()
        val chat = root.navigate(ChatRoute(ChatView.CHAT, "kitchen"))
        val tasks = chat.navigate(ChatRoute(ChatView.TASKS, "kitchen"))
        val personal = tasks.navigate(ChatRoute(ChatView.MY_TASKS))
        val otherChat = personal.navigate(ChatRoute(ChatView.CHAT, "direct"))
        assertEquals(personal.current, otherChat.back().current)
        assertEquals(tasks.current, otherChat.back().back().current)
        assertEquals(chat.current, otherChat.back().back().back().current)
        assertEquals(root, otherChat.back().back().back().back())
    }

    @Test fun selectingSameDestinationDoesNotAddBackSteps() {
        val nav = ChatNavigation().navigate(ChatRoute(ChatView.CHAT, "kitchen"))
        assertEquals(nav, nav.navigate(nav.current))
    }

    @Test fun rootBackHasNoEarlierScreenAndDoesNotChangeState() {
        val root = ChatNavigation()
        assertFalse(root.canGoBack)
        assertEquals(root, root.back())
    }

    @Test fun chatsButtonAndBackRestorePreviouslyOpenedTaskScreen() {
        val tasks = ChatNavigation().navigate(ChatRoute(ChatView.CHAT, "kitchen"))
            .navigate(ChatRoute(ChatView.TASKS, "kitchen"))
        assertEquals(tasks.current, tasks.navigate(ChatRoute()).back().current)
    }

    @Test fun newSessionStartsWithoutPreviousUsersHistory() {
        val old = ChatNavigation().navigate(ChatRoute(ChatView.CHAT, "private"))
        assertTrue(old.canGoBack)
        assertFalse(ChatNavigation().canGoBack)
        assertEquals(ChatView.CONVERSATIONS, ChatNavigation().current.view)
    }

    @Test fun roomIsRequiredOnlyForRoomScreens() {
        assertThrows(IllegalArgumentException::class.java) { ChatRoute(ChatView.CHAT) }
        assertThrows(IllegalArgumentException::class.java) { ChatRoute(ChatView.TASKS) }
        assertThrows(IllegalArgumentException::class.java) { ChatRoute(ChatView.CONVERSATIONS, "private") }
        assertThrows(IllegalArgumentException::class.java) { ChatRoute(ChatView.TRACKERS) }
        assertThrows(IllegalArgumentException::class.java) { ChatRoute(ChatView.MY_TRACKERS, "private") }
    }

    @Test fun trackersHaveTheirOwnBackHistory() {
        val chat = ChatNavigation().navigate(ChatRoute(ChatView.CHAT, "kitchen"))
        val trackers = chat.navigate(ChatRoute(ChatView.TRACKERS, "kitchen"))
        val mine = trackers.navigate(ChatRoute(ChatView.MY_TRACKERS))
        assertEquals(trackers.current, mine.back().current)
        assertEquals(chat.current, mine.back().back().current)
    }

    @Test fun trackerOpensIndividuallyAndBackReturnsToPersonalList() {
        val mine = ChatNavigation().navigate(ChatRoute(ChatView.MY_TRACKERS))
        val detail = mine.navigate(ChatRoute(ChatView.TRACKER, "kitchen", "meals"))
        assertEquals("meals", detail.current.item)
        assertEquals(mine, detail.back())
        val second = detail.navigate(ChatRoute(ChatView.TRACKER, "kitchen", "volunteers"))
        assertEquals(detail.current, second.back().current)
    }

    @Test fun trackerDetailRequiresItsRoomAndItemWithoutAllowingItemsOnOtherScreens() {
        assertThrows(IllegalArgumentException::class.java) { ChatRoute(ChatView.TRACKER, "kitchen") }
        assertThrows(IllegalArgumentException::class.java) { ChatRoute(ChatView.TRACKER, item = "meals") }
        assertThrows(IllegalArgumentException::class.java) { ChatRoute(ChatView.TRACKERS, "kitchen", "meals") }
    }

    @Test fun sharedTaskCanOpenWithoutEnteringTheChatAndBackReturnsToMyWork() {
        val mine = ChatNavigation().navigate(ChatRoute(ChatView.MY_TASKS))
        val task = mine.navigate(ChatRoute(ChatView.TASK, "private", "shared-task"))
        assertEquals("shared-task", task.current.item)
        assertEquals(mine, task.back())
        assertThrows(IllegalArgumentException::class.java) { ChatRoute(ChatView.TASK, "private") }
    }
}
