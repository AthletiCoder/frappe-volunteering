<template>
	<div>
		<PageHeader v-if="payload && !payload.flags?.show_member_projects" title="Home" />
		<div v-if="error" class="mb-4 text-bad" role="alert">{{ error }}</div>
		<div v-else-if="!payload" class="text-muted">Loading…</div>
		<div v-else-if="!payload.allowed" class="rounded-2xl border border-line bg-surface p-6 shadow-soft"><p class="text-ink">No staff actions are assigned to your account. You can view your profile or contact an administrator if you need staff access.</p></div>
		<div v-else class="space-y-6">
			<section v-if="payload.flags?.show_member_projects" aria-labelledby="member-projects-title" class="space-y-4">
				<div class="flex flex-wrap items-end justify-between gap-3">
					<h1 id="member-projects-title" class="text-2xl font-bold tracking-tight text-ink">Your active projects</h1>
					<RouterLink to="/projects?view=approved" class="text-sm font-semibold text-accent hover:underline">Open all projects</RouterLink>
				</div>
				<div v-if="payload.member_projects?.length" class="grid gap-4">
					<article v-for="project in payload.member_projects" :key="project.name" class="min-w-0 rounded-2xl border border-line bg-surface p-5 shadow-soft sm:p-6">
						<div class="flex flex-wrap items-start justify-between gap-3">
							<div class="min-w-0 max-w-4xl">
								<p class="text-xs font-semibold uppercase tracking-wide text-muted">{{ project.name }}</p>
								<h3 class="mt-2 text-xl font-bold leading-snug text-ink">{{ project.project_name }}</h3>
								<p v-if="project.project_type" class="mt-1 text-sm text-muted">{{ project.project_type }}</p>
								<p class="mt-3 whitespace-pre-line text-sm leading-relaxed text-muted">{{ project.purpose || "No project summary has been added yet." }}</p>
								<p v-if="project.starts_on || project.ends_on" class="mt-3 text-xs text-muted">{{ project.starts_on ? projectDate(project.starts_on) : "Start date not set" }} – {{ project.ends_on ? projectDate(project.ends_on) : "End date not set" }}</p>
							</div>
							<span class="shrink-0 rounded-full bg-accent-soft px-3 py-1 text-xs font-semibold text-accent">{{ project.status }}</span>
						</div>
						<div class="mt-5 border-t border-line pt-4">
							<div class="grid gap-2 sm:grid-cols-2" :class="project.can_submit_expense ? 'xl:grid-cols-4' : 'xl:grid-cols-3'">
								<RouterLink v-if="project.can_submit_expense" :to="{ path: '/expense-claim', query: { project: project.name } }" class="btn-primary min-h-11 w-full text-center">Submit an expense</RouterLink>
								<RouterLink v-if="project.can_request_advance" :to="{ path: '/advances', query: { new: '1', project: project.name } }" class="btn-secondary min-h-11 w-full text-center">Request an advance</RouterLink>
								<RouterLink to="/invoice-generator" class="btn-secondary min-h-11 w-full text-center">Prepare an invoice</RouterLink>
								<RouterLink :to="{ path: '/projects', query: { project: project.name } }" class="btn-secondary min-h-11 w-full text-center">View project</RouterLink>
							</div>
							<p v-if="project.can_request_advance && !project.can_submit_expense" class="mt-3 text-xs text-muted">Expense claims will be available when the project has an approved expense category.</p>
						</div>
					</article>
				</div>
				<div v-else class="rounded-2xl border border-line bg-surface p-5 text-sm text-muted shadow-soft">No active projects list you as a member right now. Open all projects to see your previous work, or ask a Projects Manager to add you to an active project.</div>
			</section>
			<section class="overflow-hidden rounded-2xl border border-line bg-surface shadow-soft" aria-labelledby="attention-title">
				<div class="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4"><div><p class="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Your work</p><h2 id="attention-title" class="mt-1 text-lg font-bold">Waiting on you <span v-if="waitingCount" class="ml-1 rounded-full bg-todo-soft px-2 py-0.5 align-middle text-xs font-semibold text-todo">{{ waitingCount }}</span></h2></div><RouterLink to="/todos" class="inline-flex items-center gap-1 text-sm font-semibold text-accent hover:underline">View all <Icon name="arrow-right" size="sm" /></RouterLink></div>
				<div v-if="waitingItems.length" class="divide-y divide-line"><a v-for="item in waitingPreview" :key="item.id" :href="item.route" class="flex items-center gap-3 px-5 py-3.5 transition-colors hover:bg-bg"><span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-todo-soft text-todo"><Icon :name="item.bucket === 'pay' ? 'wallet' : 'check'" size="sm" /></span><span class="min-w-0 flex-1"><span class="block text-[11px] font-semibold uppercase tracking-wide text-muted">{{ item.kind }}</span><span class="block truncate text-sm font-semibold">{{ item.title }}</span><span v-if="item.subtitle" class="block truncate text-xs text-muted">{{ item.subtitle }}</span></span><Icon name="arrow-right" size="sm" class="shrink-0 text-muted" /></a></div>
					<div v-else class="flex items-center gap-3 px-5 py-6"><span class="flex h-10 w-10 items-center justify-center rounded-xl bg-ok-soft text-ok"><Icon name="check" /></span><span><span class="block text-sm font-semibold">Nothing waiting right now</span><span class="block text-sm text-muted">You can continue your own work below.</span></span></div>
			</section>
			<section v-if="resumeItems.length" class="min-w-0 rounded-2xl border border-line bg-surface p-5 shadow-soft" aria-labelledby="resume-title"><div class="mb-3 flex flex-wrap items-center justify-between gap-2"><div><p class="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Pick up where you left off</p><h2 id="resume-title" class="mt-1 text-base font-bold">Resume drafts</h2></div><RouterLink to="/todos?bucket=resume" class="text-sm font-semibold text-accent hover:underline">View all</RouterLink></div><div class="grid min-w-0 gap-3 md:grid-cols-2"><a v-for="item in resumePreview" :key="item.id" :href="item.route" class="flex min-w-0 items-start gap-3 rounded-xl border border-line p-3 hover:bg-bg"><span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-soft text-muted"><Icon name="document-history" size="sm" /></span><span class="min-w-0 flex-1"><span class="block text-[11px] font-semibold uppercase text-muted">{{ item.kind }}</span><span class="block truncate text-sm font-semibold">{{ item.title }}</span><span class="block truncate text-xs text-muted">{{ item.subtitle }}</span></span></a></div></section>
			<section v-if="focus.roleActions.length || focus.projectActions.length || focus.personalActions.length" aria-label="Your shortcuts" class="space-y-3">
				<div class="flex flex-wrap items-end justify-between gap-2 pt-1"><div><p class="text-[11px] font-semibold uppercase tracking-[0.12em] text-accent">For your role</p><h2 class="mt-1 text-xl font-bold">Your shortcuts</h2></div><p class="text-sm text-muted">All available actions are organised in the side menu.</p></div>
				<div class="grid items-start gap-5 lg:grid-cols-2">
					<ActionGrid v-if="focus.roleActions.length" title="Your responsibilities" icon="clipboard-check" :actions="focus.roleActions" variant="dashboard" />
					<ActionGrid v-if="focus.projectActions.length" title="Project proposals" icon="folder" :actions="focus.projectActions" variant="dashboard" />
					<ActionGrid v-if="focus.personalActions.length" title="Your day-to-day" icon="clock" :actions="focus.personalActions" variant="dashboard" />
				</div>
			</section>
			<div v-if="!waitingCount" class="rounded-2xl border border-line bg-surface px-5 py-4 text-sm text-muted"><span class="font-semibold text-ink">You’re clear.</span> {{ clearHint }}</div>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { homePayload, loadHomePayload } from "../lib/home";
