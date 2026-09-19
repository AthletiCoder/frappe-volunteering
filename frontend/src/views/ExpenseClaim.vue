<template>
	<div class="max-w-5xl mx-auto">
		<PageHeader
			title="Submit an expense"
			subtitle="Record project expenses, attach the bills, and send them for independent receipt review."
			eyebrow="Expenses"
		>
			<template #actions>
				<RouterLink to="/home" class="btn-secondary">Back to Home</RouterLink>
			</template>
		</PageHeader>

		<div v-if="loading" class="text-muted">Loading your claim options…</div>
		<div v-else-if="result" class="space-y-5">
			<section class="form-card text-center py-8">
				<div class="success-mark" aria-hidden="true">✓</div>
				<h2 class="text-xl font-semibold text-ink mt-3">Sent for receipt review</h2>
				<p class="text-muted mt-2">
					Expense Claim <strong class="text-ink">{{ result.name }}</strong> was created
					for {{ money(result.total) }}.
				</p>
				<p class="text-sm text-muted mt-1">
					A receipt reviewer checks the evidence first. The claim moves to
					reporting-manager approval only after that review is verified.
				</p>
				<div v-if="result.warnings?.length" class="warning-box mt-4 text-left">
					<p class="font-semibold mb-2">Advisories for review</p>
					<p v-for="warning in result.warnings" :key="warning" class="mt-1">
						{{ plainText(warning) }}
					</p>
				</div>
				<div class="flex flex-wrap justify-center gap-2 mt-5">
					<button type="button" class="btn-primary px-5 py-2.5" @click="startAnother">
						Submit another expense
					</button>
					<RouterLink to="/home" class="btn-secondary px-5 py-2.5"
						>Return Home</RouterLink
					>
				</div>
			</section>
		</div>
		<form v-else class="space-y-5" @submit.prevent="submitClaim">
			<div v-if="error" class="error-box" role="alert">{{ error }}</div>

			<section class="form-card">
				<h2 class="form-title">Claim context</h2>
				<div class="expense-portal-grid">
					<label class="field-label"
						>Employee<input
							:value="defaults.employee_name"
							readonly
							class="field-input"
					/></label>
					<label class="field-label"
						>Reporting manager<input
							:value="defaults.approver?.name || 'Not configured'"
							readonly
							class="field-input"
					/></label>
					<label class="field-label sm:col-span-2"
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
					<label class="field-label sm:col-span-2"
						>Purpose of this claim *<textarea
							v-model.trim="form.purpose"
							required
							maxlength="500"
							rows="3"
							class="field-input"
							placeholder="Why was this expense incurred for the project?"
						></textarea>
					</label>
				</div>
				<p v-if="!defaults.projects.length" class="warning-box mt-3">
					No active project with mapped expense categories is available to you. A
					Projects Manager must add you as a member and approve labels; an Accounts
					Manager must then map them.
				</p>
			</section>

			<section class="form-card">
				<h2 class="form-title">How was this paid?</h2>
				<div class="grid sm:grid-cols-3 gap-3">
					<button
						v-for="source in sourceChoices"
						:key="source.value"
						type="button"
						:disabled="source.disabled"
						:class="[
							'choice-card',
							form.reimbursement_source === source.value ? 'choice-card-active' : '',
						]"
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

			<section class="form-card">
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

			<section class="space-y-3">
				<div class="flex flex-wrap items-end justify-between gap-2">
					<div>
						<h2 class="text-xl font-semibold text-ink">Expense items</h2>
						<p class="text-sm text-muted mt-1">
							Attach the bill to the specific item it supports. PDF, PNG or JPEG;
							maximum 5 MB each.
						</p>
					</div>
					<button
						type="button"
						class="btn-secondary"
						:disabled="form.expenses.length >= 10"
						@click="addExpense"
					>
						+ Add expense item
					</button>
				</div>

				<article v-for="(item, index) in form.expenses" :key="item.key" class="form-card">
					<div class="flex items-center justify-between gap-3 mb-4">
						<h3 class="font-semibold text-ink">Expense item {{ index + 1 }}</h3>
						<button
							v-if="form.expenses.length > 1"
							type="button"
							class="text-sm font-medium text-bad"
							@click="removeExpense(index)"
						>
							Remove
						</button>
					</div>
					<div class="expense-portal-grid">
						<label class="field-label"
							>Expense date *<input
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
						<label class="field-label"
							>Supplier / payee<input
								v-model.trim="item.supplier_name"
								maxlength="160"
								class="field-input"
						/></label>
						<label class="field-label"
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
						<label class="field-label"
							>Amount ({{ defaults.currency }}) *<input
								v-model.number="item.amount"
								type="number"
								min="0.01"
								max="999999999"
								step="0.01"
								required
								class="field-input"
						/></label>
						<label class="field-label"
							>Receipt evidence *<input
								type="file"
								accept=".pdf,.png,.jpg,.jpeg"
								required
								:disabled="readingFiles || submitting"
								class="field-input"
								@change="chooseReceipt($event, item)"
						/></label>
					</div>
					<p v-if="item.receipt_filename" class="text-xs text-muted mt-2">
						Ready to upload privately: {{ item.receipt_filename }}
					</p>
				</article>
			</section>

			<section class="form-card">
				<div class="flex flex-wrap items-center justify-between gap-4">
					<div>
						<p class="text-sm text-muted">Total claimed</p>
						<p class="text-2xl font-semibold text-ink">{{ money(total) }}</p>
					</div>
					<div class="text-sm text-muted sm:text-right">
						<p>Next: independent receipt review</p>
						<p>Then: reporting-manager approval</p>
					</div>
				</div>
				<p v-if="managerFundingShortfall" class="warning-box mt-4">
					The manager’s current advance does not cover this total. Choose another payment
					source or ask the manager to obtain additional advance funding.
				</p>
				<div class="flex justify-end mt-5">
					<button
						type="submit"
						class="btn-primary px-5 py-2.5"
						:disabled="
							submitting ||
							readingFiles ||
							!defaults.projects.length ||
							managerFundingShortfall
						"
					>
						{{ submitting ? "Submitting…" : "Submit for receipt review" }}
					</button>
				</div>
			</section>
		</form>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import SearchSelect from "../components/SearchSelect.vue";
