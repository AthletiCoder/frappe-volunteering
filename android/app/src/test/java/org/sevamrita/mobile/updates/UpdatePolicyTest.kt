package org.sevamrita.mobile.updates

import org.junit.Assert.*
import org.junit.Test
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory

class UpdatePolicyTest {
    private fun release() = UpdateRelease("org.sevamrita.mobile", 21, "0.5.1", 26, 4096,
        "a".repeat(64), "https://sevamrita.m.frappe.cloud/assets/volunteering/android_updates/SF-Tasks-0.5.1.apk", "Changes")
    private fun reject(action: () -> Unit) { assertThrows(IllegalArgumentException::class.java, action) }

    @Test fun productionAndTestingUseSeparateStableFeeds() {
        assertTrue(UpdatePolicy.feed("org.sevamrita.mobile").endsWith("/android_updates/sf-tasks-update.json"))
        assertTrue(UpdatePolicy.feed("org.sevamrita.mobile.local").endsWith("/android_updates/sf-testing-update.json"))
        reject { UpdatePolicy.feed("another.package") }
    }

    @Test fun releaseMustBelongToTheInstalledAppChannel() {
        UpdatePolicy.validate(release(), "org.sevamrita.mobile", 35)
        reject { UpdatePolicy.validate(release(), "org.sevamrita.mobile.local", 35) }
        reject { UpdatePolicy.validate(release().copy(apkUrl = release().apkUrl.replace("SF-Tasks", "SF-testing")), "org.sevamrita.mobile", 35) }
    }

    @Test fun transportAllowsOnlyTheErpSite() {
        assertTrue(UpdatePolicy.trustedTransport("https://sevamrita.m.frappe.cloud/a"))
        listOf("http://sevamrita.m.frappe.cloud/a", "https://sevamrita.m.frappe.cloud.evil.test/a", "https://user@sevamrita.m.frappe.cloud/a", "https://sevamrita.m.frappe.cloud:8443/a", "https://elsewhere.test/a").forEach {
            assertFalse(it, UpdatePolicy.trustedTransport(it))
        }
    }

    @Test fun manifestCannotSelectAnotherSiteOrUnversionedApk() {
        listOf(release().apkUrl.replace("sevamrita.m.frappe.cloud", "other.test"), release().apkUrl.replace("0.5.1", "latest"),
            release().apkUrl + "?redirect=elsewhere", release().apkUrl.replace("/SF-Tasks", "/%2e%2e/SF-Tasks")).forEach {
            reject { UpdatePolicy.validate(release().copy(apkUrl = it), "org.sevamrita.mobile", 35) }
        }
    }

    @Test fun unsupportedAndroidVersionAndInvalidDigestOrSizeAreRejected() {
        listOf(release().copy(minSdk = 36), release().copy(sha256 = "abc"), release().copy(sizeBytes = 0),
            release().copy(sizeBytes = UpdatePolicy.MAX_APK_BYTES + 1)).forEach {
            reject { UpdatePolicy.validate(it, "org.sevamrita.mobile", 35) }
        }
    }

    @Test fun onlyAValidNewerReleaseIsOffered() {
        val release = release()
        assertEquals(release, UpdatePolicy.newerRelease(release, release.packageName, 35, 20))
        assertNull(UpdatePolicy.newerRelease(release, release.packageName, 35, 21))
        assertNull(UpdatePolicy.newerRelease(release, release.packageName, 35, 22))
        reject { UpdatePolicy.newerRelease(release, "org.sevamrita.mobile.local", 35, 20) }
    }

    @Test fun browserHandoffUsesTheErpDownloadPageForTheInstalledChannel() {
        val page = "https://sevamrita.m.frappe.cloud/sf-tasks-download"
        assertEquals("$page#sf-tasks", UpdatePolicy.releasePage("org.sevamrita.mobile"))
        assertEquals("$page#sf-testing", UpdatePolicy.releasePage("org.sevamrita.mobile.local"))
        reject { UpdatePolicy.releasePage("another.package") }
    }

    @Test fun updaterHasNoPermissionOrProviderToRequestAppInstalls() {
        val factory = DocumentBuilderFactory.newInstance().apply { isNamespaceAware = true }
        val file = File(System.getProperty("sevamrita.manifest"))
        val doc = factory.newDocumentBuilder().parse(file)
        val namespace = "http://schemas.android.com/apk/res/android"
        val permissions = doc.getElementsByTagName("uses-permission")
        assertFalse((0 until permissions.length).any { permissions.item(it).attributes.getNamedItemNS(namespace, "name").nodeValue == "android.permission.REQUEST_INSTALL_PACKAGES" })
        val providers = doc.getElementsByTagName("provider")
        assertFalse((0 until providers.length).any { providers.item(it).attributes.getNamedItemNS(namespace, "authorities")?.nodeValue?.endsWith(".updates") == true })
        assertFalse(File(file.parentFile, "res/xml/update_paths.xml").exists())
    }
}
