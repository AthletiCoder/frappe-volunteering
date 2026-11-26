<template>
	<div class="home space-y-5 md:space-y-6">
		<!-- Welcome band: who you are, what's waiting, the one or two things to do next. -->
		<div v-if="payload" class="home-hero">
			<img :src="'/assets/volunteering/brand/lotus-mark.png'" alt="" class="home-hero__lotus" width="220" height="186" />
			<div class="relative min-w-0">
				<h1 v-if="!payload.flags?.show_member_projects" class="home-hero__eyebrow">Home</h1>
				<p v-else class="home-hero__eyebrow">{{ todayLabel }}</p>
				<p class="home-hero__greeting">{{ greeting }}</p>
				<p class="home-hero__summary">
					<template v-if="waitingCount"><strong>{{ waitingCount }} {{ waitingCount === 1 ? "item needs" : "items need" }} you.</strong> Start with the oldest.</template>
					<template v-else><strong>You’re clear.</strong> {{ clearHint }}</template>
				</p>
			</div>
			<div v-if="payload.allowed && (waitingCount || logWork)" class="home-hero__actions">
				<RouterLink v-if="waitingCount" to="/todos" class="hero-btn hero-btn--accent">Review what’s waiting<Icon name="arrow-right" size="sm" /></RouterLink>
				<a v-if="logWork" :href="logWork.route" class="hero-btn hero-btn--ghost"><Icon name="clock" size="sm" />Log today’s work</a>
			</div>
		</div>

		<div v-if="error" class="message-error" role="alert">{{ error }}</div>
		<div v-else-if="!payload" class="space-y-4" aria-busy="true" aria-label="Loading Home">
			<span class="sr-only">Loading…</span>
			<div class="skeleton h-36 rounded-[20px]"></div>
			<div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
				<div v-for="n in 4" :key="n" class="skeleton h-24 rounded-[14px]"></div>
			</div>
			<div class="grid gap-5 lg:grid-cols-[minmax(0,1fr)_23rem]">
				<div class="skeleton h-72 rounded-2xl"></div>
				<div class="skeleton h-72 rounded-2xl"></div>
			</div>
		</div>
		<div v-else-if="!payload.allowed" class="form-card"><p class="text-ink">No staff actions are assigned to your account. You can view your profile or contact an administrator if you need staff access.</p></div>
		<template v-else>
			<!-- At-a-glance numbers -->
			<div v-if="tiles.length" class="home-tiles">
				<StatTile v-for="tile in tiles" :key="tile.id" v-bind="tile" />
			</div>

			<div class="home-board" :class="{ 'home-board--projects': showProjects }">
				<!-- Projects come first in reading order (and on phones); on wide screens they sit in the right rail. -->
				<section v-if="showProjects" aria-labelledby="member-projects-title" class="home-board__projects min-w-0 space-y-3">
					<div class="flex flex-wrap items-center justify-between gap-2 px-1">
						<h1 id="member-projects-title" class="text-base font-semibold text-ink">Your active projects</h1>
						<RouterLink to="/projects?view=approved" class="link-arrow">Open all projects<Icon name="arrow-right" size="sm" /></RouterLink>
					</div>
					<template v-if="payload.member_projects?.length">
						<article v-for="project in payload.member_projects" :key="project.name" class="project-card min-w-0">
							<div class="project-card__head">
								<span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/10 text-white ring-1 ring-white/15"><Icon name="folder" /></span>
								<div class="min-w-0 flex-1">
									<div class="flex flex-wrap items-center gap-2">
										<p class="text-xs font-medium tabular-nums text-white/70">{{ project.name }}</p>
										<span class="project-card__status"><span class="h-1.5 w-1.5 rounded-full bg-current"></span>{{ project.status }}</span>
									</div>
									<h2 class="mt-0.5 text-[1.0625rem] font-semibold leading-snug text-white"><RouterLink :to="{ path: '/projects', query: { project: project.name } }" class="rounded-md transition-opacity hover:opacity-80">{{ project.project_name }}</RouterLink></h2>
									<p v-if="project.project_type" class="text-xs text-white/70">{{ project.project_type }}</p>
								</div>
							</div>
							<div class="px-4 pb-4 pt-3.5 sm:px-5">
								<p class="line-clamp-2 whitespace-pre-line text-sm leading-relaxed text-ink-2">{{ project.purpose || "No project summary has been added yet." }}</p>
								<p v-if="project.starts_on || project.ends_on" class="mt-2 inline-flex items-center gap-1.5 text-xs text-muted"><Icon name="calendar-check" size="sm" />{{ project.starts_on ? projectDate(project.starts_on) : "Start date not set" }} – {{ project.ends_on ? projectDate(project.ends_on) : "End date not set" }}</p>
								<RouterLink v-if="project.can_submit_expense" :to="{ path: '/expense-claim', query: { project: project.name } }" class="btn-primary mt-4 min-h-11 w-full">Submit an expense</RouterLink>
								<div class="project-card__more" :class="{ 'mt-4': !project.can_submit_expense }">
									<RouterLink v-if="project.can_request_advance" :to="{ path: '/advances', query: { new: '1', project: project.name } }" class="project-action"><Icon name="advance" size="sm" class="project-action__icon" />Request an advance</RouterLink>
									<RouterLink to="/invoice-generator" class="project-action"><Icon name="invoice" size="sm" class="project-action__icon" />Prepare an invoice</RouterLink>
									<RouterLink v-if="project.can_place_purchase_order !== false" :to="{ path: '/vendor-purchases', query: { new: '1', project: project.name } }" class="project-action"><Icon name="vendor" size="sm" class="project-action__icon" />Place purchase order</RouterLink>
									<button v-else type="button" class="project-action" disabled title="Your current approval grade cannot raise purchase orders."><Icon name="vendor" size="sm" class="project-action__icon" />Place purchase order</button>
								</div>
								<p v-if="project.can_request_advance && !project.can_submit_expense" class="mt-3 text-xs text-muted">Expense claims will be available when the project has an approved expense category.</p>
							</div>
						</article>
					</template>
					<div v-else class="kit-panel flex items-start gap-3 p-4 text-sm text-muted">
						<span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-soft text-muted"><Icon name="folder" size="sm" /></span>
						<span>No active projects list you as a member right now. Open all projects to see your previous work, or ask a Projects Manager to add you to an active project.</span>
					</div>
				</section>

				<!-- Main column: the decisions queue, then drafts. -->
				<div class="home-board__main min-w-0 space-y-5">
					<section class="kit-panel overflow-hidden" aria-labelledby="attention-title">
						<div class="flex items-center justify-between gap-3 px-4 pb-3 pt-4 sm:px-5">
							<h2 id="attention-title" class="flex items-center gap-2 text-base font-semibold">Waiting on you <span v-if="waitingCount" class="chip bg-marigold text-on-todo">{{ waitingCount }}</span></h2>
							<RouterLink to="/todos" class="link-arrow">View all <Icon name="arrow-right" size="sm" /></RouterLink>
						</div>
						<div v-if="waitingGroups.length" class="border-t border-line">
							<div v-for="group in waitingGroups" :key="group.key" class="waiting-group">
								<div class="flex items-center gap-3 px-4 pb-1.5 pt-3.5 sm:px-5">
									<Avatar :name="group.title" :tone="group.bucket === 'pay' ? 'amber' : ''" />
									<div class="min-w-0 flex-1">
										<p class="truncate text-sm font-semibold text-ink">{{ group.title }}</p>
										<p class="text-xs text-muted">{{ group.items.length }} {{ group.items.length === 1 ? "request" : "requests" }}<template v-if="group.kinds"> · {{ group.kinds }}</template></p>
									</div>
								</div>
								<ul class="px-2 pb-2 sm:px-3">
									<li v-for="item in group.items" :key="item.id">
										<a :href="item.route" class="waiting-row group">
											<span class="kind-tag">{{ item.kind }}</span>
											<span class="min-w-0 flex-1 truncate text-[13px] text-ink-2">{{ item.subtitle || item.title }}</span>
											<span class="waiting-row__open"><span class="hidden sm:inline">Open</span><Icon name="arrow-right" size="sm" /></span>
										</a>
									</li>
								</ul>
							</div>
							<RouterLink v-if="waitingCount > waitingPreview.length" to="/todos" class="flex items-center justify-center gap-1.5 border-t border-line px-5 py-3 text-[13px] font-semibold text-navy-600 transition-colors hover:bg-navy-50/60 hover:text-navy-900">{{ waitingCount - waitingPreview.length }} more waiting<Icon name="arrow-right" size="sm" /></RouterLink>
						</div>
						<div v-else class="flex items-center gap-3 border-t border-line px-5 py-6">
							<span class="flex h-10 w-10 items-center justify-center rounded-xl bg-ok-soft text-ok"><Icon name="check" /></span>
							<span><span class="block text-sm font-semibold">Nothing waiting right now</span><span class="block text-sm text-muted">You can continue your own work.</span></span>
						</div>
					</section>

					<section v-if="resumeItems.length" class="kit-panel min-w-0 p-4 sm:p-5" aria-labelledby="resume-title">
						<div class="mb-3 flex flex-wrap items-center justify-between gap-2"><div><p class="eyebrow">Pick up where you left off</p><h2 id="resume-title" class="mt-1 text-base font-semibold">Resume drafts</h2></div><RouterLink to="/todos?bucket=resume" class="link-arrow">View all</RouterLink></div>
						<div class="grid min-w-0 gap-3 md:grid-cols-2">
							<a v-for="item in resumePreview" :key="item.id" :href="item.route" class="resume-card group">
								<span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-marigold-soft text-[#7a4a00]"><Icon name="document-history" size="sm" /></span>
								<span class="min-w-0 flex-1"><span class="kind-tag">{{ item.kind }}</span><span class="mt-1 block truncate text-sm font-semibold">{{ item.title }}</span><span class="block truncate text-xs text-muted">{{ item.subtitle }}</span></span>
								<Icon name="arrow-right" size="sm" class="mt-1 shrink-0 text-muted transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-navy-900" />
							</a>
						</div>
					</section>
				</div>

			</div>

			<!-- Shortcuts: full width under the board, laid out as compact tiles. -->
			<section v-if="hasShortcuts" aria-label="Your shortcuts" class="min-w-0 space-y-3">
				<div class="flex items-end justify-between gap-2 px-1"><h2 class="text-base font-semibold">Your shortcuts</h2><p class="hidden text-xs text-muted sm:block">Everything else is in the menu.</p></div>
				<ActionGrid v-if="focus.roleActions.length" title="Your responsibilities" icon="clipboard-check" :actions="focus.roleActions" variant="tiles" />
				<ActionGrid v-if="focus.projectActions.length" title="Project proposals" icon="folder" :actions="focus.projectActions" variant="tiles" />
				<ActionGrid v-if="focus.personalActions.length" title="Your day-to-day" icon="clock" :actions="focus.personalActions" variant="tiles" />
			</section>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { homePayload, loadHomePayload } from "../lib/home";
import { homeFocus } from "../lib/workspaceNavigation";
import ActionGrid from "../components/ActionGrid.vue";
import Avatar from "../components/Avatar.vue";
import Icon from "../components/Icon.vue";
import StatTile from "../components/StatTile.vue";

const HOME_WAITING_CAP = 6;
const HOME_RESUME_CAP = 2;
const error = ref("");
const payload = computed(() => homePayload.value);
const focus = computed(() => homeFocus(payload.value));
const showProjects = computed(() => Boolean(payload.value?.flags?.show_member_projects));
const hasShortcuts = computed(() => Boolean(focus.value.roleActions.length || focus.value.projectActions.length || focus.value.personalActions.length));
function projectDate(value) {
	const date = new Date(`${String(value).slice(0, 10)}T00:00:00`);
	return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" }).format(date);
}
const now = new Date();
const todayLabel = new Intl.DateTimeFormat("en-IN", { weekday: "long", day: "numeric", month: "long" }).format(now);
const greeting = computed(() => {
	const hour = now.getHours();
	const part = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
	const first = String(payload.value?.full_name || "").trim().split(/\s+/)[0];
	return first ? `${part}, ${first}` : part;
});
const waitingItems = computed(() => payload.value?.waiting || payload.value?.todos || []);
const waitingCount = computed(() => payload.value?.waiting_count ?? waitingItems.value.length);
const waitingPreview = computed(() => waitingItems.value.slice(0, HOME_WAITING_CAP));
// Group the queue by the person (or record) it is about, keeping first-seen order.
const waitingGroups = computed(() => {
	const groups = new Map();
	for (const item of waitingPreview.value) {
		const key = `${item.bucket || ""}::${item.title || ""}`;
		if (!groups.has(key)) groups.set(key, { key, title: item.title, bucket: item.bucket, items: [] });
		groups.get(key).items.push(item);
	}
	return [...groups.values()].map((group) => ({ ...group, kinds: [...new Set(group.items.map((item) => item.kind).filter(Boolean))].join(", ") }));
});
const resumeItems = computed(() => payload.value?.resume || []);
const resumePreview = computed(() => resumeItems.value.slice(0, HOME_RESUME_CAP));
const timeActions = computed(() => payload.value?.actions?.time || []);
const logWork = computed(() => (payload.value?.flags?.show_time ? timeActions.value.find((action) => action.id === "log_work") : null) || null);
const showTime = computed(() => Boolean(payload.value?.flags?.show_time && timeActions.value.length));
const clearHint = computed(() => showTime.value ? "Log today’s work when you’re ready." : "Nothing needs you right now.");
const tiles = computed(() => {
	const data = payload.value;
	if (!data?.allowed) return [];
	const list = [{ id: "decide", label: "To decide", value: waitingCount.value, hint: waitingCount.value ? "Requests waiting on you" : "All caught up", icon: "clipboard-check", to: "/todos", attention: waitingCount.value > 0 }];
	if (resumeItems.value.length || data.flags?.show_money) {
		list.push({ id: "drafts", label: "Drafts to finish", value: resumeItems.value.length, hint: resumeItems.value.length ? "Started but not sent yet" : "Nothing half-done", icon: "document-history", to: "/todos?bucket=resume" });
	}
	if (logWork.value) {
		list.push({ id: "logs", label: "Work logs to fill", value: logWork.value.pending || 0, hint: logWork.value.pending ? "Days without a log" : "Up to date", icon: "clock", to: logWork.value.list_route || "" });
	}
	const leave = timeActions.value.find((action) => action.id === "leave");
	if (showProjects.value) {
		list.push({ id: "projects", label: "Active projects", value: data.member_projects?.length || 0, hint: data.member_projects?.[0]?.project_name || "None yet", icon: "folder", to: "/projects?view=approved" });
	} else if (leave) {
		list.push({ id: "leave", label: "Leave requests", value: leave.pending || 0, hint: "In progress", icon: "calendar-away", to: "/time-leave" });
	}
	return list.slice(0, 4);
});
onMounted(async () => {
	try { await loadHomePayload(); }
	catch (err) { error.value = err.message || String(err); }
});
</script>

<style scoped>
/* Welcome band */
.home-hero {
	position: relative;
	display: flex;
	flex-wrap: wrap;
	align-items: flex-end;
	justify-content: space-between;
	gap: 1.25rem 2rem;
	overflow: hidden;
	padding: 1.375rem 1.25rem 1.375rem;
	border-radius: 20px;
	color: #fff;
	background:
		radial-gradient(120% 140% at 100% 0%, rgb(242 181 68 / 0.16), transparent 46%),
		radial-gradient(90% 120% at 0% 100%, rgb(27 63 120 / 0.9), transparent 60%),
		linear-gradient(135deg, var(--navy-900), var(--navy-800));
	box-shadow: 0 18px 40px -22px rgb(5 34 77 / 0.55);
}
@media (min-width: 768px) {
	.home-hero { padding: 1.75rem 2rem; }
}
.home-hero__lotus {
	position: absolute;
	right: -1.5rem;
	bottom: -2.5rem;
	width: 13.75rem;
	height: auto;
	opacity: 0.07;
	filter: brightness(0) invert(1);
	pointer-events: none;
	user-select: none;
}
.home-hero__eyebrow {
	margin-bottom: 0.375rem;
	font-family: theme("fontFamily.sans");
	font-size: 0.6875rem;
	font-weight: 600;
	letter-spacing: 0.09em;
	text-transform: uppercase;
	color: rgb(255 255 255 / 0.66);
}
.home-hero__greeting {
	font-family: theme("fontFamily.display");
	font-size: clamp(1.5rem, 1.2rem + 1vw, 2rem);
	font-weight: 600;
	line-height: 1.15;
	letter-spacing: -0.015em;
	color: #fff;
}
.home-hero__summary {
	margin-top: 0.5rem;
	font-size: 0.9375rem;
	color: rgb(255 255 255 / 0.76);
}
.home-hero__summary strong {
	font-weight: 600;
	color: #fff;
}
.home-hero__actions {
	position: relative;
	display: flex;
	flex-wrap: wrap;
	gap: 0.625rem;
}
.hero-btn {
	display: inline-flex;
	min-height: 2.75rem;
	align-items: center;
	justify-content: center;
	gap: 0.5rem;
	padding: 0.5rem 1.125rem;
	border-radius: 12px;
	font-size: 0.875rem;
	font-weight: 600;
	transition: background-color var(--dur-fast) ease, transform 100ms ease, box-shadow var(--dur) var(--ease-out);
}
.hero-btn:active { transform: scale(0.98); }
.hero-btn--accent {
	background: var(--marigold);
	color: var(--on-todo);
	box-shadow: 0 8px 20px -10px rgb(242 181 68 / 0.9);
}
.hero-btn--accent:hover { background: #f5c264; }
.hero-btn--ghost {
	background: rgb(255 255 255 / 0.1);
	color: #fff;
	box-shadow: inset 0 0 0 1px rgb(255 255 255 / 0.22);
}
.hero-btn--ghost:hover { background: rgb(255 255 255 / 0.17); }
.hero-btn:focus-visible { outline-color: var(--marigold); }
@media (max-width: 639px) {
	.home-hero__actions { width: 100%; }
	.hero-btn { flex: 1 1 10rem; }
}

/* Numbers */
.home-tiles {
	display: grid;
	gap: 0.75rem;
	grid-template-columns: repeat(2, minmax(0, 1fr));
}
@media (min-width: 1024px) {
	.home-tiles { grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr)); gap: 1rem; }
}

