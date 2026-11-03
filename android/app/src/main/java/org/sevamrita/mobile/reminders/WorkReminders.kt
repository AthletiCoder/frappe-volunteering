package org.sevamrita.mobile.reminders

import android.Manifest
import android.app.AlarmManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.job.JobInfo
import android.app.job.JobParameters
import android.app.job.JobScheduler
import android.app.job.JobService
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import org.sevamrita.mobile.MainActivity
import org.sevamrita.mobile.R
import org.sevamrita.mobile.data.PortalApi
import org.sevamrita.mobile.data.PortalApiException
import org.sevamrita.mobile.data.PortalSessionRequiredException
import org.sevamrita.mobile.data.SecureSessionStore
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text
import org.sevamrita.mobile.data.runOptionalBackgroundWork
import java.security.MessageDigest
import java.util.concurrent.Executors

/** Native scheduled notifications. Cache is private and bound to this session/server. */
object WorkReminders {
    private const val CHANNEL = "work_reminders"
    private const val PERIODIC_JOB = 8041
    private const val SYNC_JOB = 8042
    private val lock = Any()
    private fun prefs(context: Context) = context.getSharedPreferences("work_reminders", Context.MODE_PRIVATE)
    private fun binding(context: Context): String? {
        val store = SecureSessionStore(context)
        val sid = store.sid() ?: return null
        return MessageDigest.getInstance("SHA-256").digest((store.baseUrl + ":" + sid).toByteArray()).joinToString("") { "%02x".format(it) }
    }

    fun start(context: Context): Boolean = runOptionalBackgroundWork({
        if (binding(context) == null) return@runOptionalBackgroundWork
        val scheduler = context.getSystemService(JobScheduler::class.java)
        scheduler.schedule(JobInfo.Builder(PERIODIC_JOB, ComponentName(context, ReminderSyncJob::class.java))
            .setPeriodic(15 * 60 * 1000L).setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setPersisted(true).build())
        requestSync(context)
    }, { Log.w("WorkReminders", "Background reminders could not be started", it) })

