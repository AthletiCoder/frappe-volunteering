package org.sevamrita.mobile.data

import org.sevamrita.mobile.BuildConfig

/** Fixed fictional fixtures only. This source file is excluded from release builds. */
object DemoLogins {
    fun accounts(server: Server): List<DemoLoginAccount> =
        if (allowsDemoLogin(BuildConfig.DEBUG, BuildConfig.LOCAL_PORTAL_ONLY, server)) listOf(
            DemoLoginAccount("demo.chat.ravi@sevamrita.local", "Ravi Menon", "Workspace owner"),
            DemoLoginAccount("demo.chat.arjun@sevamrita.local", "Arjun Sharma", "Member"),
            DemoLoginAccount("demo.chat.dev@sevamrita.local", "Dev Patil", "Viewer"),
            DemoLoginAccount("demo.tonight.employee@sevamrita.local", "Rahul Patil", "Work logging"),
            DemoLoginAccount("demo.tonight.manager@sevamrita.local", "Sanjay Kulkarni", "Work log review")
        ) else emptyList()

    fun password(email: String, server: Server): String? =
        if (accounts(server).none { it.email == email }) null
        else if (email.startsWith("demo.tonight.")) "DemoTonight!26"
        else "DemoChat!2026"
}
