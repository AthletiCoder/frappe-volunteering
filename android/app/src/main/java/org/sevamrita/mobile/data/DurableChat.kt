package org.sevamrita.mobile.data

import android.content.Context
import android.app.job.*
import android.content.ComponentName
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.AtomicFile
import android.util.Base64
import org.json.JSONObject
import org.json.JSONArray
import java.io.File
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import java.util.UUID
import java.util.concurrent.Executors

/** Encrypted private drafts/outbox. Never copied across accounts or ERP hosts. */
internal class DurableChat(private val context: Context) {
    private val folder=File(context.filesDir,"chat-work")
    private fun file(endpoint:String,user:String,slot:String)=File(folder,chatCacheIdentity(endpoint,user+"\n"+slot))
    private fun key(): SecretKey {
        val store=KeyStore.getInstance("AndroidKeyStore").apply{load(null)}
        (store.getKey("sf.chat.work.v1",null) as? SecretKey)?.let{return it}
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore").apply{
            init(KeyGenParameterSpec.Builder("sf.chat.work.v1",KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }
    fun read(endpoint:String,user:String,slot:String):JSONObject = synchronized(lock) {
        val f=file(endpoint,user,slot)
        if(!f.exists())return@synchronized JSONObject()
        val blob=JSONObject(AtomicFile(f).readFully().toString(Charsets.UTF_8))
        val cipher=Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE,key(),GCMParameterSpec(128,Base64.decode(blob.getString("iv"),Base64.NO_WRAP)))
        val data=JSONObject(cipher.doFinal(Base64.decode(blob.getString("data"),Base64.NO_WRAP)).toString(Charsets.UTF_8))
        require(data.text("user")==user && data.text("endpoint")==endpoint){"Saved work belongs to another account."}
        data.getJSONObject("value")
    }
    fun write(endpoint:String,user:String,slot:String,value:JSONObject) = synchronized(lock) {
        require(user.isNotBlank())
        val bytes=JSONObject().put("endpoint",endpoint).put("user",user).put("value",value).toString().toByteArray()
        require(bytes.size<=75*1024*1024){"Saved work is too large. Remove some attachments."}
        val cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key())
        val out=JSONObject().put("iv",Base64.encodeToString(cipher.iv,Base64.NO_WRAP)).put("data",Base64.encodeToString(cipher.doFinal(bytes),Base64.NO_WRAP)).toString().toByteArray()
        folder.mkdirs();val atomic=AtomicFile(file(endpoint,user,slot));val stream=atomic.startWrite()
        try{stream.write(out);atomic.finishWrite(stream)}catch(e:Exception){atomic.failWrite(stream);throw e}
    }
    fun delete(endpoint:String,user:String,slot:String) = synchronized(lock){AtomicFile(file(endpoint,user,slot)).delete()}
    fun list(api:PortalApi)=read(api.endpoint(),api.rememberedUser(),"outbox").items("rows")
    fun enqueue(api:PortalApi,method:String,payload:JSONObject,id:String):JSONObject = synchronized(lock){
        val rows=list(api).toMutableList()
        val existing=rows.firstOrNull{it.text("id")==id}
        if(existing!=null){require(existing.text("method")==method && existing.getJSONObject("payload").toString()==payload.toString()){"This queued request has changed. Use a new form."};return@synchronized existing}
        require(rows.size<20){"Outbox is full. Send or cancel queued work first."}
        val row=JSONObject().put("id",id).put("method",method).put("payload",payload).put("status","Waiting").put("created",System.currentTimeMillis())
        rows.add(row);write(api.endpoint(),api.rememberedUser(),"outbox",JSONObject().put("rows",JSONArray(rows)))
        row
    }
    fun remove(api:PortalApi,id:String) = synchronized(lock){write(api.endpoint(),api.rememberedUser(),"outbox",JSONObject().put("rows",JSONArray(list(api).filter{it.text("id")!=id})))}
    fun retry(api:PortalApi,id:String) = synchronized(lock){
        val rows=list(api);rows.firstOrNull{it.text("id")==id}?.put("status","Waiting")?.put("error","")
        write(api.endpoint(),api.rememberedUser(),"outbox",JSONObject().put("rows",JSONArray(rows)))
    }
    fun send(api:PortalApi,row:JSONObject):JSONObject? = synchronized(sendLock){
        // Recheck the signed-in identity before and after the network request.
        val session=SecureSessionStore(context);val identity=chatCacheIdentity(api.endpoint(),api.rememberedUser());val sid=session.sid()
        require(identity==chatCacheIdentity(session.baseUrl,session.rememberedUser()) && sid!=null){"Sign in to send queued work."}
        try{
            val result=api.call("volunteering.volunteering.collaboration_mobile.apply_operation",JSONObject().put("method",row.text("method")).put("payload",row.getJSONObject("payload")).put("request_key",row.text("id")))
            if(SecureSessionStore(context).sid()==sid)remove(api,row.text("id"))
            result
        }catch(error:Exception){
            val permanent=error is PortalApiException && error.status in listOf(400,403,404,409,417,422) || error !is java.io.IOException
            val rows=list(api);rows.firstOrNull{it.text("id")==row.text("id")}?.put("status",if(permanent)"Needs attention" else "Waiting")?.put("error",error.message.orEmpty().take(500))
            write(api.endpoint(),api.rememberedUser(),"outbox",JSONObject().put("rows",JSONArray(rows)))
            if(permanent || error is PortalSessionRequiredException || error is PortalApiException && error.status==401)throw error
            null
        }
    }
    companion object { val lock=Any();private val sendLock=Any();const val JOB=8088
        fun schedule(context:Context){context.getSystemService(JobScheduler::class.java).schedule(JobInfo.Builder(JOB,ComponentName(context,ChatOutboxJob::class.java)).setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setMinimumLatency(1000).build())}
    }
}
class ChatOutboxJob:JobService(){
    private val executor=Executors.newSingleThreadExecutor()
    @Volatile private var stopped=false
    override fun onStartJob(params:JobParameters):Boolean{stopped=false;executor.execute{
        val okay=runCatching{
            val api=PortalApi(SecureSessionStore(this));if(!api.hasSession())return@runCatching true
            api.bootstrap();val store=DurableChat(this)
            for(row in store.list(api).filter{it.text("status")=="Waiting"}){if(stopped)break;if(store.send(api,row)==null)return@runCatching false}
            true
        }.getOrDefault(false)
        if(!stopped)jobFinished(params,!okay)
    };return true}
    override fun onStopJob(params:JobParameters):Boolean{stopped=true;return true}
    override fun onDestroy(){stopped=true;executor.shutdown();super.onDestroy()}
}