import { homeFocus } from "../lib/workspaceNavigation";
import PageHeader from "../components/PageHeader.vue";
import ActionGrid from "../components/ActionGrid.vue";
import Icon from "../components/Icon.vue";

const HOME_WAITING_CAP = 3;
const HOME_RESUME_CAP = 2;
const error = ref("");
const payload = computed(() => homePayload.value);
const focus = computed(() => homeFocus(payload.value));
function projectDate(value) {
	const date = new Date(`${String(value).slice(0, 10)}T00:00:00`);
	return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" }).format(date);
}
const waitingItems = computed(() => payload.value?.waiting || payload.value?.todos || []);
const waitingCount = computed(() => payload.value?.waiting_count ?? waitingItems.value.length);
const waitingPreview = computed(() => waitingItems.value.slice(0, HOME_WAITING_CAP));
const resumeItems = computed(() => payload.value?.resume || []);
const resumePreview = computed(() => resumeItems.value.slice(0, HOME_RESUME_CAP));
const showTime = computed(() => Boolean(payload.value?.flags?.show_time && payload.value?.actions?.time?.length));
const clearHint = computed(() => showTime.value ? "Log today’s work when you’re ready." : "Nothing needs you right now.");
onMounted(async () => {
	try { await loadHomePayload(); }
	catch (err) { error.value = err.message || String(err); }
});
</script>
