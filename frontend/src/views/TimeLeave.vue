<template>
  <div class="max-w-6xl mx-auto space-y-5">
    <PageHeader title="Time and leave" subtitle="Your leave, weekly offs and attendance requests." eyebrow="People">
      <template #actions><button v-if="(workspace.eligible || workspace.can_override) && tab !== 'policy'" class="btn-primary" @click="newRequest">New request</button></template>
    </PageHeader>
    <p v-if="error" role="alert" class="message-error">{{ error }}</p><p v-if="notice" role="status" class="message-success">{{ notice }}</p>
    <div class="flex gap-2 flex-wrap" role="tablist" aria-label="Time and leave views">
      <button v-for="item in tabs" :key="item.id" role="tab" :aria-selected="tab === item.id" :class="tab === item.id ? 'btn-primary' : 'btn-secondary'" @click="changeTab(item.id)">{{ item.label }}</button>
    </div>
    <p v-if="loading" role="status" class="text-muted">Loading time and leave…</p>
    <template v-else>
      <PeopleCentre v-if="tab === 'resources'" @request-holiday="requestHoliday" />
      <template v-else-if="tab !== 'policy'">
        <div v-if="tab === 'mine'" class="grid gap-4 sm:grid-cols-3">
          <section class="form-card"><p class="text-sm text-muted">Paid leave remaining</p><p class="text-3xl font-semibold text-ink mt-2">{{ number(workspace.paid_balance) }} <span class="text-sm font-normal">days</span></p></section>
          <section class="form-card"><p class="text-sm text-muted">Compensatory leave remaining</p><p class="text-3xl font-semibold text-accent mt-2">{{ number(workspace.comp_balance) }} <span class="text-sm font-normal">days</span></p></section>
          <section class="form-card"><p class="text-sm text-muted">Leave year</p><p class="font-semibold text-ink mt-2">{{ date(workspace.leave_year?.[0]) }} – {{ date(workspace.leave_year?.[1]) }}</p><p class="text-xs text-muted mt-2">{{ workspace.policy?.monthly_leave }} days earned each month</p></section>
        </div>
        <p v-if="tab === 'mine' && !workspace.eligible" class="form-card text-muted">Automatic attendance and leave apply to salaried employees. Work logging remains available to all active employees.</p>
        <p v-if="workspace.legacy_allocation && tab === 'mine'" class="form-card text-sm">Your existing allocation keeps its original year and accrual schedule. HR can verify its balance and adopt the calendar-year policy without granting it twice.</p>
        <section v-if="editing" class="form-card request-card space-y-4">
          <div class="flex items-center justify-between gap-3"><h2 class="form-title">New request</h2><button type="button" class="request-close" aria-label="Close form" :disabled="busy" @click="editing = false">×</button></div>
          <form @submit.prevent="submit" class="request-form space-y-4">
            <div class="form-grid">
              <label v-if="workspace.can_override" class="field-label">Employee<select v-model="form.employee" required aria-label="Employee" class="field-input"><option v-if="workspace.employee" :value="workspace.employee.name">Myself</option><option v-else value="">Choose employee</option><option v-for="person in workspace.people" :key="person.name" :value="person.name">{{ person.employee_name }}</option></select></label>
              <label class="field-label">Request type<select aria-label="Request type" v-model="form.type" class="field-input" @change="typeChanged"><option v-for="type in requestTypes" :key="type">{{ type }}</option></select></label>
              <label v-if="timeLeaveHasCategory(form.type)" class="field-label">Leave category<select aria-label="Leave category" v-model="form.category" class="field-input"><option>Normal</option><option>Emergency</option><option v-if="workspace.special_effective_from">Medical</option></select></label>
              <div class="request-date-row">
                <label class="field-label">{{ form.type === 'Weekly Off Swap' ? 'Usual off to work on' : form.type === 'Compensatory Credit' ? 'Day worked' : 'From date' }}<input v-model="form.from_date" type="date" required class="field-input" /></label>
                <label v-if="form.type !== 'Compensatory Credit' && form.type !== 'Attendance Correction'" class="field-label">{{ form.type === 'Weekly Off Swap' ? 'Alternative day off' : 'To date' }}<input v-model="form.to_date" type="date" required class="field-input" /></label>
              </div>
              <label v-if="form.type === 'Attendance Correction'" class="field-label">Correct attendance to<select v-model="form.requested_status" class="field-input"><option v-for="status in attendanceStatuses" :key="status">{{ status }}</option></select></label>
              <label v-if="isLeave && !['Maternity Leave','Paternity Leave','Optional Holiday'].includes(form.type)" class="flex gap-2 items-center text-sm"><input v-model="form.half_day" type="checkbox" /> Include a half day</label>
              <label v-if="timeLeaveHasCategory(form.type) && form.half_day" class="field-label">Half-day date<input v-model="form.half_day_date" type="date" required class="field-input" /></label>
              <label v-if="timeLeaveHasCategory(form.type) && form.category === 'Medical'" class="field-label">Manager informed on<input v-model="form.manager_notified_on" type="date" :max="workspace.today" required class="field-input" /></label>
              <label v-if="['Maternity Leave','Paternity Leave'].includes(form.type)" class="field-label">Expected or actual childbirth date<input v-model="form.childbirth_date" type="date" required class="field-input" /></label>
              <label v-if="form.type === 'Maternity Leave'" class="field-label">Parental leave case<select aria-label="Parental leave case" v-model="form.parental_case" class="field-input"><option>Birth</option><option>Two or more surviving children</option><option>Adoption or commissioning</option></select></label>
              <div v-if="isLeave && (form.category === 'Medical' || ['Maternity Leave','Paternity Leave'].includes(form.type))" class="sm:col-span-2 space-y-2"><label class="field-label">Private supporting certificate<input type="file" accept=".pdf,.png,.jpg,.jpeg" :disabled="busy" class="field-input" @change="selectCertificate($event,false)" /></label><a v-if="form.certificate_url" :href="form.certificate_url" target="_blank" class="text-sm text-accent underline">View uploaded certificate</a><p class="text-xs text-muted">PDF, PNG or JPEG, up to 5 MB. Medical certificates are required before approval for more than two consecutive days. HR verifies parental eligibility separately.</p></div>
              <label class="field-label sm:col-span-2">Reason<textarea v-model.trim="form.reason" minlength="10" maxlength="2000" rows="3" required class="field-input" placeholder="Explain the request so your manager can decide."></textarea></label>
            </div>
            <p v-if="['Maternity Leave','Paternity Leave','Optional Holiday'].includes(form.type) || form.category === 'Medical'" class="text-sm text-muted">Revised entitlement rules apply to dates from {{workspace.special_effective_from}}.</p>
            <p v-if="form.type === 'Compensatory Credit'" class="text-sm text-muted">The server checks your submitted work log. At least {{ workspace.policy?.comp_hours }} hours earns one day; shorter work goes to HR. Credit expires after {{ workspace.policy?.comp_valid_months }} month(s).</p>
            <details v-if="workspace.can_override" class="rounded-xl border border-line p-4"><summary class="font-medium text-ink cursor-pointer">HR exception</summary><label class="field-label mt-3">Exception reason<textarea v-model.trim="form.hr_exception_reason" rows="2" minlength="10" maxlength="2000" class="field-input" placeholder="Required for late requests or submitting on another employee’s behalf."></textarea></label></details>
            <div class="flex items-center justify-end gap-3"><button type="button" class="btn-secondary" :disabled="busy" @click="editing = false">Cancel</button><button class="btn-primary" :disabled="busy">{{ busy ? 'Saving request…' : 'Submit request' }}</button></div>
          </form>
        </section>
        <section v-if="selected" class="form-card space-y-4">
          <div class="flex justify-between gap-3"><div><h2 class="form-title mb-1">{{ selected.type }}</h2><p class="text-sm text-muted">{{ selected.employee_name }} · {{ selected.name }}</p></div><button class="btn-secondary" :disabled="busy" @click="selected = null">Close</button></div>
          <p class="font-medium">{{ requestDates(selected) }} · {{ selected.status }}</p><p class="whitespace-pre-wrap">{{ selected.reason }}</p>
          <p v-if="selected.hr_exception_reason" class="text-sm rounded-lg bg-amber-50 p-3">HR exception: {{ selected.hr_exception_reason }}</p>
          <p v-if="selected.decision_reason" class="text-sm text-muted">Decision: {{ selected.decision_reason }}</p>
          <div v-if="selected.certificate_url" class="text-sm"><a :href="selected.certificate_url" target="_blank" class="text-accent underline">Open private supporting certificate</a></div>
          <p v-if="selected.childbirth_date" class="text-sm">Childbirth date: {{date(selected.childbirth_date)}} · {{selected.parental_case}}</p>
          <p v-if="selected.eligibility_verified_by" class="text-sm rounded-lg bg-soft p-3">Eligibility verified by {{selected.eligibility_verified_by}}: {{selected.eligibility_reason}}</p>
          <label v-if="selected.can_attach_certificate" class="field-label">Attach supporting certificate<input type="file" accept=".pdf,.png,.jpg,.jpeg" class="field-input" :disabled="busy" @change="selectCertificate($event,true)" /></label>
          <div v-if="selected.can_verify_eligibility" class="space-y-3 rounded-xl border border-line p-4"><p class="text-sm">Verify the applicable parental entitlement and eligibility. For maternity, check the qualifying service/work record and birth, adoption or commissioning circumstances.</p><label class="field-label">HR eligibility verification notes<textarea v-model.trim="eligibilityReason" minlength="10" rows="2" class="field-input"></textarea></label><button class="btn-secondary" :disabled="busy || eligibilityReason.length < 10" @click="verifyEligibility">Verify parental eligibility</button></div>
          <template v-if="selected.can_decide || selected.can_cancel || selected.can_reverse">
            <div v-if="selected.type === 'Compensatory Credit' && workspace.can_override" class="form-grid"><label class="field-label">Credit days<select v-model.number="decision.credit_days" class="field-input"><option :value="0">Choose after review</option><option :value="0.5">Half day</option><option :value="1">One day</option></select></label><label class="field-label">Valid until<input v-model="decision.valid_until" type="date" class="field-input" /></label></div>
            <label class="field-label">Decision / cancellation reason<textarea v-model.trim="decision.reason" rows="2" class="field-input" maxlength="2000"></textarea></label>
            <label v-if="workspace.can_override" class="field-label">HR exception reason <span class="font-normal text-muted">Required to waive policy or change credit</span><textarea v-model.trim="decision.override" rows="2" class="field-input" maxlength="2000"></textarea></label>
            <div class="flex flex-wrap gap-3 justify-end"><button v-if="selected.can_cancel" class="btn-secondary" :disabled="busy || decision.reason.length < 10" @click="decide('cancel')">Cancel request</button><button v-if="selected.can_reverse" class="btn-secondary" :disabled="busy || decision.reason.length < 10" @click="decide('reverse')">Reverse approval</button><button v-if="selected.can_decide" class="btn-secondary" :disabled="busy || decision.reason.length < 10" @click="decide('reject')">Reject</button><button v-if="selected.can_decide" class="btn-primary" :disabled="busy" @click="decide('approve')">Approve</button></div>
          </template>
        </section>
        <div class="flex flex-wrap gap-3"><label class="field-label min-w-40">Status<select v-model="status" class="field-input"><option value="">All requests</option><option>Open</option><option>Approved</option><option>Rejected</option><option>Cancelled</option></select></label><label v-if="tab === 'team'" class="field-label flex-1">Employee<select v-model="employeeFilter" class="field-input" @change="load"><option value="">All team members</option><option v-for="person in workspace.people" :key="person.name" :value="person.name">{{ person.employee_name }}</option></select></label></div>
        <div class="space-y-3"><button v-for="request in filteredRequests" :key="request.doctype + request.name" type="button" class="form-card w-full text-left hover:border-accent transition-colors" @click="openRequest(request)"><div class="flex justify-between gap-3"><div><h3 class="font-semibold text-ink">{{ request.type }}</h3><p class="text-sm text-muted mt-1">{{ tab === 'team' ? request.employee_name + ' · ' : '' }}{{ requestDates(request) }}</p></div><span class="text-sm font-medium" :class="request.status === 'Open' ? 'text-amber-700' : 'text-accent'">{{ request.status }}</span></div><p class="text-sm mt-3 line-clamp-2">{{ request.reason }}</p><p v-if="request.requires_hr && request.status === 'Open'" class="text-xs text-amber-700 mt-2">HR decision required</p></button><p v-if="!filteredRequests.length" class="form-card text-muted text-center">No requests match this view.</p></div>
        <section v-if="tab === 'mine' && workspace.credits?.length" class="form-card"><h2 class="form-title">Compensatory credits</h2><div v-for="credit in workspace.credits" :key="credit.name" class="py-3 border-t border-line flex flex-wrap justify-between gap-2 text-sm"><span>Worked {{ date(credit.from_date) }} · {{ number(credit.credit_days) }} day(s)</span><span>{{ number(credit.available) }} available · valid through {{ date(credit.valid_until) }}</span></div></section>
      </template>
      <template v-else>
        <section class="form-card space-y-5"><div><h2 class="form-title mb-1">HR policy</h2><p class="text-sm text-muted">Changes take effect on the chosen date. Past records keep their history; exceptions and balance corrections are recorded separately.</p></div>
          <form @submit.prevent="publish" class="space-y-6">
            <fieldset v-for="group in policyGroups" :key="group.title" class="space-y-4"><legend class="font-semibold text-ink mb-3">{{ group.title }}</legend><div class="form-grid"><label v-for="key in group.keys" :key="key" :class="booleanKeys.includes(key) ? 'flex gap-3 items-center text-sm py-2' : 'field-label'"><template v-if="booleanKeys.includes(key)"><input v-model="policyForm[key]" type="checkbox" :true-value="1" :false-value="0" />{{ policyWorkspace.labels?.[key] }}</template><template v-else>{{ policyWorkspace.labels?.[key] }}<select :aria-label="policyWorkspace.labels?.[key]" v-if="weekdayKeys.includes(key)" v-model.number="policyForm[key]" class="field-input"><option v-for="(day, index) in weekdays" :key="day" :value="index">{{ day }}</option></select><select :aria-label="policyWorkspace.labels?.[key]" v-else-if="key === 'leave_year_start_month'" v-model.number="policyForm[key]" class="field-input"><option v-for="(month, index) in months" :key="month" :value="index + 1">{{ month }}</option></select><input v-else v-model.number="policyForm[key]" type="number" :step="decimalKeys.includes(key) ? '0.25' : '1'" min="0" required class="field-input" /></template></label></div></fieldset>
            <p class="text-sm text-muted">Annual entitlement at this rate: {{ number(Number(policyForm.monthly_leave) * 12) }} days. Policy changes do not re-credit elapsed months.</p>
            <div class="form-grid"><label class="field-label">Effective from<input v-model="effectiveFrom" type="date" :min="workspace.today" required class="field-input" /></label><label class="field-label">Reason for change<textarea v-model.trim="policyReason" rows="2" required minlength="10" maxlength="2000" class="field-input"></textarea></label></div>
            <div class="flex justify-end"><button class="btn-primary" :disabled="busy">{{ busy ? 'Publishing…' : 'Publish policy revision' }}</button></div>
          </form>
        </section>
        <section class="form-card space-y-4"><h2 class="form-title">Employee balance and leave-year adoption</h2><label class="field-label">Employee<select aria-label="Employee" v-model="balanceEmployee" class="field-input" @change="balancePreview = null"><option value="">Choose employee</option><option v-for="person in workspace.people" :key="person.name" :value="person.name">{{ person.employee_name }}</option></select></label><button class="btn-secondary" :disabled="!balanceEmployee || busy" @click="previewBalance">Preview current balance</button>
          <template v-if="balancePreview"><div class="rounded-xl bg-slate-50 p-4 space-y-1 text-sm"><p>Current balance: <strong>{{ number(balancePreview.balance) }} days</strong></p><p>Current allocation: {{ date(balancePreview.allocation?.from_date) }} – {{ date(balancePreview.allocation?.to_date) }}</p><p v-if="balancePreview.has_future_leave" class="text-amber-700">Resolve open or future approved leave before adopting a different year.</p></div><label class="field-label">Reason<textarea v-model.trim="balanceReason" rows="2" minlength="10" maxlength="2000" class="field-input"></textarea></label><div class="form-grid"><label class="field-label">Adjust by days <span class="font-normal">Use a negative number to reduce</span><input v-model.number="balanceAdjustment" type="number" step="0.25" class="field-input" /></label><div class="flex items-end"><button class="btn-primary" :disabled="busy || balanceReason.length < 10 || !balanceAdjustment" @click="adjustBalance">Post balance adjustment</button></div></div><div v-if="balancePreview.needs_adoption" class="border-t border-line pt-5 space-y-3"><p class="text-sm">Adoption closes the old allocation as of yesterday, retains its past entries, and starts a new allocation today through the end of the configured leave year. Verify the opening amount before continuing.</p><label class="field-label">Verified opening balance<input v-model.number="openingBalance" type="number" step="0.25" class="field-input" /></label><label class="flex gap-2 text-sm items-start"><input v-model="confirmAdoption" type="checkbox" class="mt-1" /> I checked the opening balance and understand this changes the allocation period.</label><button class="btn-secondary" :disabled="busy || !confirmAdoption || balanceReason.length < 10 || balancePreview.has_future_leave" @click="adoptYear">Adopt leave year with this opening balance</button></div></template>
        </section>
        <section class="form-card"><h2 class="form-title">Policy history</h2><div v-for="revision in policyWorkspace.history" :key="revision.name" class="border-t border-line py-4"><div class="flex justify-between gap-3"><strong class="text-sm">Effective {{ date(revision.effective_from) }}</strong><span class="text-xs text-muted">{{ revision.published_by }}</span></div><p class="text-sm mt-2">{{ revision.reason }}</p><details class="text-sm text-muted mt-2"><summary class="cursor-pointer">View values</summary><dl class="grid sm:grid-cols-2 gap-2 mt-3"><div v-for="(value, key) in parsed(revision.settings)" :key="key"><dt>{{ policyWorkspace.labels?.[key] || key }}</dt><dd class="text-ink">{{ weekdayKeys.includes(key) ? weekdays[value] : key === 'leave_year_start_month' ? months[value - 1] : value }}</dd></div></dl></details><button class="btn-secondary mt-3" :disabled="busy" @click="useRevision(revision)">Use as starting values</button></div></section>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute } from 'vue-router';
