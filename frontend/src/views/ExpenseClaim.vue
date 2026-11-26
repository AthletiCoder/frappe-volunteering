<template>
	<div class="mx-auto max-w-6xl">
		<PageHeader
			:title="
				isCorrection
					? `Correct ${correctionName}`
					: isIntegrated
						? 'Prepare invoice and submit expense'
						: 'Submit an expense'
			"
			:subtitle="
				isCorrection
					? 'Correct the returned details or receipts, then send the claim through receipt review again.'
					: isIntegrated
						? 'Use an existing invoice or prepare and sign one here, then submit the expense for review.'
						: 'Record project expenses, attach the bills, and send them for independent receipt review.'
			"
			eyebrow="Expenses"
		>
			<template #actions>
				<RouterLink v-if="!isCorrection" :to="{ path: '/expense-claim/multiple', query: { project: form.project || route.query.project } }" class="btn-secondary">Submit multiple invoices</RouterLink>
				<RouterLink to="/expense-claims" class="btn-secondary">My claims</RouterLink>
				<RouterLink to="/home" class="btn-back">Back to Home</RouterLink>
			</template>
		</PageHeader>

		<div v-if="loading" class="text-muted">Loading your claim options…</div>
		<div v-else-if="result" class="space-y-5">
			<section class="form-card text-center py-8">
				<div class="success-mark" aria-hidden="true">✓</div>
				<h2 class="text-xl font-semibold text-ink mt-3">
					{{
						isCorrection
							? "Corrections sent for receipt review"
							: "Sent for receipt review"
					}}
				</h2>
				<p class="text-muted mt-2">
					Expense Claim <strong class="text-ink">{{ result.name }}</strong>
					{{ isCorrection ? "was resubmitted" : "was created" }}
					for {{ money(result.total) }}.
				</p>
				<p class="text-sm text-muted mt-1">
					A receipt reviewer checks the evidence first. The claim moves to
					reporting-manager approval only after that review is verified.
				</p>
				<p v-if="result.generated_invoice_number" class="text-sm text-muted mt-1">
					Signed invoice
					<strong class="text-ink">{{ result.generated_invoice_number }}</strong>
					was attached privately to the claim.
				</p>
				<div v-if="result.warnings?.length" class="warning-box mt-4 text-left">
					<p class="font-semibold mb-2">Advisories for review</p>
					<p v-for="warning in result.warnings" :key="warning" class="mt-1">
						{{ plainText(warning) }}
					</p>
				</div>
				<div class="flex flex-wrap justify-center gap-2 mt-5">
					<RouterLink
						:to="{ path: '/expense-claims', query: { claim: result.name } }"
						class="btn-primary px-5 py-2.5"
						>Track this claim</RouterLink
					>
					<button
						v-if="!isCorrection"
						type="button"
						class="btn-primary px-5 py-2.5"
						@click="startAnother"
					>
						Submit another expense
					</button>
					<RouterLink to="/home" class="btn-secondary px-5 py-2.5"
						>Return Home</RouterLink
					>
				</div>
			</section>
		</div>
		<form v-else class="form-layout" @submit.prevent="submitClaim">
			<div class="min-w-0 space-y-5">
			<div v-if="error" class="error-box" role="alert">{{ error }}</div>
            <div v-if="submissionStatus" class="warning-box" role="status"><p>{{ submissionStatus }}</p><button v-if="!submitting && submission?.pending?.args" type="button" class="btn-secondary mt-3" @click="retrySavedSubmission">Retry saved submission</button></div>
			<div v-if="isCorrection && correctionDetail?.receipt_review_notes" class="warning-box">
				<strong>Why correction was requested</strong>
				<p class="mt-1 whitespace-pre-wrap">{{ correctionDetail.receipt_review_notes }}</p>
			</div>

			<section class="form-card">
				<h2 class="step-title"><span class="step-num" :class="{ 'step-num--done': isCorrection || form.project }" aria-hidden="true">{{ stepNo.context }}</span>Claim context</h2>
				<div class="mb-4 flex flex-wrap gap-2">
					<span class="person-chip"><Avatar :name="defaults.employee_name" size="sm" /><span class="min-w-0"><span class="block text-[11px] text-muted">Employee</span><span class="block truncate text-sm font-semibold text-ink">{{ defaults.employee_name || "—" }}</span></span></span>
					<span class="person-chip"><Avatar :name="defaults.approver?.name || '?'" size="sm" tone="slate" /><span class="min-w-0"><span class="block text-[11px] text-muted">Reporting manager</span><span class="block truncate text-sm font-semibold text-ink">{{ defaults.approver?.name || "Not configured" }}</span></span></span>
				</div>
				<div class="expense-portal-grid">
					<label v-if="!isCorrection" class="field-label sm:col-span-2"
						>Project *<select
							v-model="form.project"
							required
							class="field-input"
							@change="projectChanged"
						>
							<option value="" disabled>Select a project you belong to</option>
							<option
								v-for="project in defaults.projects"
								:key="project.value"
								:value="project.value"
							>
								{{ project.label }} · {{ project.description }}
							</option>
						</select></label
					>
					<label v-else class="field-label sm:col-span-2"
						>Project<input
							:value="correctionDetail?.project_name || correctionDetail?.project"
							readonly
							class="field-input"
					/></label>
				</div>
				<p v-if="!isCorrection && !defaults.projects.length" class="warning-box mt-3">
					No active project with approved expense categories is available to you. A
					Projects Manager must add you as a member and approve the project labels.
				</p>
			</section>

			<section v-if="!isCorrection" class="form-card">
				<h2 class="step-title"><span class="step-num step-num--done" aria-hidden="true">{{ stepNo.paid }}</span>How was this paid?</h2>
				<div class="grid sm:grid-cols-3 gap-3">
					<button
						v-for="source in sourceChoices"
						:key="source.value"
						type="button"
						:disabled="source.disabled"
						:class="['option-card', form.reimbursement_source === source.value ? 'option-card--on' : '']"
						:aria-pressed="form.reimbursement_source === source.value"
						@click="form.reimbursement_source = source.value"
					>
						<span class="font-semibold">{{ source.label }}</span>
						<span class="text-sm text-muted">{{ source.hint }}</span>
					</button>
				</div>
				<label v-if="form.reimbursement_source === 'OWN_ADVANCE'" class="field-label mt-4"
					>Employee advance *<select
						v-model="form.employee_advance"
						required
						class="field-input"
					>
						<option value="" disabled>Select the advance to settle</option>
						<option
							v-for="advance in defaults.own_advances"
							:key="advance.name"
							:value="advance.name"
						>
							{{ advance.name }} · {{ advance.purpose || "Advance" }} ·
							{{ money(advance.residual) }} available
						</option>
					</select></label
				>
				<p v-if="selectedAdvance && total > 0" class="form-hint mt-3 mb-0">
					{{ money(Math.min(total, selectedAdvance.residual)) }} will be offset against
					this advance. Any remaining
					{{ money(Math.max(total - selectedAdvance.residual, 0)) }}
					is due for reimbursement after approval.
				</p>
				<p
					v-if="form.reimbursement_source === 'MANAGER_ADVANCE'"
					class="form-hint mt-3 mb-0"
				>
					The approved amount is settled from
					{{ defaults.manager_advance.manager_name }}’s advance; it is not reimbursed to
					your bank account. Maximum currently available:
					{{ money(defaults.manager_advance.maximum_available) }}.
				</p>
			</section>

			<section v-if="isIntegrated && !isCorrection" class="form-card">
				<h2 class="step-title"><span class="step-num" :class="{ 'step-num--done': invoicePath }" aria-hidden="true">{{ stepNo.invoice }}</span>Do you already have a proper invoice?</h2>
				<div class="grid sm:grid-cols-2 gap-3">
					<button
						type="button"
						:class="['option-card', invoicePath === 'EXISTING' ? 'option-card--on' : '']"
						@click="invoicePath = 'EXISTING'"
					>
						<span class="font-semibold">Yes, I have an invoice</span>
						<span class="text-sm text-muted"
							>Attach it and continue through the normal expense-claim flow.</span
						>
					</button>
					<button
						type="button"
						:class="['option-card', invoicePath === 'GENERATE' ? 'option-card--on' : '']"
						@click="invoicePath = 'GENERATE'"
					>
						<span class="font-semibold">No, prepare one now</span>
						<span class="text-sm text-muted"
							>Complete and sign an invoice on this device; it will be attached
							privately.</span
						>
					</button>
				</div>
			</section>

			<section v-if="!isCorrection && (!isIntegrated || invoicePath)" class="form-card emergency-card" :class="{ 'emergency-card--on': form.is_emergency }">
				<label class="flex items-start gap-3 cursor-pointer">
					<input v-model="form.is_emergency" type="checkbox" class="mt-1" />
					<span>
						<strong class="block text-ink">This was an emergency expense</strong>
						<span class="block text-sm text-muted"
							>Use this only when the normal prior-purchase route could not
							reasonably be followed. It does not bypass receipt review or
							approval.</span
						>
					</span>
				</label>
				<div v-if="form.is_emergency" class="expense-portal-grid mt-4">
					<label class="field-label"
						>Emergency date *<input
							v-model="form.emergency_date"
							type="date"
							required
							:max="defaults.expense_date"
							class="field-input"
					/></label>
					<label class="field-label sm:col-span-2"
						>What happened, and why was prior approval unavailable? *<textarea
							v-model.trim="form.emergency_reason"
							required
							maxlength="500"
							rows="3"
							class="field-input"
						></textarea>
					</label>
				</div>
			</section>

			<section v-if="!isIntegrated || invoicePath" class="space-y-3">
				<div class="flex flex-wrap items-end justify-between gap-2">
					<div>
						<h2 class="step-title !mb-0"><span class="step-num" :class="{ 'step-num--done': itemsComplete }" aria-hidden="true">{{ stepNo.items }}</span>Expense items</h2>
						<p class="text-sm text-muted mt-1">
							<template v-if="generatesInvoice">
								Enter the project category and business purpose. The signed invoice
								below supplies the amount and receipt evidence.
							</template>
							<template v-else>
								Attach the bill to the specific item it supports. All items in this
								claim must have the same bill date, which determines its accounting
								year. For bills with different dates, use Submit multiple invoices.
							</template>
						</p>
					</div>
					<button
						v-if="!isCorrection && !generatesInvoice"
						type="button"
						class="btn-secondary"
						:disabled="form.expenses.length >= 10"
						@click="addExpense"
					>
						+ Add expense item
					</button>
				</div>

				<article v-for="(item, index) in form.expenses" :key="item.key" class="form-card item-card">
					<div class="flex items-center justify-between gap-3 mb-4">
						<h3 class="flex items-center gap-2.5 font-semibold text-ink"><span class="item-badge" aria-hidden="true">{{ index + 1 }}</span>Expense item {{ index + 1 }}</h3>
						<span v-if="!generatesInvoice && Number(item.amount) > 0" class="ml-auto text-sm font-semibold tabular-nums text-ink">{{ money(item.amount) }}</span>
						<button
							v-if="!isCorrection && !generatesInvoice && form.expenses.length > 1"
							type="button"
							class="text-sm font-medium text-bad"
							@click="removeExpense(index)"
						>
							Remove
						</button>
					</div>
					<div class="expense-portal-grid">
						<label class="field-label"
							>Date shown on invoice / bill *<input
								v-model="item.expense_date"
								type="date"
								required
								:max="defaults.expense_date"
								class="field-input"
						/></label>
						<SearchSelect
							v-model="item.account"
							:options="accountOptions"
							:disabled="!form.project || loadingAccounts"
							label="Project expense category *"
							placeholder="Type to find an approved expense category"
							required
						/>
						<label v-if="!generatesInvoice" class="field-label"
							>Supplier / payee<input
								v-model.trim="item.supplier_name"
								maxlength="160"
								class="field-input"
						/></label>
						<label v-if="!generatesInvoice" class="field-label"
							>Receipt / invoice number<input
								v-model.trim="item.invoice_number"
								maxlength="100"
								class="field-input"
						/></label>
						<label class="field-label sm:col-span-2"
							>Description and business purpose *<textarea
								v-model.trim="item.description"
								required
								maxlength="1000"
								rows="3"
								class="field-input"
							></textarea>
						</label>
						<label v-if="!generatesInvoice" class="field-label"
							>Amount ({{ defaults.currency }}) *<input
								v-model.number="item.amount"
								type="number"
								min="0.01"
								max="999999999"
								step="0.01"
								required
								class="field-input"
						/></label>
						<label v-else class="field-label"
							>Generated invoice total<input
								:value="money(form.expenses[0].amount)"
								readonly
								class="field-input"
						/></label>
						<label v-if="!generatesInvoice" class="field-label"
							>Receipt evidence *<input
								type="file"
								accept=".pdf,.png,.jpg,.jpeg"
								:required="!item.receipt_attachment && !item.receipt_content"
								:disabled="readingFiles || submitting"
								class="field-input"
								@change="chooseReceipt($event, item)"
						/></label>
					</div>
					<p v-if="generatesInvoice" class="form-hint mt-3 mb-0">
						The signed invoice prepared below will be used as this item's private
						receipt evidence. Its grand total becomes the expense amount.
					</p>
					<p v-if="item.receipt_filename" class="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-ok">
						<Icon name="check" size="sm" />Ready to upload privately: {{ item.receipt_filename }}
					</p>
					<a
						v-else-if="item.receipt_attachment"
						:href="item.receipt_attachment"
						target="_blank"
						rel="noopener"
						class="text-sm text-accent underline mt-2 inline-block"
						>Keep current receipt, or choose a replacement above</a
					>
				</article>
			</section>

			<section v-if="generatesInvoice" aria-label="Invoice generation">
				<div class="mb-3">
					<h2 class="text-xl font-semibold text-ink">Prepare and sign the invoice</h2>
					<p class="text-sm text-muted mt-1">
						No file download is created in this flow. The signed PDF is attached
						directly to your claim when you submit it.
					</p>
				</div>
				<InvoiceGenerator
					ref="invoiceGenerator"
					embedded
					:seed="invoiceSeed"
					:signature-context="claimSignatureContext"
					@total-change="setGeneratedInvoiceTotal"
				/>
			</section>

			<section v-if="isCorrection" class="form-card">
				<label class="field-label"
					>Correction note<textarea
						v-model.trim="form.correction_note"
						maxlength="500"
						rows="3"
						class="field-input"
						placeholder="Briefly tell the reviewer what you corrected"
					></textarea>
				</label>
			</section>

			</div>

			<aside class="form-rail space-y-4">
				<section class="summary-card" aria-label="Claim summary">
					<p class="eyebrow">Total claimed</p>
					<p class="summary-total">{{ money(total) }}</p>
					<dl class="summary-list">
						<div><dt>Items</dt><dd>{{ form.expenses.length }}</dd></div>
						<div v-if="!generatesInvoice"><dt>Receipts attached</dt><dd :class="receiptsReady === form.expenses.length ? 'text-ok' : ''">{{ receiptsReady }} of {{ form.expenses.length }}</dd></div>
						<div v-if="projectLabel"><dt>Project</dt><dd>{{ projectLabel }}</dd></div>
						<div v-if="!isCorrection"><dt>Paid via</dt><dd>{{ sourceLabel }}</dd></div>
					</dl>
					<p v-if="managerFundingShortfall" class="warning-box mt-4">
						The manager’s current advance does not cover this total. Choose another payment
						source or ask the manager to obtain additional advance funding.
					</p>
					<button
						type="submit"
						class="btn-primary mt-4 min-h-11 w-full"
						:disabled="
							submitting ||
							readingFiles ||
							(!isCorrection && !defaults.projects.length) ||
							(isIntegrated && !invoicePath) ||
							(generatesInvoice && total <= 0) ||
							managerFundingShortfall
						"
					>
						{{
							submitting
								? "Submitting…"
								: isCorrection
									? "Resubmit for receipt review"
									: generatesInvoice
										? "Sign and submit for receipt review"
										: "Submit for receipt review"
						}}
					</button>
				</section>
				<section class="summary-card">
					<p class="text-sm font-semibold text-ink">What happens next</p>
					<ol class="next-steps mt-3">
						<li><span class="next-steps__dot">1</span><span>Next: independent receipt review</span></li>
						<li><span class="next-steps__dot">2</span><span>Then: reporting-manager approval<template v-if="defaults.approver?.name"> by {{ defaults.approver.name }}</template></span></li>
						<li><span class="next-steps__dot">3</span><span>{{ form.reimbursement_source === "PERSONAL" ? "Reimbursed to your approved bank account" : "Settled against the selected advance" }}</span></li>
					</ol>
				</section>
			</aside>
		</form>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import Avatar from "../components/Avatar.vue";
