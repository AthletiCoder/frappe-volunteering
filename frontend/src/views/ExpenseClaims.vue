<template>
	<div>
		<PageHeader
			:eyebrow="selected ? 'Expense claim' : 'Expenses'"
			:title="selected ? selected.name : 'My reimbursement claims'"
			:subtitle="
				selected
					? `${selected.project_name || selected.project || 'No project'} · ${selected.stage}`
					: 'Track receipt review, approval and payment for every claim you have raised.'
			"
		>
			<template #actions>
				<RouterLink
					v-if="selected?.can_correct"
					:to="{ path: '/expense-claim', query: { correct: selected.name } }"
					class="btn-primary"
					>Correct and resubmit</RouterLink
				>
				<button v-if="selected" type="button" class="btn-secondary" @click="closeDetail">
					Back to claims
				</button>
				<RouterLink v-else to="/expense-claim" class="btn-primary"
					>Submit an expense</RouterLink
				>
				<RouterLink to="/home" class="btn-secondary">Home</RouterLink>
			</template>
		</PageHeader>

		<p v-if="error" class="message-error" role="alert">{{ error }}</p>
		<p v-if="loading" class="text-muted" role="status">Loading your claims…</p>

		<template v-if="!loading && !selected">
			<section class="form-card mb-5">
				<div class="grid gap-4 sm:grid-cols-[minmax(0,1fr)_minmax(12rem,0.35fr)]">
					<label class="field-label"
						>Find a claim<input
							v-model.trim="search"
							class="field-input"
							placeholder="Search by claim number, project or purpose"
					/></label>
					<label class="field-label"
						>Status<select v-model="stage" class="field-input">
							<option v-for="option in stages" :key="option" :value="option">
								{{ option }} ({{ counts[option] || 0 }})
							</option>
						</select></label
					>
				</div>
			</section>

			<div v-if="!filtered.length" class="form-card text-center py-10">
				<h2 class="text-lg font-semibold text-ink">No matching claims</h2>
				<p class="text-sm text-muted mt-2">
					{{
						claims.length
							? "Try another status or search."
							: "You have not raised an expense claim yet."
					}}
				</p>
				<RouterLink to="/expense-claim" class="btn-primary mt-4 inline-flex"
					>Submit an expense</RouterLink
				>
			</div>

			<div class="space-y-3">
				<button
					v-for="claim in filtered"
					:key="claim.name"
					type="button"
					class="claim-card w-full text-left"
					@click="openDetail(claim.name)"
				>
					<div class="flex flex-wrap items-start justify-between gap-3">
						<div class="min-w-0">
							<div class="flex flex-wrap items-center gap-2">
								<strong class="text-ink">{{ claim.name }}</strong>
								<span :class="['status-pill', statusClass(claim.stage)]">{{
									claim.stage
								}}</span>
							</div>
							<p class="text-sm text-muted mt-1 truncate">
								{{ claim.project_name || claim.project || "No project" }}
							</p>
							<p class="text-sm text-ink mt-2">
								{{ claim.purpose || "No purpose recorded" }}
							</p>
						</div>
						<div class="sm:text-right shrink-0">
							<p class="font-semibold text-ink">
								{{ money(claim.claimed_amount, claim.currency) }}
							</p>
							<p class="text-xs text-muted mt-1">{{ date(claim.posting_date) }}</p>
						</div>
					</div>
					<div
						class="mt-3 border-t border-line pt-3 flex flex-wrap justify-between gap-2 text-xs"
					>
						<span class="text-muted">{{ claim.next_action }}</span>
						<span class="font-medium text-accent">View status and history →</span>
					</div>
				</button>
			</div>
		</template>

		<template v-if="!loading && selected">
			<section class="form-card mb-5">
				<div class="flex flex-wrap items-start justify-between gap-3">
					<div>
						<span :class="['status-pill', statusClass(selected.stage)]">{{
							selected.stage
						}}</span>
						<h2 class="text-lg font-semibold text-ink mt-3">
							{{ selected.next_action }}
						</h2>
						<p v-if="selected.pending_with" class="text-sm text-muted mt-1">
							Currently with {{ selected.pending_with }}
						</p>
					</div>
					<div class="sm:text-right">
						<p class="text-xs text-muted">Submitted</p>
						<p class="font-medium text-ink">{{ date(selected.posting_date) }}</p>
					</div>
				</div>
			</section>

			<section class="form-card mb-5">
				<h2 class="form-title">Claim summary</h2>
				<div class="grid gap-4 sm:grid-cols-2">
					<SummaryItem
						label="Project"
						:value="selected.project_name || selected.project || '—'"
					/>
					<SummaryItem label="Payment source" :value="selected.source" />
					<SummaryItem label="Purpose" :value="selected.purpose || '—'" />
					<SummaryItem label="Receipt review" :value="selected.receipt_review_status" />
				</div>
				<div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-5">
					<AmountBox
						label="Claimed"
						:value="money(selected.claimed_amount, selected.currency)"
					/>
					<AmountBox
						label="Approved"
						:value="money(selected.sanctioned_amount, selected.currency)"
					/>
					<AmountBox
						label="Paid / settled"
						:value="money(selected.reimbursed_amount, selected.currency)"
					/>
					<AmountBox
						label="Outstanding"
						:value="money(selected.outstanding_amount, selected.currency)"
						accent
					/>
				</div>
				<div v-if="selected.is_emergency" class="warning-box mt-4">
					<strong>Emergency expense</strong>
					<p class="mt-1">{{ selected.emergency_reason }}</p>
				</div>
			</section>

			<section class="form-card mb-5">
				<h2 class="form-title">Expense items and receipts</h2>
				<article
					v-for="(item, index) in selected.expenses"
					:key="`${index}-${item.expense_date}`"
					class="border-t border-line first:border-t-0 py-4 first:pt-0 last:pb-0"
				>
					<div class="flex flex-wrap justify-between gap-3">
						<div>
							<strong class="text-ink">{{ item.category }}</strong>
							<p class="text-sm text-muted mt-1">{{ item.description }}</p>
							<p
								v-if="item.supplier_name || item.invoice_number"
								class="text-xs text-muted mt-1"
							>
								{{ item.supplier_name || "Supplier not recorded" }}
								<span v-if="item.invoice_number">
									· {{ item.invoice_number }}</span
								>
							</p>
						</div>
						<div class="sm:text-right">
							<p class="font-semibold">
								{{ money(item.amount, selected.currency) }}
							</p>
							<p class="text-xs text-muted">{{ date(item.expense_date) }}</p>
						</div>
					</div>
					<a
						v-if="item.receipt_attachment"
						:href="item.receipt_attachment"
						target="_blank"
						rel="noopener"
						class="text-sm text-accent underline mt-2 inline-block"
						>View attached receipt</a
					>
				</article>
			</section>

			<section v-if="selected.receipt_review_notes" class="form-card mb-5">
				<h2 class="form-title">Receipt-review notes</h2>
				<p class="text-sm whitespace-pre-wrap">{{ selected.receipt_review_notes }}</p>
				<p v-if="selected.receipt_reviewed_on" class="text-xs text-muted mt-2">
					{{ dateTime(selected.receipt_reviewed_on) }}
				</p>
			</section>

			<section class="form-card">
				<h2 class="form-title">Status history</h2>
				<ol class="space-y-4">
					<li
						v-for="(event, index) in selected.timeline"
						:key="`${event.when}-${index}`"
						class="timeline-row"
					>
						<span class="timeline-dot" aria-hidden="true"></span>
						<div>
							<strong class="text-sm text-ink">{{ event.label }}</strong>
							<p class="text-xs text-muted mt-0.5">
								{{ dateTime(event.when)
								}}<span v-if="event.by"> · {{ event.by }}</span>
							</p>
							<p v-if="event.detail" class="text-sm mt-1 whitespace-pre-wrap">
								{{ event.detail }}
							</p>
						</div>
					</li>
				</ol>
			</section>
		</template>
	</div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import { call } from "../lib/frappe";

