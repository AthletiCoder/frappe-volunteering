package org.sevamrita.mobile.push

import android.app.*
import android.app.job.*
import android.content.*
import android.net.Uri
import android.os.Build
import com.google.android.gms.tasks.Tasks
import com.google.firebase.FirebaseApp
import com.google.firebase.FirebaseOptions
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import org.json.JSONArray
import org.json.JSONObject
import org.sevamrita.mobile.MainActivity
import org.sevamrita.mobile.R
import org.sevamrita.mobile.data.*
import org.sevamrita.mobile.reminders.WorkReminders
import java.security.MessageDigest
import java.util.UUID
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

internal object ChatPush {
    private const val API = "volunteering.volunteering.collaboration_push."
    private const val JOB = 8043
    private const val CHANNEL = "chat_messages"
    private val lock = Any()
    @Volatile var visibleRoom: String = ""
        private set

    fun enterRoom(context: Context, room: String) = synchronized(lock) {
        visibleRoom = room
        if (room.isNotBlank()) context.getSystemService(NotificationManager::class.java).cancel("chat:$room", 0)
    }

    fun leaveRoom(room: String) = synchronized(lock) {
        if (visibleRoom == room) visibleRoom = ""
    }
    private fun prefs(context: Context) = context.getSharedPreferences("chat_push", Context.MODE_PRIVATE)
    private fun binding(context: Context): String? {
        val store = SecureSessionStore(context)
        val sid = store.sid() ?: return null
        return MessageDigest.getInstance("SHA-256").digest((store.baseUrl + ":" + sid).toByteArray()).joinToString("") { "%02x".format(it) }
    }

    fun initialize(context: Context, config: JSONObject? = null): Boolean = synchronized(lock) {
        try {
            val data = config ?: JSONObject(prefs(context).getString("config", "{}").orEmpty())
            if (!data.optBoolean("enabled")) return false
            val options = FirebaseOptions.Builder().setApplicationId(data.getString("app_id")).setApiKey(data.getString("api_key"))
                .setProjectId(data.getString("project_id")).setGcmSenderId(data.getString("sender_id")).build()
            val existing = FirebaseApp.getApps(context).firstOrNull { it.name == FirebaseApp.DEFAULT_APP_NAME }
            if (existing != null && existing.options != options) existing.delete()
            if (FirebaseApp.getApps(context).none { it.name == FirebaseApp.DEFAULT_APP_NAME }) FirebaseApp.initializeApp(context, options)
            FirebaseMessaging.getInstance().isAutoInitEnabled = false
            true
        } catch (_: Exception) { false }
    }

    /** Called on the existing background sync worker; never blocks login or chat rendering. */
    fun sync(context: Context) {
        val expected = binding(context) ?: return
        try {
            synchronized(lock) {
                if (prefs(context).getString("binding", null) != expected) {
                    prefs(context).edit().remove("pending").remove("delivered").remove("binding").commit()
                }
            }
            val api = PortalApi(SecureSessionStore(context)); api.bootstrap()
            val config = api.call(API + "get_push_config", JSONObject().put("package_name", context.packageName))
            if (binding(context) != expected) return
            prefs(context).edit().putString("config", config.toString()).apply()
            if (!initialize(context, config)) return
            val token = Tasks.await(FirebaseMessaging.getInstance().token, 20, TimeUnit.SECONDS)
            if (binding(context) != expected) return
            val installation = prefs(context).getString("installation", null) ?: UUID.randomUUID().toString().also {
                prefs(context).edit().putString("installation", it).commit()
            }
            api.call(API + "register_device", JSONObject().put("installation", installation).put("package_name", context.packageName)
                .put("token", token).put("binding", expected))
            if (binding(context) == expected) prefs(context).edit().putString("binding", expected).apply()
        } catch (_: Exception) { /* Missing config, old backend or offline: retry quietly next sync. */ }
    }

    fun unregister(context: Context, api: PortalApi) {
        try {
            val installation = prefs(context).getString("installation", null)
            if (installation != null) api.call(API + "unregister_device", JSONObject().put("installation", installation).put("package_name", context.packageName))
        } catch (_: Exception) { /* A stale push contains no message text and cannot pass the next session check. */ }
        synchronized(lock) { prefs(context).edit().remove("binding").remove("pending").remove("delivered").commit() }
        context.getSystemService(NotificationManager::class.java).activeNotifications.filter { it.notification.channelId == CHANNEL }
            .forEach { context.getSystemService(NotificationManager::class.java).cancel(it.tag, it.id) }
        context.getSystemService(JobScheduler::class.java).cancel(JOB)
    }