import Icon from "../components/Icon.vue";
import SearchSelect from "../components/SearchSelect.vue";
import InvoiceGenerator from "./InvoiceGenerator.vue";
import { call } from "../lib/frappe";
import { ExpenseSubmission } from "../lib/expenseSubmission";

const API = "volunteering.volunteering.expense_claim_portal.";
const route = useRoute();
const isIntegrated = computed(() => route.name === "InvoiceExpenseClaim");
const correctionName = computed(() => String(route.query.correct || "").trim());
const isCorrection = computed(() => Boolean(correctionName.value));
const correctionDetail = ref(null);
const invoicePath = ref("");
const invoiceGenerator = ref(null);
let itemKey = 1;
let accountRequest = 0;
const defaults = ref({
	employee_name: "",
	currency: "INR",
	expense_date: "",
	projects: [],
	own_advances: [],
	manager_advance: { available: false, manager_name: "", maximum_available: 0 },
	approver: {},
});
const blankExpense = () => ({
	key: itemKey++,
	expense_date: defaults.value.expense_date || "",
	account: "",
	supplier_name: "",
	invoice_number: "",
	description: "",
	amount: null,
	receipt_filename: "",
	receipt_content: "",
	receipt_attachment: "",
});
const form = reactive({
	project: "",
	reimbursement_source: "PERSONAL",
	employee_advance: "",
	is_emergency: false,
	emergency_date: "",
	emergency_reason: "",
	correction_note: "",
	expenses: [blankExpense()],
});
const accountOptions = ref([]);
const stepNo = computed(() => {
	let n = 0;
	const steps = { context: ++n };
	if (!isCorrection.value) steps.paid = ++n;
	if (isIntegrated.value && !isCorrection.value) steps.invoice = ++n;
	steps.items = ++n;
	return steps;
});
const receiptsReady = computed(() => form.expenses.filter((item) => item.receipt_filename || item.receipt_content || item.receipt_attachment).length);
const itemsComplete = computed(() => form.expenses.every((item) => item.account && item.description && (generatesInvoice.value || (Number(item.amount) > 0 && (item.receipt_filename || item.receipt_content || item.receipt_attachment)))));
const projectLabel = computed(() => isCorrection.value ? correctionDetail.value?.project_name || correctionDetail.value?.project || "" : defaults.value.projects.find((project) => project.value === form.project)?.label || "");
const sourceLabel = computed(() => sourceChoices.value?.find?.((source) => source.value === form.reimbursement_source)?.label || "Personal funds");
const loading = ref(true);
const loadingAccounts = ref(false);
const readingFiles = ref(false);
const submitting = ref(false);
const error = ref("");
const result = ref(null);
const submissionStatus = ref("");
let submission;
async function recoverSubmission() {
    if (isCorrection.value || !defaults.value.employee) return;
    submission = new ExpenseSubmission({ slot: defaults.value.employee + (isIntegrated.value ? ":combined" : ":single"), call, status: value => submissionStatus.value = value });
    const recovered = await submission.restore();
    if (recovered) { result.value = recovered; return; }
    const saved = submission.pending?.draft;
    if (saved) {
        Object.assign(form, saved.form);
        invoicePath.value = saved.invoicePath || "";
        itemKey = Math.max(itemKey, ...form.expenses.map(item => Number(item.key) + 1));
        accountOptions.value = await call(`${API}get_project_accounts`, { project: form.project });
        submissionStatus.value ||= "Your previous submission is saved on this device. Retry it safely below.";
    }
}
async function retrySavedSubmission() {
    if (submitting.value || !submission?.pending) return;
    submitting.value = true; error.value = "";
    try { result.value = await submission.retry(); }
    catch (e) { error.value = e.message; }
    finally { submitting.value = false; }
}
const total = computed(() =>
	form.expenses.reduce((sum, item) => sum + Number(item.amount || 0), 0),
);
const generatesInvoice = computed(
	() => isIntegrated.value && invoicePath.value === "GENERATE" && !isCorrection.value,
);
const invoiceSeed = computed(() => ({
	expense_date: form.expenses[0]?.expense_date || "",
	description: form.expenses[0]?.description || "",
}));
const claimSignatureContext = computed(() => {
	const item = form.expenses[0] || {};
	return {
		project: form.project,
		reimbursement_source: form.reimbursement_source,
		employee_advance: form.employee_advance,
		is_emergency: form.is_emergency,
		emergency_date: form.emergency_date,
		emergency_reason: form.emergency_reason,
		expense: {
			expense_date: item.expense_date,
			account: item.account,
			description: item.description,
			amount: item.amount,
		},
	};
});
const selectedAdvance = computed(() =>
	form.reimbursement_source === "OWN_ADVANCE"
		? defaults.value.own_advances.find((advance) => advance.name === form.employee_advance)
		: null,
);
const managerFundingShortfall = computed(
	() =>
		form.reimbursement_source === "MANAGER_ADVANCE" &&
		total.value > Number(defaults.value.manager_advance.maximum_available || 0),
);
const sourceChoices = computed(() => [
	{
		value: "PERSONAL",
		label: "Paid personally",
		hint: "Reimburse me after approval",
		disabled: false,
	},
	{
		value: "OWN_ADVANCE",
		label: "Against my advance",
		hint: defaults.value.own_advances.length
			? "Settle an advance already paid to me"
			: "No paid unsettled advance is available",
		disabled: !defaults.value.own_advances.length,
	},
	{
		value: "MANAGER_ADVANCE",
		label: "Against manager’s advance",
		hint: defaults.value.manager_advance.available
			? `Available from ${defaults.value.manager_advance.manager_name}`
			: "No manager advance is available",
		disabled: !defaults.value.manager_advance.available,
	},
]);

