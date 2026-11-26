<template>
	<div class="work-log-page mx-auto max-w-5xl space-y-4 pb-4">
        <PageHeader :title="pageTitle" eyebrow="Time & leave">
            <template v-if="editing" #actions><RouterLink :to="{ path: '/work-logs', query: calendarQuery }" class="btn-back">Calendar</RouterLink></template>
        </PageHeader>
		<p v-if="error" role="alert" class="message-error">{{ error }}</p>
		<p v-if="message" role="status" class="message-success">{{ message }}</p>
		<p v-if="loading" role="status" class="text-muted">Loading work logs…</p>
		<template v-else-if="workspace">
        <nav v-if="!editing && workspace.can_review_team" class="view-tabs" aria-label="Work log views">
            <button v-if="workspace.can_create" :class="{ selected: listView === 'mine' }" :aria-current="listView === 'mine' ? 'page' : undefined" :disabled="busy" @click="changeView('mine')">My logs</button>
            <button :class="{ selected: listView === 'team' }" :aria-current="listView === 'team' ? 'page' : undefined" :disabled="busy" @click="changeView('team')">Team review</button>
        </nav>
			<template v-if="!editing">
                <template v-if="listView === 'team' && !route.query.employee">
                    <section class="kit-panel overflow-hidden">
                        <div class="flex flex-wrap items-end justify-between gap-3 border-b border-line px-4 py-4 sm:px-5">
                            <div><h2 class="text-base font-semibold text-ink">Your team</h2><p class="mt-1 text-sm text-muted">Select a person to view their monthly calendar and review their work.<template v-if="workspace.month"> · <span class="font-medium text-ink">{{ monthLabel(workspace.month) }}</span></template></p></div>
                            <form class="flex w-full gap-2 sm:w-auto" @submit.prevent="searchPeople"><input v-model="peopleQuery" type="search" class="field-input !mt-0 min-w-0 sm:w-64" aria-label="Search team" placeholder="Search by name" /><button class="btn-secondary" :disabled="busy">Search</button></form>
                        </div>
                        <p v-if="!workspace.people?.length" class="px-5 py-10 text-center text-sm text-muted">No employees match this view.</p>
                        <button v-for="person in workspace.people" :key="person.name" class="person-card group" :disabled="busy" @click="openPerson(person)">
                            <Avatar :name="person.employee_name" />
                            <span class="min-w-0 flex-1 text-left"><strong class="block truncate text-sm text-ink">{{ person.employee_name }}</strong><span class="block truncate text-xs text-muted">{{ person.designation || person.name }}</span></span>
                            <span class="hidden w-40 shrink-0 sm:block"><span class="flex justify-between text-[11px] text-muted"><span>{{ hoursLabel(person.total_hours) }} h recorded</span></span><span class="mt-1 block h-1.5 overflow-hidden rounded-full bg-soft"><span class="block h-full rounded-full bg-navy-600" :style="{ width: Math.min(100, (Number(person.total_hours || 0) / 176) * 100) + '%' }"></span></span></span>
                            <span v-if="person.submitted" class="chip shrink-0 bg-marigold-soft text-[#7a4a00]">{{ person.submitted }} awaiting review</span>
                            <span v-else class="chip shrink-0 bg-ok-soft text-ok">Up to date</span>
                            <Icon name="arrow-right" size="sm" class="hidden shrink-0 text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-navy-900 sm:block" />
                        </button>
                    </section>
                    <div v-if="workspace.page > 1 || workspace.has_more" class="flex items-center justify-between"><button class="btn-secondary" :disabled="busy || workspace.page === 1" @click="peoplePage(workspace.page - 1)">Previous</button><span>Page {{ workspace.page }}</span><button class="btn-secondary" :disabled="busy || !workspace.has_more" @click="peoplePage(workspace.page + 1)">Next</button></div>
                </template>
                <template v-else-if="workspace.days">
                    <div v-if="listView === 'team'" class="flex flex-wrap items-center justify-between gap-3"><h2 class="text-xl font-semibold text-ink">{{ workspace.calendar_employee.employee_name }}</h2><button class="btn-secondary" @click="changeView('team')">Back to team</button></div>
                    <div class="calendar-layout">
                    <section class="calendar-panel kit-panel space-y-4 p-4 sm:p-5" aria-label="Work log calendar">
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
                        <div class="flex flex-wrap gap-x-4 gap-y-2 border-t border-line pt-3 text-xs text-muted"><span v-for="status in statuses" :key="status" class="inline-flex items-center gap-2"><span :class="['legend-dot', dayClass(status)]"></span>{{ status }}</span></div>
                    </section>
                    <aside class="space-y-4">
                        <section class="summary-row" aria-label="Monthly summary">
                            <div class="summary-row__total"><span>Total time</span><strong>{{ durationLabel(workspace.summary.total_hours) }}</strong></div>
                            <div><span>Submitted</span><strong>{{ workspace.summary.submitted_total ?? workspace.summary.Submitted + workspace.summary.Reviewed }}</strong></div>
                            <div><span>Awaiting review</span><strong>{{ workspace.summary.awaiting_review ?? workspace.summary.Submitted }}</strong></div>
                            <div><span>Reviewed</span><strong>{{ workspace.summary.Reviewed }}</strong></div>
                        </section>
                        <div v-if="missingDays && listView !== 'team'" class="kit-panel flex items-start gap-3 p-4 text-sm"><span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-bad-soft text-bad"><Icon name="clock" size="sm" /></span><span><strong class="block text-ink">{{ missingDays }} {{ missingDays === 1 ? "day" : "days" }} you can still log</strong><span class="text-xs text-muted">Older unfilled days are past the logging window.</span></span></div>
                    </aside>
                    </div>

                </template>
			</template>
            <template v-else-if="log">
                <div class="log-editor">
                    <div class="min-w-0 space-y-4">
                        <div class="log-dayhead">
                            <label class="log-date" :class="{ 'log-date--locked': !log.can_edit || !!log.name || busy }">
                                <span class="log-date__tile" aria-hidden="true"><span class="log-date__month">{{ monthShort(form.date) }}</span><span class="log-date__day">{{ Number(String(form.date).slice(8, 10)) || "" }}</span></span>
                                <span class="min-w-0"><span class="block text-xs font-medium text-muted">{{ weekdayLabel(form.date) }}</span><span class="block text-base font-semibold text-ink">{{ dateLabel(form.date) }}</span><span v-if="log.can_edit && !log.name" class="block text-xs text-navy-600">Change date</span></span>
                                <input v-model="form.date" type="date" aria-label="Work date" :min="workspace.can_override ? undefined : workspace.earliest_date" :max="workspace.today" :disabled="!log.can_edit || !!log.name || busy" @change="switchDate" />
                            </label>
                            <div class="flex flex-wrap items-center gap-2">
                                <span :class="['status', statusClass(log.status)]"><span class="h-1.5 w-1.5 rounded-full bg-current"></span>{{ log.status }}</span>
                                <span v-if="log.is_wfh" class="chip bg-navy-50 text-navy-900"><Icon name="home" size="sm" />Work from home</span>
                            </div>
                            <h2 v-if="!log.is_own" class="w-full text-base font-semibold text-ink">{{ log.employee_name }}</h2>
                        </div>
                        <form ref="logForm" id="work-log-form" class="space-y-3" @submit.prevent="save(false)">
                            <section v-for="(item, index) in form.items" :key="item.key" class="activity-card">
                                <div class="flex items-center gap-3">
                                    <span class="activity-num" aria-hidden="true">{{ index + 1 }}</span>
                                    <h2 class="min-w-0 flex-1 truncate text-[15px] font-semibold text-ink">{{ log.can_edit ? 'Activity ' + (index + 1) : item.task_title }}</h2>
                                    <div v-if="log.can_edit" class="worklog-time-picker" :aria-label="'Time spent on activity ' + (index + 1)"><Icon name="clock" size="sm" class="ml-1.5 hidden text-muted sm:block" /><label><span class="sr-only">Hours</span><select aria-label="Hours" v-model.number="item.duration_hours" :disabled="busy" @change="changeDuration(item)"><option v-for="h in 25" :key="h - 1" :value="h - 1">{{ h - 1 }} h</option></select></label><label><span class="sr-only">Minutes</span><select aria-label="Minutes" v-model.number="item.duration_minutes" :disabled="busy || item.duration_hours === 24" @change="changeDuration(item)"><option v-for="m in 60" :key="m - 1" :value="m - 1">{{ m - 1 }} min</option></select></label></div>
                                    <strong v-else class="chip whitespace-nowrap bg-navy-50 text-navy-900"><Icon name="clock" size="sm" />{{ durationLabel(item.time_spent_hours) }}</strong>
                                    <button v-if="log.can_edit && form.items.length > 1" type="button" class="remove-activity" :disabled="busy" :aria-label="'Remove activity ' + (index + 1)" @click="form.items.splice(index, 1)"><Icon name="close" size="sm" /></button>
                                </div>
                                <div v-if="log.can_edit" class="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_14rem]">
                                    <label class="field-label">Activity *<input v-model.trim="item.task_title" required maxlength="140" class="field-input" :disabled="busy" placeholder="What did you work on?" /></label>
                                    <div class="min-w-0"><label class="field-label" :for="'project-' + item.key">Project</label><select :id="'project-' + item.key" v-model="item.project" class="field-input" :disabled="busy"><option value="">General work</option><option v-if="item.project && !workspace.projects.some(p => p.name === item.project)" :value="item.project">{{ item.project_name || item.project }}</option><option v-for="project in workspace.projects" :key="project.name" :value="project.name">{{ project.project_name }}</option></select></div>
                                    <label class="field-label sm:col-span-2">Details *<textarea :value="workLogDetails(item.description, item.output_link)" @input="setDetails(item, $event.target.value)" required minlength="11" maxlength="4000" rows="3" class="field-input" :disabled="busy" placeholder="Describe the work and what was completed. Paste any links here." /></label>
                                </div>
                                <template v-else>
                                    <p class="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-ink-2">{{ workLogDetails(item.description, item.output_link) }}</p>
                                    <p class="mt-3"><span class="chip bg-soft text-ink-2"><Icon name="folder" size="sm" />{{ item.project_name || 'General work' }}</span></p>
                                </template>
                            </section>
                            <div v-if="!form.items.length" class="activity-card text-sm text-muted">No activities were recorded for this day.</div>
                            <label v-if="log.can_edit && workspace.can_override" class="field-label activity-card">HR exception reason <span class="font-normal text-muted">Required for late or on-behalf entries</span><textarea v-model="form.hr_exception_reason" minlength="10" maxlength="2000" rows="2" class="field-input"></textarea></label>
                            <div v-if="log.can_edit" class="grid gap-3" :class="!showNotes && !form.notes ? 'sm:grid-cols-[minmax(0,1fr)_auto]' : ''">
                                <button type="button" class="add-tile" :disabled="busy || form.items.length >= 100" @click="form.items.push(emptyItem())">+ Add activity</button>
                                <button v-if="!showNotes && !form.notes" type="button" class="add-tile add-tile--quiet" @click="showNotes = true">+ Add notes</button>
                            </div>
                            <label v-if="log.can_edit && (showNotes || form.notes)" class="field-label activity-card">Notes (optional)<textarea v-model.trim="form.notes" rows="2" maxlength="4000" class="field-input" :disabled="busy" placeholder="Anything your manager should know about the day" /></label>
                            <div v-else-if="form.notes" class="activity-card"><h2 class="text-sm font-semibold">Notes</h2><p class="mt-2 whitespace-pre-wrap text-sm text-ink-2">{{ form.notes }}</p></div>
                        </form>
                        <section v-if="log.can_review" class="activity-card space-y-3"><h2 class="font-semibold text-ink">Manager review</h2><label class="field-label">Private review notes<textarea v-model="remarks" maxlength="4000" rows="2" class="field-input" :disabled="busy" placeholder="Visible to managers and HR" /></label></section>
                        <section v-else-if="log.manager_remarks" class="activity-card"><h2 class="font-semibold text-ink">Private review notes</h2><p class="mt-3 whitespace-pre-wrap text-sm text-muted">{{ log.manager_remarks }}</p></section>
                    </div>
                    <!-- Day summary: a side card on wide screens, a sticky action bar on phones. -->
                    <footer class="form-footer">
                        <div class="hidden lg:block">
                            <p class="eyebrow">Day total</p>
                            <p class="mt-1 font-display text-[2rem] font-semibold leading-none tabular-nums text-ink">{{ durationLabel(totalHours) }}</p>
                            <div class="mt-3 h-1.5 overflow-hidden rounded-full bg-soft" aria-hidden="true"><div class="h-full rounded-full bg-navy-900 transition-[width] duration-300" :style="{ width: Math.min(100, (totalHours / 8) * 100) + '%' }"></div></div>
                            <p class="mt-1.5 text-xs text-muted">Against an 8-hour day</p>
                        </div>
                        <p class="text-sm font-medium text-ink lg:mt-4 lg:border-t lg:border-line lg:pt-4">{{ form.items.length }} {{ form.items.length === 1 ? 'activity' : 'activities' }} · {{ durationLabel(totalHours) }}</p>
                        <div v-if="log.can_edit" class="mt-2 flex gap-3 lg:mt-3 lg:flex-col-reverse"><button type="submit" form="work-log-form" class="btn-secondary min-h-11 flex-1" :disabled="busy">Save draft</button><button type="button" class="btn-primary min-h-11 flex-1" :disabled="busy" @click="submitForm">{{ busy ? 'Saving…' : 'Submit log' }}</button></div>
                        <button v-else-if="log.can_review" class="btn-primary mt-2 min-h-11 w-full" :disabled="busy" @click="review">Mark as reviewed</button>
                        <p v-if="log.can_edit" class="mt-3 hidden text-xs leading-relaxed text-muted lg:block">Drafts stay private. Submitting sends the log to your manager and updates your attendance.</p>
                    </footer>
                </div>
            </template>
		</template>
	</div>
