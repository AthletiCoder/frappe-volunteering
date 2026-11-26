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
                <button v-if="selected?.can_withdraw" type="button" class="btn-secondary" :disabled="closing" @click="closeAction = 'withdraw'">Withdraw claim</button>
                <button v-if="selected?.can_delete" type="button" class="btn-secondary" :disabled="closing" @click="closeAction = 'delete'">Delete draft</button>
				<button v-if="selected" type="button" class="btn-secondary" @click="closeDetail">
					Back to claims
				</button>
				<RouterLink v-else to="/expense-claim" class="btn-primary"
					>Submit an expense</RouterLink
				>
				<RouterLink v-if="!selected" to="/expense-claim/multiple" class="btn-secondary">Submit multiple invoices</RouterLink>
				<RouterLink to="/home" class="btn-back">Home</RouterLink>
			</template>
		</PageHeader>

		<p v-if="error" class="message-error" role="alert">{{ error }}</p>
		<p v-if="loading" class="text-muted" role="status">Loading your claims…</p>

		<template v-if="!loading && !selected">
			<div class="list-board">
				<aside class="min-w-0 space-y-4">
					<div class="filter-rail kit-panel" role="group" aria-label="Filter claims by status">
						<button v-for="option in stages" :key="option" type="button" class="filter-btn" :class="{ 'filter-btn--active': stage === option }" :aria-pressed="stage === option" @click="stage = option">
							<span class="filter-btn__dot" :class="statusDot(option)"></span>
							<span class="min-w-0 flex-1 truncate text-left">{{ option }}</span>
							<span class="filter-btn__count">{{ counts[option] || 0 }}</span>
						</button>
					</div>
					<div v-if="claims.length" class="kit-panel hidden p-4 lg:block">
						<p class="eyebrow">Claimed in this view</p>
						<p class="mt-1 font-display text-2xl font-semibold tabular-nums text-ink">{{ money(filteredTotal, claims[0]?.currency) }}</p>
						<p class="mt-1 text-xs text-muted">{{ filtered.length }} {{ filtered.length === 1 ? "claim" : "claims" }}</p>
					</div>
				</aside>
				<section class="min-w-0 space-y-3" aria-label="Claims">
					<label class="field-label relative block"><span class="sr-only">Find a claim</span><Icon name="search" size="sm" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" /><input v-model.trim="search" class="field-input !mt-0 pl-9" aria-label="Find a claim" placeholder="Search by claim number, project or purpose" /></label>
					<div v-if="!filtered.length" class="kit-panel flex flex-col items-center px-6 py-12 text-center">
						<span class="flex h-12 w-12 items-center justify-center rounded-2xl bg-navy-50 text-navy-900"><Icon name="receipt" /></span>
						<h2 class="mt-3 text-base font-semibold text-ink">No matching claims</h2>
						<p class="mt-1 text-sm text-muted">{{ claims.length ? "Try another status or search." : "You have not raised an expense claim yet." }}</p>
						<RouterLink to="/expense-claim" class="btn-primary mt-4 inline-flex">Submit an expense</RouterLink>
					</div>
					<div v-else class="kit-panel overflow-hidden">
						<div class="list-head" aria-hidden="true"><span>Claim</span><span>Status</span><span class="text-right">Amount</span><span></span></div>
						<button v-for="claim in filtered" :key="claim.name" type="button" class="list-row group" @click="openDetail(claim.name)">
							<span class="min-w-0">
								<span class="flex flex-wrap items-center gap-x-2"><strong class="text-sm text-ink">{{ claim.name }}</strong><span class="text-xs text-muted">{{ date(claim.posting_date) }}</span></span>
								<span class="mt-0.5 block truncate text-[13px] text-ink-2">{{ claim.purpose || "No purpose recorded" }}</span>
								<span class="block truncate text-xs text-muted">{{ claim.project_name || claim.project || "No project" }}</span>
							</span>
							<span class="list-row__status"><span :class="['status-pill', statusClass(claim.stage)]">{{ claim.stage }}</span><span class="mt-1 block text-xs text-muted">{{ claim.next_action }}</span></span>
							<span class="list-row__amount">{{ money(claim.claimed_amount, claim.currency) }}</span>
							<Icon name="arrow-right" size="sm" class="list-row__arrow" />
						</button>
					</div>
				</section>
			</div>
		</template>

		<template v-if="!loading && selected">
			<section v-if="closeAction" class="kit-panel mb-5 p-5" role="region" aria-label="Close claim">
				<h2 class="font-display text-base font-semibold text-ink">{{ closeAction === 'delete' ? 'Delete this unsubmitted draft?' : 'Withdraw this claim?' }}</h2>
				<p class="mb-3 mt-1 text-sm text-muted">{{ closeAction === 'delete' ? 'This removes the draft and its attachments.' : 'This closes the claim and removes it from review. Its receipts and withdrawal reason stay in the history. It cannot be reopened.' }}</p>
				<label v-if="closeAction === 'withdraw'" class="field-label">Withdrawal reason<textarea v-model.trim="withdrawalReason" maxlength="1000" rows="2" class="field-input" :disabled="closing"></textarea></label>
				<div class="mt-3 flex gap-3"><button type="button" class="btn-secondary" :disabled="closing" @click="closeAction = ''">Keep claim</button><button type="button" class="btn-primary" :disabled="closing || (closeAction === 'withdraw' && !withdrawalReason)" @click="closeClaim">{{ closing ? 'Saving…' : closeAction === 'delete' ? 'Delete draft permanently' : 'Confirm withdrawal' }}</button></div>
			</section>

			<section class="kit-panel detail-hero">
				<div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
					<div class="min-w-0 flex-1">
						<span :class="['status-pill', statusClass(selected.stage)]">{{ selected.stage }}</span>
						<h2 class="mt-3 font-display text-lg font-semibold text-ink">{{ selected.next_action }}</h2>
						<p v-if="selected.pending_with" class="mt-1 text-sm text-muted">Currently with {{ selected.pending_with }}</p>
					</div>
					<div class="shrink-0 text-left sm:text-right">
						<p class="text-xs text-muted">Claimed</p>
						<p class="font-display text-2xl font-semibold tabular-nums text-ink">{{ money(selected.claimed_amount, selected.currency) }}</p>
						<p class="mt-0.5 text-xs text-muted">Submitted {{ dateTime(selected.creation) }}</p>
					</div>
				</div>
				<ProgressTracker class="mt-5 border-t border-line pt-5" :steps="claimSteps(selected.stage, selected.timeline, selected.pending_with)" label="Claim progress" />
			</section>
			<p v-if="selected.withdrawal_reason" class="mt-4 rounded-2xl bg-soft p-4 text-sm text-ink">Withdrawn: {{ selected.withdrawal_reason }}</p>

			<div class="form-layout mt-5">
				<div class="min-w-0 space-y-5">
					<div v-if="selected.is_emergency" class="rounded-2xl border border-warn/40 bg-warn-soft p-4 text-sm text-ink">
						<strong>Emergency expense</strong>
						<p class="mt-1">{{ selected.emergency_reason }}</p>
					</div>

					<section v-if="selected.related_invoices?.length > 1" class="kit-panel overflow-hidden">
						<header class="border-b border-line px-5 py-4">
							<h2 class="font-display text-base font-semibold text-ink">Invoices in this submission</h2>
							<p class="mt-1 text-sm text-muted">Combined amount for approval: {{ money(selected.expense_submission_total, selected.currency) }}. Each invoice is reviewed and posted separately.</p>
						</header>
						<button v-for="invoice in selected.related_invoices" :key="invoice.name" type="button" class="list-row group" :aria-current="invoice.name === selected.name ? 'true' : undefined" @click="openDetail(invoice.name)">
							<span class="min-w-0"><strong class="text-sm text-ink">{{ invoice.name }}</strong><span class="block text-xs text-muted">{{ date(invoice.posting_date) }} · {{ invoice.workflow_state }}</span></span>
							<span class="list-row__amount">{{ money(invoice.total_claimed_amount, selected.currency) }}</span>
						</button>
					</section>

					<section class="kit-panel overflow-hidden">
						<header class="border-b border-line px-5 py-4">
							<h2 class="font-display text-base font-semibold text-ink">Expense items and receipts</h2>
							<p v-if="selected.purpose" class="mt-1 text-sm text-muted">{{ selected.purpose }}</p>
						</header>
						<article
							v-for="(item, index) in selected.expenses"
							:key="`${index}-${item.expense_date}`"
							class="claim-item"
						>
							<span class="claim-item__icon" aria-hidden="true"><Icon name="receipt" size="sm" /></span>
							<div class="min-w-0 flex-1">
								<div class="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
									<strong class="text-sm text-ink">{{ item.category }}</strong>
									<strong class="tabular-nums text-ink">{{ money(item.amount, selected.currency) }}</strong>
								</div>
								<p class="mt-1 text-sm text-ink-2">{{ item.description }}</p>
								<p class="mt-1 text-xs text-muted">
									{{ date(item.expense_date) }}<template v-if="item.supplier_name || item.invoice_number"> · {{ item.supplier_name || "Supplier not recorded" }}<span v-if="item.invoice_number"> · {{ item.invoice_number }}</span></template>
								</p>
								<a
									v-if="item.receipt_attachment"
									:href="item.receipt_attachment"
									target="_blank"
									rel="noopener"
									class="link-arrow mt-2 inline-flex"
									>View attached receipt</a
								>
							</div>
						</article>
					</section>

					<section v-if="selected.receipt_review_notes" class="kit-panel p-5">
						<h2 class="font-display text-base font-semibold text-ink">Receipt-review notes</h2>
						<p class="mt-2 whitespace-pre-wrap text-sm">{{ selected.receipt_review_notes }}</p>
						<p v-if="selected.receipt_reviewed_on" class="mt-2 text-xs text-muted">
							{{ dateTime(selected.receipt_reviewed_on) }}
						</p>
					</section>
				</div>

				<aside class="form-rail min-w-0 space-y-4" aria-label="Claim facts">
					<div class="summary-card">
						<p class="eyebrow">Money</p>
						<dl class="summary-list !mt-2 !border-t-0 !pt-0">
							<div><dt>Claimed</dt><dd>{{ money(selected.claimed_amount, selected.currency) }}</dd></div>
							<div><dt>Approved</dt><dd>{{ selected.is_approved ? money(selected.approved_amount, selected.currency) : selected.stage === 'Withdrawn' || selected.stage === 'Rejected' ? 'Not approved' : 'Awaiting approval' }}</dd></div>
							<div><dt>Paid / settled</dt><dd>{{ money(selected.reimbursed_amount, selected.currency) }}</dd></div>
							<div class="border-t border-line pt-2"><dt class="font-semibold text-ink">Outstanding</dt><dd>{{ selected.outstanding_amount == null ? 'Awaiting approval' : money(selected.outstanding_amount, selected.currency) }}</dd></div>
						</dl>
					</div>
					<div class="kit-panel p-5">
						<p class="eyebrow">Details</p>
						<dl class="summary-list !mt-2 !border-t-0 !pt-0">
							<div><dt>Project</dt><dd>{{ selected.project_name || selected.project || '—' }}</dd></div>
							<div><dt>Payment source</dt><dd>{{ selected.source }}</dd></div>
							<div><dt>Receipt review</dt><dd>{{ selected.receipt_review_status }}</dd></div>
							<div><dt>Invoice / accounting date</dt><dd>{{ date(selected.posting_date) }}</dd></div>
						</dl>
					</div>
					<section class="kit-panel p-5">
						<h2 class="mb-4 font-display text-base font-semibold text-ink">Status history</h2>
						<ActivityTimeline :events="historyEvents" />
					</section>
				</aside>
			</div>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import { dotClass } from "../lib/tones.js";
