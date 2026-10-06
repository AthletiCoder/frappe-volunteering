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
    LOCAL("Local emulator", "http://10.0.2.2:8001");

    companion object {
        fun available(): List<Server> = if (BuildConfig.DEBUG) entries else entries.filter { it != LOCAL }
    }
}

/** Session cookies are encrypted with a non-exportable Android Keystore key. */
class SecureSessionStore(context: Context) {
    private val prefs = context.getSharedPreferences("sevamrita_mobile", Context.MODE_PRIVATE)
    private val alias = "sevamrita.session.v1"

    var server: Server
        get() = Server.entries.firstOrNull { it.name == prefs.getString("server", null) }
            ?.takeIf { it != Server.LOCAL || BuildConfig.DEBUG }
            ?: if (BuildConfig.DEBUG) Server.STAGING else Server.PRODUCTION
        set(value) {
            require(value != Server.LOCAL || BuildConfig.DEBUG)
            if (server != value) clear()
            prefs.edit().putString("server", value.name).apply()
        }

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
