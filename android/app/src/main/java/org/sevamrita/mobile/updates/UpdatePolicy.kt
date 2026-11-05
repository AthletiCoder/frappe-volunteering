package org.sevamrita.mobile.updates

import java.net.URI
import java.io.File
import java.io.InputStream
import java.security.MessageDigest

internal data class UpdateRelease(
    val packageName: String, val versionCode: Long, val versionName: String,
    val minSdk: Int, val sizeBytes: Long, val sha256: String, val apkUrl: String, val notes: String
)

internal data class UpdateIdentity(val packageName: String, val versionCode: Long, val certificates: Set<String>)

internal object UpdatePolicy {
    const val REPO = "AthletiCoder/frappe-volunteering"
    const val MAX_APK_BYTES = 100L * 1024 * 1024
    private val packages = setOf("org.sevamrita.mobile", "org.sevamrita.mobile.local")
    private val redirectHosts = setOf("github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com", "github-releases.githubusercontent.com")

    fun feed(packageName: String): String {
        require(packageName in packages) { "Updates are unavailable for this app build." }
        val file = if (packageName.endsWith(".local")) "sf-testing-update.json" else "sf-tasks-update.json"
        return "https://github.com/$REPO/releases/download/sf-tasks-updates/$file"
    }

    fun trustedTransport(url: String): Boolean = runCatching {
        val uri = URI(url)
        uri.scheme == "https" && uri.host in redirectHosts && uri.userInfo == null && uri.port in listOf(-1, 443)
    }.getOrDefault(false)

    fun validate(release: UpdateRelease, packageName: String, sdk: Int) {
        require(packageName in packages && release.packageName == packageName) { "This update belongs to a different app." }
        require(release.versionCode > 0 && release.versionName.matches(Regex("[0-9]+\\.[0-9]+\\.[0-9]+(?:-local)?"))) { "Invalid update version." }
        require(release.minSdk in 26..sdk) { "This update needs a newer Android version." }
        require(release.sizeBytes in 1..MAX_APK_BYTES && release.sha256.matches(Regex("[a-f0-9]{64}"))) { "Invalid update verification details." }
        val uri = URI(release.apkUrl)
        val app = if (packageName.endsWith(".local")) "SF-testing" else "SF-Tasks"
        require(trustedTransport(release.apkUrl) && uri.host == "github.com" && uri.rawQuery == null && uri.rawFragment == null &&
            uri.rawPath.matches(Regex("/$REPO/releases/download/sf-tasks-v[0-9]+\\.[0-9]+\\.[0-9]+/$app-[0-9]+\\.[0-9]+\\.[0-9]+\\.apk"))) { "Unrecognised update download location." }
    }

    fun verifyIdentity(installed: UpdateIdentity, archive: UpdateIdentity, release: UpdateRelease) {
        require(archive.packageName == installed.packageName && archive.packageName == release.packageName &&
            archive.versionCode == release.versionCode && archive.versionCode > installed.versionCode) { "The downloaded app version does not match this update." }
        require(installed.certificates.isNotEmpty() && archive.certificates == installed.certificates) { "The downloaded app has a different signing key." }
    }
}

/** The final APK exists only after its complete size and digest have been checked. */
internal fun verifiedDownload(input: InputStream, directory: File, release: UpdateRelease, progress: (Long) -> Unit): File {
    require(release.sizeBytes in 1..UpdatePolicy.MAX_APK_BYTES)
    directory.mkdirs()
    val partial = File(directory, "update.part")
    val result = File(directory, "update.apk")
    partial.delete(); result.delete()
    try {
        val digest = MessageDigest.getInstance("SHA-256")
        var total = 0L
        partial.outputStream().use { out ->
            val buffer = ByteArray(32 * 1024)
            while (true) {
                if (Thread.currentThread().isInterrupted) throw java.io.InterruptedIOException()
                val count = input.read(buffer)
                if (count < 0) break
                total += count
                require(total <= release.sizeBytes) { "The update download has an unexpected size." }
                digest.update(buffer, 0, count); out.write(buffer, 0, count); progress(total)
            }
        }
        require(total == release.sizeBytes && digest.digest().hex() == release.sha256) { "The update download could not be verified. Please retry." }
        check(partial.renameTo(result)) { "Could not save the update. Free some storage and retry." }
        return result
    } catch (error: Exception) { partial.delete(); result.delete(); throw error }
}

internal fun ByteArray.hex(): String = joinToString("") { "%02x".format(it) }