</template>

<script setup>
import { uid } from "../lib/uid";
import { computed, onBeforeUnmount, reactive, ref, watch } from "vue";
import { RouterLink, onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import Avatar from "../components/Avatar.vue";
import Icon from "../components/Icon.vue";
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
const missingDays = computed(() => (workspace.value?.days || []).filter(day => day.status === "Not filled" && day.can_open && day.date < workspace.value.today).length);
const statuses = ["Not filled", "Draft", "Submitted", "Reviewed", "Holiday", "On leave"];
const dayClass = status => ({ "Not filled": "day-missing", Draft: "day-draft", Submitted: "day-submitted", Reviewed: "day-reviewed" })[status] || "day-unavailable";
const dayLabel = day => day ? `${dateLabel(day.date)}, ${day.status}${day.total_hours != null ? ', ' + hoursLabel(day.total_hours) + ' hours' : ''}${day.day_note ? ', ' + day.day_note : ''}${day.cancelled ? ', cancelled log' : ''}` : "";
const totalHours = computed(() => Number(form.items.reduce((sum, item) => sum + (Number(item.time_spent_hours) || 0), 0).toFixed(6)));
const snapshot = () => JSON.stringify(form);
const dirty = computed(() => (log.value?.can_edit && original.value && snapshot() !== original.value)
    || (log.value?.can_review && remarks.value !== (log.value.manager_remarks || "")));
const emptyItem = () => ({ key: uid(), task_title: "", project: "", description: "", time_spent_hours: "", duration_hours: 0, duration_minutes: 0, output_link: "" });
const dateLabel = value => new Date(String(value).slice(0, 10) + "T12:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
const monthShort = value => value ? new Date(String(value).slice(0, 10) + "T12:00:00").toLocaleDateString("en-IN", { month: "short" }) : "";
const weekdayLabel = value => value ? new Date(String(value).slice(0, 10) + "T12:00:00").toLocaleDateString("en-IN", { weekday: "long" }) : "";
const monthLabel = value => new Date(value + "-01T12:00:00").toLocaleDateString("en-IN", { month: "long", year: "numeric" });
const statusClass = status => ({ Draft: "bg-warn-soft text-warn", Submitted: "bg-navy-50 text-navy-900", Reviewed: "bg-ok-soft text-ok", Cancelled: "bg-bad-soft text-bad" })[status] || "bg-soft text-muted";
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
.person-card { @apply flex w-full items-center gap-4 px-4 py-3.5 text-left transition-colors sm:px-5; }
.person-card + .person-card, p + .person-card { border-top: 1px solid var(--line); }
.person-card:hover:not(:disabled) { background: color-mix(in srgb, var(--navy-50) 70%, transparent); }
.person-avatar { @apply flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-accent-soft text-lg font-semibold text-accent; }
.calendar-grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: clamp(4px, 1vw, 10px); }
.weekday { @apply py-2 text-center text-xs font-medium text-muted; }
.calendar-day { @apply relative flex min-w-0 flex-col items-start justify-between gap-1 rounded-xl border border-line p-2 text-left transition-all focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent sm:p-2.5; min-height: 72px; }
.calendar-day::after { content: ""; position: absolute; top: 0.5rem; right: 0.5rem; width: 0.4375rem; height: 0.4375rem; border-radius: 999px; background: currentColor; opacity: 0.85; }
.calendar-day.day-unavailable::after { display: none; }
.calendar-day:not(:disabled):hover { border-color: var(--navy-200); box-shadow: var(--shadow-lift); transform: translateY(-1px); }
.calendar-day.today { border-color: var(--navy-900); box-shadow: inset 0 0 0 1px var(--navy-900); }
.day-number { @apply text-sm font-semibold text-ink; }
.day-hours { @apply text-xs font-semibold; }
.day-missing { background: var(--surface); color: var(--bad); border-style: dashed; border-color: color-mix(in srgb, var(--bad) 35%, var(--line)); }
.day-draft { background: var(--warn-soft); color: var(--warn); border-color: transparent; }
.day-submitted { background: var(--navy-50); color: var(--navy-600); border-color: transparent; }
.day-reviewed { background: var(--ok-soft); color: var(--ok); border-color: transparent; }
.day-unavailable { @apply bg-soft text-muted; border-color: transparent; }
.day-unavailable .day-number { color: var(--muted); }
.legend-dot { @apply inline-block h-2 w-2 rounded-full; background: currentColor; }
.legend-dot.day-unavailable { background: var(--line-strong); }
.legend-dot.day-missing { border: 0; }
.month-arrow { @apply flex h-10 w-10 items-center justify-center rounded-xl border border-line-strong bg-surface text-xl text-ink transition-colors hover:bg-navy-50 disabled:opacity-30; }
.month-input { @apply max-w-full border-none bg-transparent text-center text-base font-semibold text-ink; }
.summary-card { @apply flex flex-col gap-2 rounded-2xl border border-line bg-surface p-4; }
.summary-card strong { @apply text-lg text-ink; }
.summary-card span { @apply text-xs text-muted; }
.view-tabs { @apply inline-flex max-w-full gap-1 self-start rounded-xl bg-soft p-1; }
.view-tabs button { @apply min-h-9 rounded-lg px-4 py-1.5 text-sm font-semibold text-muted transition-colors hover:text-ink; }
.view-tabs button.selected { @apply bg-surface text-navy-900 shadow-soft; box-shadow: 0 0 0 1px var(--line), var(--shadow-soft); }
@media (max-width: 420px) { .calendar-day { min-height: 62px; padding: 8px 0; } .card { padding: 16px; } }
.label { @apply block text-sm font-medium text-ink; }
.input { @apply mt-2 block w-full rounded-xl border border-line bg-surface px-3 py-3 text-ink outline-none focus:border-accent disabled:bg-soft; }
.status { @apply rounded-full px-3 py-1 text-xs font-medium; }
</style>

<style scoped>
.calendar-layout { display: grid; gap: 1.25rem; align-items: start; }
@media (min-width: 1024px) { .calendar-layout { grid-template-columns: minmax(0, 1fr) 17rem; gap: 1.5rem; } .calendar-layout > aside { position: sticky; top: 5.5rem; } }
.summary-row { @apply grid grid-cols-3 gap-2.5 sm:grid-cols-4 lg:grid-cols-3; }
.summary-row div { @apply flex min-w-0 flex-col gap-1 rounded-2xl border border-line bg-surface px-2.5 py-3; box-shadow: var(--shadow-soft); }
.summary-row .summary-row__total { @apply col-span-3 sm:col-span-1 lg:col-span-3; background: linear-gradient(135deg, var(--navy-900), var(--navy-600)); border-color: transparent; }
.summary-row .summary-row__total span { color: rgb(255 255 255 / 0.7); }
.summary-row .summary-row__total strong { color: #fff; font-size: 1.5rem; }
.summary-row strong { @apply font-display text-xl font-semibold tabular-nums text-ink; }
.summary-row span { @apply text-[11px] font-medium leading-tight text-muted; }
.activity-card { @apply rounded-2xl border border-line bg-surface p-4 sm:p-5; box-shadow: var(--shadow-soft); }
.activity-num { @apply flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-navy-900 text-xs font-semibold text-white; }
.worklog-time-picker { @apply flex shrink-0 items-center gap-0.5 rounded-xl border border-line-strong bg-surface p-0.5; }
.worklog-time-picker select { @apply rounded-lg border-0 bg-transparent py-1.5 pl-2 text-sm font-semibold text-ink shadow-none; min-width: 0; }
.worklog-time-picker select:focus { box-shadow: var(--ring); }
.worklog-time-picker label select { padding: 0.375rem 0.25rem 0.375rem 0.5rem; }
.worklog-time-picker label select::picker-icon { width: 0.875rem; padding-left: 0.25rem; }
.remove-activity { @apply flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-bad-soft hover:text-bad; }
.add-tile { @apply flex min-h-[3rem] w-full items-center justify-center rounded-2xl border-[1.5px] border-dashed border-line-strong px-5 text-sm font-semibold text-navy-600 transition-colors hover:border-navy-600 hover:bg-navy-50 hover:text-navy-900 disabled:opacity-50; }
.add-tile--quiet { @apply text-muted; }
.log-editor { display: grid; gap: 1rem; align-items: start; }
@media (min-width: 1024px) { .log-editor { grid-template-columns: minmax(0, 1fr) 18rem; gap: 1.5rem; } }
.log-dayhead { @apply flex flex-wrap items-center justify-between gap-3; }
.log-date { @apply relative flex items-center gap-3 rounded-2xl border border-line bg-surface py-2 pl-2 pr-5 transition-colors; box-shadow: var(--shadow-soft); cursor: pointer; }
.log-date:not(.log-date--locked):hover { @apply border-navy-200; }
.log-date--locked { cursor: default; }
.log-date input { position: absolute; inset: 0; opacity: 0; width: 100%; cursor: inherit; }
.log-date__tile { @apply flex h-12 w-12 shrink-0 flex-col items-center justify-center overflow-hidden rounded-xl bg-navy-900 text-white; }
.log-date__month { @apply text-[10px] font-semibold uppercase tracking-wider text-white/70; }
.log-date__day { @apply font-display text-lg font-semibold leading-none; }
.status { @apply inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold; }
.form-footer { @apply sticky bottom-0 z-10 !mt-auto -mx-4 border-t border-line bg-surface px-4 py-3; padding-bottom: max(12px, env(safe-area-inset-bottom)); }
@media (min-width: 640px) { .form-footer { @apply mx-0 rounded-2xl border px-5; } }
@media (min-width: 1024px) { .form-footer { position: sticky; top: 5.5rem; bottom: auto; margin-top: 0 !important; padding: 1.25rem; box-shadow: var(--shadow-soft); } }
.text-ink-2 { color: var(--ink-2); }
@media (max-width: 640px) {
    
    .calendar-grid { gap: 4px; }
    .calendar-day { min-height: 68px; }
    .calendar-day .day-number { font-size: 16px; }
    .calendar-day::after { display: none; }
    .calendar-panel .legend-dot { width: 8px; height: 8px; }
    .calendar-panel > div:nth-last-child(1) { column-gap: 10px; font-size: 10px; }
}
</style>