onMounted(loadForm);
watch(
	() => form.reimbursement_source,
	(source) => {
		if (source !== "OWN_ADVANCE") form.employee_advance = "";
	},
);
watch(invoicePath, (path) => {
	if (path !== "GENERATE") return;
	form.expenses.splice(1);
	const item = form.expenses[0];
	item.supplier_name = "";
	item.invoice_number = "";
	item.receipt_filename = "";
	item.receipt_content = "";
	item.receipt_attachment = "";
});

async function loadDefaults() {
	loading.value = true;
	error.value = "";
	try {
		defaults.value = await call(`${API}get_expense_claim_form`);
		form.expenses.forEach((item) => (item.expense_date = defaults.value.expense_date));
		form.emergency_date = defaults.value.expense_date;
		if (
			route.query.reimbursement_source === "OWN_ADVANCE" &&
			defaults.value.own_advances.some(
				(advance) => advance.name === route.query.employee_advance,
			)
		) {
			form.reimbursement_source = "OWN_ADVANCE";
			form.employee_advance = String(route.query.employee_advance);
		}
		if (
			route.query.reimbursement_source === "MANAGER_ADVANCE" &&
			defaults.value.manager_advance.available
		) {
			form.reimbursement_source = "MANAGER_ADVANCE";
		}
		const requestedProject = String(route.query.project || "");
		if (!isCorrection.value && defaults.value.projects.some((project) => project.value === requestedProject)) {
			form.project = requestedProject;
			await projectChanged();
		} else if (defaults.value.projects.length === 1) {
			form.project = defaults.value.projects[0].value;
			await projectChanged();
		}
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		loading.value = false;
	}
}

