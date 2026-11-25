package org.sevamrita.mobile.ui

internal fun timeLeaveHasCategory(type: String): Boolean =
    type in listOf("Privilege Leave", "Compensatory Leave", "Leave Without Pay")

internal fun timeLeaveCategory(type: String, category: String): String =
    if (timeLeaveHasCategory(type)) category else "Normal"
