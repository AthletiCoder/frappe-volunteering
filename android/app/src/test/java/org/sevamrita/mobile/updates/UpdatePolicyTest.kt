package org.sevamrita.mobile.updates

import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.ByteArrayInputStream
import java.io.IOException
import java.io.InputStream
import java.io.File
import java.security.MessageDigest
import javax.xml.parsers.DocumentBuilderFactory

class UpdatePolicyTest {
    @get:Rule val temporary = TemporaryFolder()
    private val content = "a signed APK is verified separately by Android".toByteArray()
    private fun release() = UpdateRelease("org.sevamrita.mobile", 21, "0.5.1", 26, content.size.toLong(),
        MessageDigest.getInstance("SHA-256").digest(content).hex(),
        "https://github.com/AthletiCoder/frappe-volunteering/releases/download/sf-tasks-v0.5.1/SF-Tasks-0.5.1.apk", "Changes")
    private fun reject(action: () -> Unit) { assertThrows(IllegalArgumentException::class.java, action) }

    @Test fun productionAndTestingUseSeparateStableFeeds() {
        assertTrue(UpdatePolicy.feed("org.sevamrita.mobile").endsWith("/sf-tasks-updates/sf-tasks-update.json"))
        assertTrue(UpdatePolicy.feed("org.sevamrita.mobile.local").endsWith("/sf-tasks-updates/sf-testing-update.json"))
        reject { UpdatePolicy.feed("another.package") }
    }

    @Test fun releaseMustBelongToTheInstalledAppChannel() {
        UpdatePolicy.validate(release(), "org.sevamrita.mobile", 35)
        reject { UpdatePolicy.validate(release(), "org.sevamrita.mobile.local", 35) }
        reject { UpdatePolicy.validate(release().copy(apkUrl = release().apkUrl.replace("SF-Tasks", "SF-testing")), "org.sevamrita.mobile", 35) }
    }

    @Test fun transportAllowsHttpsGitHubRedirectsOnly() {
        assertTrue(UpdatePolicy.trustedTransport("https://release-assets.githubusercontent.com/a?token=x"))
        listOf("http://github.com/a", "https://github.com.evil.test/a", "https://user@github.com/a", "https://github.com:8443/a", "https://elsewhere.test/a").forEach {
            assertFalse(it, UpdatePolicy.trustedTransport(it))
        }
    }

    @Test fun manifestCannotSelectAnotherRepositoryOrUnversionedApk() {
        listOf(release().apkUrl.replace("AthletiCoder", "someone"), release().apkUrl.replace("sf-tasks-v0.5.1", "latest"),
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

    @Test fun upgradePreservesPackageAndSigningKey() {
        val installed = UpdateIdentity("org.sevamrita.mobile", 20, setOf("certificate"))
        UpdatePolicy.verifyIdentity(installed, installed.copy(versionCode = 21), release())
        reject { UpdatePolicy.verifyIdentity(installed, installed.copy(versionCode = 21, certificates = setOf("other")), release()) }
        reject { UpdatePolicy.verifyIdentity(installed, installed.copy(versionCode = 21, packageName = "org.sevamrita.mobile.local"), release()) }
        reject { UpdatePolicy.verifyIdentity(installed, installed.copy(versionCode = 21, certificates = emptySet()), release()) }
    }

    @Test fun sameVersionDowngradesAndMislabelledPackagesAreNeverInstalled() {
        val installed = UpdateIdentity("org.sevamrita.mobile", 20, setOf("certificate"))
        listOf(19L, 20L, 22L).forEach { version ->
            reject { UpdatePolicy.verifyIdentity(installed, installed.copy(versionCode = version), release()) }
        }
    }

    @Test fun validDownloadIsPromotedOnlyAfterVerification() {
        val directory = temporary.newFolder()
        val progress = mutableListOf<Long>()
        val file = verifiedDownload(ByteArrayInputStream(content), directory, release()) { progress += it }
        assertArrayEquals(content, file.readBytes())
        assertEquals(content.size.toLong(), progress.last())
        assertFalse(File(directory, "update.part").exists())
    }

    @Test fun truncatedOversizeAndCorruptDownloadsLeaveNoInstallableFile() {
        listOf(content.dropLast(1).toByteArray(), content + byteArrayOf(0), content.copyOf().apply { this[0] = 0 }).forEach { bytes ->
            val directory = temporary.newFolder()
            reject { verifiedDownload(ByteArrayInputStream(bytes), directory, release()) {} }
            assertTrue(directory.listFiles().isNullOrEmpty())
        }
    }

    @Test fun interruptedDownloadCleansPartialAndCanBeRetried() {
        val directory = temporary.newFolder()
        val broken = object : InputStream() { override fun read(): Int = throw IOException("Connection interrupted") }
        assertThrows(IOException::class.java) { verifiedDownload(broken, directory, release()) {} }
        assertTrue(directory.listFiles().isNullOrEmpty())
        assertTrue(verifiedDownload(ByteArrayInputStream(content), directory, release()) {}.exists())
    }

    @Test fun installerFileProviderIsPrivateAndNarrowlyScoped() {
        val factory = DocumentBuilderFactory.newInstance().apply { isNamespaceAware = true }
        val file = File(System.getProperty("sevamrita.manifest"))
        val doc = factory.newDocumentBuilder().parse(file)
        val namespace = "http://schemas.android.com/apk/res/android"
        val providers = doc.getElementsByTagName("provider")
        val provider = (0 until providers.length).map { providers.item(it) }.single {
            it.attributes.getNamedItemNS(namespace, "name").nodeValue == "androidx.core.content.FileProvider"
        }
        assertEquals("false", provider.attributes.getNamedItemNS(namespace, "exported").nodeValue)
        assertEquals("true", provider.attributes.getNamedItemNS(namespace, "grantUriPermissions").nodeValue)
        val paths = factory.newDocumentBuilder().parse(File(file.parentFile, "res/xml/update_paths.xml"))
        assertEquals(1, paths.getElementsByTagName("cache-path").length)
        assertEquals("app-updates/", paths.getElementsByTagName("cache-path").item(0).attributes.getNamedItem("path").nodeValue)
        assertEquals(0, paths.getElementsByTagName("root-path").length)
        val permissions = doc.getElementsByTagName("uses-permission")
        assertTrue((0 until permissions.length).any { permissions.item(it).attributes.getNamedItemNS(namespace, "name").nodeValue == "android.permission.REQUEST_INSTALL_PACKAGES" })
    }
}
