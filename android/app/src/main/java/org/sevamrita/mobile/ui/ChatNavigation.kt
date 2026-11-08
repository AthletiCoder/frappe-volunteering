package org.sevamrita.mobile.ui

/** Collaboration destinations only; ERP workflows remain on the web. */
enum class ChatView { CONVERSATIONS, CHAT, TASKS, MY_TASKS, TRACKERS, MY_TRACKERS, TRACKER, TASK, SEARCH, MENTIONS, SETTINGS, OUTBOX }

data class ChatRoute(val view: ChatView = ChatView.CONVERSATIONS, val room: String = "", val item: String = "") {
    init {
        require((view in listOf(ChatView.CHAT, ChatView.TASKS, ChatView.TRACKERS, ChatView.TRACKER, ChatView.TASK)) == room.isNotBlank())
        require((view in listOf(ChatView.TRACKER, ChatView.TASK)) == item.isNotBlank())
    }
}

data class ChatNavigation(
    val current: ChatRoute = ChatRoute(),
    val history: List<ChatRoute> = emptyList()
) {
    val canGoBack: Boolean get() = history.isNotEmpty()
    fun navigate(route: ChatRoute): ChatNavigation = if (route == current) this
        else ChatNavigation(route, history + current)
    fun back(): ChatNavigation = if (!canGoBack) this else ChatNavigation(history.last(), history.dropLast(1))
}
