<template>
	<div>
		<PageHeader :title="payload?.allowed ? `Hello ${firstName}` : 'Home'" :subtitle="payload?.greeting || ''" eyebrow="Workspace">
			<template #actions>
				<RouterLink to="/profile" class="btn-secondary">Profile</RouterLink>
				<button type="button" class="btn-secondary" :disabled="loggingOut" @click="logout">{{ loggingOut ? "Logging out…" : "Logout" }}</button>
			</template>
		</PageHeader>
		<p v-if="logoutError" class="mb-4 text-bad" role="alert">{{ logoutError }}</p>
		<div v-if="error" class="mb-4 text-bad" role="alert">{{ error }}</div>
		<div v-else-if="!payload" class="text-muted">Loading…</div>
		<div v-else-if="!payload.allowed" class="rounded-2xl border border-line bg-surface p-6 shadow-soft"><p class="text-ink">Home is for staff. Use the volunteer portal for your activities.</p></div>
		<div v-else class="space-y-6">
			<div class="grid items-start gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(20rem,1fr)]">
				<section class="overflow-hidden rounded-2xl border border-line bg-surface shadow-soft" aria-labelledby="attention-title">
					<div class="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4"><div><p class="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Your work</p><h2 id="attention-title" class="mt-1 text-lg font-bold">Waiting on you <span v-if="waitingCount" class="ml-1 rounded-full bg-todo-soft px-2 py-0.5 align-middle text-xs font-semibold text-todo">{{ waitingCount }}</span></h2></div><RouterLink to="/todos" class="inline-flex items-center gap-1 text-sm font-semibold text-accent hover:underline">View all <Icon name="arrow-right" size="sm" /></RouterLink></div>
				<div v-if="waitingItems.length" class="divide-y divide-line"><a v-for="item in waitingPreview" :key="item.id" :href="item.route" class="flex items-center gap-3 px-5 py-3.5 transition-colors hover:bg-bg"><span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-todo-soft text-todo"><Icon :name="item.bucket === 'pay' ? 'wallet' : 'check'" size="sm" /></span><span class="min-w-0 flex-1"><span class="block text-[11px] font-semibold uppercase tracking-wide text-muted">{{ item.kind }}</span><span class="block truncate text-sm font-semibold">{{ item.title }}</span><span v-if="item.subtitle" class="block truncate text-xs text-muted">{{ item.subtitle }}</span></span><Icon name="arrow-right" size="sm" class="shrink-0 text-muted" /></a></div>
					<div v-else class="flex items-center gap-3 px-5 py-6"><span class="flex h-10 w-10 items-center justify-center rounded-xl bg-ok-soft text-ok"><Icon name="check" /></span><span><span class="block text-sm font-semibold">Nothing waiting right now</span><span class="block text-sm text-muted">You can continue your own work below.</span></span></div>
					<div v-if="historyLinks.length" class="border-t border-line px-5 py-4"><p class="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Your records</p><div class="grid gap-2 sm:grid-cols-2"><a v-for="action in historyLinks" :key="action.id" :href="action.list_route" class="flex items-center justify-between gap-2 rounded-lg bg-bg px-3 py-2 text-sm font-medium hover:bg-accent-soft"><span class="truncate">{{ historyLabel(action) }}</span><span class="rounded-full bg-surface px-2 py-0.5 text-xs text-muted">{{ action.pending || 0 }}</span></a></div></div>
				</section>
				<section class="rounded-2xl border border-line bg-surface p-5 shadow-soft" aria-labelledby="quick-title"><p class="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Get started</p><h2 id="quick-title" class="mt-1 text-lg font-bold">Quick actions</h2><p class="mt-1 text-sm text-muted">Common tasks for your access.</p><div class="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2"><a v-for="action in quickActions" :key="action.id" :href="action.route" class="flex min-h-12 items-center justify-between gap-2 rounded-xl border border-line bg-bg px-3 py-2 text-sm font-medium transition-colors hover:border-accent hover:bg-accent-soft"><span class="truncate">{{ action.label }}</span><Icon name="arrow-right" size="sm" class="shrink-0 text-accent" /></a></div></section>
			</div>
			<section v-if="resumeItems.length" class="min-w-0 rounded-2xl border border-line bg-surface p-5 shadow-soft" aria-labelledby="resume-title"><div class="mb-3 flex flex-wrap items-center justify-between gap-2"><div><p class="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Pick up where you left off</p><h2 id="resume-title" class="mt-1 text-base font-bold">Resume drafts</h2></div><RouterLink to="/todos?bucket=resume" class="text-sm font-semibold text-accent hover:underline">View all</RouterLink></div><div class="grid min-w-0 gap-3 md:grid-cols-2"><a v-for="item in resumePreview" :key="item.id" :href="item.route" class="flex min-w-0 items-start gap-3 rounded-xl border border-line p-3 hover:bg-bg"><span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-soft text-muted"><Icon name="document-history" size="sm" /></span><span class="min-w-0 flex-1"><span class="block text-[11px] font-semibold uppercase text-muted">{{ item.kind }}</span><span class="block truncate text-sm font-semibold">{{ item.title }}</span><span class="block truncate text-xs text-muted">{{ item.subtitle }}</span></span></a></div></section>
			<div class="flex flex-wrap items-end justify-between gap-2 pt-1"><div><p class="text-[11px] font-semibold uppercase tracking-[0.12em] text-accent">Explore your workspace</p><h2 class="mt-1 text-xl font-bold">Everything you can do</h2></div><p class="text-sm text-muted">Only actions available to your account are shown.</p></div>
			<div class="grid items-start gap-5 lg:grid-cols-2"><div v-for="group in orderedGroups" :id="group.id" :key="group.id" class="scroll-mt-24"><ActionGrid :title="group.title" :icon="group.icon" :actions="group.actions" variant="dashboard" /></div></div>
			<details v-if="hasMore" class="group rounded-2xl border border-line bg-surface shadow-soft"><summary class="flex cursor-pointer list-none items-center justify-between px-5 py-4 text-sm font-semibold text-ink">More resources <span class="font-normal text-muted group-open:hidden">Programs, people and setup</span></summary><div class="space-y-6 border-t border-line px-5 py-5"><ProgramsStrip :programs="payload.programs" /><LinkStrip v-if="payload.people?.length" title="People" icon="people" :links="payload.people" /><LinkStrip v-if="payload.admin?.length" title="Setup" icon="desk" :links="payload.admin" /></div></details>
			<div v-if="!waitingCount" class="rounded-2xl border border-line bg-surface px-5 py-4 text-sm text-muted"><span class="font-semibold text-ink">You’re clear.</span> {{ clearHint }}</div>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { homePayload, loadHomePayload, stopHomePoll } from "../lib/home";
