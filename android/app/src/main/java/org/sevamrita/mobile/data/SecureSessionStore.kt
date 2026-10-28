package org.sevamrita.mobile.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.sevamrita.mobile.BuildConfig
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

enum class Server(val label: String, val url: String) {
    PRODUCTION("Production", "https://sevamrita.m.frappe.cloud"),
    STAGING("Staging", "https://sevamrita-staging.m.frappe.cloud"),
    LOCAL("Local Wi-Fi / emulator", "http://10.0.2.2:8001");

    companion object {
        fun available(): List<Server> = if (BuildConfig.DEBUG) listOf(LOCAL, PRODUCTION, STAGING) else listOf(PRODUCTION)
    }
}

/** Session cookies are encrypted with a non-exportable Android Keystore key. */
class SecureSessionStore(context: Context) {
    private val prefs = context.getSharedPreferences("sevamrita_mobile", Context.MODE_PRIVATE)
    private val alias = "sevamrita.session.v1"

    var server: Server
        get() = Server.available().firstOrNull { it.name == prefs.getString("server", null) }
            ?: if (BuildConfig.DEBUG) Server.LOCAL else Server.PRODUCTION
        set(value) {
            require(value != Server.LOCAL || BuildConfig.DEBUG)
            if (server != value) clear()
            prefs.edit().putString("server", value.name).apply()
        }

    /** Debug-only LAN endpoint. Never copied into release builds or used for production. */
    var localAddress: String
        get() = prefs.getString("local_address", "10.0.2.2") ?: "10.0.2.2"
        set(value) {
            require(BuildConfig.DEBUG) { "Local HTTP is only available in debug builds." }
            val address = value.trim()
            require(isPrivateIpv4(address)) { "Enter your laptop's private Wi-Fi IPv4 address." }
            if (address != localAddress) clear()
            prefs.edit().putString("local_address", address).apply()
        }

    val baseUrl: String
        get() = if (server == Server.LOCAL) "http://$localAddress:8001" else server.url

    fun saveSid(sid: String) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val data = Base64.encodeToString(cipher.doFinal(sid.toByteArray(Charsets.UTF_8)), Base64.NO_WRAP)
        val iv = Base64.encodeToString(cipher.iv, Base64.NO_WRAP)
        prefs.edit().putString("sid", data).putString("iv", iv).apply()
    }

    fun sid(): String? = try {
        val data = prefs.getString("sid", null) ?: return null
        val iv = prefs.getString("iv", null) ?: return null
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, Base64.decode(iv, Base64.NO_WRAP)))
        String(cipher.doFinal(Base64.decode(data, Base64.NO_WRAP)), Charsets.UTF_8)
    } catch (_: Exception) {
        clear()
        null
    }

    fun clear() { prefs.edit().remove("sid").remove("iv").apply() }

    private fun key(): SecretKey {
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (keyStore.getKey(alias, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(
            KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build()
        )
        return generator.generateKey()
    }
}

/** Only RFC 1918 LAN addresses (and the Android emulator's host alias) are accepted. */
internal fun isPrivateIpv4(value: String): Boolean {
    val octets = value.split('.')
    if (octets.size != 4 || octets.any { it.isEmpty() || it.length > 3 || it.any { c -> !c.isDigit() } }) return false
    val numbers = octets.map { it.toIntOrNull() ?: return false }
    if (numbers.any { it !in 0..255 }) return false
    return numbers[0] == 10 || (numbers[0] == 172 && numbers[1] in 16..31) ||
        (numbers[0] == 192 && numbers[1] == 168)
}
