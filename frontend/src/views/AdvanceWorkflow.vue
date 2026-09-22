<template>
	<div>
		<PageHeader
			eyebrow="Advances"
			:title="selected ? selected.name : 'Advance work'"
			:subtitle="
				selected
					? `${selected.employee_name} · ${selected.project_name || selected.project}`
					: 'Review, disburse and settle advances from Home.'
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
		<p v-if="loading" class="text-muted" role="status">Loading advances…</p>

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
					v-for="advance in currentQueue"
					:key="advance.name"
					type="button"
					class="advance-card w-full text-left"
					@click="openDetail(advance.name)"
				>
					<div class="flex flex-wrap justify-between gap-3">
						<div>
							<strong>{{ advance.employee_name }}</strong>
							<p class="text-sm text-muted mt-1">
								{{ advance.name }} · {{ advance.project || "No project" }}
							</p>
						</div>
						<div class="sm:text-right">
							<strong>{{ money(advance.amount, advance.currency) }}</strong>
							<p v-if="advance.paid_amount" class="text-xs text-muted mt-1">
								Paid {{ money(advance.paid_amount, advance.currency) }}
							</p>
							<p v-if="advance.kind === 'return'" class="text-xs text-muted mt-1">
								Unused {{ money(advance.residual_amount, advance.currency) }}
							</p>
							<p class="text-xs text-muted mt-1">
								Required {{ date(advance.required_by_date) }}
							</p>
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
					<Summary label="Use" :value="selected.advance_use" />
					<Summary label="Workflow" :value="selected.workflow_state" />
				</div>
				<div class="grid gap-3 grid-cols-2 sm:grid-cols-5 mt-4">
					<Summary
						label="Requested"
						:value="money(selected.requested_amount, selected.currency)"
					/>
					<Summary
						label="Paid"
						:value="money(selected.paid_amount, selected.currency)"
					/>
					<Summary
						label="Claimed"
						:value="money(selected.claimed_amount, selected.currency)"
					/>
					<Summary
						label="Returned"
						:value="money(selected.returned_amount, selected.currency)"
					/>
					<Summary
						label="Residual"
						:value="money(selected.residual_amount, selected.currency)"
					/>
				</div>
			</section>

			<section class="form-card mb-5">
				<h2 class="form-title">Request details</h2>
				<p class="whitespace-pre-wrap">{{ selected.purpose }}</p>
				<p
					v-if="selected.additional_note"
					class="text-sm text-muted mt-3 whitespace-pre-wrap"
				>
					{{ selected.additional_note }}
				</p>
				<div class="grid gap-3 sm:grid-cols-3 mt-4 text-sm">
					<Summary label="Requested on" :value="date(selected.posting_date)" />
					<Summary label="Required by" :value="date(selected.required_by_date)" />
					<Summary
						label="Expected settlement"
						:value="date(selected.expected_settlement_date)"
					/>
				</div>
				<a
					v-if="selected.supporting_document"
					:href="selected.supporting_document"
					target="_blank"
					rel="noopener"
					class="text-sm text-accent underline mt-4 inline-block"
					>Open private estimate / quotation</a
				>
			</section>

			<section v-if="selected.access.approval" class="form-card mb-5">
				<h2 class="form-title">Approval decision</h2>
				<p class="form-hint">
					The authority check is recalculated now from this request plus the employee’s
					other live outstanding advances.
				</p>
				<div class="grid gap-3 sm:grid-cols-3">
					<Summary
						label="This request"
						:value="money(selected.approval_flags.request_amount, selected.currency)"
					/>
					<Summary
						label="Other outstanding"
						:value="
							money(selected.approval_flags.other_outstanding, selected.currency)
						"
					/>
					<Summary
						label="Authority exposure"
						:value="
							money(selected.approval_flags.approval_exposure, selected.currency)
						"
					/>
				</div>
				<div v-if="selected.approval_flags.can_escalate" class="warning-box mt-4">
					This live total exceeds your approval authority. Review it, then escalate it to
					the next linked manager.
				</div>
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
						Escalate to next manager
					</button>
					<button
						v-if="selected.approval_flags.can_approve"
						type="button"
						class="btn-primary"
						:disabled="busy"
						@click="decide('approve')"
					>
						Approve advance
					</button>
				</div>
			</section>

			<section v-if="selected.access.disbursement" class="form-card mb-5">
				<h2 class="form-title">Accounts disbursement</h2>
				<p class="form-hint">
					Create and submit a Payment Entry against this approved advance. This records
					the payment in the ledgers; it does not call a bank API.
				</p>
				<div class="grid gap-4 sm:grid-cols-2">
					<label class="field-label"
						>Amount to pay *<input
							v-model.number="payment.amount"
							type="number"
							min="0.01"
							:max="selected.outstanding_to_pay"
							step="0.01"
							required
							class="field-input"
					/></label>
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
								v-for="mode in availableModes"
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
						:disabled="busy || !payment.paid_from || !payment.amount"
						@click="disburse"
					>
						Create and submit Payment Entry
					</button>
				</div>
			</section>

			<section v-if="selected.access.return" class="form-card mb-5">
				<h2 class="form-title">Record unused advance returned</h2>
				<p class="form-hint">
					Accounts must first receive the cash or confirm the bank credit. Submitting
					this form posts a Journal Entry against the advance; it does not transfer
					funds.
				</p>
				<div v-if="selected.pending_claims?.length" class="warning-box mb-4">
					Resolve pending claims against this advance before recording a return:
					{{ selected.pending_claims.join(", ") }}.
				</div>
				<div class="grid gap-4 sm:grid-cols-2">
					<label class="field-label"
						>Amount received *<input
							v-model.number="returned.amount"
							type="number"
							min="0.01"
							:max="selected.return_options.maximum"
							step="0.01"
							required
							class="field-input"
					/></label>
					<label class="field-label"
						>Received into *<select
							v-model="returned.received_into"
							required
							class="field-input"
						>
							<option value="" disabled>
								Select the bank or cash ledger that received the funds
							</option>
							<option
								v-for="account in selected.return_options.accounts"
								:key="account.value"
								:value="account.value"
							>
								{{ account.label }} · {{ account.type }}
							</option>
						</select></label
					>
					<label class="field-label"
						>Posting date *<input
							v-model="returned.posting_date"
							type="date"
							required
							class="field-input"
					/></label>
					<template v-if="selectedReturnAccount?.type === 'Bank'">
						<label class="field-label"
							>Bank receipt reference *<input
								v-model.trim="returned.reference_no"
								required
								class="field-input"
						/></label>
						<label class="field-label"
							>Bank receipt date *<input
								v-model="returned.reference_date"
								type="date"
								required
								class="field-input"
						/></label>
					</template>
				</div>
				<div class="flex justify-end mt-5">
					<button
						type="button"
						class="btn-primary"
						:disabled="
							busy ||
							Boolean(selected.pending_claims?.length) ||
							!returned.received_into ||
							!returned.amount
						"
						@click="recordReturn"
					>
						Confirm receipt and submit Journal Entry
					</button>
				</div>
			</section>

			<section v-if="selected.expense_claims.length" class="form-card">
				<h2 class="form-title">Bills submitted against this advance</h2>
				<a
					v-for="claim in selected.expense_claims"
					:key="claim.name"
					:href="claim.route"
					class="claim-link"
				>
					<span>{{ claim.name }} · {{ claim.status }}</span>
					<strong>{{ money(claim.allocated_amount, selected.currency) }}</strong>
				</a>
			</section>
		</template>
	</div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import { call } from "../lib/frappe";

