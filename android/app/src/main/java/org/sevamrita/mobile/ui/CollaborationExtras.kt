package org.sevamrita.mobile.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AlternateEmail
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.*
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.LocalContext
import org.json.JSONObject
import org.json.JSONArray
import org.sevamrita.mobile.data.*
import java.time.LocalTime
import java.util.UUID

private val tagPattern=Regex("@\\[([^\\]\\n]{1,160})]\\(([^)\\s]{1,140})\\)")
internal fun mentionLabel(body:String)=tagPattern.replace(body){"@"+it.groupValues[1]}
internal class MentionVisualTransformation:VisualTransformation {
    override fun filter(text:AnnotatedString):TransformedText {
        val source=text.text;val output=StringBuilder();val forward=IntArray(source.length+1);val reverse=mutableListOf(0);var at=0
        for(match in tagPattern.findAll(source)){
            while(at<match.range.first){forward[at]=output.length;output.append(source[at++]);reverse.add(at)}
            val start=at;val label="@"+match.groupValues[1]
            label.forEachIndexed{i,ch->output.append(ch);reverse.add((start+i+1).coerceAtMost(match.range.last+1))}
            for(i in start..match.range.last)forward[i]=(output.length-label.length+(i-start).coerceAtMost(label.length))
            at=match.range.last+1;reverse[reverse.lastIndex]=at
        }
        while(at<source.length){forward[at]=output.length;output.append(source[at++]);reverse.add(at)}
        forward[source.length]=output.length
        return TransformedText(AnnotatedString(output.toString()),object:OffsetMapping{
            override fun originalToTransformed(offset:Int)=forward[offset.coerceIn(0,source.length)]
            override fun transformedToOriginal(offset:Int)=reverse[offset.coerceIn(0,reverse.lastIndex)]
        })
    }
}
internal fun canReadCachedChat(hasCache: Boolean, error: Exception): Boolean =
    hasCache && error is java.io.IOException && error !is PortalApiException && error !is PortalSessionRequiredException

internal fun syncMentionValue(current: TextFieldValue, external: String): TextFieldValue =
    if (current.text == external) current else TextFieldValue(external, androidx.compose.ui.text.TextRange(external.length))

@Composable internal fun rememberMentionValue(value: String): MutableState<TextFieldValue> {
    val field = rememberSaveable(stateSaver = TextFieldValue.Saver) { mutableStateOf(TextFieldValue(value, androidx.compose.ui.text.TextRange(value.length))) }
    val next = syncMentionValue(field.value, value)
    if (next != field.value) field.value = next
    return field
}

@Composable internal fun MentionSuggestions(body:String,members:List<JSONObject>,change:(String)->Unit){
    val match=Regex("(?:^|\\s)@([^@\\n\\[\\]()]{0,50})$").find(body)
    if(match!=null){
        val query=match.groupValues[1]
        val candidates=members.filter{it.text("full_name").contains(query,true) || it.text("user").contains(query,true)}.take(5)
        Surface(color=MaterialTheme.colorScheme.surface,tonalElevation=3.dp){Column(Modifier.fillMaxWidth()){
            candidates.forEach{person->TextButton(onClick={
                val start=body.lastIndexOf('@');change(body.take(start)+"@[${person.text("full_name")}](${person.text("user")}) ")
            },modifier=Modifier.fillMaxWidth()){Text(person.text("full_name"))}}
        }}
    }
}
@Composable internal fun MentionInput(label:String,value:String,members:List<JSONObject>,enabled:Boolean=true,change:(String)->Unit){
    val field = rememberMentionValue(value)
    OutlinedTextField(field.value,{field.value=it;change(it.text)},label={Text(label)},modifier=Modifier.fillMaxWidth(),minLines=2,maxLines=5,enabled=enabled,
        visualTransformation=MentionVisualTransformation(),trailingIcon={IconButton(onClick={change(value+if(value.endsWith(" ")||value.isBlank())"@" else " @")},enabled=enabled){Icon(Icons.Default.AlternateEmail,"Mention a member")}})
    MentionSuggestions(value,members,change)
}

