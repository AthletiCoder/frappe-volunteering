<template>
	<div>
		<div v-if="error" class="message-error mb-4" role="alert">{{ error }}</div>
		<div v-else-if="!payload" class="space-y-4" aria-busy="true">
			<span class="sr-only">Loading…</span>
			<div class="skeleton h-9 w-56"></div>
			<div class="grid gap-5 lg:grid-cols-[15rem_minmax(0,1fr)]">
				<div class="skeleton h-56 rounded-2xl"></div>
				<div class="skeleton h-96 rounded-2xl"></div>
			</div>
		</div>
		<div v-else-if="!payload.allowed" class="form-card">
			<h1 class="text-2xl font-semibold text-ink">Waiting is for staff</h1>
			<p class="mt-2 text-sm text-muted">{{ payload.greeting }}</p>
		</div>
		<div v-else>
			<PageHeader eyebrow="Home" title="Waiting" :subtitle="summaryLine">
				<template #actions>
					<RouterLink to="/home" class="btn-back">Back to Home</RouterLink>
				</template>
			</PageHeader>

			<div class="waiting-board">
				<!-- Filters: a vertical rail on wide screens, a wrapping row on phones. -->
				<aside class="min-w-0 space-y-4">
					<div class="filter-rail kit-panel" role="group" aria-label="Filter waiting items">
						<button
							v-for="chip in chips"
							:key="chip.id"
							type="button"
							class="filter-btn"
							:class="{ 'filter-btn--active': filter === chip.id }"
							:aria-pressed="filter === chip.id"
							@click="filter = chip.id"
						>
							<span class="filter-btn__icon" :class="chip.tone"><Icon :name="chip.icon" size="sm" /></span>
							<span class="min-w-0 flex-1 truncate text-left">{{ chip.label }}</span>
							<span class="filter-btn__count">{{ chip.count }}</span>
						</button>
					</div>
					<div v-if="oldestDays !== null" class="kit-panel hidden p-4 lg:block">
						<p class="eyebrow">Oldest in this view</p>
						<p class="mt-1 font-display text-2xl font-semibold tabular-nums text-ink">{{ oldestDays }} {{ oldestDays === 1 ? "day" : "days" }}</p>
						<p class="mt-1 text-xs leading-relaxed text-muted">Clearing the oldest first keeps people from waiting on you.</p>
					</div>
				</aside>

				<!-- The queue, grouped by the person or record it is about. -->
				<section class="min-w-0" aria-labelledby="waiting-list-title">
					<div class="mb-3 flex items-center justify-between gap-3 px-1">
						<h2 id="waiting-list-title" class="flex items-center gap-2 text-base font-semibold">{{ listTitle }} <span class="chip bg-soft text-ink-2 tabular-nums">{{ filtered.length }}</span></h2>
						<p v-if="pageCount > 1" class="text-xs text-muted">Page {{ page }} of {{ pageCount }}</p>
					</div>

					<div v-if="groups.length" class="kit-panel overflow-hidden">
						<div class="waiting-head" aria-hidden="true">
							<span>Type</span><span>Details</span><span class="text-right">Waiting</span><span></span>
						</div>
						<div v-for="group in groups" :key="group.key" class="waiting-group">
							<div class="flex items-center gap-3 px-4 pb-1 pt-3.5 sm:px-5">
								<Avatar :name="group.title" size="sm" :tone="group.bucket === 'pay' ? 'amber' : group.bucket === 'resume' ? 'slate' : ''" />
								<p class="min-w-0 flex-1 truncate text-sm font-semibold text-ink">{{ group.title }}</p>
								<span class="text-xs tabular-nums text-muted">{{ group.items.length }} {{ group.items.length === 1 ? "item" : "items" }}</span>
							</div>
							<ul class="px-2 pb-2 sm:px-3">
								<li v-for="item in group.items" :key="item.id">
									<a :href="item.route" class="waiting-item group">
										<span class="waiting-item__kind"><span class="kind-tag" :class="bucketTag(item.bucket)">{{ item.kind }}</span></span>
										<span class="waiting-item__details">{{ item.bucket === "resume" ? [item.title, item.subtitle].filter(Boolean).join(" · ") : item.subtitle || item.title }}</span>
										<span class="waiting-item__age" :class="{ 'waiting-item__age--old': ageDays(item) >= 7 }">{{ ageLabel(item) }}</span>
										<span class="waiting-item__open"><span class="hidden sm:inline">Open</span><Icon name="arrow-right" size="sm" /></span>
									</a>
								</li>
							</ul>
						</div>
					</div>
					<div v-else class="kit-panel flex flex-col items-center px-6 py-12 text-center">
						<span class="flex h-12 w-12 items-center justify-center rounded-2xl bg-ok-soft text-ok"><Icon name="check" /></span>
						<h3 class="mt-3 text-sm font-semibold text-ink">Nothing here</h3>
						<p class="mt-1 text-sm text-muted">Nothing in this filter. You’re clear.</p>
					</div>

					<div v-if="pageCount > 1" class="mt-4 flex items-center justify-between text-sm">
						<button type="button" class="btn-secondary text-sm" :disabled="page <= 1" @click="page = Math.max(1, page - 1)">Previous</button>
						<span class="text-muted">Page {{ page }} of {{ pageCount }}</span>
						<button type="button" class="btn-secondary text-sm" :disabled="page >= pageCount" @click="page = Math.min(pageCount, page + 1)">Next</button>
					</div>
				</section>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { homePayload, loadHomePayload } from "../lib/home";