    fun receive(context: Context, entry: String, expected: String) = synchronized(lock) {
        if (!validPush(entry, expected, binding(context), prefs(context).getString("binding", null))) return@synchronized
        val pending = JSONArray(prefs(context).getString("pending", "[]"))
        if ((0 until pending.length()).none { pending.optString(it) == entry }) pending.put(entry)
        val bounded = JSONArray((maxOf(0, pending.length() - 100) until pending.length()).map { pending.getString(it) })
        prefs(context).edit().putString("pending", bounded.toString()).commit()
        val scheduler = context.getSystemService(JobScheduler::class.java)
        val job = JobInfo.Builder(JOB, ComponentName(context, ChatPushJob::class.java)).setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
        try {
            if (Build.VERSION.SDK_INT >= 31) job.setExpedited(true) else job.setMinimumLatency(0)
            if (scheduler.schedule(job.build()) == JobScheduler.RESULT_FAILURE) scheduler.schedule(JobInfo.Builder(JOB,
                ComponentName(context, ChatPushJob::class.java)).setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setMinimumLatency(0).build())
        } catch (_: Exception) { WorkReminders.requestSync(context) }
    }

    fun drain(context: Context): Boolean {
        val expected = binding(context) ?: return true
        val pending = synchronized(lock) { JSONArray(prefs(context).getString("pending", "[]")) }
        if (pending.length() == 0) return true
        return try {
            val api = PortalApi(SecureSessionStore(context)); api.bootstrap()
            for (i in 0 until pending.length()) {
                val entry = pending.getString(i)
                if (binding(context) != expected) return true
                val delivered = prefs(context).getStringSet("delivered", emptySet()).orEmpty()
                if (entry !in delivered) {
                    val message = try { api.call(API + "get_notification_entry", JSONObject().put("name", entry)) }
                    catch (error: PortalApiException) { if (error.status == 404) JSONObject().put("notify", false) else throw error }
                    if (message.optBoolean("notify")) api.call("volunteering.volunteering.collaboration_mobile.mark_delivered", JSONObject()
                        .put("space", message.text("space")).put("entry", entry))
                    synchronized(lock) {
                        if (binding(context) != expected) return true
                        // The periodic sync and a push job may both fetch this entry. Recheck under the same lock used to record delivery.
                        val deliveredNow = prefs(context).getStringSet("delivered", emptySet()).orEmpty()
                        if (entry !in deliveredNow) {
                            if (message.optBoolean("notify") && visibleRoom != message.text("space")) show(context, message)
                            prefs(context).edit().putStringSet("delivered", (deliveredNow + entry).toList().takeLast(1000).toSet()).commit()
                        }
                    }
                }
                synchronized(lock) {
                    val current = JSONArray(prefs(context).getString("pending", "[]"))
                    prefs(context).edit().putString("pending", JSONArray((0 until current.length()).map { current.getString(it) }.filter { it != entry }).toString()).commit()
                }
            }
            true
        } catch (error: Exception) {
            if (error is PortalSessionRequiredException || error is PortalApiException && error.status in listOf(401, 403)) {
                synchronized(lock) { if (binding(context) == expected) prefs(context).edit().remove("pending").remove("binding").commit() }
                true
            } else false
        }
    }

    private fun show(context: Context, message: JSONObject) {
        if (!WorkReminders.notificationsAllowed(context)) return
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL, "Chat messages", NotificationManager.IMPORTANCE_HIGH))
        val room = message.text("space")
        val intent = Intent(context, MainActivity::class.java).setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            .setData(Uri.parse("sevamrita://chat/$room")).putExtra("work_room", room).putExtra("work_kind", "Chat")
        val open = PendingIntent.getActivity(context, 0, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val generic = Notification.Builder(context, CHANNEL).setSmallIcon(R.drawable.ic_work_reminder).setContentTitle("New chat message").build()
        manager.notify("chat:$room", 0, Notification.Builder(context, CHANNEL).setSmallIcon(R.drawable.ic_work_reminder)
            .setContentTitle(message.text("title")).setContentText("${message.text("sender")}: ${message.text("body")}")
            .setStyle(Notification.BigTextStyle().bigText("${message.text("sender")}: ${message.text("body")}"))
            .setContentIntent(open).setAutoCancel(true).setVisibility(Notification.VISIBILITY_PRIVATE).setPublicVersion(generic).build())
    }
}

internal fun validPush(entry: String, remoteBinding: String, sessionBinding: String?, registeredBinding: String?): Boolean =
    entry.matches(Regex("[a-zA-Z0-9_-]{1,140}")) && remoteBinding.length == 64 && remoteBinding == sessionBinding && remoteBinding == registeredBinding

class TasksApplication : Application() {
    override fun onCreate() { super.onCreate(); ChatPush.initialize(this) }
}

class ChatMessagingService : FirebaseMessagingService() {
    override fun onNewToken(token: String) { WorkReminders.requestSync(applicationContext) }
    override fun onMessageReceived(message: RemoteMessage) {
        ChatPush.receive(applicationContext, message.data["entry"].orEmpty(), message.data["binding"].orEmpty())
    }
    override fun onDeletedMessages() { WorkReminders.requestSync(applicationContext) }
}

class ChatPushJob : JobService() {
    private val executor = Executors.newSingleThreadExecutor()
    @Volatile private var stopped = false
    override fun onStartJob(params: JobParameters): Boolean {
        stopped = false
        executor.execute { val success = ChatPush.drain(applicationContext); if (!stopped) jobFinished(params, !success) }
        return true
    }
    override fun onStopJob(params: JobParameters): Boolean { stopped = true; return true }
    override fun onDestroy() { stopped = true; executor.shutdown(); super.onDestroy() }
}