@Composable internal fun SubtaskEditor(config:JSONObject,members:List<JSONObject>,change:(JSONObject)->Unit){
    val rows=config.items("subtasks")
    fun set(next:List<JSONObject>)=change(JSONObject(config.toString()).put("subtasks",JSONArray(next)))
    EditorDisclosure("Subtasks","${rows.size} subtasks",rows.isNotEmpty()){
        rows.forEachIndexed{i,row->
            EditorSection("Subtask ${i+1}"){
                fun field(key:String,value:String){set(rows.mapIndexed{n,x->if(i==n)JSONObject(x.toString()).put(key,value) else x})}
                EditorText("Subtask title",row.text("title")){field("title",it)}
                EditorSelect("Responsible person",row.text("assignee"),listOf("" to "Parent task owner")+members.filter{it.text("access_level")!="Viewer"}.map{it.text("user") to it.text("full_name")}){field("assignee",it)}
                EditorDate("Subtask deadline",row.text("deadline")){field("deadline",it)}
                TextButton(onClick={set(rows.filterIndexed{n,_->n!=i})}){Text("Remove subtask")}
            }
        }
        OutlinedButton(onClick={set(rows+JSONObject().put("id",UUID.randomUUID().toString()).put("title","").put("status","Open"))},enabled=rows.size<100){Text("Add subtask")}
    }
}
@Composable internal fun SubtaskList(task:JSONObject,members:List<JSONObject>,user:String,busy:Boolean,update:(String,String)->Unit){
    val rows=task.optJSONObject("item_data")?.items("subtasks").orEmpty()
    EditorSection("Subtasks (${rows.count{it.text("status")=="Completed"}}/${rows.size})"){
        if(rows.isEmpty())Text("No subtasks. Use Edit to add smaller steps.",color=MaterialTheme.colorScheme.onSurfaceVariant)
        rows.forEach{row->
            val can=task.text("status") in listOf("Open","In progress") && (task.optBoolean("can_edit")||row.text("assignee")==user)
            HorizontalDivider()
            Text(row.text("title"),fontWeight=FontWeight.SemiBold)
            val who=members.firstOrNull{it.text("user")==row.text("assignee")}?.text("full_name") ?: task.text("assignee_name")
            Text(listOfNotNull(who.ifBlank{null},row.text("deadline").takeIf{it.isNotBlank()}?.let{"Due $it"}).joinToString(" · "),style=MaterialTheme.typography.bodySmall)
            if(can && !busy)EditorSelect("Subtask status",row.text("status"),listOf("Open","In progress","Completed").map{it to it}){update(row.text("id"),it)}
            else Text(row.text("status"),color=MaterialTheme.colorScheme.primary)
        }
    }
}

@Composable internal fun TrackerComments(name:String,members:List<JSONObject>,model:PortalViewModel){
    var rows by remember(name){mutableStateOf(emptyList<JSONObject>())};var cursor by remember(name){mutableStateOf("")}
    var allowed by remember(name){mutableStateOf(false)};var loading by remember(name){mutableStateOf(false)}
    val slot="comments:$name"
    val initial=remember(name){model.savedDraft(slot)}
    var body by remember(name){mutableStateOf(initial.text("body"))};var key by remember(name){mutableStateOf(initial.text("key").ifBlank{UUID.randomUUID().toString()})}
    fun load(before:String=""){loading=true;model.featureCall("get_comments",JSONObject().put("name",name).put("before",before.ifBlank{null})){
        if(it.optBoolean("_error")){loading=false;return@featureCall}
        rows=(if(before.isBlank())emptyList() else rows)+it.items("comments");cursor=it.text("next_cursor");allowed=it.optBoolean("can_comment");loading=false
    }}
    LaunchedEffect(name){load()}
    LaunchedEffect(body,key){kotlinx.coroutines.delay(250);model.saveDraft(slot,JSONObject().put("body",body).put("key",key))}
    Column(Modifier.fillMaxWidth(),verticalArrangement=Arrangement.spacedBy(12.dp)){
        if(allowed){MentionInput("Comment on this tracker",body,members, !model.state.value.busy){body=it}
            Button(onClick={model.chatCall("post_comment",JSONObject().put("name",name).put("body",body).put("request_key",key)){
                body="";key=UUID.randomUUID().toString();model.forgetDraft(slot);if(!it.optBoolean("queued"))load()
            }},enabled=body.isNotBlank()&&!model.state.value.busy){Text("Post comment")}}
        else Text("Comments from conversation members",color=MaterialTheme.colorScheme.onSurfaceVariant)
        if(rows.isEmpty()){Text(if(loading)"Loading comments…" else "No comments loaded.");if(!loading)TextButton(onClick={load()}){Text("Refresh comments")}}
        rows.forEach{row->Surface(shape=MaterialTheme.shapes.medium,color=MaterialTheme.colorScheme.surfaceVariant){Column(Modifier.padding(14.dp),verticalArrangement=Arrangement.spacedBy(5.dp)){
            Text(row.text("author_name"),fontWeight=FontWeight.SemiBold);Text(row.text("body"));Text(row.text("creation").take(16),style=MaterialTheme.typography.labelSmall)
            if(row.optBoolean("can_remove"))TextButton(onClick={model.chatCall("edit_entry",JSONObject().put("name",row.text("name")).put("expected_modified",row.text("modified")).put("remove",true)){load()}}){Text("Remove")}
        }}}
        if(cursor.isNotBlank())OutlinedButton(onClick={load(cursor)},enabled=!loading){Text("Older comments")}
    }
}

