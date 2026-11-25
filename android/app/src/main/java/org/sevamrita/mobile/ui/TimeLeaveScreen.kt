package org.sevamrita.mobile.ui

import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.ui.platform.LocalContext
import androidx.compose.foundation.clickable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import org.sevamrita.mobile.SectionCard
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text
import java.time.LocalDate
import java.util.UUID

private fun timeRequestDates(row:JSONObject) = if(row.text("type")=="Weekly Off Swap") "Work: ${row.text("from_date")} · Off: ${row.text("to_date")}" else "${row.text("from_date")} – ${row.text("to_date")}"
private val timeTypes = listOf("Privilege Leave", "Compensatory Leave", "Leave Without Pay", "Weekly Off Swap", "Compensatory Credit", "WFH", "Attendance Correction")
private val weekNames = listOf("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
private val monthNames = listOf("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
private fun JSONObject.edit(key: String, value: Any): String = JSONObject(toString()).put(key,value).toString()

@Composable
fun TimeLeaveScreen(state: PortalState, model: PortalViewModel) {
    val data = state.timeWorkspace
    var form by rememberSaveable { mutableStateOf("") }
    var requestKey by rememberSaveable { mutableStateOf(UUID.randomUUID().toString()) }
    var selected by rememberSaveable { mutableStateOf("") }
    BackHandler(enabled = form.isNotBlank() || selected.isNotBlank()) { if (!state.busy) { form=""; selected="" } }
    val tabs = listOf("mine" to "My requests", "resources" to "People centre") + (if(data.optBoolean("can_review")) listOf("team" to "Team review") else emptyList()) +
        (if(data.optBoolean("can_override")) listOf("policy" to "HR policy") else emptyList())
    Column(Modifier.fillMaxSize()) {
        ScrollableTabRow(selectedTabIndex = tabs.indexOfFirst { it.first == state.timeView }.coerceAtLeast(0), edgePadding = 12.dp) {
            tabs.forEach { (id,label) -> Tab(selected = id == state.timeView, onClick = { if(!state.busy){form="";selected="";model.openTimeLeave(id)} }, text={Text(label)}) }
        }
        if(state.timeView == "resources") { PeopleCentreScreen(state,model){day->model.openTimeLeave("mine");requestKey=UUID.randomUUID().toString();form=JSONObject().put("employee",data.optJSONObject("employee")?.text("name")).put("type","Optional Holiday").put("category","Normal").put("from_date",day).put("to_date",day).put("reason","").toString()};return@Column }
        if(state.timeView == "policy") { HrTimePolicyScreen(state,model); return@Column }
        if(form.isNotBlank()) {
            val draft = JSONObject(form)
            TimeRequestForm(data,draft,state.busy,model,onChange={key,value->val next=JSONObject(draft.edit(key,value));if(key=="type"){next.put("category",timeLeaveCategory(value.toString(),next.text("category")));if(!timeLeaveHasCategory(value.toString()))next.put("half_day",false)};form=next.toString()},onCancel={form=""},onSubmit={
                val payload=JSONObject(draft.toString())
                if(payload.text("type") in listOf("Compensatory Credit","Attendance Correction"))payload.put("to_date",payload.text("from_date"))
                model.timeAction("time_leave_portal.submit_time_request",JSONObject().put("details",payload).put("request_key",requestKey)){form="";requestKey=UUID.randomUUID().toString()}
            }); return@Column
        }
        if(selected.isNotBlank()) {
            val row=JSONObject(selected)
            TimeDecisionScreen(row,data.optBoolean("can_override"),state.busy,model,onRefresh={selected=it.toString()},onClose={selected=""},onDecide={action,reason,override,days,expiry->
                model.timeAction("time_leave_portal.decide_time_request",JSONObject().put("doctype",row.text("doctype")).put("name",row.text("name"))
                    .put("action",action).put("expected_modified",row.text("modified")).put("reason",reason).put("override",override)
                    .put("credit_days",days).put("valid_until",expiry)){selected=""}
            });return@Column
        }
        LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
            if(state.timeView == "mine") {
                item { Row(horizontalArrangement=Arrangement.spacedBy(12.dp)) {
                    Surface(Modifier.weight(1f),shape=MaterialTheme.shapes.large,color=MaterialTheme.colorScheme.secondaryContainer) { Column(Modifier.padding(16.dp)) {Text("Paid leave remaining",style=MaterialTheme.typography.labelLarge,minLines=2);Text("${data.optDouble("paid_balance",0.0)} days",style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.Bold)} }
                    Surface(Modifier.weight(1f),shape=MaterialTheme.shapes.large,color=MaterialTheme.colorScheme.tertiaryContainer) { Column(Modifier.padding(16.dp)) {Text("Compensatory leave remaining",style=MaterialTheme.typography.labelLarge,minLines=2);Text("${data.optDouble("comp_balance",0.0)} days",style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.Bold)} }
                } }
                if(data.optBoolean("eligible") || data.optBoolean("can_override"))item { Button(onClick={requestKey=UUID.randomUUID().toString();val today=data.text("today").ifBlank{LocalDate.now().toString()};form=JSONObject().put("employee",data.optJSONObject("employee")?.text("name")).put("type","Privilege Leave").put("category","Normal").put("from_date",today).put("to_date",today).put("half_day",false).put("manager_notified_on",today).put("parental_case","Birth").put("half_day_date",today).put("reason","").put("hr_exception_reason","").put("requested_status","Present").toString()},enabled=!state.busy,modifier=Modifier.fillMaxWidth()){Text("New request")} }
                else item { Text("Automatic leave and attendance policy applies to salaried employees. Work logging remains available to all active staff.",style=MaterialTheme.typography.bodyMedium) }
                if(data.optBoolean("legacy_allocation"))item { Text("Your older allocation keeps its original year and accrual schedule until HR verifies and adopts its balance.",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant) }
            }
            val rows=data.items("requests")
            if(rows.isEmpty())item { SectionCard { Text("No requests in this view.") } }
            items(rows,key={it.text("doctype")+it.text("name")}){row->
                Surface(Modifier.fillMaxWidth().clickable{selected=row.toString()},shape=MaterialTheme.shapes.large,tonalElevation=1.dp) {
                    Column(Modifier.padding(18.dp),verticalArrangement=Arrangement.spacedBy(6.dp)) {
                        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text(row.text("type"),fontWeight=FontWeight.SemiBold,modifier=Modifier.weight(1f));Text(row.text("status"),style=MaterialTheme.typography.labelLarge,color=MaterialTheme.colorScheme.primary)}
                        if(state.timeView == "team")Text(row.text("employee_name"),style=MaterialTheme.typography.bodyMedium)
                        Text(timeRequestDates(row),style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(row.text("reason"),maxLines=2,style=MaterialTheme.typography.bodyMedium)
                        if(row.optBoolean("requires_hr"))Text("HR decision required",style=MaterialTheme.typography.labelMedium,color=MaterialTheme.colorScheme.error)
                    }
                }
            }
            if(state.timeView == "mine")items(data.items("credits")){credit->SectionCard { Text("Worked ${credit.text("from_date")}",fontWeight=FontWeight.SemiBold);Text("${credit.optDouble("available")} day(s) available · valid through ${credit.text("valid_until")}",style=MaterialTheme.typography.bodySmall) } }
            item { Spacer(Modifier.height(16.dp)) }
        }
    }
}

@Composable
private fun TimeText(label:String,value:String,numeric:Boolean=false,change:(String)->Unit) {
    OutlinedTextField(value=value,onValueChange=change,label={Text(label)},modifier=Modifier.fillMaxWidth(),
        keyboardOptions=KeyboardOptions(keyboardType=if(numeric)KeyboardType.Decimal else KeyboardType.Text),minLines=if(label.contains("reason",true))2 else 1)
}

@Composable
private fun TimeRequestForm(
    data: JSONObject, form: JSONObject, busy: Boolean, model: PortalViewModel,
    onChange: (String, Any) -> Unit, onCancel: () -> Unit, onSubmit: () -> Unit
) {
    val type = form.text("type")
    val ordinaryLeave = timeLeaveHasCategory(type)
    val parental = type in listOf("Maternity Leave", "Paternity Leave")
    val medical = ordinaryLeave && form.text("category") == "Medical"
    val context = LocalContext.current
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) try {
            model.uploadTimeCertificate(readTrackerAttachment(context, uri)) { onChange("certificate_url", it.text("file_url")) }
        } catch (error: Exception) { model.error(error.message ?: "Unable to read certificate") }
    }
    val choices = data.optJSONArray("request_types")?.let { values ->
        (0 until values.length()).map(values::getString)
    } ?: timeTypes
    Column(Modifier.fillMaxSize()) {
        LazyColumn(Modifier.weight(1f), contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item { Text("New request", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold) }
            if (data.optBoolean("can_override")) item {
                TimeRequestSelect("Employee", form.text("employee"),
                    listOf((data.optJSONObject("employee")?.text("name").orEmpty()) to
                        (if (data.optJSONObject("employee") == null) "Choose employee" else "Myself")) +
                        data.items("people").map { it.text("name") to it.text("employee_name") }, !busy) { onChange("employee", it) }
            }
            item { TimeRequestSelect("Request type", type, choices.map { it to it }, !busy) { onChange("type", it) } }
            if (ordinaryLeave) item {
                TimeRequestCategory(form.text("category"), data.text("special_effective_from").isNotBlank(), !busy) { onChange("category", it) }
            }
            item {
                TimeRequestDates(
                    startLabel = when (type) { "Weekly Off Swap" -> "Usual off to work on"; "Compensatory Credit" -> "Day worked"; else -> "From date" },
                    start = form.text("from_date"),
                    endLabel = when (type) { "Compensatory Credit", "Attendance Correction" -> null; "Weekly Off Swap" -> "Alternative day off"; else -> "To date" },
                    end = form.text("to_date"), enabled = !busy,
                    changeStart = { onChange("from_date", it) }, changeEnd = { onChange("to_date", it) })
            }
            if (type == "Attendance Correction") item {
                TimeRequestSelect("Correct attendance to", form.text("requested_status"),
                    listOf("Present", "Half Day", "Absent", "Holiday", "Work From Home").map { it to it }, !busy) { onChange("requested_status", it) }
            }
            if (ordinaryLeave) item {
                Row(Modifier.fillMaxWidth().heightIn(min = 48.dp).toggleable(
                    value = form.optBoolean("half_day"), enabled = !busy, role = Role.Checkbox,
                    onValueChange = { onChange("half_day", it) }), verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = form.optBoolean("half_day"), onCheckedChange = null, enabled = !busy)
                    Text("Include a half day", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(start = 10.dp))
                }
            }
            if (ordinaryLeave && form.optBoolean("half_day")) item {
                TimeRequestDate("Half-day date", form.text("half_day_date"), !busy) { onChange("half_day_date", it) }
            }
            if (medical) item {
                TimeRequestDate("Manager informed on", form.text("manager_notified_on").ifBlank { data.text("today") }, !busy) { onChange("manager_notified_on", it) }
            }
            if (parental) item {
                TimeRequestDate("Expected or actual childbirth date", form.text("childbirth_date"), !busy) { onChange("childbirth_date", it) }
            }
            if (type == "Maternity Leave") item {
                TimeRequestSelect("Parental leave case", form.text("parental_case").ifBlank { "Birth" },
                    listOf("Birth", "Two or more surviving children", "Adoption or commissioning").map { it to it }, !busy) { onChange("parental_case", it) }
            }
            if (medical || parental) item {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    OutlinedButton(onClick = { picker.launch(arrayOf("application/pdf", "image/png", "image/jpeg")) },
                        enabled = !busy, shape = RoundedCornerShape(10.dp), modifier = Modifier.heightIn(min = 48.dp)) {
                        Icon(Icons.Default.AttachFile, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(6.dp))
                        Text(if (form.text("certificate_url").isBlank()) "Attach certificate" else "Replace certificate")
                    }
                    if (form.text("certificate_url").isNotBlank()) Text("Private certificate uploaded", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                    Text(if (parental) "Optional supporting evidence. HR verifies eligibility before approval." else
                        "Required before approval for more than two consecutive days. PDF or image, up to 5 MB.",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            item {
                OutlinedTextField(value = form.text("reason"), onValueChange = { onChange("reason", it) },
                    label = { Text("Reason") }, enabled = !busy, modifier = Modifier.fillMaxWidth(),
                    minLines = 3, maxLines = 6, shape = RoundedCornerShape(10.dp))
            }
            if (type == "Compensatory Credit") item {
                Text("At least ${data.optJSONObject("policy")?.optDouble("comp_hours", 6.0)} logged hours earns a day. Shorter work requires an HR exception.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (data.optBoolean("can_override")) item {
                OutlinedTextField(value = form.text("hr_exception_reason"), onValueChange = { onChange("hr_exception_reason", it) },
                    label = { Text("HR exception reason (optional)") }, enabled = !busy,
                    modifier = Modifier.fillMaxWidth(), minLines = 2, shape = RoundedCornerShape(10.dp))
            }
        }
        Surface(color = MaterialTheme.colorScheme.surface) {
            Column {
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
                    TextButton(onClick = onCancel, enabled = !busy, modifier = Modifier.heightIn(min = 48.dp)) { Text("Cancel") }
                    Button(onClick = onSubmit, enabled = !busy && form.text("reason").trim().length >= 10,
                        modifier = Modifier.weight(1f).heightIn(min = 48.dp), shape = RoundedCornerShape(10.dp)) {
                        Text(if (busy) "Saving…" else "Submit request")
                    }
                }
            }
        }
    }
}

@Composable
private fun TimeDecisionScreen(row:JSONObject,hr:Boolean,busy:Boolean,model:PortalViewModel,onRefresh:(JSONObject)->Unit,onClose:()->Unit,onDecide:(String,String,String,Double,String)->Unit) {
    val context=LocalContext.current
    val picker=rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()){uri->if(uri!=null)try{model.uploadTimeCertificate(readTrackerAttachment(context,uri),row.text("name"),row.text("modified"),onRefresh)}catch(e:Exception){model.error(e.message?:"Unable to read certificate")}}
    var eligibility by rememberSaveable(row.text("name")){mutableStateOf("")}
    var reason by rememberSaveable(row.text("name")){mutableStateOf("")};var override by rememberSaveable(row.text("name")){mutableStateOf("")}
    var days by rememberSaveable(row.text("name")){mutableStateOf(row.optDouble("days",0.0).toString())};var expiry by rememberSaveable(row.text("name")){mutableStateOf(row.text("valid_until"))}
    LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(14.dp)) {
        item { Text(row.text("type"),style=MaterialTheme.typography.headlineSmall,fontWeight=FontWeight.Bold);Text(row.text("employee_name"));Text("${timeRequestDates(row)} · ${row.text("status")}",style=MaterialTheme.typography.bodySmall) }
        item { SectionCard { Text(row.text("reason"));if(row.text("hr_exception_reason").isNotBlank())Text("HR exception: ${row.text("hr_exception_reason")}");if(row.text("decision_reason").isNotBlank())Text("Decision: ${row.text("decision_reason")}") } }
        if(row.text("certificate_url").isNotBlank())item{TextButton(onClick={model.openReceipt(row.text("certificate_url"),Page.TIME_LEAVE)}){Text("Open private certificate")}}
        if(row.optBoolean("can_attach_certificate"))item{OutlinedButton(onClick={picker.launch(arrayOf("application/pdf","image/png","image/jpeg"))},enabled=!busy,modifier=Modifier.fillMaxWidth()){Text("Attach supporting certificate")}}
        if(row.text("eligibility_verified_by").isNotBlank())item{Text("Eligibility verified by ${row.text("eligibility_verified_by")}: ${row.text("eligibility_reason")}",style=MaterialTheme.typography.bodySmall)}
        if(row.optBoolean("can_verify_eligibility"))item{SectionCard{Text("Verify qualifying service/work records and the applicable birth, adoption or commissioning entitlement.",style=MaterialTheme.typography.bodySmall);TimeText("HR eligibility verification notes",eligibility){eligibility=it};OutlinedButton(onClick={model.resourceAction("hr_special_leave.verify_parental_eligibility",JSONObject().put("name",row.text("name")).put("expected_modified",row.text("modified")).put("reason",eligibility),onRefresh)},enabled=!busy && eligibility.trim().length>=10){Text("Verify parental eligibility")}}}
        if(row.optBoolean("can_decide")||row.optBoolean("can_cancel")||row.optBoolean("can_reverse")){
            item { TimeText("Decision or cancellation reason",reason){reason=it} }
            if(hr)item { TimeText("HR exception reason (to waive a policy)",override){override=it} }
            if(hr && row.text("type")=="Compensatory Credit"){
                item { SelectField("Credit days",days,listOf("0.0" to "Choose after review","0.5" to "Half day","1.0" to "One day")){days=it} }
                item { DateField("Valid until",expiry){expiry=it} }
            }
            if(row.optBoolean("can_decide"))item { Button(onClick={onDecide("approve",reason,override,days.toDoubleOrNull()?:0.0,expiry)},enabled=!busy,modifier=Modifier.fillMaxWidth()){Text("Approve")};OutlinedButton(onClick={onDecide("reject",reason,override,days.toDoubleOrNull()?:0.0,expiry)},enabled=!busy && reason.trim().length>=10,modifier=Modifier.fillMaxWidth()){Text("Reject")} }
            if(row.optBoolean("can_cancel"))item { OutlinedButton(onClick={onDecide("cancel",reason,override,days.toDoubleOrNull()?:0.0,expiry)},enabled=!busy && reason.trim().length>=10,modifier=Modifier.fillMaxWidth()){Text("Cancel request")} }
            if(row.optBoolean("can_reverse"))item { OutlinedButton(onClick={onDecide("reverse",reason,override,days.toDoubleOrNull()?:0.0,expiry)},enabled=!busy && reason.trim().length>=10,modifier=Modifier.fillMaxWidth()){Text("Reverse approval")} }
        }
        item { OutlinedButton(onClick=onClose,enabled=!busy,modifier=Modifier.fillMaxWidth()){Text("Back to requests")} }
    }
}