async function loadForm() {
	await loadDefaults();
	if (!isCorrection.value || error.value) { if (!error.value) await recoverSubmission(); return; }
	loading.value = true;
	try {
		const detail = await call(`${API}get_my_expense_claim`, { name: correctionName.value });
		if (!detail.can_correct) throw new Error("This claim is not available for correction.");
		correctionDetail.value = detail;
		form.project = detail.project;
		accountOptions.value = detail.account_options || [];
		form.expenses = (detail.expenses || []).map((item) => ({
			key: itemKey++,
			name: item.name,
			expense_date: item.expense_date,
			account: item.account,
			supplier_name: item.supplier_name,
			invoice_number: item.invoice_number,
			description: item.description,
			amount: Number(item.amount || 0),
			receipt_filename: "",
			receipt_content: "",
			receipt_attachment: item.receipt_attachment,
		}));
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		loading.value = false;
	}
}

async function projectChanged() {
	const request = ++accountRequest;
	error.value = "";
	form.expenses.forEach((item) => (item.account = ""));
	accountOptions.value = [];
	if (!form.project) return;
	loadingAccounts.value = true;
	try {
		const options = await call(`${API}get_project_accounts`, { project: form.project });
		if (request !== accountRequest) return;
		accountOptions.value = options;
		if (accountOptions.value.length === 1) {
			form.expenses.forEach((item) => (item.account = accountOptions.value[0].value));
		}
	} catch (e) {
		if (request === accountRequest) error.value = e.message || String(e);
	} finally {
		if (request === accountRequest) loadingAccounts.value = false;
	}
}

