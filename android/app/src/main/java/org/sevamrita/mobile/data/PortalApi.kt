package org.sevamrita.mobile.data

import okhttp3.FormBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.MediaType.Companion.toMediaType
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class PortalApi(private val session: SecureSessionStore) {
    private val client = OkHttpClient.Builder()
        .followRedirects(false)
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(45, TimeUnit.SECONDS)
        .build()
    private var csrf: String? = null
    var currentUser: String = ""
        private set

    fun hasSession() = session.sid() != null
    fun server() = session.server
    fun setServer(server: Server) { session.server = server; csrf = null }

    fun login(username: String, password: String) {
        val body = FormBody.Builder().add("usr", username).add("pwd", password).build()
        val response = client.newCall(
            Request.Builder().url("${session.server.url}/api/method/login").post(body).build()
        ).execute()
        response.use {
            val parsed = parse(it.code, it.body?.string().orEmpty())
            val cookies = it.headers.values("Set-Cookie")
            val sid = cookies.firstNotNullOfOrNull { cookie ->
                Regex("(?:^|;\\s*)sid=([^;]+)").find(cookie)?.groupValues?.get(1)
            } ?: throw IOException("Login did not create a session. Please check the account and server.")
            if (parsed.optString("message") != "Logged In") throw IOException("Unable to sign in.")
            session.saveSid(sid)
        }
        try { bootstrap() } catch (error: Exception) { logoutLocal(); throw error }
    }

    fun bootstrap() {
        val data = call("volunteering.volunteering.mobile_session.get_mobile_session", get = true)
        currentUser = data.optString("user")
        csrf = data.optString("csrf_token").takeIf { it.isNotBlank() }
            ?: throw IOException("The server did not provide a secure session token.")
    }

    fun logoutLocal() { csrf = null; currentUser = ""; session.clear() }

    fun logout() {
        try { if (session.sid() != null && csrf != null) call("logout") }
        catch (_: Exception) { /* Expired/offline sessions must still be removed from the device. */ }
        finally { logoutLocal() }
    }

    fun call(method: String, args: JSONObject = JSONObject(), get: Boolean = false): JSONObject {
        require(method.matches(Regex("[A-Za-z_][A-Za-z0-9_.]*")))
        val sid = session.sid() ?: throw IOException("Please sign in again.")
        val url = "${session.server.url}/api/method/$method"
        val builder = Request.Builder().url(url).header("Cookie", "sid=$sid")
            .header("Accept", "application/json")
        if (get) {
            // GET is used only for parameterless, read-only endpoints.
            require(args.length() == 0)
            builder.get()
        } else {
            val token = csrf ?: throw IOException("Your session needs to be refreshed. Please sign in again.")
            builder.header("X-Frappe-CSRF-Token", token)
                .post(args.toString().toRequestBody("application/json; charset=utf-8".toMediaType()))
        }
        client.newCall(builder.build()).execute().use { response ->
            val parsed = parse(response.code, response.body?.string().orEmpty())
            val message = parsed.opt("message")
            return if (message is JSONObject) message else JSONObject().put("value", message)
        }
    }

    fun privateFile(path: String): ByteArray {
        require(path.startsWith("/private/files/") && !path.contains("..") && !path.contains('?')) {
            "Only private receipt attachments can be opened here."
        }
        val sid = session.sid() ?: throw IOException("Please sign in again.")
        client.newCall(Request.Builder().url(session.server.url + path).header("Cookie", "sid=$sid").get().build())
            .execute().use { response ->
                if (!response.isSuccessful) throw IOException("Receipt cannot be opened (${response.code}).")
                val body = response.body ?: throw IOException("Receipt is empty.")
                if (body.contentLength() > 10 * 1024 * 1024) throw IOException("Receipt is too large for the mobile viewer.")
                val bytes = body.byteStream().use { input ->
                    val output = java.io.ByteArrayOutputStream()
                    val buffer = ByteArray(8192)
                    while (true) {
                        val count = input.read(buffer)
                        if (count < 0) break
                        if (output.size() + count > 10 * 1024 * 1024) throw IOException("Receipt is too large for the mobile viewer.")
                        output.write(buffer, 0, count)
                    }
                    output.toByteArray()
                }
                if (bytes.isEmpty()) throw IOException("Receipt is empty.")
                return bytes
            }
    }

    private fun parse(code: Int, body: String): JSONObject {
        val json = try { JSONObject(body) } catch (_: Exception) {
            throw IOException(if (code in 300..399) "Your session has expired. Please sign in again." else "Server returned an unreadable response ($code).")
        }
        if (code !in 200..299 || json.has("exc")) {
            val messages = json.optString("_server_messages")
            val detail = try {
                val first = JSONArray(messages).optString(0)
                JSONObject(first).optString("message")
            } catch (_: Exception) { "" }
            throw IOException(detail.ifBlank { json.optString("message").ifBlank { "Request failed ($code)." } })
        }
        return json
    }
}

fun JSONObject.text(key: String): String = optString(key).takeUnless { it == "null" } ?: ""
fun JSONObject.items(key: String): List<JSONObject> = (optJSONArray(key) ?: JSONArray()).let { array ->
    (0 until array.length()).mapNotNull { array.optJSONObject(it) }
}
fun JSONObject.display(key: String, fallback: String = "—"): String = text(key).ifBlank { fallback }