import Avatar from "../components/Avatar.vue";
import Icon from "../components/Icon.vue";
import PageHeader from "../components/PageHeader.vue";

const PAGE_SIZE = 20;
const DAY = 86400000;

const route = useRoute();
const error = ref("");
const payload = computed(() => homePayload.value);
const filter = ref("all");
const page = ref(1);

const waiting = computed(() => payload.value?.waiting || payload.value?.todos || []);
const resume = computed(() => payload.value?.resume || []);

const filtered = computed(() => {
	if (filter.value === "resume") return resume.value;
	if (filter.value === "review") return waiting.value.filter((row) => row.bucket === "review");
	if (filter.value === "pay") return waiting.value.filter((row) => row.bucket === "pay");
	return [...waiting.value, ...resume.value];
});

const pageCount = computed(() => Math.max(1, Math.ceil(filtered.value.length / PAGE_SIZE)));
const pageItems = computed(() => {
	const start = (page.value - 1) * PAGE_SIZE;
	return filtered.value.slice(start, start + PAGE_SIZE);
});

function stamp(item) {
	const raw = item.raised_at || item.modified;
	if (!raw) return null;
	const time = new Date(String(raw).replace(" ", "T")).getTime();
	return Number.isNaN(time) ? null : time;
}
function ageDays(item) {
	const time = stamp(item);
	return time === null ? -1 : Math.max(0, Math.floor((Date.now() - time) / DAY));
}
function ageLabel(item) {
	const days = ageDays(item);
	if (days < 0) return "";
	if (days === 0) return "Today";
	if (days === 1) return "1 day";
	if (days < 60) return `${days} days`;
	return `${Math.round(days / 30)} months`;
}
function bucketTag(bucket) {
	if (bucket === "pay") return "kind-tag--pay";
	if (bucket === "resume") return "kind-tag--draft";
	return "";
}

const groups = computed(() => {
	const map = new Map();
	for (const item of pageItems.value) {
		const draft = item.bucket === "resume";
		const key = draft ? "resume::" : `${item.bucket || ""}::${item.title || ""}`;
		if (!map.has(key)) map.set(key, { key, title: draft ? "Your drafts" : item.title, bucket: item.bucket, items: [] });
		map.get(key).items.push(item);
	}
	return [...map.values()];
});

const oldestDays = computed(() => {
	const ages = filtered.value.map(ageDays).filter((days) => days >= 0);
	return ages.length ? Math.max(...ages) : null;
});

const chips = computed(() => [
	{ id: "all", label: "All", count: waiting.value.length + resume.value.length, icon: "clipboard-check", tone: "bg-navy-50 text-navy-900" },
	{ id: "review", label: "Decide", count: waiting.value.filter((row) => row.bucket === "review").length, icon: "check", tone: "bg-marigold-soft text-[#7a4a00]" },
	{ id: "pay", label: "Pay", count: waiting.value.filter((row) => row.bucket === "pay").length, icon: "wallet", tone: "bg-warn-soft text-warn" },
	{ id: "resume", label: "Drafts", count: resume.value.length, icon: "document-history", tone: "bg-soft text-muted" },
]);

