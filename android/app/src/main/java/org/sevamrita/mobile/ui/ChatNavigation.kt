package org.sevamrita.mobile.ui

/** Native conversations, tasks and daily work destinations. */
enum class ChatView { CONVERSATIONS, CHAT, TASKS, MY_TASKS, TRACKERS, MY_TRACKERS, TRACKER, TASK, SEARCH, MENTIONS, SETTINGS, OUTBOX, WORK_LOGS, WORK_LOG, TIME_LEAVE }

enum class TasksSection { CHATS, WORK_LOGS, TIME_LEAVE }

fun ChatRoute.section(): TasksSection =
    if (view == ChatView.TIME_LEAVE) TasksSection.TIME_LEAVE else if (view in listOf(ChatView.WORK_LOGS, ChatView.WORK_LOG)) TasksSection.WORK_LOGS else TasksSection.CHATS

/** Saved UI preferences never grant access to a section that is no longer allowed. */
fun tasksStartRoute(savedSection: String?, chatAccess: Boolean, workLogAccess: Boolean): ChatRoute =
    if (workLogAccess && savedSection == TasksSection.TIME_LEAVE.name) ChatRoute(ChatView.TIME_LEAVE)
    else if (!chatAccess || (workLogAccess && savedSection == TasksSection.WORK_LOGS.name)) ChatRoute(ChatView.WORK_LOGS)
    else ChatRoute()

data class ChatRoute(val view: ChatView = ChatView.CONVERSATIONS, val room: String = "", val item: String = "") {
    init {
        require((view in listOf(ChatView.CHAT, ChatView.TASKS, ChatView.TRACKERS, ChatView.TRACKER, ChatView.TASK)) == room.isNotBlank())
        require(view == ChatView.WORK_LOG || (view in listOf(ChatView.TRACKER, ChatView.TASK)) == item.isNotBlank())
    }
}

data class ChatNavigation(
    val current: ChatRoute = ChatRoute(),
    val history: List<ChatRoute> = emptyList()
) {
    val canGoBack: Boolean get() = history.isNotEmpty()
    fun navigate(route: ChatRoute): ChatNavigation = if (route == current) this
        else ChatNavigation(route, history + current)
    fun switchSection(section: TasksSection): ChatNavigation = ChatNavigation(
        current = when(section) { TasksSection.WORK_LOGS -> ChatRoute(ChatView.WORK_LOGS); TasksSection.TIME_LEAVE -> ChatRoute(ChatView.TIME_LEAVE); else -> ChatRoute() }
    )
    fun back(): ChatNavigation = if (!canGoBack) this else ChatNavigation(history.last(), history.dropLast(1))
}
