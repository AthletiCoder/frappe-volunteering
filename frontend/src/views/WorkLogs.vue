<template>
	<div class="work-log-page mx-auto max-w-5xl space-y-4 pb-4">
        <PageHeader :title="pageTitle">
            <template v-if="editing" #actions><RouterLink :to="{ path: '/work-logs', query: calendarQuery }" class="text-sm font-medium text-accent">← Calendar</RouterLink></template>
        </PageHeader>
		<p v-if="error" role="alert" class="message-error">{{ error }}</p>
		<p v-if="message" role="status" class="message-success">{{ message }}</p>
		<p v-if="loading" role="status" class="text-muted">Loading work logs…</p>
		<template v-else-if="workspace">
			<template v-if="!editing">
                <template v-if="listView === 'team' && !route.query.employee">
                    <section class="card space-y-4">
                        <div><h2 class="text-xl font-semibold text-ink">Your team</h2><p class="mt-2 text-sm text-muted">Select a person to view their monthly calendar and review their work.</p><p v-if="workspace.month" class="mt-2 text-sm font-medium text-ink">{{ monthLabel(workspace.month) }}</p></div>
                        <form class="flex gap-3" @submit.prevent="searchPeople"><input v-model="peopleQuery" type="search" class="input !mt-0" aria-label="Search team" placeholder="Search by name" /><button class="btn-secondary" :disabled="busy">Search</button></form>
                    </section>
                    <p v-if="!workspace.people?.length" class="card text-muted">No employees match this view.</p>
                    <button v-for="person in workspace.people" :key="person.name" class="person-card" :disabled="busy" @click="openPerson(person)">
                        <span class="person-avatar">{{ person.employee_name.slice(0, 1) }}</span>
                        <span class="min-w-0 flex-1 text-left"><strong class="block text-ink">{{ person.employee_name }}</strong><span class="mt-1 block text-sm text-muted">{{ person.designation || person.name }}</span><span class="mt-2 block text-sm text-muted">{{ hoursLabel(person.total_hours) }} h recorded<span v-if="person.submitted"> · {{ person.submitted }} awaiting review</span></span></span><span class="text-accent" aria-hidden="true">→</span>
                    </button>
                    <div v-if="workspace.page > 1 || workspace.has_more" class="flex items-center justify-between"><button class="btn-secondary" :disabled="busy || workspace.page === 1" @click="peoplePage(workspace.page - 1)">Previous</button><span>Page {{ workspace.page }}</span><button class="btn-secondary" :disabled="busy || !workspace.has_more" @click="peoplePage(workspace.page + 1)">Next</button></div>
                </template>
                <template v-else-if="workspace.days">
                    <div v-if="listView === 'team'" class="flex flex-wrap items-center justify-between gap-3"><h2 class="text-xl font-semibold text-ink">{{ workspace.calendar_employee.employee_name }}</h2><button class="btn-secondary" @click="changeView('team')">Back to team</button></div>
                    <section class="calendar-panel space-y-3" aria-label="Work log calendar">
                        <div class="flex items-center justify-between gap-2">
                            <button class="month-arrow" aria-label="Previous month" :disabled="busy" @click="changeMonth(offsetMonth(workspace.month, -1))">‹</button>
                            <div class="flex items-center gap-3"><label class="sr-only" for="log-month">Month</label><input id="log-month" type="month" :value="workspace.month" :max="workspace.today.slice(0, 7)" class="month-input" :disabled="busy" @change="changeMonth($event.target.value)" /><button class="text-xs text-accent" :disabled="busy" @click="changeMonth(workspace.today.slice(0, 7))">This month</button></div>
                            <button class="month-arrow" aria-label="Next month" :disabled="busy || workspace.month >= workspace.today.slice(0, 7)" @click="changeMonth(offsetMonth(workspace.month, 1))">›</button>
                        </div>
                        <div class="calendar-grid">
                            <span v-for="day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']" :key="day" class="weekday">{{ day }}</span>
                            <template v-for="(date, index) in dates" :key="date || 'empty-' + index">
                                <button v-if="date" :data-date="date" :aria-label="dayLabel(dayMap[date])" :title="dayMap[date]?.day_note || ''" :disabled="busy || !dayMap[date]?.can_open" :class="['calendar-day', dayClass(dayMap[date]?.status), { today: date === workspace.today }]" @click="openDay(dayMap[date])"><span class="day-number">{{ Number(date.slice(8)) }}</span><span class="day-hours">{{ dayMap[date]?.total_hours != null ? hoursLabel(dayMap[date].total_hours) + ' h' : dayMap[date]?.status === 'Holiday' ? 'Off' : dayMap[date]?.status === 'On leave' ? 'Leave' : '—' }}</span></button>
                                <span v-else class="calendar-empty" aria-hidden="true"></span>
                            </template>
                        </div>
                        <div class="flex flex-wrap gap-x-5 gap-y-3 text-xs"><span v-for="status in statuses" :key="status" class="inline-flex items-center gap-2"><span :class="['legend-dot', dayClass(status)]"></span>{{ status }}</span></div>
                    </section>
                    <section class="summary-row" aria-label="Monthly summary"><div><strong>{{ durationLabel(workspace.summary.total_hours) }}</strong><span>Total time</span></div><div><strong>{{ workspace.summary.submitted_total ?? workspace.summary.Submitted + workspace.summary.Reviewed }}</strong><span>Submitted</span></div><div><strong>{{ workspace.summary.awaiting_review ?? workspace.summary.Submitted }}</strong><span>Awaiting review</span></div><div><strong>{{ workspace.summary.Reviewed }}</strong><span>Reviewed</span></div></section>
                </template>
			</template>
            <template v-else-if="log">
                <div class="flex flex-wrap items-center gap-3">
                    <h2 v-if="!log.is_own" class="w-full font-semibold text-ink">{{ log.employee_name }}</h2>
                    <label class="date-button"><span aria-hidden="true">▦</span> {{ dateLabel(form.date) }}<input v-model="form.date" type="date" aria-label="Work date" :min="workspace.can_override ? undefined : workspace.earliest_date" :max="workspace.today" :disabled="!log.can_edit || !!log.name || busy" @change="switchDate" /></label>
                    <span :class="['status', statusClass(log.status)]">{{ log.status }}</span>
                    <span v-if="log.is_wfh" class="text-xs text-accent">Work from home</span>
                </div>
                <form ref="logForm" id="work-log-form" class="space-y-3" @submit.prevent="save(false)">
                    <section v-for="(item, index) in form.items" :key="item.key" class="activity-card space-y-3">
                        <div class="flex items-center justify-between gap-2"><h2 class="font-semibold text-ink">{{ log.can_edit ? 'Activity ' + (index + 1) : item.task_title }}</h2><div v-if="log.can_edit" class="worklog-time-picker" :aria-label="'Time spent on activity ' + (index + 1)"><label><span class="sr-only">Hours</span><select aria-label="Hours" v-model.number="item.duration_hours" :disabled="busy" @change="changeDuration(item)"><option v-for="h in 25" :key="h - 1" :value="h - 1">{{ h - 1 }} h</option></select></label><label><span class="sr-only">Minutes</span><select aria-label="Minutes" v-model.number="item.duration_minutes" :disabled="busy || item.duration_hours === 24" @change="changeDuration(item)"><option v-for="m in 60" :key="m - 1" :value="m - 1">{{ m - 1 }} min</option></select></label></div><strong v-else class="whitespace-nowrap text-sm text-accent">{{ durationLabel(item.time_spent_hours) }}</strong><button v-if="log.can_edit && form.items.length > 1" type="button" class="remove-activity" :disabled="busy" :aria-label="'Remove activity ' + (index + 1)" @click="form.items.splice(index, 1)">×</button></div>
                        <template v-if="log.can_edit">
                            <label class="label">Activity *<input v-model.trim="item.task_title" required maxlength="140" class="input" :disabled="busy" placeholder="What did you work on?" /></label>
                            <label class="sr-only" :for="'project-' + item.key">Project</label><select :id="'project-' + item.key" v-model="item.project" class="project-input" :disabled="busy"><option value="">General work</option><option v-if="item.project && !workspace.projects.some(p => p.name === item.project)" :value="item.project">{{ item.project_name || item.project }}</option><option v-for="project in workspace.projects" :key="project.name" :value="project.name">{{ project.project_name }}</option></select>
                            <label class="label">Details *<textarea :value="workLogDetails(item.description, item.output_link)" @input="setDetails(item, $event.target.value)" required minlength="11" maxlength="4000" rows="2" class="input" :disabled="busy" placeholder="Describe the work and what was completed." /></label>
                        </template>
                        <template v-else><p class="whitespace-pre-wrap text-sm leading-relaxed text-ink">{{ workLogDetails(item.description, item.output_link) }}</p><p class="text-xs text-muted">{{ item.project_name || 'General work' }}</p></template>
                    </section>
                    <label v-if="log.can_edit && workspace.can_override" class="field-label">HR exception reason <span class="font-normal text-muted">Required for late or on-behalf entries</span><textarea v-model="form.hr_exception_reason" minlength="10" maxlength="2000" rows="2" class="field-input"></textarea></label><div v-if="log.can_edit" class="flex gap-5"><button type="button" class="text-sm font-medium text-accent" :disabled="busy || form.items.length >= 100" @click="form.items.push(emptyItem())">+ Add activity</button><button v-if="!showNotes && !form.notes" type="button" class="text-sm font-medium text-accent" @click="showNotes = true">+ Add notes</button></div>
                    <label v-if="log.can_edit && (showNotes || form.notes)" class="label">Notes (optional)<textarea v-model.trim="form.notes" rows="2" maxlength="4000" class="input" :disabled="busy" /></label>
                    <div v-else-if="form.notes" class="activity-card"><h2 class="text-sm font-semibold">Notes</h2><p class="mt-2 whitespace-pre-wrap text-sm">{{ form.notes }}</p></div>
                </form>
                <section v-if="log.can_review" class="activity-card space-y-3"><h2 class="font-semibold text-ink">Manager review</h2><label class="label">Private review notes<textarea v-model="remarks" maxlength="4000" rows="2" class="input" :disabled="busy" placeholder="Visible to managers and HR" /></label></section>
                <section v-else-if="log.manager_remarks" class="activity-card"><h2 class="font-semibold text-ink">Private review notes</h2><p class="mt-3 whitespace-pre-wrap text-sm text-muted">{{ log.manager_remarks }}</p></section>
                <footer class="form-footer"><p class="text-sm font-medium text-ink">{{ form.items.length }} {{ form.items.length === 1 ? 'activity' : 'activities' }} · {{ durationLabel(totalHours) }}</p><div v-if="log.can_edit" class="mt-2 flex gap-3"><button type="submit" form="work-log-form" class="btn-secondary flex-1" :disabled="busy">Save draft</button><button type="button" class="btn-primary flex-1" :disabled="busy" @click="submitForm">{{ busy ? 'Saving…' : 'Submit log' }}</button></div><button v-else-if="log.can_review" class="btn-primary mt-2 w-full" :disabled="busy" @click="review">Mark as reviewed</button></footer>
            </template>
        <nav v-if="!editing && workspace.can_review_team" class="view-tabs" aria-label="Work log views">
            <button v-if="workspace.can_create" :class="{ selected: listView === 'mine' }" :aria-current="listView === 'mine' ? 'page' : undefined" :disabled="busy" @click="changeView('mine')">My logs</button>
            <button :class="{ selected: listView === 'team' }" :aria-current="listView === 'team' ? 'page' : undefined" :disabled="busy" @click="changeView('team')">Team review</button>
        </nav>
		</template>
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from "vue";
import { RouterLink, onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import { call } from "../lib/frappe";
import { monthDates, offsetMonth, hoursLabel, durationMinutes, durationHours, durationLabel, workLogDetails } from "../lib/workLogCalendar";

const API = "volunteering.volunteering.work_log_portal.";
const route = useRoute(), router = useRouter();
const workspace = ref(null), access = ref(null), loading = ref(true), busy = ref(false), error = ref(""), message = ref("");
const form = reactive({ date: "", notes: "", items: [] });
const peopleQuery = ref("");
const logForm = ref(null), showNotes = ref(false);
const remarks = ref(""), original = ref("");
const editing = computed(() => Boolean(route.query.log || route.query.new));
const log = computed(() => workspace.value?.log);
const pageTitle = computed(() => (editing.value ? !log.value?.is_own && !!log.value : listView.value === "team") ? "Team work log" : "My work log");
const listView = computed(() => route.query.view === "team" ? "team" : "mine");
const calendarQuery = computed(() => ({ view: listView.value, month: route.query.month || workspace.value?.month || form.date.slice(0, 7) || undefined, employee: listView.value === "team" ? route.query.employee : undefined }));
const dates = computed(() => monthDates(workspace.value?.month || ""));
const dayMap = computed(() => Object.fromEntries((workspace.value?.days || []).map(day => [day.date, day])));
const statuses = ["Not filled", "Draft", "Submitted", "Reviewed", "Holiday", "On leave"];
const dayClass = status => ({ "Not filled": "day-missing", Draft: "day-draft", Submitted: "day-submitted", Reviewed: "day-reviewed" })[status] || "day-unavailable";
const dayLabel = day => day ? `${dateLabel(day.date)}, ${day.status}${day.total_hours != null ? ', ' + hoursLabel(day.total_hours) + ' hours' : ''}${day.day_note ? ', ' + day.day_note : ''}${day.cancelled ? ', cancelled log' : ''}` : "";
const totalHours = computed(() => Number(form.items.reduce((sum, item) => sum + (Number(item.time_spent_hours) || 0), 0).toFixed(6)));
const snapshot = () => JSON.stringify(form);
const dirty = computed(() => (log.value?.can_edit && original.value && snapshot() !== original.value)
    || (log.value?.can_review && remarks.value !== (log.value.manager_remarks || "")));
const emptyItem = () => ({ key: crypto.randomUUID(), task_title: "", project: "", description: "", time_spent_hours: "", duration_hours: 0, duration_minutes: 0, output_link: "" });
const dateLabel = value => new Date(String(value).slice(0, 10) + "T12:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
const monthLabel = value => new Date(value + "-01T12:00:00").toLocaleDateString("en-IN", { month: "long", year: "numeric" });
const statusClass = status => ({ Draft: "bg-soft text-muted", Submitted: "bg-accent-soft text-accent", Reviewed: "bg-ok-soft text-ok", Cancelled: "bg-bad-soft text-bad" })[status];
function apply(data) {
    workspace.value = data;
    if (data.log) {
        form.date = String(data.log.date).slice(0, 10); form.notes = data.log.notes || ""; form.hr_exception_reason = "";
        form.items = data.log.items.map(item => ({ ...emptyItem(), ...item, duration_hours: Math.floor(durationMinutes(item.time_spent_hours) / 60), duration_minutes: durationMinutes(item.time_spent_hours) % 60 }));
        showNotes.value = false;
        remarks.value = data.log.manager_remarks || ""; original.value = snapshot();
    }
}
let revision = 0;
async function load() {
    const current = ++revision;
    loading.value = !workspace.value; busy.value = true; error.value = ""; message.value = "";
    try {
        if (!access.value) access.value = await call(API + "get_work_log_access");
        if (current !== revision) return;
        if (!editing.value && !access.value.can_create && listView.value === "mine") {
            await router.replace({ path: "/work-logs", query: { view: "team" } }); return;
        }
        let data;
        if (editing.value) data = await call(API + "get_work_log", { name: route.query.log || "", date: route.query.date || "", employee: route.query.employee || "" });
        else if (listView.value === "team" && !route.query.employee) {
            peopleQuery.value = route.query.search || "";
            data = await call(API + "get_work_log_team", { month: route.query.month || "", query: peopleQuery.value, page: Number(route.query.page) || 1 });
        } else data = await call(API + "get_work_log_calendar", { month: route.query.month || "", employee: listView.value === "team" ? route.query.employee : "" });
        if (current === revision) apply(data);
    } catch (e) { if (current === revision) error.value = e.message; }
    finally { if (current === revision) { loading.value = false; busy.value = false; } }
}
function changeView(view) { router.push({ path: "/work-logs", query: { view, month: workspace.value?.month || route.query.month } }); }
function changeMonth(month) { if (month && !busy.value) router.push({ path: "/work-logs", query: { ...calendarQuery.value, month } }); }
function openPerson(person) { router.push({ path: "/work-logs", query: { view: "team", month: workspace.value.month, employee: person.name } }); }
function peoplePage(page) { router.push({ path: "/work-logs", query: { ...route.query, page } }); }
function searchPeople() { router.push({ path: "/work-logs", query: { ...route.query, search: peopleQuery.value || undefined, page: undefined } }); }
function openDay(day) {
    if (!day?.can_open || busy.value) return;
    router.push({ path: "/work-logs", query: { ...calendarQuery.value, ...(day.name ? { log: day.name } : { new: "1", date: day.date }) } });
}
function setDetails(item, value) {
    item.description = value; item.output_link = "";
}
function changeDuration(item) {
    if (item.duration_hours === 24) item.duration_minutes = 0;
    item.time_spent_hours = durationHours(item.duration_hours, item.duration_minutes);
}
function switchDate() {
    const date = form.date;
    if (dirty.value && form.items.some(item => item.task_title || item.description || item.time_spent_hours) && !window.confirm("Discard the unsaved work items and open the selected date?")) { form.date = log.value.date; return; }
    original.value = snapshot();
    router.replace({ path: "/work-logs", query: { new: "1", date, view: "mine", month: date.slice(0, 7) } });
}
async function save(submit) {
    if (busy.value) return;
    busy.value = true; error.value = ""; message.value = "";
    try {
        const data = await call(API + "save_work_log", { details: { name: log.value.name || "", modified: log.value.modified || "", date: form.date, employee: log.value.employee, hr_exception_reason: form.hr_exception_reason, notes: form.notes, items: form.items.map(({ key, project_name, duration_hours, duration_minutes, ...item }) => item) }, submit: Number(submit) });
        apply(data); message.value = submit ? "Work log submitted." : "Draft saved.";
    } catch (e) { error.value = e.message; }
    finally { busy.value = false; }
}
function submitForm() {
    if (!logForm.value?.reportValidity()) return;
    if (form.items.some(item => !(Number(item.time_spent_hours) > 0))) { error.value = "Set the time spent on each activity."; return; }
    if (totalHours.value <= 0 || totalHours.value > 24) { error.value = "Total hours must be greater than zero and at most 24."; return; }
    if (window.confirm("Submit this work log? Submitted logs are available for manager review and update attendance.")) save(true);
}
async function review() {
    busy.value = true; error.value = "";
    try { apply(await call(API + "review_work_log", { name: log.value.name, expected_modified: log.value.modified, remarks: remarks.value })); message.value = "Work log reviewed."; }
    catch (e) { error.value = e.message; }
    finally { busy.value = false; }
}
function confirmLeave() { return !dirty.value || window.confirm("Discard unsaved work log changes?"); }
onBeforeRouteLeave(confirmLeave);
onBeforeRouteUpdate(confirmLeave);
const beforeUnload = event => { if (dirty.value) { event.preventDefault(); event.returnValue = ""; } };
window.addEventListener("beforeunload", beforeUnload);
onBeforeUnmount(() => { revision++; window.removeEventListener("beforeunload", beforeUnload); });
watch(() => route.fullPath, load, { immediate: true });
</script>

<style scoped>
.card { @apply rounded-2xl border border-line bg-surface p-5 shadow-soft sm:p-6; }
.work-log-page { min-height: calc(100dvh - 10rem); display: flex; flex-direction: column; }
.person-card { @apply flex w-full items-center gap-4 rounded-2xl border border-line bg-surface p-5 hover:border-accent; }
.person-avatar { @apply flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-accent-soft text-lg font-semibold text-accent; }
.calendar-grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: clamp(4px, 1vw, 10px); }
.weekday { @apply py-2 text-center text-xs font-medium text-muted; }
.calendar-day { @apply flex min-w-0 flex-col items-center justify-center gap-2 rounded-xl border border-transparent py-3 transition-shadow focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent; min-height: 72px; }
.calendar-day:not(:disabled):hover { @apply border-accent shadow-soft; }
.calendar-day.today { @apply border-accent; box-shadow: 0 0 0 1px var(--color-accent, #08745e); }
.day-number { @apply text-sm font-semibold; }
.day-hours { @apply text-xs; }
.day-missing { background: #ffedeb; color: #96372e; }
.day-draft { background: #fff2d2; color: #765600; }
.day-submitted { background: #e7efff; color: #224f94; }
.day-reviewed { background: #dcf3e6; color: #165e3c; }
.day-unavailable { @apply bg-soft text-muted; }
.legend-dot { @apply inline-block h-3 w-3 rounded-full border border-current; }
.month-arrow { @apply flex h-11 w-11 items-center justify-center rounded-xl border border-line text-2xl text-ink disabled:opacity-30; }
.month-input { @apply max-w-full border-none bg-transparent text-center text-base font-semibold text-ink; }
.summary-card { @apply flex flex-col gap-2 rounded-2xl border border-line bg-surface p-4; }
.summary-card strong { @apply text-lg text-ink; }
.summary-card span { @apply text-xs text-muted; }
.view-tabs { @apply sticky bottom-0 z-10 !mt-auto flex gap-2 rounded-2xl border border-line bg-surface p-2 shadow-soft; }
.view-tabs button { @apply flex-1 rounded-xl px-4 py-3 text-sm font-medium text-muted; }
.view-tabs button.selected { @apply bg-accent-soft text-accent; }
@media (max-width: 420px) { .calendar-day { min-height: 62px; padding: 8px 0; } .card { padding: 16px; } }
.label { @apply block text-sm font-medium text-ink; }
.input { @apply mt-2 block w-full rounded-xl border border-line bg-surface px-3 py-3 text-ink outline-none focus:border-accent disabled:bg-soft; }
.status { @apply rounded-full px-3 py-1 text-xs font-medium; }
.message-error { @apply rounded-xl border border-bad bg-bad-soft p-4 text-sm text-bad; }
.message-success { @apply rounded-xl border border-ok bg-ok-soft p-4 text-sm text-ink; }
</style>

<style scoped>
.calendar-panel { margin-inline: -10px; }
.summary-row { @apply grid grid-cols-4 gap-2 border-t border-line pt-3; }
.summary-row div { @apply flex flex-col gap-1; }
.summary-row strong { @apply text-sm font-semibold text-ink; }
.summary-row span { @apply text-xs text-muted; }
.activity-card { @apply rounded-2xl border border-line bg-surface p-4; }
.activity-card .input { @apply mt-1 py-2.5; }
.worklog-time-picker { @apply flex shrink-0 items-center gap-1 rounded-lg border border-line bg-soft px-1; }
.worklog-time-picker select { @apply rounded-lg bg-transparent py-2 pl-1 text-xs font-medium text-ink; }
.remove-activity { @apply flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xl text-muted hover:bg-soft; }
.project-input { @apply w-full rounded-lg border border-line bg-soft px-3 py-2 text-sm text-ink; }
.date-button { @apply relative inline-flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2 text-sm font-medium text-ink; }
.date-button input { position: absolute; inset: 0; opacity: 0; width: 100%; cursor: pointer; }
.form-footer { @apply sticky bottom-0 z-10 !mt-auto border-t border-line bg-surface py-3; padding-bottom: max(12px, env(safe-area-inset-bottom)); }
@media (max-width: 640px) {
    .calendar-panel { margin-inline: -10px; }
    .calendar-grid { gap: 4px; }
    .calendar-day { min-height: 68px; }
    .calendar-day .day-number { font-size: 16px; }
    .calendar-panel .legend-dot { width: 8px; height: 8px; }
    .calendar-panel > div:nth-last-child(1) { column-gap: 10px; font-size: 10px; }
}
</style>