const API = "volunteering.volunteering.expense_claim_portal.";
const route = useRoute();
const router = useRouter();
const loading = ref(true);
const error = ref("");
const claims = ref([]);
const counts = ref({});
const selected = ref(null);
const stage = ref("All");
const search = ref("");
const stages = [
	"All",
	"Draft",
	"Needs correction",
	"Receipt review",
	"Manager approval",
	"Approved / unpaid",
	"Paid",
	"Rejected",
	"Cancelled",
];

const filtered = computed(() => {
	const needle = search.value.toLowerCase();
	return claims.value.filter(
		(claim) =>
			(stage.value === "All" || claim.stage === stage.value) &&
			`${claim.name} ${claim.project_name || ""} ${claim.project || ""} ${claim.purpose || ""}`
				.toLowerCase()
				.includes(needle),
	);
});

const SummaryItem = defineComponent({
	props: { label: String, value: [String, Number] },
	setup(props) {
		return () =>
			h("div", { class: "rounded-xl bg-soft p-3" }, [
				h("p", { class: "text-xs text-muted" }, props.label),
				h("p", { class: "text-sm font-medium text-ink mt-1" }, String(props.value || "—")),
			]);
	},
});

const AmountBox = defineComponent({
	props: { label: String, value: String, accent: Boolean },
	setup(props) {
		return () =>
			h(
				"div",
				{
					class: `rounded-xl border border-line p-3 ${props.accent ? "bg-accent-soft" : "bg-bg"}`,
				},
				[
					h("p", { class: "text-xs text-muted" }, props.label),
					h("p", { class: "font-semibold text-ink mt-1" }, props.value),
				],
			);
	},
});

