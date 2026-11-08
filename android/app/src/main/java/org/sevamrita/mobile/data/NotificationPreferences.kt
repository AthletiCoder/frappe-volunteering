package org.sevamrita.mobile.data

import android.content.Context
import java.time.LocalTime
import java.time.ZonedDateTime

internal fun inQuietHours(now:LocalTime,start:LocalTime,end:LocalTime):Boolean = when {
    start==end -> false
    start<end -> now>=start && now<end
    else -> now>=start || now<end
}
internal class NotificationPreferences(context:Context){
    private val session=SecureSessionStore(context)
    private val prefs=context.getSharedPreferences("chat_notification_preferences",0)
    private val prefix get()=chatCacheIdentity(session.baseUrl,session.rememberedUser())+":"
    fun text(key:String,default:String)=prefs.getString(prefix+key,default) ?: default
    fun bool(key:String,default:Boolean)=prefs.getBoolean(prefix+key,default)
    fun set(key:String,value:String){prefs.edit().putString(prefix+key,value).apply()}
    fun set(key:String,value:Boolean){prefs.edit().putBoolean(prefix+key,value).apply()}
    fun quiet(now:LocalTime=LocalTime.now())=bool("quiet",false) && inQuietHours(now,LocalTime.parse(text("quiet_start","22:00")),LocalTime.parse(text("quiet_end","07:00")))
    fun chat(room:String,mentioned:Boolean,assigned:Boolean=false):Boolean{
        val mode=text("room:$room", "Default").takeUnless{it=="Default"} ?: text("messages","All messages")
        return !quiet() && when(mode){"Muted"->false;"Mentions only"->mentioned;"Mentions & assignments"->mentioned||assigned;else->true}
    }
    fun quietEndsAt():Long {
        val now=ZonedDateTime.now();val end=LocalTime.parse(text("quiet_end","07:00"))
        var finish=now.toLocalDate().atTime(end).atZone(now.zone)
        if(!finish.isAfter(now))finish=finish.plusDays(1)
        return finish.toInstant().toEpochMilli()
    }
    fun reminders()=bool("reminders",true) && !quiet()
}