import PeopleCentre from './PeopleCentre.vue';
import {timeLeaveHasCategory, timeLeaveCategory} from "../lib/timeLeaveForm.js";
import PageHeader from '../components/PageHeader.vue';
import { call } from '../lib/frappe';
const API = 'volunteering.volunteering.time_leave_portal.', POLICY = 'volunteering.volunteering.hr_policy.', BALANCE = 'volunteering.volunteering.hr_leave_balances.';
const route = useRoute(), workspace = ref({}), policyWorkspace = ref({}), policyForm = reactive({}), tab = ref(route.query.view === 'team' ? 'team' : route.query.view === 'policy' ? 'policy' : 'mine');
const loading = ref(true), busy = ref(false), error = ref(''), notice = ref(''), editing = ref(false), selected = ref(null), status = ref(''), employeeFilter = ref('');
const eligibilityReason=ref('');
const form = reactive({}), decision = reactive({reason:'', override:'', credit_days:1, valid_until:''});
let requestKey = ''; const newKey = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), x => x.toString(16).padStart(2,'0')).join('');
const types = ['Privilege Leave','Compensatory Leave','Leave Without Pay','Weekly Off Swap','Compensatory Credit','WFH','Attendance Correction'];
const attendanceStatuses = ['Present','Half Day','Absent','Holiday','Work From Home'];
const weekdays = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
const weekdayKeys = ['weekly_off_day','swap_off_day','swap_notice_weekday'], booleanKeys = ['comp_half_day_enabled','allow_negative_paid_leave','apply_to_unpaid','attendance_based_payroll','calendar_day_payroll','charter_enabled'], decimalKeys = ['monthly_leave','carry_forward_days','full_day_hours','half_day_hours','comp_hours','pf_employee_rate','pf_employer_rate'];
const policyGroups = [
  {title:'Work week and logging',keys:['weekly_off_day','swap_off_day','swap_notice_weekday','work_log_days','half_day_hours','full_day_hours','attendance_based_payroll','calendar_day_payroll']},
  {title:'Compensatory leave',keys:['comp_hours','comp_valid_months','comp_half_day_enabled']},
  {title:'Accrual and leave year',keys:['monthly_leave','carry_forward_days','leave_year_start_month','allow_negative_paid_leave','apply_to_unpaid']},
  {title:'Parental and optional leave',keys:['maternity_weeks','paternity_days','paternity_window_months','optional_holidays','medical_certificate_days','medical_notice_days']},
  {title:'Payroll deductions',keys:['pf_employee_rate','pf_employer_rate','pf_wage_ceiling','pt_male_lower','pt_male_upper','pt_female_exempt','pt_middle_rate','pt_regular_rate','pt_february_rate']},
  {title:'Notice and emergency leave',keys:['short_leave_days','extended_notice_days','emergency_max_days','emergency_regularize_hours','director_approval_days']},
];
const effectiveFrom = ref(''), policyReason = ref(''), balanceEmployee = ref(''), balancePreview = ref(null), balanceAdjustment = ref(0), openingBalance = ref(0), balanceReason = ref(''), confirmAdoption = ref(false);
let balanceKey = newKey(), adoptionKey = newKey();
const tabs = computed(() => [{id:'mine',label:'My requests'}, {id:'resources',label:'People centre'}, ...(workspace.value.can_review ? [{id:'team',label:'Team review'}] : []), ...(workspace.value.can_override ? [{id:'policy',label:'HR policy & balances'}] : [])]);
const filteredRequests = computed(() => (workspace.value.requests || []).filter(x => !status.value || x.status === status.value));
const requestTypes = computed(()=>workspace.value.request_types || types);
const isLeave = computed(() => ['Privilege Leave','Compensatory Leave','Leave Without Pay','Maternity Leave','Paternity Leave','Optional Holiday'].includes(form.type));
function requestHoliday(day){tab.value='mine';newRequest();form.type='Optional Holiday';form.from_date=day;form.to_date=day;}
const parsed = value => typeof value === 'string' ? JSON.parse(value) : value;
const number = value => Number(value || 0).toLocaleString('en-IN',{maximumFractionDigits:3});
const date = value => value ? new Intl.DateTimeFormat('en-IN',{dateStyle:'medium'}).format(new Date(value)) : '—';
const requestDates = row => row.type === 'Weekly Off Swap' ? 'Work: ' + date(row.from_date) + ' · Off: ' + date(row.to_date) : date(row.from_date) + (row.from_date !== row.to_date ? ' – ' + date(row.to_date) : '');
onMounted(async()=>{await load();if(route.query.type && (workspace.value.eligible || workspace.value.can_override))newRequest();});
async function load(){loading.value = true; error.value = '';try {workspace.value = await call(API+'get_time_workspace',{view:tab.value === 'team' ? 'team' : 'mine',employee:employeeFilter.value});if(tab.value === 'policy'){policyWorkspace.value = await call(POLICY+'get_hr_policy_workspace');Object.assign(policyForm,policyWorkspace.value.policy);effectiveFrom.value = workspace.value.today;}}catch(e){error.value=e.message;}finally{loading.value=false;}}
async function changeTab(value){if(busy.value)return;tab.value=value;editing.value=false;selected.value=null;await load();}
function newRequest(){Object.assign(form,{employee:workspace.value.employee?.name,type:types.includes(route.query.type) ? route.query.type : 'Privilege Leave',category:'Normal',from_date:workspace.value.today,to_date:workspace.value.today,half_day:false,half_day_date:workspace.value.today,reason:'',requested_status:'Present',hr_exception_reason:'',manager_notified_on:workspace.value.today,childbirth_date:'',parental_case:'Birth',certificate_url:''});requestKey=newKey();editing.value=true;selected.value=null;}
function typeChanged(){form.category=timeLeaveCategory(form.type,form.category);if(!timeLeaveHasCategory(form.type))form.half_day=false;if(['Compensatory Credit','Attendance Correction'].includes(form.type))form.to_date=form.from_date;}
async function operation(fn){if(busy.value)return;busy.value=true;error.value='';notice.value='';try{await fn();}catch(e){error.value=e.message;}finally{busy.value=false;}}
async function submit(){await operation(async()=>{const payload={...form};if(['Compensatory Credit','Attendance Correction'].includes(payload.type))payload.to_date=payload.from_date;const row=await call(API+'submit_time_request',{details:payload,request_key:requestKey});editing.value=false;await load();openRequest(row);notice.value='Request saved and sent for review.';});}
function openRequest(row){eligibilityReason.value='';selected.value=row;Object.assign(decision,{reason:'',override:'',credit_days:Number(row.days || 0),valid_until:row.valid_until || ''});}
async function decide(action){await operation(async()=>{await call(API+'decide_time_request',{doctype:selected.value.doctype,name:selected.value.name,action,expected_modified:selected.value.modified,...decision});selected.value=null;await load();notice.value='Decision recorded.';});}
async function selectCertificate(event,existing){const file=event.target.files?.[0];if(!file)return;await operation(async()=>{if(file.size>5*1024*1024)throw new Error('Choose a certificate up to 5 MB.');const content=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=reject;reader.readAsDataURL(file);});const result=await call('volunteering.volunteering.hr_special_leave.upload_certificate',{filename:file.name,content});if(existing){selected.value=await call('volunteering.volunteering.hr_special_leave.attach_certificate',{name:selected.value.name,file_url:result.file_url,expected_modified:selected.value.modified});notice.value='Private certificate attached.';}else form.certificate_url=result.file_url;});event.target.value='';}
async function verifyEligibility(){await operation(async()=>{selected.value=await call('volunteering.volunteering.hr_special_leave.verify_parental_eligibility',{name:selected.value.name,expected_modified:selected.value.modified,reason:eligibilityReason.value});eligibilityReason.value='';notice.value='Eligibility verified. The reporting manager can now decide the request.';});}
function useRevision(revision){Object.assign(policyForm,policyWorkspace.value.policy,parsed(revision.settings));effectiveFrom.value=revision.effective_from < workspace.value.today ? workspace.value.today : revision.effective_from;policyReason.value="";window.scrollTo({top:0,behavior:"smooth"});}
async function publish(){await operation(async()=>{policyWorkspace.value=await call(POLICY+'publish_hr_policy',{values:{...policyForm},effective_from:effectiveFrom.value,reason:policyReason.value,expected_revision:policyWorkspace.value.revision,expected_publication_revision:policyWorkspace.value.publication_revision});policyReason.value='';notice.value='Dated policy revision published. Historical records were not recalculated.';});}
async function previewBalance(){await operation(async()=>{balancePreview.value=await call(BALANCE+'preview_leave_adoption',{employee:balanceEmployee.value});openingBalance.value=balancePreview.value.balance;confirmAdoption.value=false;});}
async function adjustBalance(){await operation(async()=>{await call(BALANCE+'adjust_leave_balance',{employee:balanceEmployee.value,days:balanceAdjustment.value,reason:balanceReason.value,request_key:balanceKey});balanceKey=newKey();balancePreview.value=await call(BALANCE+'preview_leave_adoption',{employee:balanceEmployee.value});balanceAdjustment.value=0;notice.value='Reasoned leave adjustment posted.';});}
async function adoptYear(){await operation(async()=>{balancePreview.value=await call(BALANCE+'adopt_leave_year',{employee:balanceEmployee.value,opening_balance:openingBalance.value,reason:balanceReason.value,expected_allocation:balancePreview.value.allocation?.name,request_key:adoptionKey});adoptionKey=newKey();confirmAdoption.value=false;notice.value='Leave year adopted with the verified opening balance.';});}
</script>