import Icon from "../components/Icon.vue";
import ProgressTracker from "../components/ProgressTracker.vue";
import ActivityTimeline from "../components/ActivityTimeline.vue";
import { claimSteps } from "../lib/requestProgress.js";
import { call } from "../lib/frappe";

const API = "volunteering.volunteering.expense_claim_portal.";
const route = useRoute();
const router = useRouter();
const loading = ref(true);
const error = ref("");
const claims = ref([]);
const counts = ref({});
const selected = ref(null);
const closeAction = ref(""), withdrawalReason = ref(""), closing = ref(false);
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
	"Withdrawn",
	"Accounts classification",
];

const filteredTotal = computed(() => filtered.value.reduce((sum, claim) => sum + Number(claim.claimed_amount || 0), 0));
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

async function closeClaim() {
    if (closing.value) return;
    closing.value = true; error.value = "";
    try {
        const name = selected.value.name, expected_modified = selected.value.modified;
        if (closeAction.value === "delete") {
            await call("volunteering.volunteering.expense_claim_withdrawal.delete_expense_claim_draft", { name, expected_modified });
            closeAction.value = ""; await closeDetail();
        } else {
            selected.value = await call("volunteering.volunteering.expense_claim_withdrawal.withdraw_expense_claim", { name, expected_modified, reason: withdrawalReason.value });
            closeAction.value = "";
        }
    } catch (e) { error.value = e.message; }
    finally { closing.value = false; }
}
async function loadDetail(name) {
    closeAction.value = ""; withdrawalReason.value = "";
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

const historyEvents = computed(() =>
	(selected.value?.timeline || []).map((event) => ({
		label: event.label,
		meta: [dateTime(event.when), event.by].filter(Boolean).join(" · "),
		detail: event.detail,
	})),
);

function dateTime(value) {
	if (!value) return "—";
	return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(
		new Date(value),
	);
}

// Rail dots need a solid colour; the pill classes only carry pale backgrounds.
function statusDot(value) {
	const tone = { "status-ok": "ok", "status-bad": "bad", "status-warn": "warn" }[statusClass(value)];
	return dotClass(value === "All" ? "info" : tone || "muted");
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
.text-ink-2 { color: var(--ink-2); }
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
.detail-hero { padding: 1.25rem; }
@media (min-width: 640px) { .detail-hero { padding: 1.5rem; } }
.claim-item { display: flex; gap: 0.875rem; padding: 1rem 1.25rem; }
.claim-item + .claim-item { border-top: 1px solid var(--line); }
.claim-item__icon { display: inline-flex; width: 2.25rem; height: 2.25rem; flex-shrink: 0; align-items: center; justify-content: center; border-radius: 10px; background: var(--navy-50); color: var(--navy-900); }
.text-ink-2 { color: var(--ink-2); }
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
</style>