function addExpense() {
	if (form.expenses.length >= 10) return;
	const item = blankExpense();
	if (accountOptions.value.length === 1) item.account = accountOptions.value[0].value;
	form.expenses.push(item);
}

function removeExpense(index) {
	if (form.expenses.length > 1) form.expenses.splice(index, 1);
}

async function chooseReceipt(event, item) {
	const file = event.target.files?.[0];
	item.receipt_filename = "";
	item.receipt_content = "";
	if (!file) return;
	if (file.size > 5 * 1024 * 1024) {
		error.value = "Each receipt must be 5 MB or smaller.";
		event.target.value = "";
		return;
	}
	readingFiles.value = true;
	try {
		item.receipt_filename = file.name;
		item.receipt_content = await fileBase64(file);
	} catch (e) {
		error.value = "The selected receipt could not be read.";
		event.target.value = "";
	} finally {
		readingFiles.value = false;
	}
}

function fileBase64(file) {
	return new Promise((resolve, reject) => {
		const reader = new FileReader();
		reader.onload = () => resolve(String(reader.result || "").split(",")[1] || "");
		reader.onerror = reject;
		reader.readAsDataURL(file);
	});
}

async function submitClaim() {
	if (submitting.value || readingFiles.value) return;
	error.value = "";
	if (isIntegrated.value && !invoicePath.value) {
		error.value = "Choose whether you already have an invoice or need to prepare one.";
		return;
	}
	if (
		!generatesInvoice.value &&
		form.expenses.some((item) => !item.receipt_content && !item.receipt_attachment)
	) {
		error.value = "Attach receipt evidence to every expense item.";
		return;
	}
	submitting.value = true;
	try {
		// The stable key is only for Vue rendering; it is not claim data.
		const expenses = form.expenses.map(({ key, receipt_attachment, ...item }) => item);
		if (isCorrection.value) {
			result.value = await call(`${API}resubmit_expense_claim`, {
				name: correctionName.value,
				payload: { expenses, correction_note: form.correction_note },
			});
		} else if (generatesInvoice.value) {
			const invoicePayload = invoiceGenerator.value?.getSubmissionPayload();
			const payload = { ...form, expenses };
			delete payload.correction_note;
			result.value = await submission.submit(`${API}submit_generated_invoice_expense_claim`, { claim_payload: payload, invoice_payload: invoicePayload }, { form: JSON.parse(JSON.stringify(form)), invoicePath: invoicePath.value });
		} else {
			const payload = { ...form, expenses };
			delete payload.correction_note;
			result.value = await submission.submit(`${API}submit_expense_claim`, { payload }, { form: JSON.parse(JSON.stringify(form)), invoicePath: invoicePath.value });
		}
		window.scrollTo({ top: 0, behavior: "smooth" });
	} catch (e) {
		error.value = e.message || String(e);
		window.scrollTo({ top: 0, behavior: "smooth" });
	} finally {
		submitting.value = false;
	}
}

