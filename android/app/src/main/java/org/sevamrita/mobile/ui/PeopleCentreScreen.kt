package org.sevamrita.mobile.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.background
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import org.sevamrita.mobile.SectionCard
import org.sevamrita.mobile.money
import org.sevamrita.mobile.data.items
import org.sevamrita.mobile.data.text
import java.time.LocalDate
import java.util.UUID

@Composable
fun PeopleCentreScreen(state: PortalState, model: PortalViewModel, requestHoliday: (String) -> Unit) {
    val data=state.timeResources
    val guide=data.optJSONObject("settings")?:JSONObject()
    var section by rememberSaveable{mutableStateOf("guide")}
    val listState=rememberLazyListState()
    LaunchedEffect(section){listState.scrollToItem(0)}
    var year by rememberSaveable{mutableStateOf(LocalDate.now().year.toString())}
    var holidayText by rememberSaveable{mutableStateOf(JSONObject().put("kind","Fixed").put("enabled",true).toString())}
    val holiday=JSONObject(holidayText)
    var holidayReason by rememberSaveable{mutableStateOf("")}
    var employee by rememberSaveable{mutableStateOf("")}
    val profileSource=state.timePayroll.optJSONObject("profile")?:JSONObject()
    var profileText by rememberSaveable(profileSource.text("employee"),profileSource.text("modified")){mutableStateOf(profileSource.toString())}
    val profile=JSONObject(profileText)
    var pfLedger by rememberSaveable(data.toString()){mutableStateOf(data.optJSONObject("payroll_accounts")?.text("SF Employee PF").orEmpty())}
    var ptLedger by rememberSaveable(data.toString()){mutableStateOf(data.optJSONObject("payroll_accounts")?.text("SF Professional Tax").orEmpty())}
    var ledgerReason by rememberSaveable{mutableStateOf("")}
    var profileReason by rememberSaveable{mutableStateOf("")}
    var month by rememberSaveable{mutableStateOf(LocalDate.now().toString().take(7))}
    var unpaid by rememberSaveable{mutableStateOf("0")}
    var handbookText by rememberSaveable(data.text("revision")){mutableStateOf(guide.toString())}
    var roleEmployee by rememberSaveable{mutableStateOf("")}
    var reportingText by rememberSaveable{mutableStateOf("")}
    var reportingReason by rememberSaveable{mutableStateOf("")}
    var handbookReason by rememberSaveable{mutableStateOf("")}
    val sections=listOf("guide" to "Guide","holidays" to "Holidays")+(if(data.optBoolean("can_payroll"))listOf("payroll" to "Payroll")else emptyList())+(if(data.optBoolean("can_manage"))listOf("edit" to "Edit guide")else emptyList())
    Column(Modifier.fillMaxSize()){
        ScrollableTabRow(sections.indexOfFirst{it.first==section}.coerceAtLeast(0),edgePadding=8.dp){sections.forEach{(id,title)->Tab(section==id,{section=id},text={Text(title)})}}
        LazyColumn(Modifier.fillMaxSize(),state=listState,contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(14.dp)){
            if(section=="guide"){
                item {
                    Text("Team policy charter",style=MaterialTheme.typography.headlineSmall,fontWeight=FontWeight.Bold)
                    Text("Effective ${guideDate(guide.text("effective_from"))}",style=MaterialTheme.typography.labelLarge,color=MaterialTheme.colorScheme.primary)
                }
                if(data.text("reporting_manager").isNotBlank())item {
                    SectionCard {
                        Text("Your reporting manager",style=MaterialTheme.typography.labelMedium,color=MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(data.text("reporting_manager"),style=MaterialTheme.typography.bodyLarge,fontWeight=FontWeight.SemiBold)
                    }
                }
                items(peopleGuideSections(data),key={it.first}) { (title,points) -> GuidePolicyCard(title,points) }
                item { Text("Who to contact",style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.Bold,modifier=Modifier.semantics{heading()}) }
                items(guide.items("contacts"),key={it.text("area")}) { row ->
                    GuidePolicyCard(row.text("area"),listOf(
                        GuidePoint("Contact",listOf(row.text("name"),row.text("title")).filter{it.isNotBlank()}.joinToString(" · ")),
                        GuidePoint("Help with",row.text("details"))))
                }
                if(data.items("salary_slips").isNotEmpty())item {
                    Text("My payslips",style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.Bold,modifier=Modifier.semantics{heading()})
                }
                items(data.items("salary_slips"),key={it.text("name")}) { row ->
                    GuidePolicyCard("${guideDate(row.text("start_date"))} – ${guideDate(row.text("end_date"))}",listOf(
                        GuidePoint("Gross pay",money(row.optDouble("gross_pay",0.0))),
                        GuidePoint("Employee deductions",money(row.optDouble("total_deduction",0.0))),
                        GuidePoint("Net pay",money(row.optDouble("net_pay",0.0))),
                        GuidePoint("Employer PF",money(row.optDouble("sf_employer_pf",0.0)))))
                }
            }
            if(section=="holidays"){
                item{Text("Holiday calendar",style=MaterialTheme.typography.headlineSmall,fontWeight=FontWeight.Bold);Text("${data.optInt("fixed_count")} / 12 fixed holidays · ${data.optDouble("optional_used",0.0)} / ${data.optInt("optional_limit",2)} optional days reserved or used",style=MaterialTheme.typography.bodySmall)}
                item{Row(horizontalArrangement=Arrangement.spacedBy(10.dp)){OutlinedTextField(year,{year=it},label={Text("Year")},singleLine=true,modifier=Modifier.weight(1f));OutlinedButton(onClick={year.toIntOrNull()?.let(model::loadPeopleCentre)},enabled=!state.busy){Text("Show")}}}
                if(data.items("holidays").isEmpty())item{SectionCard{Text("HR has not published holiday dates for this year yet. Festival dates require confirmation.")}}
                items(data.items("holidays")){row->SectionCard{
                    Text(row.text("holiday_name"),fontWeight=FontWeight.Bold);Text("${row.text("holiday_date")} · ${row.text("kind")}${if(row.optInt("enabled")==0)" · Disabled" else ""}")
                    if(row.text("kind")=="Optional" && row.optInt("enabled")==1 && data.optJSONObject("employee")!=null)TextButton(onClick={requestHoliday(row.text("holiday_date"))}){Text("Request day off")}
                    if(data.optBoolean("can_manage"))TextButton(onClick={holidayText=JSONObject(row.toString()).put("enabled",row.optInt("enabled")==1).toString();holidayReason=""}){Text("Edit")}
                }}
                if(data.optBoolean("can_manage")){
                    item{HorizontalDivider();Text(if(holiday.text("name").isBlank())"Add holiday" else "Edit holiday",style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.Bold)}
                    item{CentreText("Holiday name",holiday.text("holiday_name")){holidayText=holiday.changed("holiday_name",it)}}
                    item{DateField("Holiday date",holiday.text("holiday_date"),required=true){holidayText=holiday.changed("holiday_date",it)}}
                    item{SelectField("Holiday type",holiday.text("kind"),listOf("Fixed" to "Fixed","Optional" to "Optional")){holidayText=holiday.changed("kind",it)}}
                    item{Row{Checkbox(holiday.optBoolean("enabled"),{holidayText=holiday.changed("enabled",it)});Text("Published",Modifier.padding(top=12.dp))}}
                    item{CentreText("Reason for calendar change",holidayReason){holidayReason=it}}
                    item{Button(onClick={model.resourceAction("hr_resources.save_holiday",JSONObject().put("details",holiday).put("reason",holidayReason).put("expected_modified",holiday.text("modified"))){holidayText=JSONObject().put("kind","Fixed").put("enabled",true).toString();holidayReason="";model.loadPeopleCentre(year.toIntOrNull()?:LocalDate.now().year)}},enabled=!state.busy && holidayReason.trim().length>=10,modifier=Modifier.fillMaxWidth()){Text("Save holiday")}}
                }
            }
            if(section=="payroll" && data.optBoolean("can_payroll")){
                item{Text("Payroll liability ledgers",style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.Bold)}
                item{SelectField("PF payable ledger",pfLedger,data.items("liability_accounts").map{it.text("name") to it.text("account_name")}){pfLedger=it};SelectField("Professional Tax payable ledger",ptLedger,data.items("liability_accounts").map{it.text("name") to it.text("account_name")}){ptLedger=it};CentreText("Reason for payroll ledger change",ledgerReason){ledgerReason=it}}
                item{OutlinedButton(onClick={model.resourceAction("hr_resources.configure_payroll_ledgers",JSONObject().put("pf_account",pfLedger).put("pt_account",ptLedger).put("reason",ledgerReason)){ledgerReason=""}},enabled=!state.busy && pfLedger.isNotBlank() && ptLedger.isNotBlank() && ledgerReason.trim().length>=10,modifier=Modifier.fillMaxWidth()){Text("Save payroll ledgers")}}
                item{Text("Employee payroll setup",style=MaterialTheme.typography.headlineSmall,fontWeight=FontWeight.Bold);Text("Profiles enrol each employee. Monthly values support the preview; actual payslips use their salary structure.",style=MaterialTheme.typography.bodySmall)}
                item{SelectField("Employee",employee,data.items("people").map{it.text("name") to it.text("employee_name")}){employee=it;model.loadPayrollProfile(it)}}
                if(profile.text("employee")==employee && employee.isNotBlank()){
                    item{DateField("Effective from",profile.text("effective_from")){profileText=profile.changed("effective_from",it)}}
                    for((key,label) in listOf("monthly_basic" to "Monthly basic (INR)","monthly_gross" to "Monthly gross (INR)","basic_component" to "Basic salary component"))item{CentreText(label,profile.text(key)){profileText=profile.changed(key,it)}}
                    item{SelectField("Payroll state",profile.text("payroll_state"),listOf("Maharashtra" to "Maharashtra","Other" to "Other")){profileText=profile.changed("payroll_state",it)}}
                    for((key,label) in listOf("pf_enrolled" to "PF enrolled","pt_applicable" to "Professional Tax applies","pt_exempt" to "PT exempt"))item{Row{Checkbox(profile.optInt(key)!=0,{profileText=profile.changed(key,if(it)1 else 0)});Text(label,Modifier.padding(top=12.dp))}}
                    if(profile.optInt("pt_exempt")!=0)item{CentreText("PT exemption reason",profile.text("pt_exemption_reason")){profileText=profile.changed("pt_exemption_reason",it)}}
                    item{Text("Company PF wage cap: ₹25,000. Employer PF is separate from employee deductions. Higher-wage PF uses the applicable employee/employer arrangement.",style=MaterialTheme.typography.bodySmall)}
                    item{CentreText("Reason for payroll change",profileReason){profileReason=it}}
                    item{Button(onClick={model.resourceAction("hr_resources.save_payroll_profile",JSONObject().put("details",profile).put("reason",profileReason).put("expected_modified",profile.text("modified"))){profileReason="";model.loadPayrollProfile(employee)}},enabled=!state.busy && profileReason.trim().length>=10,modifier=Modifier.fillMaxWidth()){Text("Save payroll profile")}}
                    item{HorizontalDivider();Text("Salary preview",style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.Bold)}
                    item{CentreText("Month (YYYY-MM)",month){month=it};CentreText("Unpaid equivalent days",unpaid){unpaid=it}}
                    item{OutlinedButton(onClick={model.previewPayroll(employee,month,unpaid)},enabled=!state.busy,modifier=Modifier.fillMaxWidth()){Text("Preview calculation")}}
                    val preview=state.timePayrollPreview
                    if(preview.has("calendar_days"))item{SectionCard{Text("${preview.optInt("calendar_days")} calendar days · ${preview.text("unpaid_days")} unpaid days");Text("Salary reduction ${money(preview.optDouble("salary_reduction",0.0))}");Text("Gross after absence ${money(preview.optDouble("gross_after_absence",0.0))}");Text("Employee PF ${money(preview.optDouble("employee_pf",0.0))} · PT ${money(preview.optDouble("professional_tax",0.0))}");Text("Employer PF ${money(preview.optDouble("employer_pf",0.0))}");Text("Net before other deductions ${money(preview.optDouble("net_before_other_deductions",0.0))}",fontWeight=FontWeight.Bold);Text("Preview only. Submitted payslips remain the accounting record.",style=MaterialTheme.typography.bodySmall)}}
                    items(state.timePayroll.items("history")){row->SectionCard{Text("Effective ${row.text("effective_from")}",fontWeight=FontWeight.SemiBold);Text(row.text("reason"));Text(row.text("author"),style=MaterialTheme.typography.bodySmall)}}
                }
            }
            if(section=="edit" && data.optBoolean("can_manage")){
                val handbook=JSONObject(handbookText)
                item{Text("Employee role and reporting",style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.Bold)}
                item{SelectField("Reporting employee",roleEmployee,data.items("people").map{it.text("name") to it.text("employee_name")}){value->roleEmployee=value;model.resourceAction("hr_resources.get_employee_reporting",JSONObject().put("employee",value)){reportingText=it.toString();reportingReason=""}}}
                if(reportingText.isNotBlank()){
                    val reporting=JSONObject(reportingText)
                    item{CentreText("Designation",reporting.text("designation")){reportingText=reporting.changed("designation",it)}}
                    item{SelectField("Reporting manager",reporting.text("reports_to"),listOf("" to "No reporting manager")+data.items("people").filter{it.text("name")!=roleEmployee}.map{it.text("name") to it.text("employee_name")}){reportingText=reporting.changed("reports_to",it)}}
                    item{SelectField("Employment type",reporting.text("employment_type"),data.optJSONArray("employment_types")?.let{list->(0 until list.length()).map{list.getString(it) to list.getString(it)}}?:emptyList()){reportingText=reporting.changed("employment_type",it)}}
                    item{CentreText("Reason for employee change",reportingReason){reportingReason=it}}
                    item{Button(onClick={model.resourceAction("hr_resources.save_employee_reporting",JSONObject().put("employee",roleEmployee).put("reports_to",reporting.text("reports_to")).put("designation",reporting.text("designation")).put("employment_type",reporting.text("employment_type").takeIf{it.isNotBlank()}).put("expected_modified",reporting.text("modified")).put("reason",reportingReason)){reportingText=it.toString();reportingReason=""}},enabled=!state.busy && reportingReason.trim().length>=10,modifier=Modifier.fillMaxWidth()){Text("Save employee reporting")}}
                }
                item{Text("Edit organisation and guidance",style=MaterialTheme.typography.headlineSmall,fontWeight=FontWeight.Bold)}
                item{CentreText("Working-day availability",handbook.text("availability")){handbookText=handbook.changed("availability",it)};CentreText("Notice and exit terms",handbook.text("exit_terms")){handbookText=handbook.changed("exit_terms",it)}}
                items(handbook.items("positions")){row->
                    SectionCard{Text(row.text("name"),fontWeight=FontWeight.Bold)
                        for((key,label)in listOf("name" to "Name","title" to "Role","functional_line" to "Functional line"))CentreText(label,row.text(key)){value->
                            val rows=handbook.items("positions");val changed=org.json.JSONArray();rows.forEach{changed.put(if(it.text("id")==row.text("id"))JSONObject(row.changed(key,value))else it)};handbookText=handbook.changed("positions",changed)}
                        SelectField("Reports to position",row.text("manager_id"),listOf("" to "No direct reporting line")+handbook.items("positions").filter{it.text("id")!=row.text("id")}.map{it.text("id") to it.text("name")}){value->val changed=org.json.JSONArray();handbook.items("positions").forEach{changed.put(if(it.text("id")==row.text("id"))JSONObject(row.changed("manager_id",value))else it)};handbookText=handbook.changed("positions",changed)}
                    }
                }
                items(handbook.items("contacts")){row->SectionCard{Text(row.text("area"),fontWeight=FontWeight.Bold);for((key,label)in listOf("name" to "Contact name","title" to "Contact role","details" to "Help with"))CentreText(label,row.text(key)){value->val changed=org.json.JSONArray();handbook.items("contacts").forEach{changed.put(if(it.text("area")==row.text("area"))JSONObject(row.changed(key,value))else it)};handbookText=handbook.changed("contacts",changed)}}}
                item{CentreText("Reason for handbook change",handbookReason){handbookReason=it};Text("Use Employee role and reporting above to update actual employee records.",style=MaterialTheme.typography.bodySmall)}
                item{Button(onClick={model.resourceAction("hr_resources.save_charter",JSONObject().put("settings",handbook).put("expected_revision",data.text("revision")).put("reason",handbookReason)){handbookReason="";model.loadPeopleCentre()}},enabled=!state.busy && handbookReason.trim().length>=10,modifier=Modifier.fillMaxWidth()){Text("Publish handbook revision")}}
            }
        }
    }
}
private fun JSONObject.changed(key:String,value:Any)=JSONObject(toString()).put(key,value).toString()
@Composable private fun CentreText(label:String,value:String,change:(String)->Unit){OutlinedTextField(value,change,label={Text(label)},modifier=Modifier.fillMaxWidth(),minLines=if(label.contains("reason",true)||label.contains("availability",true))2 else 1)}

private data class GuidePoint(val label:String,val detail:String)

@Composable
private fun GuidePolicyCard(title:String,points:List<GuidePoint>) {
    SectionCard {
        Text(title,style=MaterialTheme.typography.titleMedium,fontWeight=FontWeight.SemiBold,modifier=Modifier.semantics{heading()})
        for(point in points.filter{it.detail.isNotBlank()}) {
            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(10.dp),verticalAlignment=Alignment.Top) {
                Box(Modifier.padding(top=8.dp).size(5.dp).background(MaterialTheme.colorScheme.primary,CircleShape))
                Text(buildAnnotatedString {
                    withStyle(SpanStyle(fontWeight=FontWeight.SemiBold)){append(point.label);append(": ")}
                    append(point.detail)
                },style=MaterialTheme.typography.bodyMedium,modifier=Modifier.weight(1f))
            }
        }
    }
}