import { call } from "../lib/frappe";

const API = "volunteering.volunteering.expense_claim_portal.";
const route = useRoute();
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
});
const form = reactive({
	project: "",
	purpose: "",
	reimbursement_source: "PERSONAL",
	employee_advance: "",
	is_emergency: false,
	emergency_date: "",
	emergency_reason: "",
	expenses: [blankExpense()],
});
const accountOptions = ref([]);
const loading = ref(true);
const loadingAccounts = ref(false);
const readingFiles = ref(false);
const submitting = ref(false);
const error = ref("");
const result = ref(null);
const total = computed(() =>
	form.expenses.reduce((sum, item) => sum + Number(item.amount || 0), 0),
);
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

onMounted(loadDefaults);
watch(
	() => form.reimbursement_source,
	(source) => {
		if (source !== "OWN_ADVANCE") form.employee_advance = "";
	},
);

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
		if (defaults.value.projects.length === 1) {
			form.project = defaults.value.projects[0].value;
			await projectChanged();
		}
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
	if (form.expenses.some((item) => !item.receipt_content)) {
		error.value = "Attach receipt evidence to every expense item.";
		return;
	}
	submitting.value = true;
	try {
		// The stable key is only for Vue rendering; it is not claim data.
		const payload = {
			...form,
			expenses: form.expenses.map(({ key, ...item }) => item),
		};
		result.value = await call(`${API}submit_expense_claim`, { payload });
		window.scrollTo({ top: 0, behavior: "smooth" });
	} catch (e) {
		error.value = e.message || String(e);
		window.scrollTo({ top: 0, behavior: "smooth" });
	} finally {
		submitting.value = false;
	}
}

function startAnother() {
	result.value = null;
	form.project = "";
	form.purpose = "";
	form.reimbursement_source = "PERSONAL";
	form.employee_advance = "";
	form.is_emergency = false;
	form.emergency_reason = "";
	form.emergency_date = defaults.value.expense_date;
	form.expenses = [blankExpense()];
	accountOptions.value = [];
	if (defaults.value.projects.length === 1) {
		form.project = defaults.value.projects[0].value;
		projectChanged();
	}
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
.form-card {
	@apply rounded-2xl border border-line bg-surface p-4 sm:p-5 shadow-soft;
}
.form-title {
	@apply text-lg font-semibold text-ink mb-3;
}
.form-hint {
	@apply text-sm text-muted mb-3;
}
.expense-portal-grid {
	@apply grid sm:grid-cols-2 gap-4;
}
.field-label {
	@apply block text-sm font-medium text-ink;
}
.field-input {
	@apply mt-1 block w-full rounded-xl border border-line bg-surface px-3 py-2.5 text-sm text-ink;
}
.field-input:focus {
	outline: 2px solid var(--accent);
	outline-offset: 2px;
}
.choice-card {
	@apply flex min-h-24 flex-col items-start gap-1 rounded-xl border border-line bg-bg p-4 text-left text-ink transition-colors;
}
.choice-card-active {
	@apply border-accent bg-accent-soft;
}
.choice-card:disabled {
	@apply cursor-not-allowed opacity-50;
}
.error-box {
	@apply rounded-xl border border-bad bg-bad-soft p-4 text-sm text-bad;
}
.warning-box {
	@apply rounded-xl border border-warn bg-warn-soft p-3 text-sm text-ink;
}
.success-mark {
	@apply mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-ok-soft text-2xl font-bold text-ok;
}
</style>
