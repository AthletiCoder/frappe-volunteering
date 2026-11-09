package org.sevamrita.mobile.updates

import java.net.URI

internal data class UpdateRelease(
    val packageName: String, val versionCode: Long, val versionName: String,
    val minSdk: Int, val sizeBytes: Long, val sha256: String, val apkUrl: String, val notes: String
)

internal object UpdatePolicy {
    private const val ERP_ORIGIN = "https://sevamrita.m.frappe.cloud"
    private const val ASSET_PATH = "/assets/volunteering/android_updates"
    const val MAX_APK_BYTES = 100L * 1024 * 1024

    private fun channel(packageName: String) = when (packageName) {
        "org.sevamrita.mobile" -> "sf-tasks"
        "org.sevamrita.mobile.local" -> "sf-testing"
        else -> throw IllegalArgumentException("Updates are unavailable for this app build.")
    }

    fun feed(packageName: String) = "$ERP_ORIGIN$ASSET_PATH/${channel(packageName)}-update.json"

    fun releasePage(packageName: String) = "$ERP_ORIGIN/sf-tasks-download#${channel(packageName)}"

    fun trustedTransport(url: String): Boolean = runCatching {
        val uri = URI(url)
        uri.scheme == "https" && uri.host == URI(ERP_ORIGIN).host &&
            uri.userInfo == null && uri.port in listOf(-1, 443)
    }.getOrDefault(false)

    fun newerRelease(release: UpdateRelease, packageName: String, sdk: Int, installedVersionCode: Long): UpdateRelease? {
        validate(release, packageName, sdk)
        return release.takeIf { it.versionCode > installedVersionCode }
    }

    fun validate(release: UpdateRelease, packageName: String, sdk: Int) {
        val channel = channel(packageName)
        require(release.packageName == packageName) { "This update belongs to a different app." }
        require(release.versionCode > 0 && release.versionName.matches(Regex("[0-9]+\\.[0-9]+\\.[0-9]+(?:-local)?"))) { "Invalid update version." }
        require(release.minSdk in 26..sdk) { "This update needs a newer Android version." }
        require(release.sizeBytes in 1..MAX_APK_BYTES && release.sha256.matches(Regex("[a-f0-9]{64}"))) { "Invalid update verification details." }
        val app = if (channel == "sf-testing") "SF-testing" else "SF-Tasks"
        val version = release.versionName.removeSuffix("-local")
        require(release.apkUrl == "$ERP_ORIGIN$ASSET_PATH/$app-$version.apk") {
            "Unrecognised update download location."
        }
    }
}