@Composable
private fun HrTimePolicyScreen(state:PortalState,model:PortalViewModel) {
    val workspace=state.timePolicy;val source=workspace.optJSONObject("policy")?:JSONObject();val labels=workspace.optJSONObject("labels")?:JSONObject()
    var text by rememberSaveable(workspace.text("revision")){mutableStateOf(source.toString())};val form=JSONObject(text)
    var effective by rememberSaveable{mutableStateOf(LocalDate.now().toString())};var reason by rememberSaveable{mutableStateOf("")}
    var employee by rememberSaveable{mutableStateOf("")};var amount by rememberSaveable{mutableStateOf("")};var adjustmentReason by rememberSaveable{mutableStateOf("")}
    var opening by rememberSaveable(state.timeBalancePreview.text("employee")){mutableStateOf(state.timeBalancePreview.optDouble("balance",0.0).toString())}
    var confirmed by rememberSaveable{mutableStateOf(false)};var balanceKey by rememberSaveable{mutableStateOf(UUID.randomUUID().toString())}
    val booleans=setOf("comp_half_day_enabled","allow_negative_paid_leave","apply_to_unpaid","attendance_based_payroll","calendar_day_payroll","charter_enabled")
    LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(14.dp)) {
        item { Text("Dated HR policy",style=MaterialTheme.typography.headlineSmall,fontWeight=FontWeight.Bold);Text("Changes apply from the chosen date. Past records retain their history.",style=MaterialTheme.typography.bodySmall) }
        items(source.keys().asSequence().toList()){key->
            when {
                key in booleans -> Row { Checkbox(form.optInt(key)!=0,{text=form.edit(key,if(it)1 else 0)});Text(labels.text(key),Modifier.weight(1f).padding(top=12.dp)) }
                key in setOf("weekly_off_day","swap_off_day","swap_notice_weekday") -> SelectField(labels.text(key),form.optInt(key).toString(),weekNames.mapIndexed{i,value->i.toString() to value}){text=form.edit(key,it.toInt())}
                key=="leave_year_start_month" -> SelectField(labels.text(key),form.optInt(key).toString(),monthNames.mapIndexed{i,value->(i+1).toString() to value}){text=form.edit(key,it.toInt())}
                else -> TimeText(labels.text(key),form.opt(key)?.toString().orEmpty(),true){text=form.edit(key,it)}
            }
        }
        item { DateField("Effective from",effective){effective=it} }
        item { TimeText("Reason for policy change",reason){reason=it} }
        item { Button(onClick={model.timeAction("hr_policy.publish_hr_policy",JSONObject().put("values",form).put("effective_from",effective).put("reason",reason).put("expected_revision",workspace.text("revision")).put("expected_publication_revision",workspace.text("publication_revision"))){reason=""}},enabled=!state.busy && reason.trim().length>=10,modifier=Modifier.fillMaxWidth()){Text("Publish policy revision")} }
        item { HorizontalDivider();Text("Employee balance",style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.Bold) }
        item { SelectField("Employee",employee,state.timeWorkspace.items("people").map{it.text("name") to it.text("employee_name")}){employee=it;confirmed=false;model.previewTimeBalance(it)} }
        val preview=state.timeBalancePreview
        if(preview.text("employee")==employee && employee.isNotBlank()){
            item { SectionCard { Text("Balance: ${preview.optDouble("balance",0.0)} days");Text("Allocation: ${preview.optJSONObject("allocation")?.text("from_date")} – ${preview.optJSONObject("allocation")?.text("to_date")}",style=MaterialTheme.typography.bodySmall) } }
            item { TimeText("Adjustment in days (+ / −)",amount,true){amount=it} }
            item { TimeText("Reason for balance correction",adjustmentReason){adjustmentReason=it} }
            item { Button(onClick={model.timeAction("hr_leave_balances.adjust_leave_balance",JSONObject().put("employee",employee).put("days",amount).put("reason",adjustmentReason).put("request_key",balanceKey)){balanceKey=UUID.randomUUID().toString();amount="";model.previewTimeBalance(employee)}},enabled=!state.busy && adjustmentReason.trim().length>=10 && amount.toDoubleOrNull()?.let{it!=0.0}==true,modifier=Modifier.fillMaxWidth()){Text("Post balance adjustment")} }
            if(preview.optBoolean("needs_adoption")){
                item { Text("Adoption closes the older allocation yesterday and starts the configured leave year today with the verified opening. Resolve future leave first.",style=MaterialTheme.typography.bodySmall) }
                item { TimeText("Verified opening balance",opening,true){opening=it} }
                item { Row {Checkbox(confirmed,{confirmed=it});Text("I checked the opening balance and allocation change.",Modifier.padding(top=12.dp))} }
                item { OutlinedButton(onClick={model.timeAction("hr_leave_balances.adopt_leave_year",JSONObject().put("employee",employee).put("opening_balance",opening).put("reason",adjustmentReason).put("expected_allocation",preview.optJSONObject("allocation")?.text("name")).put("request_key",balanceKey)){balanceKey=UUID.randomUUID().toString();confirmed=false;model.previewTimeBalance(employee)}},enabled=!state.busy && confirmed && adjustmentReason.trim().length>=10 && !preview.optBoolean("has_future_leave"),modifier=Modifier.fillMaxWidth()){Text("Adopt leave year")} }
            }
        }
        item { HorizontalDivider();Text("Policy history",style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.Bold) }
        items(workspace.items("history")){revision->SectionCard{Text("Effective ${revision.text("effective_from")}",fontWeight=FontWeight.SemiBold);Text(revision.text("reason"));Text(revision.text("published_by"),style=MaterialTheme.typography.bodySmall);TextButton(onClick={val values=JSONObject(source.toString());val saved=revision.opt("settings");val settings=if(saved is JSONObject)saved else JSONObject(saved.toString());settings.keys().forEach{key->values.put(key,settings.get(key))};text=values.toString();effective=maxOf(revision.text("effective_from"),LocalDate.now().toString());reason=""}){Text("Use as starting values")}} }
    }
}
