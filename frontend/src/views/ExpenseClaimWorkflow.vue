<template>
	<div>
		<PageHeader
			eyebrow="Expenses"
			:title="selected ? selected.name : 'Expense claim work'"
			:subtitle="
				selected
					? `${selected.employee_name} · ${selected.project_name || selected.project}`
					: 'Verify receipts, decide claims and reimburse approved expenses from Home.'
			"
		>
			<template #actions>
				<button v-if="selected" type="button" class="btn-secondary" @click="closeDetail">
					Back to queue
				</button>
				<RouterLink to="/home" class="btn-secondary">Home</RouterLink>
			</template>
		</PageHeader>

		<p v-if="error" class="error-box mb-4" role="alert">{{ error }}</p>
		<p v-if="success" class="success-box mb-4" role="status">{{ success }}</p>
		<p v-if="loading" class="text-muted" role="status">Loading expense claims…</p>

		<template v-if="!loading && !selected">
			<div class="flex flex-wrap gap-2 mb-5">
				<button
					v-for="option in visibleTabs"
					:key="option.key"
					type="button"
					:class="['queue-tab', tab === option.key ? 'queue-tab-active' : '']"
					@click="tab = option.key"
				>
					{{ option.label }} <span>{{ counts[option.key] || 0 }}</span>
				</button>
			</div>

			<section v-if="!currentQueue.length" class="form-card text-center py-10">
				<h2 class="text-lg font-semibold">Nothing waiting here</h2>
				<p class="text-sm text-muted mt-2">This queue is clear.</p>
			</section>
			<div v-else class="space-y-3">
				<button
					v-for="claim in currentQueue"
					:key="claim.name"
					type="button"
					class="claim-card w-full text-left"
					@click="openDetail(claim.name)"
				>
					<div class="flex flex-wrap justify-between gap-3">
						<div>
							<strong>{{ claim.employee_name }}</strong>
							<p class="text-sm text-muted mt-1">
								{{ claim.name }} · {{ claim.project || "No project" }}
							</p>
						</div>
						<div class="sm:text-right">
							<strong>{{ money(claim.amount, claim.currency) }}</strong>
							<p class="text-xs text-muted mt-1">{{ date(claim.posting_date) }}</p>
						</div>
					</div>
				</button>
			</div>
		</template>

		<template v-if="!loading && selected">
			<section class="form-card mb-5">
				<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
					<Summary label="Employee" :value="selected.employee_name" />
					<Summary label="Project" :value="selected.project_name || selected.project" />
					<Summary label="Payment source" :value="selected.source" />
					<Summary label="Workflow" :value="selected.workflow_state" />
				</div>
				<div class="grid gap-3 grid-cols-2 sm:grid-cols-3 mt-4">
					<Amount
						label="Claimed"
						:value="money(selected.claimed_amount, selected.currency)"
					/>
					<Amount
						label="Sanctioned"
						:value="money(selected.sanctioned_amount, selected.currency)"
					/>
					<Amount
						label="Already settled"
						:value="money(selected.reimbursed_amount, selected.currency)"
					/>
				</div>
			</section>

			<section class="form-card mb-5">
				<h2 class="form-title">Expense items and receipts</h2>
				<article v-for="item in selected.expenses" :key="item.name" class="expense-row">
					<div class="flex flex-wrap justify-between gap-3">
						<div class="min-w-0">
							<strong>{{ item.category }}</strong>
							<p class="text-sm mt-1 whitespace-pre-wrap">{{ item.description }}</p>
							<p class="text-xs text-muted mt-1">
								{{ item.supplier_name || "Supplier not recorded" }}
								<span v-if="item.invoice_number">
									· {{ item.invoice_number }}</span
								>
								· {{ date(item.expense_date) }}
							</p>
						</div>
						<strong>{{ money(item.amount, selected.currency) }}</strong>
					</div>
					<a
						v-if="item.receipt_attachment"
						:href="item.receipt_attachment"
						target="_blank"
						rel="noopener"
						class="text-sm text-accent underline mt-2 inline-block"
						>Open private receipt</a
					>
				</article>
			</section>

			<section v-if="selected.access.receipt_review" class="form-card mb-5">
				<h2 class="form-title">Receipt review</h2>
				<p class="form-hint">Open the attached receipts before recording your decision.</p>
				<label class="field-label mt-4"
					>Review notes<textarea
						v-model.trim="review.notes"
						rows="3"
						class="field-input"
					></textarea>
				</label>
				<div class="flex flex-wrap justify-end gap-2 mt-4">
					<button
						type="button"
						class="btn-danger"
						:disabled="busy"
						@click="requestCorrection"
					>
						Request correction
					</button>
					<button
						type="button"
						class="btn-primary"
						:disabled="busy"
						@click="verifyReceipts"
					>
						Verify receipts
					</button>
				</div>
			</section>

			<section v-if="selected.access.approval" class="form-card mb-5">
				<h2 class="form-title">Manager decision</h2>
				<p class="form-hint">
					Approve the full claim or reduce individual sanctioned amounts. A zero total
					should be rejected.
				</p>
				<div class="space-y-3">
					<label v-for="item in selected.expenses" :key="item.name" class="sanction-row">
						<span>
							<strong>{{ item.category }}</strong>
							<small>Claimed {{ money(item.amount, selected.currency) }}</small>
						</span>
						<input
							v-model.number="sanctioned[item.name]"
							type="number"
							min="0"
							:max="item.amount"
							step="0.01"
							class="field-input mt-0"
							:aria-label="`Sanctioned amount for ${item.category}`"
						/>
					</label>
				</div>
				<p class="text-right font-semibold mt-3">
					Sanctioned total: {{ money(sanctionedTotal, selected.currency) }}
				</p>
				<div v-if="approvalMessage" class="warning-box mt-4">{{ approvalMessage }}</div>
				<label class="field-label mt-4"
					>Decision note / reason<textarea
						v-model.trim="decisionReason"
						rows="3"
						class="field-input"
					></textarea>
				</label>
				<div class="flex flex-wrap justify-end gap-2 mt-4">
					<button
						type="button"
						class="btn-danger"
						:disabled="busy"
						@click="decide('reject')"
					>
						Reject
					</button>
					<button
						v-if="selected.approval_flags.can_escalate"
						type="button"
						class="btn-secondary"
						:disabled="busy"
						@click="decide('escalate')"
					>
						Escalate
					</button>
					<button
						v-if="selected.approval_flags.can_approve"
						type="button"
						class="btn-primary"
						:disabled="busy"
						@click="decide('approve')"
					>
						Approve {{ money(sanctionedTotal, selected.currency) }}
					</button>
				</div>
			</section>

			<section v-if="selected.access.classification" class="form-card mb-5">
				<h2 class="form-title">Accounts classification</h2>
				<p class="form-hint">
					The manager has approved these amounts. Allocate every sanctioned item to one
					or more Expense Accounts. This submits the claim and posts the expense liability;
					payment remains a separate later step.
				</p>
				<div class="space-y-4">
					<section
						v-for="item in classificationRows"
						:key="item.expense_detail"
						class="rounded-xl border border-line bg-bg p-4"
					>
						<div class="flex flex-wrap justify-between gap-2 mb-3">
							<div>
								<strong>{{ item.label }}</strong>
								<p v-if="item.suggested_accounts.length" class="field-help mt-1">
									Project suggestions: {{ suggestedLabels(item) }}
								</p>
							</div>
							<strong>{{ money(item.required_amount, selected.currency) }}</strong>
						</div>
						<div class="space-y-3">
							<div
								v-for="(allocation, index) in item.allocations"
								:key="`${item.expense_detail}-${index}`"
								class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_10rem_auto] sm:items-end"
							>
								<SearchSelect
									v-model="allocation.expense_account"
									:label="`Expense account ${index + 1}`"
									:required="true"
									:disabled="busy"
									:options="classificationAccountOptions(item, index)"
								/>
								<label class="field-label"
									>Amount *<input
										v-model.number="allocation.amount"
										type="number"
										min="0.01"
										step="0.01"
										class="field-input"
								/></label>
								<button
									type="button"
									class="btn-secondary text-bad"
									:disabled="busy || item.allocations.length === 1"
									@click="removeAllocation(item, index)"
								>
									Remove
								</button>
							</div>
						</div>
						<div class="flex flex-wrap items-center justify-between gap-3 mt-3">
							<button type="button" class="btn-secondary" :disabled="busy" @click="addAllocation(item)">
								+ Split to another account
							</button>
							<p :class="['text-sm font-semibold', allocationMatches(item) ? 'text-ok' : 'text-bad']">
								Allocated {{ money(allocationTotal(item), selected.currency) }} of
								{{ money(item.required_amount, selected.currency) }}
							</p>
						</div>
					</section>
				</div>
				<label class="field-label mt-4"
					>Accounts note<textarea v-model.trim="classificationNote" rows="3" class="field-input"></textarea>
				</label>
				<div class="flex justify-end mt-5">
					<button type="button" class="btn-primary" :disabled="busy || !classificationValid" @click="finaliseClassification">
						Finalise accounts and submit claim
					</button>
				</div>
			</section>

			<section v-if="selected.access.reimbursement" class="form-card">
				<h2 class="form-title">Accounts reimbursement</h2>
				<p class="form-hint">
					Submitting creates the accounting Payment Entry and settles the approved
					liability. It does not call a bank API.
				</p>
				<div class="grid gap-4 sm:grid-cols-2">
					<label class="field-label"
						>Pay from *<select
							v-model="payment.paid_from"
							required
							class="field-input"
						>
							<option value="" disabled>Select a bank or cash ledger</option>
							<option
								v-for="account in selected.payment.accounts"
								:key="account.value"
								:value="account.value"
							>
								{{ account.label }} · {{ account.type }}
							</option>
						</select></label
					>
					<label class="field-label"
						>Mode of payment<select
							v-model="payment.mode_of_payment"
							class="field-input"
						>
							<option value="">Not specified</option>
							<option
								v-for="mode in selected.payment.modes_of_payment"
								:key="mode.name"
								:value="mode.name"
							>
								{{ mode.name }}
							</option>
						</select></label
					>
					<label class="field-label"
						>Posting date *<input
							v-model="payment.posting_date"
							type="date"
							required
							class="field-input"
					/></label>
					<template v-if="selectedPaymentAccount?.type === 'Bank'">
						<label class="field-label"
							>Transaction reference number *<input
								v-model.trim="payment.reference_no"
								required
								class="field-input"
						/></label>
						<label class="field-label"
							>Transaction reference date *<input
								v-model="payment.reference_date"
								type="date"
								required
								class="field-input"
						/></label>
					</template>
				</div>
				<div v-if="selectedPaymentAccount?.type === 'Bank'" class="info-box mt-4">
					<template v-if="selected.payment.approved_bank">
						<strong>Approved employee bank details</strong>
						<p class="mt-1">
							{{ selected.payment.approved_bank.bank_name }} ·
							{{ selected.payment.approved_bank.account_number_masked }} ·
							{{ selected.payment.approved_bank.ifsc }}
						</p>
					</template>
					<p v-else>
						No approved employee bank account is available; choose Cash or obtain
						approval first.
					</p>
				</div>
				<div class="flex justify-end mt-5">
					<button
						type="button"
						class="btn-primary"
						:disabled="busy || !payment.paid_from"
						@click="reimburse"
					>
						Create and submit Payment Entry
					</button>
				</div>
			</section>
		</template>
	</div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import SearchSelect from "../components/SearchSelect.vue";