import { call } from "../lib/frappe";
import PageHeader from "../components/PageHeader.vue";
import ActionGrid from "../components/ActionGrid.vue";
import ProgramsStrip from "../components/ProgramsStrip.vue";
import LinkStrip from "../components/LinkStrip.vue";
import Icon from "../components/Icon.vue";

const HOME_WAITING_CAP = 3;
const HOME_RESUME_CAP = 2;
const GROUPS = {
	system_management: { title: "System management", icon: "desk" },
	hr_management: { title: "HR management", icon: "people" },
	team: { title: "My team", icon: "people" },
	projects: { title: "Projects", icon: "folder" },
	accounts: { title: "Accounts", icon: "wallet" },
	money: { title: "Expenses and advances", icon: "wallet" },
	time: { title: "Time and leave", icon: "clock" },
	organisation: { title: "Organisation", icon: "desk" },
};
const error = ref("");
const loggingOut = ref(false);
const logoutError = ref("");
const payload = computed(() => homePayload.value);
const firstName = computed(() => (payload.value?.full_name || "").split(" ")[0] || "there");
const waitingItems = computed(() => payload.value?.waiting || payload.value?.todos || []);
const waitingCount = computed(() => payload.value?.waiting_count ?? waitingItems.value.length);
const waitingPreview = computed(() => waitingItems.value.slice(0, HOME_WAITING_CAP));
const resumeItems = computed(() => payload.value?.resume || []);
const resumePreview = computed(() => resumeItems.value.slice(0, HOME_RESUME_CAP));
const showTime = computed(() => Boolean(payload.value?.flags?.show_time && payload.value?.actions?.time?.length));
const clearHint = computed(() => showTime.value ? "Log today’s work when you’re ready." : "Nothing needs you right now.");
const hasMore = computed(() => Boolean(payload.value?.programs || payload.value?.people?.length || payload.value?.admin?.length));
const orderedGroups = computed(() => {
	const actions = payload.value?.actions || {};
	let order = ["money", "time", "projects", "organisation", "team", "accounts", "hr_management", "system_management"];
	if (actions.system_management?.length) order = ["system_management", "hr_management", "projects", "accounts", "team", "money", "time", "organisation"];
	else if (actions.hr_management?.length) order = ["hr_management", "team", "time", "projects", "money", "accounts", "organisation"];
	else if (actions.accounts?.length) order = ["accounts", "projects", "money", "team", "time", "organisation"];
	else if (actions.projects?.some((row) => row.id === "review_project_proposals")) order = ["projects", "team", "money", "time", "organisation"];
	else if (actions.team?.length) order = ["team", "money", "projects", "time", "organisation"];
	return order.filter((id) => actions[id]?.length).map((id) => ({ id, ...GROUPS[id], actions: actions[id] }));
});
const quickActions = computed(() => {
	const rows = orderedGroups.value.flatMap((group) => group.actions)
		.filter((row) => row.id !== "approved_projects");
	const byId = new Map();
	for (const row of rows) if (!byId.has(row.id)) byId.set(row.id, row);
	let priority = ["claim", "advance", "invoice_expense_claim", "invoice_generator", "log_work", "leave"];
	if (payload.value?.actions?.system_management?.length) priority = ["manage_users", "manage_employees", "review_project_proposals", "chart_of_accounts", "claim", "invoice_generator"];
	else if (payload.value?.actions?.hr_management?.length) priority = ["manage_employees", "my_team", "leave", "fix_attendance", "invoice_generator"];
	else if (payload.value?.actions?.accounts?.length) priority = ["project_account_mapping", "bank_account", "advance_disbursement", "chart_of_accounts", "claim", "invoice_generator"];
	else if (payload.value?.actions?.projects?.some((row) => row.id === "review_project_proposals")) priority = ["review_project_proposals", "create_project", "invoice_generator", "claim", "advance"];
	const selected = priority.map((id) => byId.get(id)).filter(Boolean);
	return [...selected, ...rows.filter((row) => !selected.includes(row))].slice(0, 6);
});
const historyLinks = computed(() => {
	const rows = orderedGroups.value.flatMap((group) => group.actions).filter((row) => row.list_route);
	const order = ["claim", "advance", "leave", "log_work", "my_project_requests"];
	const rank = (id) => order.includes(id) ? order.indexOf(id) : order.length;
	return [...new Map(rows.map((row) => [row.list_route, row])).values()]
		.sort((a, b) => rank(a.id) - rank(b.id)).slice(0, 4);
});
function historyLabel(action) {
	return { claim: "Claims and reimbursements", advance: "Advance requests", leave: "Leave requests", log_work: "Work logs" }[action.id]
		|| `View ${action.list_label.toLowerCase()}`;
}
async function logout() {
	if (loggingOut.value) return;
	loggingOut.value = true;
	logoutError.value = "";
	try { await call("logout"); stopHomePoll(); homePayload.value = null; window.location.replace("/login?redirect-to=%2Fvolunteering%2Fhome"); }
	catch (err) { logoutError.value = err.message || "Unable to log out. Please try again."; loggingOut.value = false; }
}
onMounted(async () => {
	try { await loadHomePayload(); }
	catch (err) { error.value = err.message || String(err); }
});
</script>
