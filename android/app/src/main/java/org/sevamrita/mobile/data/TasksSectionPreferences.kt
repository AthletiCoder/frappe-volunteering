package org.sevamrita.mobile.data

import android.content.Context

/** Keeps the last section separate for each login and server, including after logout. */
internal class TasksSectionPreferences(context: Context) {
    private val prefs = context.getSharedPreferences("tasks_last_section", Context.MODE_PRIVATE)

    fun read(endpoint: String, user: String): String? =
        if (user.isBlank()) null else prefs.getString(chatCacheIdentity(endpoint, user), null)

    fun remember(endpoint: String, user: String, section: String) {
        if (user.isNotBlank()) prefs.edit().putString(chatCacheIdentity(endpoint, user), section).apply()
    }
}
