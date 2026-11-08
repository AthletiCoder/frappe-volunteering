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
            val postponed = JSONObject(prefs(context).getString("quiet_deferrals", "{}")).optLong(it.text("key"))
            ReminderEvent(it.text("key"), it.text("item"), it.text("space"), it.text("kind"), it.text("title"), maxOf(it.optLong("timestamp_ms"), postponed))
        }
    }.getOrDefault(emptyList())

    private fun deferQuietReminders(context: Context, delivered: Set<String>, now: Long, until: Long) {
        val events = cached(context)
        val prior = JSONObject(prefs(context).getString("quiet_deferrals", "{}"))
        val next = JSONObject()
        events.forEach { if (prior.has(it.key) && it.key !in delivered) next.put(it.key, prior.getLong(it.key)) }
        quietDeferrals(events, delivered, now, until).forEach { (key, at) -> next.put(key, at) }
        prefs(context).edit().putString("quiet_deferrals", next.toString()).commit()
    }

    fun reschedule(context: Context) = synchronized(lock) {
        if (prefs(context).getString("binding", null) != binding(context) || binding(context) == null) return@synchronized
        if (!prefs(context).getBoolean("summary_notifications_v1", false)) {
            val notifications = context.getSystemService(NotificationManager::class.java)
            notifications.activeNotifications.filter { it.notification.channelId == CHANNEL }.forEach { notifications.cancel(it.tag, it.id) }
            cached(context).forEach { context.getSystemService(AlarmManager::class.java).cancel(alarmIntent(context, it.key)) }
            prefs(context).edit().putBoolean("summary_notifications_v1", true).commit()
        }
        val delivered = prefs(context).getStringSet("delivered", emptySet()).orEmpty()
        val manager = context.getSystemService(AlarmManager::class.java)
        manager.cancel(alarmIntent(context, "batch"))
        val options = org.sevamrita.mobile.data.NotificationPreferences(context)
        if (options.bool("reminders", true) && options.quiet()) deferQuietReminders(context, delivered, System.currentTimeMillis(), options.quietEndsAt())
        pendingReminders(cached(context), delivered, System.currentTimeMillis()).firstOrNull()?.let { event ->
            val at = maxOf(event.at, System.currentTimeMillis() + 1500, if(options.quiet())options.quietEndsAt() else 0)
            val intent = alarmIntent(context, "batch")
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
        val now = System.currentTimeMillis()
        val due = dueReminders(cached(context), delivered, now)
        if (due.isEmpty()) { reschedule(context); return@synchronized }
        val options=org.sevamrita.mobile.data.NotificationPreferences(context)
        if(options.bool("reminders",true) && options.quiet()){
            deferQuietReminders(context, delivered, now, options.quietEndsAt())
            val alarm=context.getSystemService(AlarmManager::class.java);val at=options.quietEndsAt()
            try{if(precise(context))alarm.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,at,alarmIntent(context,"batch"))else alarm.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,at,alarmIntent(context,"batch"))}
            catch(_:SecurityException){alarm.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,at,alarmIntent(context,"batch"))}
            return@synchronized
        }
        if (!options.bool("reminders",true)) {
            prefs(context).edit().putStringSet("delivered",(delivered+due.map { it.key }).toList().takeLast(2000).toSet()).commit();reschedule(context);return@synchronized
        }
        val event = due.first()
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL, "Task and tracker reminders", NotificationManager.IMPORTANCE_HIGH))
        // Remove pre-upgrade per-occurrence alerts and alarms. Keep chat alerts untouched.
        manager.activeNotifications.filter { it.notification.channelId == CHANNEL }.forEach { manager.cancel(it.tag, it.id) }
        cached(context).forEach { context.getSystemService(AlarmManager::class.java).cancel(alarmIntent(context, it.key)) }
        val intent = Intent(context, MainActivity::class.java).setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            .setData(Uri.parse("sevamrita://work/reminders"))
        if (due.size == 1) intent.putExtra("work_item", event.item).putExtra("work_room", event.room).putExtra("work_kind", event.kind)
        else intent.putExtra("work_kind", "Reminders")
        val open = PendingIntent.getActivity(context, 0, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val generic = Notification.Builder(context, CHANNEL).setSmallIcon(R.drawable.ic_work_reminder).setContentTitle("Sevamrita work reminder").build()
        val notification = Notification.Builder(context, CHANNEL).setSmallIcon(R.drawable.ic_work_reminder)
            .setContentTitle(if (due.size == 1) "${event.kind} reminder" else "${due.size} work reminders")
            .setContentText(if (due.size == 1) event.title else due.take(3).joinToString(" · ") { it.title })
            .setContentIntent(open).setAutoCancel(true).setVisibility(Notification.VISIBILITY_PRIVATE).setPublicVersion(generic)
            .setOnlyAlertOnce(false)
        if (due.size > 1) notification.setStyle(Notification.InboxStyle().also { style ->
            due.take(6).forEach { style.addLine("${it.kind}: ${it.title}") }
            if (due.size > 6) style.setSummaryText("+${due.size - 6} more · open to view")
        })
        manager.notify("work-reminder-summary", 0, notification.build())
        val keys = pendingReminders(cached(context), delivered, now).filter { it.at <= now + 1000 }.map { it.key }
        prefs(context).edit().putStringSet("delivered", (delivered + keys).toList().takeLast(2000).toSet()).commit()
        reschedule(context)
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
        executor.execute {
            org.sevamrita.mobile.data.DurableChat.schedule(applicationContext)
            val success = WorkReminders.sync(applicationContext)
            org.sevamrita.mobile.push.ChatPush.sync(applicationContext)
            org.sevamrita.mobile.push.ChatPush.drain(applicationContext)
            if (running.remove(params.jobId)) jobFinished(params, !success)
        }
        return true
    }
    override fun onStopJob(params: JobParameters): Boolean { running.remove(params.jobId); return true }
    override fun onDestroy() { running.clear(); executor.shutdown(); super.onDestroy() }
}