const listTitle = computed(() => ({ all: "Everything waiting", review: "To decide", pay: "To pay", resume: "Your drafts" })[filter.value] || "Waiting");
const summaryLine = computed(() => {
	const decide = chips.value[1].count, pay = chips.value[2].count, drafts = chips.value[3].count;
	const parts = [];
	if (decide) parts.push(`${decide} to decide`);
	if (pay) parts.push(`${pay} to pay`);
	if (drafts) parts.push(`${drafts} ${drafts === 1 ? "draft" : "drafts"} to finish`);
	return parts.length ? `${parts.join(" · ")}.` : "Nothing needs a decision or follow-up right now.";
});

watch(filter, () => {
	page.value = 1;
});

onMounted(async () => {
	const bucket = route.query.bucket;
	if (typeof bucket === "string" && ["review", "pay", "resume", "all"].includes(bucket)) {
		filter.value = bucket;
	}
	try {
		await loadHomePayload({ notify: false });
	} catch (e) {
		error.value = e.message || String(e);
	}
});
</script>

<style scoped>
.waiting-board {
	display: grid;
	gap: 1.25rem;
	align-items: start;
}
@media (min-width: 1024px) {
	.waiting-board {
		grid-template-columns: 15rem minmax(0, 1fr);
		gap: 1.5rem;
	}
	.waiting-board > aside {
		position: sticky;
		top: 5.5rem;
	}
}

/* Filter buttons use the shared .filter-rail / .filter-btn kit. */
/* Queue: a table on wide screens, stacked rows on phones. */
.waiting-head {
	display: none;
}
@media (min-width: 768px) {
	.waiting-head {
		display: grid;
		grid-template-columns: 8.5rem minmax(0, 1fr) 6.5rem 4rem;
		gap: 1rem;
		padding: 0.625rem 1.5rem 0.625rem calc(0.75rem + 0.625rem);
		border-bottom: 1px solid var(--line);
		background: var(--soft);
		font-size: 0.6875rem;
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--muted);
	}
}
.waiting-group + .waiting-group {
	border-top: 1px solid var(--line);
}
.waiting-item {
	display: grid;
	grid-template-columns: auto minmax(0, 1fr) auto;
	grid-template-areas: "kind age open" "details details details";
	align-items: center;
	gap: 0.25rem 0.625rem;
	min-height: 2.75rem;
	padding: 0.5rem 0.625rem;
	border-radius: 10px;
	transition: background-color var(--dur-fast) ease;
}
@media (min-width: 768px) {
	.waiting-item {
		grid-template-columns: 8.5rem minmax(0, 1fr) 6.5rem 4rem;
		grid-template-areas: "kind details age open";
		gap: 1rem;
	}
}
.waiting-item:hover {
	background: color-mix(in srgb, var(--navy-50) 75%, transparent);
}
.waiting-item__kind { grid-area: kind; min-width: 0; }
.waiting-item__details {
	grid-area: details;
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	font-size: 0.8125rem;
	color: var(--ink-2);
}
.waiting-item__age {
	grid-area: age;
	font-size: 0.75rem;
	font-variant-numeric: tabular-nums;
	color: var(--muted);
}
@media (min-width: 768px) {
	.waiting-item__age { text-align: right; }
}
.waiting-item__age--old { color: var(--todo); font-weight: 600; }
.waiting-item__open {
	grid-area: open;
	display: inline-flex;
	justify-self: end;
	align-items: center;
	gap: 0.25rem;
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--navy-600);
	opacity: 0.75;
	transition: opacity var(--dur-fast) ease, gap var(--dur-fast) ease;
}
.waiting-item:hover .waiting-item__open { opacity: 1; gap: 0.375rem; }
.kind-tag--pay { background: var(--warn-soft); color: var(--warn); }
.kind-tag--draft { background: var(--marigold-soft); color: #7a4a00; }
</style>