async function load() {
	loading.value = true;
	error.value = "";
	try {
		const result = await call(`${API}get_my_expense_claims`);
		claims.value = result.claims || [];
		counts.value = result.counts || {};
		if (route.query.claim) await loadDetail(String(route.query.claim));
		else selected.value = null;
	} catch (e) {
		error.value = e.message || String(e);
		selected.value = null;
	} finally {
		loading.value = false;
	}
}

async function loadDetail(name) {
	selected.value = await call(`${API}get_my_expense_claim`, { name });
}

async function openDetail(name) {
	await router.push({ path: "/expense-claims", query: { claim: name } });
}

async function closeDetail() {
	await router.push({ path: "/expense-claims" });
}

function money(value, currency = "INR") {
	return new Intl.NumberFormat("en-IN", {
		style: "currency",
		currency: currency || "INR",
		maximumFractionDigits: 2,
	}).format(Number(value || 0));
}

function date(value) {
	if (!value) return "—";
	return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium" }).format(new Date(value));
}

function dateTime(value) {
	if (!value) return "—";
	return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(
		new Date(value),
	);
}

function statusClass(value) {
	if (value === "Paid") return "status-ok";
	if (["Needs correction", "Rejected", "Cancelled"].includes(value)) return "status-bad";
	if (["Receipt review", "Manager approval", "Approved / unpaid"].includes(value))
		return "status-warn";
	return "status-neutral";
}

watch(() => route.fullPath, load);
onMounted(load);
</script>

<style scoped>
.form-card {
	@apply rounded-2xl border border-line bg-surface p-4 sm:p-5 shadow-soft;
}
.form-title {
	@apply text-lg font-semibold text-ink mb-3;
}
.field-label {
	@apply block text-sm font-medium text-ink;
}
.field-input {
	@apply mt-1 block w-full rounded-xl border border-line bg-surface px-3 py-2.5 text-sm text-ink;
}
.claim-card {
	@apply rounded-2xl border border-line bg-surface p-4 shadow-soft transition-all duration-150 hover:-translate-y-0.5 hover:shadow-lift;
}
.status-pill {
	@apply inline-flex rounded-full px-2.5 py-1 text-xs font-semibold;
}
.status-ok {
	@apply bg-ok-soft text-ok;
}
.status-warn {
	@apply bg-warn-soft text-warn;
}
.status-bad {
	@apply bg-bad-soft text-bad;
}
.status-neutral {
	@apply bg-soft text-muted;
}
.timeline-row {
	@apply relative grid grid-cols-[0.75rem_minmax(0,1fr)] gap-3;
}
.timeline-row:not(:last-child)::before {
	content: "";
	@apply absolute left-[0.3rem] top-3 h-[calc(100%+0.5rem)] w-px bg-line;
}
.timeline-dot {
	@apply relative z-10 mt-1 h-2.5 w-2.5 rounded-full bg-accent;
}
.message-error {
	@apply rounded-xl border border-bad bg-bad-soft p-4 text-sm text-bad;
}
.warning-box {
	@apply rounded-xl border border-warn bg-warn-soft p-3 text-sm text-ink;
}
</style>