    fun requestSync(context: Context): Boolean = runOptionalBackgroundWork({
        if (binding(context) == null) return@runOptionalBackgroundWork
        context.getSystemService(JobScheduler::class.java).schedule(JobInfo.Builder(SYNC_JOB, ComponentName(context, ReminderSyncJob::class.java))
            .setMinimumLatency(1000).setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).build())
    }, { Log.w("WorkReminders", "Background reminder refresh could not be scheduled", it) })

    private fun clearCache(context: Context) {
        val alarms = context.getSystemService(AlarmManager::class.java)
        cached(context).forEach { alarms.cancel(alarmIntent(context, it.key)) }
        context.getSystemService(NotificationManager::class.java).cancelAll()
        prefs(context).edit().clear().commit()
    }

    fun clear(context: Context) = synchronized(lock) {
        clearCache(context)
        context.getSystemService(JobScheduler::class.java).cancel(PERIODIC_JOB)
        context.getSystemService(JobScheduler::class.java).cancel(SYNC_JOB)
    }

    internal fun sync(context: Context): Boolean {
        val expected = binding(context) ?: run { clear(context); return true }
        return try {
            val api = PortalApi(SecureSessionStore(context))
            api.bootstrap()
            val feed = api.call("volunteering.volunteering.collaboration_mobile.get_reminders")
            synchronized(lock) {
                if (binding(context) != expected) return true
                if (prefs(context).getString("binding", null) != expected) clearCache(context)
                cached(context).forEach { context.getSystemService(AlarmManager::class.java).cancel(alarmIntent(context, it.key)) }
                prefs(context).edit().putString("binding", expected).putString("events", feed.optJSONArray("reminders")?.toString() ?: "[]").commit()
                reschedule(context)
            }
            true
        } catch (error: Exception) {
            if (error is PortalSessionRequiredException || error is PortalApiException && error.status in listOf(401, 403)) {
                synchronized(lock) { if (binding(context) == expected) clear(context) }
                true
            } else false
        }
    }

    private fun cached(context: Context): List<ReminderEvent> = runCatching {
        JSONObject().put("events", JSONArray(prefs(context).getString("events", "[]"))).items("events").map {
            ReminderEvent(it.text("key"), it.text("item"), it.text("space"), it.text("kind"), it.text("title"), it.optLong("timestamp_ms"))
        }
    }.getOrDefault(emptyList())

    fun reschedule(context: Context) = synchronized(lock) {
        if (prefs(context).getString("binding", null) != binding(context) || binding(context) == null) return@synchronized
        val delivered = prefs(context).getStringSet("delivered", emptySet()).orEmpty()
        val manager = context.getSystemService(AlarmManager::class.java)
        pendingReminders(cached(context), delivered, System.currentTimeMillis()).forEach { event ->
            val at = maxOf(event.at, System.currentTimeMillis() + 1500)
            val intent = alarmIntent(context, event.key)
            try {
                if (precise(context)) manager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, intent)
                else manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, intent)
            } catch (_: SecurityException) { manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, intent) }
        }
    }

    fun precise(context: Context): Boolean = Build.VERSION.SDK_INT < 31 || context.getSystemService(AlarmManager::class.java).canScheduleExactAlarms()
    fun notificationsAllowed(context: Context): Boolean = (Build.VERSION.SDK_INT < 33 || context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED) && context.getSystemService(NotificationManager::class.java).areNotificationsEnabled()

    private fun alarmIntent(context: Context, key: String): PendingIntent = PendingIntent.getBroadcast(context, 0,
        Intent(context, WorkReminderReceiver::class.java).setAction("org.sevamrita.mobile.WORK_REMINDER")
            .setData(Uri.parse("sevamrita://reminder/$key")).putExtra("key", key), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)

    internal fun deliver(context: Context, key: String) = synchronized(lock) {
        if (!notificationsAllowed(context) || prefs(context).getString("binding", null) != binding(context) || binding(context) == null) return@synchronized
        val delivered = prefs(context).getStringSet("delivered", emptySet()).orEmpty()
        val event = pendingReminders(cached(context), delivered, System.currentTimeMillis()).firstOrNull { it.key == key } ?: return@synchronized
        if (event.at > System.currentTimeMillis() + 1000) { reschedule(context); return@synchronized }
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL, "Task and tracker reminders", NotificationManager.IMPORTANCE_HIGH))
        val intent = Intent(context, MainActivity::class.java).setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            .setData(Uri.parse("sevamrita://work/${event.item}")).putExtra("work_item", event.item).putExtra("work_room", event.room).putExtra("work_kind", event.kind)
        val open = PendingIntent.getActivity(context, 0, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val generic = Notification.Builder(context, CHANNEL).setSmallIcon(R.drawable.ic_work_reminder).setContentTitle("Sevamrita work reminder").build()
        manager.notify(event.key, 0, Notification.Builder(context, CHANNEL).setSmallIcon(R.drawable.ic_work_reminder)
            .setContentTitle("${event.kind} reminder").setContentText(event.title).setContentIntent(open).setAutoCancel(true)
            .setVisibility(Notification.VISIBILITY_PRIVATE).setPublicVersion(generic).setOnlyAlertOnce(true).build())
        prefs(context).edit().putStringSet("delivered", (delivered + key).toList().takeLast(2000).toSet()).commit()
        requestSync(context)
    }
}

class WorkReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) { WorkReminders.deliver(context, intent.getStringExtra("key").orEmpty()) }
}

class ReminderRestartReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) { WorkReminders.reschedule(context); WorkReminders.start(context) }
}

class ReminderSyncJob : JobService() {
    private val executor = Executors.newSingleThreadExecutor()
    private val running = java.util.Collections.synchronizedSet(mutableSetOf<Int>())
    override fun onStartJob(params: JobParameters): Boolean {
        running.add(params.jobId)
        executor.execute { val success = WorkReminders.sync(applicationContext); if (running.remove(params.jobId)) jobFinished(params, !success) }
        return true
    }
    override fun onStopJob(params: JobParameters): Boolean { running.remove(params.jobId); return true }
    override fun onDestroy() { running.clear(); executor.shutdown(); super.onDestroy() }
}