import { call } from "../lib/frappe";

const API = "volunteering.volunteering.expense_claim_workflow_portal.";
const route = useRoute();
const router = useRouter();
const loading = ref(true);
const busy = ref(false);
const error = ref("");
const success = ref("");
const queuePayload = ref({ queues: {}, counts: {} });
const selected = ref(null);
const tab = ref(String(route.query.view || "receipt_review"));
const review = reactive({ notes: "" });
const sanctioned = reactive({});
const decisionReason = ref("");
const classificationRows = ref([]);
const classificationNote = ref("");
const payment = reactive({
	paid_from: "",
	mode_of_payment: "",
	posting_date: "",
	reference_no: "",
	reference_date: "",
});

const allTabs = [
	{ key: "receipt_review", label: "Receipt review" },
	{ key: "approval", label: "Manager approval" },
	{ key: "classification", label: "Accounts classification" },
	{ key: "reimbursement", label: "Accounts reimbursement" },
];
const counts = computed(() => queuePayload.value.counts || {});
const visibleTabs = computed(() =>
	allTabs.filter(
		(option) =>
			(option.key === "receipt_review" && queuePayload.value.can_review_receipts) ||
			(option.key === "reimbursement" && queuePayload.value.can_reimburse) ||
			(option.key === "classification" && queuePayload.value.can_classify) ||
			option.key === "approval",
	),
);
const currentQueue = computed(() => queuePayload.value.queues?.[tab.value] || []);
const sanctionedTotal = computed(() =>
	Object.values(sanctioned).reduce((sum, amount) => sum + Number(amount || 0), 0),
);
const selectedPaymentAccount = computed(() =>
	selected.value?.payment?.accounts?.find((account) => account.value === payment.paid_from),
);
const classificationValid = computed(
	() =>
		classificationRows.value.length > 0 &&
		classificationRows.value.every(
			(item) =>
				allocationMatches(item) &&
				item.allocations.length > 0 &&
				item.allocations.every((row) => row.expense_account && Number(row.amount) > 0),
		),
);
const approvalMessage = computed(
	() =>
		selected.value?.approval_flags?.manager_float_message ||
		(selected.value?.approval_flags?.strict_budget_messages || []).join(" "),
);