/* Board: main column + right rail. Projects lead in DOM order but sit in the rail. */
.home-board {
	display: grid;
	gap: 1.25rem;
	align-items: start;
}
@media (min-width: 1024px) {
	.home-board {
		grid-template-columns: minmax(0, 1fr) minmax(20rem, 24rem);
		grid-template-rows: auto auto 1fr;
		gap: 1.25rem 1.5rem;
	}
	.home-board__main { grid-column: 1; grid-row: 1 / 4; }
	.home-board__projects { grid-column: 2; grid-row: 1; }
	.home-board:not(.home-board--projects) { grid-template-columns: minmax(0, 1fr); }
}

/* Project card: navy header, actions below. */
.project-card {
	overflow: hidden;
	border: 1px solid var(--line);
	border-radius: var(--radius-card);
	background: var(--surface);
	box-shadow: var(--shadow-soft);
	transition: box-shadow var(--dur) var(--ease-out), border-color var(--dur) ease;
}
.project-card:hover {
	border-color: var(--navy-100);
	box-shadow: var(--shadow-lift);
}
.project-card__head {
	display: flex;
	align-items: flex-start;
	gap: 0.875rem;
	padding: 1rem 1rem 1rem;
	background:
		radial-gradient(120% 160% at 100% 0%, rgb(242 181 68 / 0.18), transparent 50%),
		linear-gradient(135deg, var(--navy-900), var(--navy-600));
}
@media (min-width: 640px) {
	.project-card__head { padding: 1.125rem 1.25rem; }
}
.project-card__status {
	display: inline-flex;
	align-items: center;
	gap: 0.3rem;
	border-radius: 999px;
	background: rgb(255 255 255 / 0.12);
	padding: 0.0625rem 0.5rem;
	font-size: 0.6875rem;
	font-weight: 600;
	color: #b6f0cf;
}
.project-card__more {
	display: grid;
	gap: 0.125rem;
	margin-top: 0.5rem;
}
.project-action {
	display: flex;
	min-height: 2.75rem;
	width: 100%;
	align-items: center;
	gap: 0.75rem;
	padding: 0.5rem 0.625rem;
	border-radius: 10px;
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ink);
	text-align: left;
	transition: background-color var(--dur-fast) ease, color var(--dur-fast) ease;
}
.project-action:hover:not(:disabled) {
	background: var(--navy-50);
	color: var(--navy-900);
}
.project-action:disabled {
	cursor: not-allowed;
	opacity: 0.5;
}
.project-action__icon {
	box-sizing: content-box;
	padding: 0.375rem;
	border-radius: 8px;
	background: var(--soft);
	color: var(--navy-900);
}