@Composable internal fun CollaborationUtilityScreen(state:PortalState,model:PortalViewModel){
    val route=state.chatNavigation.current.view
    val context=LocalContext.current
    when(route){
        ChatView.SETTINGS->{
            val prefs=remember(state.user){NotificationPreferences(context)};var revision by remember{mutableIntStateOf(0)}
            var room by remember{mutableStateOf("")}
            LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)){
                item{EditorSection("Appearance"){
                    EditorSelect("Theme",Appearance.mode.value,listOf("Light","Dark","System").map{it to it}){Appearance.set(context,it)}
                    Text("Dark mode uses a deep background, light text and distinct colours for pending, active and completed work.",style=MaterialTheme.typography.bodySmall)
                }}
                item{key(revision){EditorSection("Notifications"){
                    EditorSelect("Chat alerts",prefs.text("messages","All messages"),listOf("All messages","Mentions & assignments","Mentions only","Muted").map{it to it}){prefs.set("messages",it);revision++}
                    Row(verticalAlignment=Alignment.CenterVertically){Switch(prefs.bool("reminders",true),{prefs.set("reminders",it);revision++;org.sevamrita.mobile.reminders.WorkReminders.reschedule(context)});Spacer(Modifier.width(12.dp));Text("Task and tracker reminders")}
                    Row(verticalAlignment=Alignment.CenterVertically){Switch(prefs.bool("quiet",false),{prefs.set("quiet",it);revision++;org.sevamrita.mobile.reminders.WorkReminders.reschedule(context)});Spacer(Modifier.width(12.dp));Text("Quiet hours")}
                    if(prefs.bool("quiet",false)){
                        EditorTime("Quiet from",LocalTime.parse(prefs.text("quiet_start","22:00"))){prefs.set("quiet_start",it.toString());revision++;org.sevamrita.mobile.reminders.WorkReminders.reschedule(context)}
                        EditorTime("Quiet until",LocalTime.parse(prefs.text("quiet_end","07:00"))){prefs.set("quiet_end",it.toString());revision++;org.sevamrita.mobile.reminders.WorkReminders.reschedule(context)}
                    }
                    Text("Preferences apply to this account on this phone. Muting alerts does not hide messages or mentions. Due reminders during quiet hours wait until quiet hours end.",style=MaterialTheme.typography.bodySmall)
                }}}
                item{key(revision){EditorSection("Per-conversation alerts"){
                    EditorSelect("Conversation",room,state.chatHome.items("spaces").map{it.text("name") to it.text("title")}){room=it}
                    if(room.isNotBlank())EditorSelect("Alert mode",prefs.text("room:$room","Default"),listOf("Default","All messages","Mentions & assignments","Mentions only","Muted").map{it to it}){prefs.set("room:$room",it);revision++}
                }}}
            }
        }
        ChatView.OUTBOX->LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(10.dp)){
            item{Text("Queued work is saved privately for this account. Waiting items send when connected. Changes rejected by the server need attention.")}
            if(state.outbox.isEmpty())item{Text("Nothing waiting to send.")}
            items(state.outbox,key={it.text("id")}){row->EditorSection(row.text("method").replace('_',' ')){
                Text(row.text("status"),color=if(row.text("status")=="Waiting")MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error)
                val data=row.optJSONObject("payload") ?: JSONObject();Text(mentionLabel(data.text("body").ifBlank{data.text("note").ifBlank{data.optJSONObject("payload")?.text("body").orEmpty()}}).take(180))
                if(row.text("error").isNotBlank())Text(row.text("error"),style=MaterialTheme.typography.bodySmall)
                Row{TextButton(onClick={model.outboxAction(row.text("id"),true)}){Text("Retry")};TextButton(onClick={model.outboxAction(row.text("id"),false)}){Text("Cancel sending")}}
            }}
        }
        else->SearchMentionsScreen(state,model)
    }
}
@Composable private fun SearchMentionsScreen(state:PortalState,model:PortalViewModel){
    val mentions=state.chatNavigation.current.view==ChatView.MENTIONS
    var query by rememberSaveable{mutableStateOf("")};var kind by rememberSaveable{mutableStateOf("All")};var unread by rememberSaveable{mutableStateOf(false)}
    var rows by remember{mutableStateOf(emptyList<JSONObject>())};var cursor by remember{mutableStateOf("")};var count by remember{mutableIntStateOf(0)}
    var loading by remember{mutableStateOf(false)};var revision by remember{mutableIntStateOf(0)}
    fun load(before:String=""){
        if(!mentions&&query.trim().length<2)return
        val revisionHere=++revision;loading=true
        val args=if(mentions)JSONObject().put("unread_only",unread).put("before",before.ifBlank{null}) else JSONObject().put("query",query.trim()).put("kind",kind).put("space",state.searchSpace.ifBlank{null}).put("before",before.ifBlank{null})
        model.featureCall(if(mentions)"get_mentions" else "search_conversation",args){if(revision==revisionHere){
            if(it.optBoolean("_error")){loading=false;return@featureCall}
            rows=(if(before.isBlank())emptyList() else rows)+it.items(if(mentions)"mentions" else "results");cursor=it.text("next_cursor");count=it.optInt("unread_count");loading=false
        }}
    }
    LaunchedEffect(mentions,unread){if(mentions)load()}
    LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)){
        item{if(mentions){Text("$count unread mentions",style=MaterialTheme.typography.titleMedium);FilterChip(unread,{unread=!unread},label={Text("Unread only")})}
        else{OutlinedTextField(query,{query=it;revision++;loading=false},label={Text("Search messages, work or filenames")},modifier=Modifier.fillMaxWidth(),singleLine=true)
            EditorSelect("Search in",kind,listOf("All","Messages","Tasks","Trackers","Files").map{it to it}){kind=it}
            Button(onClick={load()},enabled=query.trim().length>=2){Text("Search")}
            if(state.searchSpace.isNotBlank())Text("Searching this conversation",style=MaterialTheme.typography.bodySmall)
        }}
        if(loading)item{Text("Searching…")}
        if(rows.isEmpty()&&!loading)item{Text(if(mentions)"No mentions in this view." else "Enter at least two characters to search conversation history.")}
        items(rows,key={it.text("id").ifBlank{it.text("name")}}){row->Surface(onClick={
            if(mentions)model.featureCall("mark_mention_seen",JSONObject().put("entry",row.text("name"))){load()}
            when(row.text("kind")){"File"->model.openReceipt(row.text("file_url"),Page.COLLABORATION);"Tracker"->model.openTracker(row.text("space"),row.text("item"));"Task"->model.openTask(row.text("space"),row.text("item"));else->model.openChatEntry(row.text("space"),row.text("name"))}
        },color=if(row.optBoolean("unread"))MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surface,shape=MaterialTheme.shapes.medium){Column(Modifier.fillMaxWidth().padding(14.dp),verticalArrangement=Arrangement.spacedBy(5.dp)){
            Text(row.text("space_title"),color=MaterialTheme.colorScheme.primary,style=MaterialTheme.typography.labelLarge)
            Text(row.text("title").ifBlank{row.text("body")},maxLines=4);Text(row.text("creation").take(16),style=MaterialTheme.typography.labelSmall)
        }}}
        if(cursor.isNotBlank())item{OutlinedButton(onClick={load(cursor)},enabled=!loading){Text("Load more")}}
    }
}