private fun guideDate(value:String):String = runCatching {
    LocalDate.parse(value).format(java.time.format.DateTimeFormatter.ofPattern("d MMM yyyy",java.util.Locale.ENGLISH))
}.getOrDefault(value)

private fun peopleGuideSections(data:JSONObject):List<Pair<String,List<GuidePoint>>> {
    val p=data.optJSONObject("guide_policy")?:JSONObject()
    val settings=data.optJSONObject("settings")?:JSONObject()
    fun number(key:String,fallback:Double)=java.math.BigDecimal.valueOf(p.optDouble(key,fallback)).stripTrailingZeros().toPlainString()
    val half=number("half_day_hours",3.0);val full=number("full_day_hours",6.0)
    val leaveYear=runCatching{java.time.Month.of(p.optInt("leave_year_start_month",1)).getDisplayName(java.time.format.TextStyle.FULL,java.util.Locale.ENGLISH)}.getOrDefault("January")
    val approvals=mutableListOf(
        GuidePoint("Leave earned","${number("monthly_leave",2.5)} days each month (${java.math.BigDecimal.valueOf(p.optDouble("monthly_leave",2.5)*12).stripTrailingZeros().toPlainString()} days a year)."),
        GuidePoint("Carry-forward","Up to ${number("carry_forward_days",15.0)} days into the next leave year."),
        GuidePoint("Leave year","Begins in $leaveYear."),
        GuidePoint("Short leave","Up to ${p.optInt("short_leave_days",3)} days: give the same number of days’ notice."),
        GuidePoint("Longer leave","Give at least ${p.optInt("extended_notice_days",14)} days’ notice."),
        GuidePoint("Approval","Your reporting manager approves leave and weekly-off swaps."))
    if(p.optInt("director_approval_days",0)>0)approvals.add(GuidePoint("Extended approval","Leave above ${p.optInt("director_approval_days")} days requires Director approval."))
    val sections=mutableListOf(
        "Work logs and attendance" to listOf(
            GuidePoint("Log your work","Within ${p.optInt("work_log_days",4)} calendar days of the work date."),
            GuidePoint("Full day","$full hours or more."),
            GuidePoint("Half day","$half to under $full hours."),
            GuidePoint("Under $half hours","Unpaid unless approved leave or an HR correction covers the absence.")),
        "Paid leave and approvals" to approvals,
        "Compensatory leave" to listOf(
            GuidePoint("Credit","${number("comp_hours",6.0)}+ hours worked on an eligible day earns one day. Shorter work needs HR review."),
            GuidePoint("Use within","${p.optInt("comp_valid_months",2)} months of the eligible work date.")),
        "Medical leave" to listOf(
            GuidePoint("Inform your manager",if(p.optInt("medical_notice_days",0)==0)"The same day. Advance notice is waived for sudden illness." else "Within ${p.optInt("medical_notice_days")} days. Advance notice is waived for sudden illness."),
            GuidePoint("Medical certificate","Required before approval for more than ${p.optInt("medical_certificate_days",2)} consecutive days.")),
        "Parental leave" to listOf(
            GuidePoint("Maternity","Up to ${p.optInt("maternity_weeks",26)} paid weeks for eligible employees. HR verifies the applicable entitlement."),
            GuidePoint("Paternity","${p.optInt("paternity_days",5)} paid working days within ${p.optInt("paternity_window_months",3)} months of childbirth."),
            GuidePoint("Approval","HR verifies eligibility first; your reporting manager decides the request."),
            GuidePoint("Separate allowances","Parental leave and optional holidays do not use your annual paid-leave balance.")),
        "Salary and deductions" to listOf(
            GuidePoint("Salary calculation",if(p.optInt("calendar_day_payroll",1)==1)"Uses the actual calendar days in the month." else "Uses the configured payroll calendar."),
            GuidePoint("Amount paid","Based on approved attendance, leave and unpaid days."),
            GuidePoint("Employee PF","${number("pf_employee_rate",12.0)}% of eligible Basic for enrolled employees."),
            GuidePoint("Employer PF","Sevamrita contributes ${number("pf_employer_rate",12.0)}% separately; this is not deducted from your take-home pay."),
            GuidePoint("Company PF wage cap",if(p.optDouble("pf_wage_ceiling",25000.0)>0)money(p.optDouble("pf_wage_ceiling",25000.0)) else "No company wage cap configured."),
            GuidePoint("Maharashtra Professional Tax","The upper band is ${money(p.optDouble("pt_regular_rate",200.0))} monthly, or ${money(p.optDouble("pt_february_rate",300.0))} in February. Salary thresholds and exemptions apply."),
            GuidePoint("Enrolment","HR confirms PF enrolment and Professional Tax applicability or exemptions.")),
        "Working arrangements" to listOf(
            GuidePoint("Availability",settings.text("availability")),
            GuidePoint("Notice and exit",settings.text("exit_terms"))))
    data.optJSONObject("payroll_profile")?.let{profile->sections.add("Your payroll profile" to listOf(
        GuidePoint("Effective from",guideDate(profile.text("effective_from"))),
        GuidePoint("PF",if(profile.optInt("pf_enrolled")==1)"Enrolled." else "Not enrolled."),
        GuidePoint("Professional Tax",if(profile.optInt("pt_applicable")==1&&profile.optInt("pt_exempt")==0)"Applies." else "Not applicable or exempt.")))}
    return sections
}