/* Waiting queue */
.waiting-group + .waiting-group {
	border-top: 1px solid var(--line);
}
.waiting-row {
	display: flex;
	min-height: 2.5rem;
	align-items: center;
	gap: 0.625rem;
	padding: 0.375rem 0.625rem;
	border-radius: 10px;
	transition: background-color var(--dur-fast) ease;
}
.waiting-row:hover {
	background: color-mix(in srgb, var(--navy-50) 75%, transparent);
}
.waiting-row__open {
	display: inline-flex;
	flex-shrink: 0;
	align-items: center;
	gap: 0.25rem;
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--navy-600);
	opacity: 0.75;
	transition: opacity var(--dur-fast) ease, gap var(--dur-fast) ease;
}
.waiting-row:hover .waiting-row__open {
	opacity: 1;
	gap: 0.375rem;
}

.resume-card {
	display: flex;
	min-width: 0;
	align-items: flex-start;
	gap: 0.75rem;
	padding: 0.75rem;
	border: 1px solid var(--line);
	border-radius: 12px;
	transition: border-color var(--dur-fast) ease, background-color var(--dur-fast) ease;
}
.resume-card:hover {
	border-color: var(--navy-200);
	background: color-mix(in srgb, var(--navy-50) 50%, transparent);
}
.text-ink-2 { color: var(--ink-2); }
</style>
