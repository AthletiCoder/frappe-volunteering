package org.sevamrita.mobile.data

import org.junit.Assert.*
import org.junit.Test
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory

/** A network-constrained JobScheduler job throws on Android 14+ without this permission. */
class ReminderPlatformContractTest {
    @Test fun reminderSchedulerDeclaresRequiredAndroidPlatformPermissions() {
        val factory = DocumentBuilderFactory.newInstance().apply { isNamespaceAware = true }
        val manifest = factory.newDocumentBuilder().parse(File(System.getProperty("sevamrita.manifest")))
        val nodes = manifest.getElementsByTagName("uses-permission")
        val permissions = (0 until nodes.length).map { nodes.item(it).attributes.getNamedItemNS("http://schemas.android.com/apk/res/android", "name").nodeValue }
        assertTrue("Network-constrained jobs must not invalidate login on Android 14+", "android.permission.ACCESS_NETWORK_STATE" in permissions)
        assertTrue("Persisted jobs need reboot permission", "android.permission.RECEIVE_BOOT_COMPLETED" in permissions)
        assertTrue("Android 13+ notifications require opt-in", "android.permission.POST_NOTIFICATIONS" in permissions)
    }
}