const API = "volunteering.volunteering.advance_workflow_portal.";
const route = useRoute();
const router = useRouter();
const loading = ref(true);
const busy = ref(false);
const error = ref("");
const success = ref("");
const selected = ref(null);
const queuePayload = ref({ queues: {}, counts: {} });
const tab = ref(String(route.query.view || "approval"));
const decisionReason = ref("");
const payment = reactive({
	amount: null,
	paid_from: "",
	mode_of_payment: "",
	posting_date: "",
	reference_no: "",
	reference_date: "",
});
const returned = reactive({
	amount: null,
	received_into: "",
	posting_date: "",
	reference_no: "",
	reference_date: "",
});

const allTabs = [
	{ key: "approval", label: "Approval requests" },
	{ key: "disbursement", label: "Accounts disbursement" },
	{ key: "return", label: "Unused advances" },
];
const counts = computed(() => queuePayload.value.counts || {});
const visibleTabs = computed(() =>
	allTabs.filter((option) => option.key === "approval" || queuePayload.value.can_disburse),
);
const currentQueue = computed(() => queuePayload.value.queues?.[tab.value] || []);
const selectedPaymentAccount = computed(() =>
	selected.value?.payment?.accounts?.find((account) => account.value === payment.paid_from),
);
const selectedReturnAccount = computed(() =>
	selected.value?.return_options?.accounts?.find(
		(account) => account.value === returned.received_into,
	),
);
const availableModes = computed(() =>
	(selected.value?.payment?.modes_of_payment || []).filter(
		(mode) => mode.type === selectedPaymentAccount.value?.type,
	),
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

async function load() {
	loading.value = true;
	error.value = "";
	try {
		queuePayload.value = await call(`${API}get_advance_work_queue`);
		if (!visibleTabs.value.some((item) => item.key === tab.value)) {
			tab.value = visibleTabs.value[0]?.key || "approval";
		}
		if (route.query.advance) await loadDetail(String(route.query.advance));
		else selected.value = null;
	} catch (e) {
		error.value = e.message || String(e);
		selected.value = null;
	} finally {
		loading.value = false;
	}
}

async function loadDetail(name) {
	selected.value = await call(`${API}get_advance_work_item`, { name });
	decisionReason.value = "";
	payment.amount = selected.value.payment?.outstanding || null;
	payment.paid_from =
		selected.value.payment?.accounts?.find((account) => account.type === "Cash")?.value || "";
	payment.mode_of_payment = "";
	payment.posting_date = selected.value.payment?.posting_date || "";
	payment.reference_no = "";
	payment.reference_date = selected.value.payment?.posting_date || "";
	returned.amount = selected.value.return_options?.maximum || null;
	returned.received_into = "";
	returned.posting_date = selected.value.return_options?.posting_date || "";
	returned.reference_no = "";
	returned.reference_date = selected.value.return_options?.posting_date || "";
}

async function openDetail(name) {
	await router.push({ path: "/advance-workflow", query: { advance: name } });
}
async function closeDetail() {
	await router.push({ path: "/advance-workflow", query: { view: tab.value } });
}

async function runAction(task, message) {
	busy.value = true;
	error.value = "";
	success.value = "";
	try {
		await task();
		success.value = message;
		await router.push({ path: "/advance-workflow", query: { view: tab.value } });
		await load();
	} catch (e) {
		error.value = e.message || String(e);
		window.scrollTo({ top: 0, behavior: "smooth" });
	} finally {
		busy.value = false;
	}
}

function decide(action) {
	if (["reject", "escalate"].includes(action) && !decisionReason.value) {
		error.value = `Give a reason before you ${action} this advance.`;
		return;
	}
	return runAction(
		() =>
			call(`${API}decide_advance`, {
				name: selected.value.name,
				action,
				reason: decisionReason.value,
			}),
		action === "approve"
			? "Advance approved and sent to Accounts for disbursement."
			: action === "reject"
				? "Advance rejected."
				: "Advance sent to the next linked manager.",
	);
}

function disburse() {
	if (
		!window.confirm(
			`Create and submit a Payment Entry for ${money(payment.amount, selected.value.currency)}?`,
		)
	)
		return;
	return runAction(
		() =>
			call(`${API}disburse_advance`, {
				name: selected.value.name,
				payment,
			}),
		"Payment Entry submitted and the advance disbursed.",
	);
}

function recordReturn() {
	if (
		!window.confirm(
			`Confirm ${money(returned.amount, selected.value.currency)} was received and post a Journal Entry against ${selected.value.name}?`,
		)
	)
		return;
	return runAction(
		() =>
			call(`${API}record_advance_return`, { name: selected.value.name, details: returned }),
		"Advance return recorded in the ledger.",
	);
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
		router.replace({ path: "/advance-workflow", query: { view: value } });
});
watch(selectedPaymentAccount, () => {
	if (!availableModes.value.some((mode) => mode.name === payment.mode_of_payment))
		payment.mode_of_payment = "";
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
.advance-card {
	@apply rounded-2xl border border-line bg-surface p-4 shadow-soft hover:shadow-lift;
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
.claim-link {
	@apply flex flex-wrap justify-between gap-3 border-t border-line py-3 text-sm text-accent first:border-0;
}
</style>
