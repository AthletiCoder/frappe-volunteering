package org.sevamrita.mobile.updates

import android.content.Context
import android.os.Build
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import org.sevamrita.mobile.BuildConfig
import java.util.concurrent.TimeUnit

internal class NoPublishedUpdateException : Exception()

/** Deliberately separate from PortalApi: no ERP cookies, credentials or CSRF tokens. */
internal class AppUpdateClient(private val context: Context) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS).readTimeout(15, TimeUnit.SECONDS).callTimeout(20, TimeUnit.SECONDS)
        .followRedirects(true).followSslRedirects(false)
        .addNetworkInterceptor { chain ->
            check(UpdatePolicy.trustedTransport(chain.request().url.toString())) { "The update server redirected to an unrecognised location." }
            chain.proceed(chain.request())
        }.build()

    fun latest(): UpdateRelease? {
        client.newCall(Request.Builder().url(UpdatePolicy.feed(context.packageName)).header("Cache-Control", "no-cache").build()).execute().use { response ->
            if (response.code == 404) throw NoPublishedUpdateException()
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
            return UpdatePolicy.newerRelease(
                release, context.packageName, Build.VERSION.SDK_INT, BuildConfig.VERSION_CODE.toLong()
            )
        }
    }
}