<style scoped>
.form-card { display: block; min-width: 0; padding: 1.5rem; border: 1px solid var(--line); border-radius: 1.15rem; background: var(--surface); box-shadow: var(--shadow-soft); }
button.form-card { width: 100%; text-align: left; transition: border-color .15s, box-shadow .15s; }
button.form-card:hover { border-color: var(--accent); box-shadow: 0 3px 14px rgb(0 0 0 / .05); }
.form-title { margin: 0; color: var(--ink); font-size: 1.15rem; font-weight: 700; line-height: 1.4; }
.form-grid { background: transparent; border: 0; padding: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1.25rem; min-width: 0; }
.request-card { padding: 1.1rem 1.25rem; }
.request-form .form-grid { gap: .85rem 1rem; }
.request-form .field-input { min-height: 2.6rem; margin-top: .3rem; padding: .5rem .7rem; }
.request-form textarea.field-input { min-height: 5rem; }
.request-date-row { grid-column: 1 / -1; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .75rem; }
.request-close { display: grid; place-items: center; min-width: 2.75rem; min-height: 2.75rem; border-radius: .65rem; color: var(--muted); font-size: 1.5rem; }
.request-close:hover { background: var(--soft); color: var(--ink); }
.field-label { background: transparent; border: 0; padding: 0; border-radius: 0; display: flex; flex-direction: column; min-width: 0; color: var(--ink); font-size: .875rem; font-weight: 600; line-height: 1.5; }
.field-input { display: block; width: 100%; min-width: 0; min-height: 2.9rem; margin-top: .45rem; padding: .7rem .85rem; border: 1px solid var(--line); border-radius: .7rem; background: var(--surface); color: var(--ink); font-size: .925rem; font-weight: 400; line-height: 1.45; }
textarea.field-input { resize: vertical; min-height: 5.5rem; }
.field-input:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
fieldset { margin: 0; padding: 0 0 1.5rem; border: 0; border-bottom: 1px solid var(--line); border-radius: 0; background: transparent; }
fieldset > legend { float: none; width: auto; margin: 0 0 1rem; padding: 0; border: 0; font-size: 1rem; line-height: 1.4; }
input[type=checkbox] { width: 1.05rem; height: 1.05rem; flex: none; accent-color: var(--accent); }
.message-error, .message-success { padding: .85rem 1rem; border: 1px solid; border-radius: .8rem; font-size: .875rem; line-height: 1.5; }
.message-error { border-color: var(--bad); background: var(--bad-soft); color: var(--bad); }
.message-success { border-color: var(--ok); background: var(--ok-soft); color: var(--ink); }
[role=tablist] { padding-bottom: .25rem; }
[role=tab] { min-height: 2.6rem; }
p, dd { overflow-wrap: anywhere; }
@media (max-width: 640px) {
  .form-card { padding: 1.1rem; border-radius: 1rem; }
  .form-grid { grid-template-columns: minmax(0, 1fr); gap: 1rem; }
  .field-input { font-size: 1rem; }
  .btn-primary, .btn-secondary { min-height: 2.7rem; }
}
@media (max-width: 360px) { .request-date-row { grid-template-columns: minmax(0, 1fr); } }
</style>
