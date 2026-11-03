package org.sevamrita.mobile.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.AtomicFile
import android.util.Base64
import org.json.JSONObject
import java.io.File
import java.security.KeyStore
import java.security.MessageDigest
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

internal fun chatCacheIdentity(endpoint: String, user: String): String = MessageDigest.getInstance("SHA-256")
    .digest((endpoint + "\n" + user).toByteArray()).joinToString("") { "%02x".format(it) }

/** Private, encrypted UI snapshots. Never caches passwords or attachment bytes. */
internal class ChatSnapshotCache(context: Context) {
    private val directory = File(context.filesDir, "chat-snapshots")
    private val alias = "sevamrita.chat.snapshots.v1"
    private val lock = Any()
    fun read(endpoint: String, user: String): JSONObject? = synchronized(lock) {
        if (user.isBlank()) return@synchronized null
        runCatching {
            val file = File(directory, chatCacheIdentity(endpoint, user))
            if (!file.exists() || file.length() > 8 * 1024 * 1024) return@synchronized null
            val envelope = JSONObject(AtomicFile(file).readFully().toString(Charsets.UTF_8))
            val key = key(false) ?: return@synchronized null
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, Base64.decode(envelope.text("iv"), Base64.NO_WRAP)))
            JSONObject(cipher.doFinal(Base64.decode(envelope.text("data"), Base64.NO_WRAP)).toString(Charsets.UTF_8))
                .takeIf { it.text("user") == user && it.text("endpoint") == endpoint }
        }.getOrNull()
    }

    fun write(endpoint: String, user: String, snapshot: JSONObject, stillCurrent: () -> Boolean = { true }) = synchronized(lock) {
        if (user.isBlank() || !stillCurrent()) return@synchronized
        runCatching {
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.ENCRYPT_MODE, key(true))
            val content = JSONObject(snapshot.toString()).put("user", user).put("endpoint", endpoint).toString().toByteArray()
            if (content.size > 5 * 1024 * 1024) return@synchronized
            val data = JSONObject().put("iv", Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
                .put("data", Base64.encodeToString(cipher.doFinal(content), Base64.NO_WRAP)).toString().toByteArray()
            if (!stillCurrent()) return@synchronized
            directory.mkdirs()
            val atomic = AtomicFile(File(directory, chatCacheIdentity(endpoint, user)))
            val output = atomic.startWrite()
            try { output.write(data); atomic.finishWrite(output) } catch (error: Exception) { atomic.failWrite(output); throw error }
        }
        Unit
    }

    fun clear() = synchronized(lock) { directory.deleteRecursively(); Unit }
    private fun key(create: Boolean): SecretKey? {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(alias, null) as? SecretKey)?.let { return it }
        if (!create) return null
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }
}
