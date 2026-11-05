package org.sevamrita.mobile.updates

import android.content.Context
import android.content.Intent
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.FileProvider
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.TimeUnit

/** Deliberately separate from PortalApi: no ERP cookies, credentials or CSRF tokens. */
internal class AppUpdateClient(private val context: Context) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS).readTimeout(45, TimeUnit.SECONDS).callTimeout(5, TimeUnit.MINUTES)
        .followRedirects(true).followSslRedirects(false)
        .addNetworkInterceptor { chain ->
            check(UpdatePolicy.trustedTransport(chain.request().url.toString())) { "The update server redirected to an unrecognised location." }
            chain.proceed(chain.request())
        }.build()
    private val directory get() = File(context.cacheDir, "app-updates")

    fun latest(): UpdateRelease? {
        client.newCall(Request.Builder().url(UpdatePolicy.feed(context.packageName)).header("Cache-Control", "no-cache").build()).execute().use { response ->
            if (response.code == 404) return null // No release has been published for this channel yet.
            check(response.isSuccessful) { "The update service is unavailable. Please try again later." }
            val body = response.body ?: error("The update service returned an empty response.")
            val bytes = body.byteStream().use { input ->
                val output = java.io.ByteArrayOutputStream()
                val buffer = ByteArray(4096)
                while (output.size() <= 64 * 1024) {
                    val count = input.read(buffer, 0, minOf(buffer.size, 64 * 1024 + 1 - output.size()))
                    if (count < 0) break
                    output.write(buffer, 0, count)
                }
                output.toByteArray()
            }
            require(bytes.size <= 64 * 1024) { "Invalid update response." }
            val json = JSONObject(bytes.toString(Charsets.UTF_8))
            val release = UpdateRelease(json.getString("package_name"), json.getLong("version_code"), json.getString("version_name"),
                json.getInt("min_sdk"), json.getLong("size_bytes"), json.getString("sha256"), json.getString("apk_url"),
                json.optString("release_notes").take(4000))
            UpdatePolicy.validate(release, context.packageName, Build.VERSION.SDK_INT)
            return release.takeIf { it.versionCode > installed().versionCode }
        }
    }

    fun download(release: UpdateRelease, progress: (Long) -> Unit): File {
        UpdatePolicy.validate(release, context.packageName, Build.VERSION.SDK_INT)
        client.newCall(Request.Builder().url(release.apkUrl).build()).execute().use { response ->
            check(response.isSuccessful) { "The update could not be downloaded. Please retry." }
            val body = response.body ?: error("The update download was empty.")
            val length = body.contentLength()
            require(length < 0 || length == release.sizeBytes) { "Unexpected update download size." }
            val file = body.byteStream().use { verifiedDownload(it, directory, release, progress) }
            try { verify(file, release); return file } catch (error: Exception) { file.delete(); throw error }
        }
    }

    fun installIntent(file: File, release: UpdateRelease): Intent {
        // Re-check immediately before handing the file to Android, including after returning from Settings.
        verify(file, release)
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.updates", file)
        return Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }

    private fun verify(file: File, release: UpdateRelease) {
        require(file.parentFile?.canonicalFile == directory.canonicalFile && file.length() == release.sizeBytes) { "The downloaded update is unavailable. Please download it again." }
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input -> val buffer = ByteArray(32 * 1024); while (true) { val n = input.read(buffer); if (n < 0) break; digest.update(buffer, 0, n) } }
        require(digest.digest().hex() == release.sha256) { "The update could not be verified. Please download it again." }
        @Suppress("DEPRECATION")
        val archive = context.packageManager.getPackageArchiveInfo(file.absolutePath, signingFlags()) ?: error("The downloaded file is not an Android app.")
        require((archive.applicationInfo?.minSdkVersion ?: Int.MAX_VALUE) <= Build.VERSION.SDK_INT) { "This update needs a newer Android version." }
        UpdatePolicy.verifyIdentity(installed(), identity(archive), release)
    }

    @Suppress("DEPRECATION")
    private fun installed() = identity(context.packageManager.getPackageInfo(context.packageName, signingFlags()))

    @Suppress("DEPRECATION")
    private fun signingFlags() = if (Build.VERSION.SDK_INT >= 28) PackageManager.GET_SIGNING_CERTIFICATES else PackageManager.GET_SIGNATURES

    @Suppress("DEPRECATION")
    private fun identity(info: PackageInfo): UpdateIdentity {
        val signatures = if (Build.VERSION.SDK_INT >= 28) info.signingInfo?.apkContentsSigners else info.signatures
        return UpdateIdentity(info.packageName, if (Build.VERSION.SDK_INT >= 28) info.longVersionCode else info.versionCode.toLong(),
            signatures.orEmpty().map { MessageDigest.getInstance("SHA-256").digest(it.toByteArray()).hex() }.toSet())
    }
}
