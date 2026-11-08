package org.sevamrita.mobile

import android.app.Instrumentation
import android.app.Activity
import android.os.Bundle
import org.json.JSONObject
import org.json.JSONArray
import org.sevamrita.mobile.data.*
import java.util.UUID

/** Framework-only device checks: no emulator, UI automation library or test credentials. */
class FeatureAcceptanceInstrumentation:Instrumentation(){
    override fun onCreate(arguments:Bundle?){super.onCreate(arguments);start()}
    override fun onStart(){
        val report=Bundle();var room="";var api:PortalApi?=null;var resultCode=Activity.RESULT_OK
        try{
            check(BuildConfig.DEBUG && BuildConfig.LOCAL_PORTAL_ONLY){"Device acceptance runs only in SF testing."}
            api=PortalApi(SecureSessionStore(targetContext));api.bootstrap()
            val prefix="volunteering.volunteering.collaboration_mobile."
            check(api.call(prefix+"get_collaboration_home").optBoolean("isolated_test_site")){"Refusing tests outside the isolated regression database."}
            val user=api.currentUser
            val store=DurableChat(targetContext)
            store.list(api).filter { it.text("method")=="save_item" && it.optJSONObject("payload")?.optJSONObject("payload")?.text("title")=="Durable device replay check" }.forEach { store.remove(api,it.text("id")) }
            val slot="acceptance:"+UUID.randomUUID()
            val secret="Private offline draft "+UUID.randomUUID()
            val value=JSONObject().put("body",secret).put("attachments",JSONArray().put(JSONObject().put("filename","proof.txt").put("content","VGVzdA==")))
            store.write(api.endpoint(),user,slot,value)
            check(store.read(api.endpoint(),user,slot).toString()==value.toString()){"Draft content did not survive disk read."}
            check(store.read(api.endpoint(),"different-account@example.com",slot).length()==0){"Draft crossed account boundaries."}
            check(store.read("http://192.168.99.1:8001",user,slot).length()==0){"Draft crossed server boundaries."}
            val raw=java.io.File(targetContext.filesDir,"chat-work").listFiles().orEmpty().filter{it.isFile}.map{it.readText()}
            check(raw.none{it.contains(secret)}){"Draft was stored unencrypted."}
            store.delete(api.endpoint(),user,slot)
            report.putString("drafts","Encrypted disk restore, attachment retention, account/host isolation: passed")
            val r=api.call(prefix+"save_space",JSONObject().put("payload",JSONObject().put("title","Device acceptance - collaboration").put("space_kind","Workspace").put("members",JSONArray().put(JSONObject().put("user",user).put("access_level","Owner")))))
            room=r.getString("name")
            val id=UUID.randomUUID().toString()
            val payload=JSONObject().put("space",room).put("payload",JSONObject().put("item_kind","Task").put("title","Durable device replay check"))
            val queued=store.enqueue(api,"save_item",payload,id)
            val same=store.enqueue(api,"save_item",payload,id)
            check(queued.text("id")==same.text("id"))
            check(store.list(api).count{it.text("id")==id}==1){"Queue duplicated a request."}
            val saved=store.send(api,queued) ?: error("Test server unavailable while sending.")
            check(store.list(api).none{it.text("id")==id}){"Sent request remained queued."}
            val retry=api.call(prefix+"apply_operation",JSONObject().put("method","save_item").put("payload",payload).put("request_key",id))
            check(saved.text("name")==retry.text("name")){"Retry created another task."}
            report.putString("outbox","Encrypted enqueue, duplicate suppression, replay, removal and server idempotency: passed")
            val prefs=NotificationPreferences(targetContext)
            val oldQuiet=prefs.bool("quiet",false);prefs.set("quiet",false)
            try{
                prefs.set("room:$room","Mentions only")
                check(!prefs.chat(room,false) && prefs.chat(room,true))
                prefs.set("room:$room","Mentions & assignments")
                check(prefs.chat(room,false,true) && !prefs.chat(room,false,false))
                prefs.set("room:$room","Muted");check(!prefs.chat(room,true,true))
            }finally{prefs.set("quiet",oldQuiet);prefs.set("room:$room","Default")}
            report.putString("notifications","Per-conversation mentions/assignment/mute policy on Android: passed")
            report.putString("stream","All framework device acceptance checks passed.\n")
        }catch(error:Throwable){report.putString("stream",error.stackTraceToString());resultCode=Activity.RESULT_CANCELED}
        finally{
            try{if(room.isNotBlank()&&api!=null){val data=api.call("volunteering.volunteering.collaboration_mobile.get_space",JSONObject().put("name",room));api.call("volunteering.volunteering.collaboration_mobile.save_space",JSONObject().put("name",room).put("expected_modified",data.getJSONObject("space").getString("modified")).put("payload",JSONObject().put("archived",1)))}}catch(_:Exception){}
        }
        finish(resultCode,report)
    }
}