const Summary = defineComponent({
	props: { label: String, value: [String, Number] },
	setup(props) {
		return () =>
			h("div", { class: "rounded-xl bg-soft p-3" }, [
				h("p", { class: "text-xs text-muted" }, props.label),
				h("p", { class: "text-sm font-medium mt-1" }, String(props.value || "—")),
			]);
	},
});
const Amount = Summary;

async function load() {
	loading.value = true;
	error.value = "";
	try {
		queuePayload.value = await call(`${API}get_expense_claim_work_queue`);
		if (!visibleTabs.value.some((item) => item.key === tab.value)) {
			tab.value = visibleTabs.value[0]?.key || "approval";
		}
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
	selected.value = await call(`${API}get_expense_claim_work_item`, { name });
	review.notes = "";
	Object.keys(sanctioned).forEach((key) => delete sanctioned[key]);
	selected.value.expenses.forEach((item) => (sanctioned[item.name] = Number(item.amount || 0)));
	decisionReason.value = "";
	classificationNote.value = selected.value.classification?.note || "";
	classificationRows.value = (selected.value.classification?.items || []).map((item) => {
		let allocations = (item.allocations || []).map((row) => ({ ...row }));
		if (!allocations.length && Number(item.required_amount) > 0) {
			allocations = [
				{
					expense_account: item.suggested_accounts?.[0] || "",
					amount: Number(item.required_amount || 0),
				},
			];
		}
		return { ...item, allocations };
	});
	payment.paid_from =
		selected.value.payment?.accounts?.find((account) => account.type === "Cash")?.value || "";
	payment.mode_of_payment = "";
	payment.posting_date = selected.value.payment?.posting_date || "";
	payment.reference_no = "";
	payment.reference_date = selected.value.payment?.posting_date || "";
}

async function openDetail(name) {
	await router.push({ path: "/expense-claim-workflow", query: { claim: name } });
}
async function closeDetail() {
	await router.push({ path: "/expense-claim-workflow", query: { view: tab.value } });
}

async function runAction(task, message) {
	busy.value = true;
	error.value = "";
	success.value = "";
	try {
		await task();
		success.value = message;
		await router.push({ path: "/expense-claim-workflow", query: { view: tab.value } });
		await load();
	} catch (e) {
		error.value = e.message || String(e);
		window.scrollTo({ top: 0, behavior: "smooth" });
	} finally {
		busy.value = false;
	}
}

function verifyReceipts() {
	return runAction(
		() =>
			call(`${API}review_expense_claim_receipts`, {
				name: selected.value.name,
				decision: "verify",
				notes: review.notes,
			}),
		"Receipts verified; the claim is now with its manager.",
	);
}
function requestCorrection() {
	if (!review.notes) {
		error.value = "Explain what the employee must correct.";
		return;
	}
	return runAction(
		() =>
			call(`${API}review_expense_claim_receipts`, {
				name: selected.value.name,
				decision: "request_correction",
				notes: review.notes,
			}),
		"The claim was returned to the employee for correction.",
	);
}
function decide(action) {
	if (["reject", "escalate"].includes(action) && !decisionReason.value) {
		error.value = `Give a reason before you ${action} this claim.`;
		return;
	}
	return runAction(
		() =>
			call(`${API}decide_expense_claim`, {
				name: selected.value.name,
				action,
				sanctioned_amounts: sanctioned,
				reason: decisionReason.value,
			}),
		action === "approve"
			? "Claim approved by the manager and sent to Accounts for classification."
			: action === "reject"
				? "Claim rejected."
				: "Claim escalated.",
	);
}
function classificationAccountOptions(item, currentIndex) {
	const current = item.allocations[currentIndex]?.expense_account;
	return (selected.value.classification?.accounts || []).filter(
		(option) =>
			option.value === current ||
			!item.allocations.some(
				(row, index) => index !== currentIndex && row.expense_account === option.value,
			),
	);
}
function suggestedLabels(item) {
	const lookup = new Map(
		(selected.value.classification?.accounts || []).map((account) => [account.value, account.label]),
	);
	return item.suggested_accounts.map((account) => lookup.get(account) || account).join(", ");
}
function allocationTotal(item) {
	return item.allocations.reduce((sum, row) => sum + Number(row.amount || 0), 0);
}
function allocationMatches(item) {
	return Math.abs(allocationTotal(item) - Number(item.required_amount || 0)) < 0.005;
}
function addAllocation(item) {
	item.allocations.push({ expense_account: "", amount: 0 });
}
function removeAllocation(item, index) {
	item.allocations.splice(index, 1);
}
function finaliseClassification() {
	if (!classificationValid.value) {
		error.value = "Allocate every sanctioned amount exactly before finalising accounts.";
		return;
	}
	if (!window.confirm("Submit this approved claim and post its expense liability now? Payment will remain outstanding.")) return;
	return runAction(
		() =>
			call(`${API}classify_expense_claim_accounts`, {
				name: selected.value.name,
				note: classificationNote.value,
				allocations: classificationRows.value.map((item) => ({
					expense_detail: item.expense_detail,
					allocations: item.allocations.map((row) => ({
						expense_account: row.expense_account,
						amount: Number(row.amount),
					})),
				})),
			}),
		"Accounts classified and claim submitted. It is now ready for reimbursement.",
	);
}
function reimburse() {
	if (
		!window.confirm(
			"Create and submit the Payment Entry now? This posts the reimbursement to the ledgers.",
		)
	)
		return;
	return runAction(async () => {
		const result = await call(`${API}reimburse_expense_claim`, {
			name: selected.value.name,
			payment,
		});
		success.value = `Payment Entry ${result.payment_entry} submitted.`;
	}, "Payment Entry submitted and the claim settled.");
}

function money(value, currency = "INR") {
	return new Intl.NumberFormat("en-IN", {
		style: "currency",
		currency,
		maximumFractionDigits: 2,
	}).format(Number(value || 0));
}
function date(value) {
	return value
		? new Intl.DateTimeFormat("en-IN", { dateStyle: "medium" }).format(new Date(value))
		: "—";
}

watch(() => route.fullPath, load);
watch(tab, (value) => {
	if (!selected.value && route.query.view !== value)
		router.replace({ path: "/expense-claim-workflow", query: { view: value } });
});
onMounted(load);
</script>

<style scoped>
.form-card {
	@apply rounded-2xl border border-line bg-surface p-4 sm:p-5 shadow-soft;
}
.form-title {
	@apply text-lg font-semibold text-ink mb-2;
}
.form-hint {
	@apply text-sm text-muted mb-4;
}
.field-label {
	@apply block text-sm font-medium text-ink;
}
.field-input {
	@apply mt-1 block w-full rounded-xl border border-line bg-surface px-3 py-2.5 text-sm text-ink;
}
.queue-tab {
	@apply rounded-full border border-line bg-surface px-3 py-2 text-sm font-medium text-muted;
}
.queue-tab-active {
	@apply border-accent bg-accent text-on-accent;
}
.claim-card {
	@apply rounded-2xl border border-line bg-surface p-4 shadow-soft hover:shadow-lift;
}
.expense-row {
	@apply border-t border-line py-4 first:border-t-0 first:pt-0 last:pb-0;
}
.sanction-row {
	@apply grid gap-3 rounded-xl border border-line bg-bg p-3 sm:grid-cols-[minmax(0,1fr)_10rem] sm:items-center;
}
.sanction-row small {
	@apply block text-xs text-muted mt-1;
}
.error-box {
	@apply rounded-xl border border-bad bg-bad-soft p-4 text-sm text-bad;
}
.success-box {
	@apply rounded-xl border border-ok bg-ok-soft p-4 text-sm text-ok;
}
.warning-box {
	@apply rounded-xl border border-warn bg-warn-soft p-3 text-sm text-ink;
}
.info-box {
	@apply rounded-xl border border-line bg-soft p-3 text-sm text-ink;
}
.btn-danger {
	@apply rounded-xl bg-bad px-4 py-2 text-sm font-semibold text-white disabled:opacity-50;
}
</style>
