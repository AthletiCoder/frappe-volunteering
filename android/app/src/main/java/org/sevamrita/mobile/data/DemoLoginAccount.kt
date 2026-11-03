package org.sevamrita.mobile.data

data class DemoLoginAccount(val email: String, val name: String, val access: String) {
    val label: String get() = "$name · $access"
}

internal fun allowsDemoLogin(debug: Boolean, localOnly: Boolean, server: Server): Boolean =
    debug && localOnly && server == Server.LOCAL