async function startAnother() {
	await submission?.reset();
	result.value = null;
	form.project = "";
	form.reimbursement_source = "PERSONAL";
	form.employee_advance = "";
	form.is_emergency = false;
	form.emergency_reason = "";
	form.emergency_date = defaults.value.expense_date;
	form.expenses = [blankExpense()];
	invoicePath.value = "";
	accountOptions.value = [];
	if (defaults.value.projects.length === 1) {
		form.project = defaults.value.projects[0].value;
		projectChanged();
	}
}

function setGeneratedInvoiceTotal(value) {
	if (!form.expenses[0]) return;
	form.expenses[0].amount = Number(value || 0);
}

function money(value) {
	return new Intl.NumberFormat("en-IN", {
		style: "currency",
		currency: defaults.value.currency || "INR",
		maximumFractionDigits: 2,
	}).format(Number(value || 0));
}

function plainText(value) {
	const document = new DOMParser().parseFromString(String(value), "text/html");
	return document.body.textContent || "";
}
</script>

<style scoped>
.expense-portal-grid {
	@apply grid sm:grid-cols-2 gap-4;
}
.person-chip { @apply flex min-w-0 max-w-full items-center gap-2.5 rounded-xl border border-line bg-soft py-1.5 pl-1.5 pr-3.5; }
.item-badge { @apply inline-flex h-6 w-6 items-center justify-center rounded-full bg-navy-900 text-[11px] font-bold text-white; }
.item-card { border-left: 3px solid var(--navy-100); }
.emergency-card { transition: border-color var(--dur) ease, background-color var(--dur) ease; }
.emergency-card--on { border-color: color-mix(in srgb, var(--warn) 40%, var(--line)); background: linear-gradient(180deg, var(--warn-soft), var(--surface) 60%); }
.success-mark {
	@apply mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-ok-soft text-2xl font-bold text-ok;
}
</style>
