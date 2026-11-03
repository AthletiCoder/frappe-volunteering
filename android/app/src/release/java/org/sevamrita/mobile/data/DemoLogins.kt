package org.sevamrita.mobile.data

/** Production builds contain no demo credentials or account selector. */
object DemoLogins {
    fun accounts(server: Server): List<DemoLoginAccount> = emptyList()
    fun password(email: String, server: Server): String? = null
}
