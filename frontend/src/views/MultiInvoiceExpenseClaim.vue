<template>
	<div class="max-w-5xl mx-auto">
		<PageHeader
			eyebrow="Expenses"
			title="Submit multiple invoices"
			subtitle="Send several dated bills together. Each invoice is reviewed and posted separately in the financial year of its invoice date."
		>
			<template #actions>
				<RouterLink to="/expense-claim" class="btn-secondary">Single invoice form</RouterLink>
				<RouterLink to="/expense-claims" class="btn-secondary">My claims</RouterLink>
			</template>
		</PageHeader>
		<p v-if="error" class="message-error mb-5" role="alert">{{ error }}</p>
		<p v-if="loading" class="text-muted">Loading your options…</p>
		<section v-else-if="result" class="form-card space-y-4">
			<h2 class="text-xl font-semibold">Sent for receipt review</h2>
			<p>{{ result.claims.length }} invoices totalling {{ money(result.total) }} were submitted together. Each now has a separate claim and invoice-date accounting period.</p>
			<div class="divide-y divide-line rounded-xl border border-line">
				<RouterLink
					v-for="claim in result.claims"
					:key="claim.name"
					:to="{ path: '/expense-claims', query: { claim: claim.name } }"
					class="flex items-center justify-between gap-3 p-4 text-accent hover:bg-bg"
				>
					<span>{{ claim.name }}</span><span>{{ money(claim.total) }} →</span>
				</RouterLink>
			</div>
			<RouterLink to="/home" class="btn-secondary inline-flex">Return Home</RouterLink>
		</section>
		<form v-else class="space-y-5" @submit.prevent="submit">
			<section class="form-card">
				<h2 class="text-lg font-semibold mb-4">Claim context</h2>
				<div class="grid gap-4 sm:grid-cols-2">
					<label class="field-label">Employee<input :value="defaults.employee_name" readonly class="field-input" /></label>
					<label class="field-label">Reporting manager<input :value="defaults.approver?.name || 'Not configured'" readonly class="field-input" /></label>
					<label class="field-label sm:col-span-2">Project *
						<select v-model="form.project" required class="field-input" @change="projectChanged">
							<option value="" disabled>Select a project you belong to</option>
							<option v-for="project in defaults.projects" :key="project.value" :value="project.value">{{ project.label }} · {{ project.description }}</option>
						</select>
					</label>
				</div>
				<p v-if="!defaults.projects.length" class="mt-3 text-sm text-muted">No active project with approved expense categories is available to you.</p>
			</section>

			<section class="form-card">
				<h2 class="text-lg font-semibold mb-3">How were these paid?</h2>
				<p class="text-sm text-muted mb-4">All invoices in this submission must use the same payment source and project.</p>
				<div class="grid gap-3 sm:grid-cols-3">
					<button v-for="source in sources" :key="source.value" type="button" :disabled="source.disabled"
						:class="['choice-card', form.reimbursement_source === source.value ? 'choice-card-active' : '']"
						@click="form.reimbursement_source = source.value; form.employee_advance = ''">
						<strong>{{ source.label }}</strong><span class="text-sm text-muted">{{ source.hint }}</span>
					</button>
				</div>
				<label v-if="form.reimbursement_source === 'OWN_ADVANCE'" class="field-label mt-4">Paid employee advance *
					<select v-model="form.employee_advance" required class="field-input">
						<option value="" disabled>Select your advance</option>
						<option v-for="advance in defaults.own_advances" :key="advance.name" :value="advance.name">{{ advance.name }} · {{ money(advance.residual) }} available</option>
					</select>
				</label>
				<p v-if="form.reimbursement_source === 'MANAGER_ADVANCE'" class="mt-3 text-sm text-muted">Currently available from {{ defaults.manager_advance.manager_name }}: {{ money(defaults.manager_advance.maximum_available) }}.</p>
			</section>

			<section class="form-card">
				<label class="flex items-start gap-3 cursor-pointer">
					<input v-model="form.is_emergency" type="checkbox" class="mt-1" />
					<span><strong class="block">These were emergency expenses</strong><span class="block text-sm text-muted">This does not bypass receipt review or approval.</span></span>
				</label>
				<div v-if="form.is_emergency" class="grid gap-4 sm:grid-cols-2 mt-4">
					<label class="field-label">Emergency date *<input v-model="form.emergency_date" type="date" :max="defaults.expense_date" required class="field-input" /></label>
					<label class="field-label sm:col-span-2">Why was prior approval unavailable? *<textarea v-model.trim="form.emergency_reason" required maxlength="500" rows="3" class="field-input"></textarea></label>
				</div>
			</section>

			<div class="flex flex-wrap items-end justify-between gap-3">
				<div><h2 class="text-xl font-semibold">Invoices</h2><p class="text-sm text-muted mt-1">One date and one private receipt per invoice; add the billed items below it.</p></div>
				<button type="button" class="btn-secondary" :disabled="form.invoices.length >= 10" @click="addInvoice">+ Add invoice</button>
			</div>
			<section v-for="(invoice, invoiceIndex) in form.invoices" :key="invoice.key" class="form-card">
				<div class="flex items-center justify-between gap-3 mb-4">
					<h3 class="text-lg font-semibold">Invoice {{ invoiceIndex + 1 }}</h3>
					<button v-if="form.invoices.length > 2" type="button" class="text-sm font-medium text-bad" @click="form.invoices.splice(invoiceIndex, 1)">Remove invoice</button>
				</div>
				<div class="grid gap-4 sm:grid-cols-2">
					<label class="field-label">Date shown on invoice *<input v-model="invoice.invoice_date" type="date" :max="defaults.expense_date" required class="field-input" /></label>
					<label class="field-label">Invoice number<input v-model.trim="invoice.invoice_number" maxlength="100" class="field-input" /></label>
					<label class="field-label sm:col-span-2">Supplier / payee<input v-model.trim="invoice.supplier_name" maxlength="160" class="field-input" /></label>
					<label class="field-label sm:col-span-2">Invoice or bill (PDF, PNG or JPEG; max 5 MB) *
						<input type="file" accept=".pdf,.png,.jpg,.jpeg" required class="field-input" :disabled="readingFiles || submitting" @change="chooseReceipt($event, invoice)" />
					</label>
				</div>
				<p v-if="invoice.receipt_filename" class="text-xs text-muted mt-2">Ready to upload privately: {{ invoice.receipt_filename }}</p>
				<div class="mt-5 space-y-3">
					<div class="flex items-center justify-between gap-3"><h4 class="font-semibold">Items on this invoice</h4><button type="button" class="btn-secondary" :disabled="invoice.items.length >= 10" @click="invoice.items.push(blankItem())">+ Add item</button></div>
					<div v-for="(item, itemIndex) in invoice.items" :key="item.key" class="rounded-xl border border-line p-4">
						<div class="flex items-center justify-between mb-3"><strong>Item {{ itemIndex + 1 }}</strong><button v-if="invoice.items.length > 1" type="button" class="text-sm text-bad" @click="invoice.items.splice(itemIndex, 1)">Remove</button></div>
						<div class="grid gap-4 sm:grid-cols-2">
							<SearchSelect v-model="item.account" :options="accountOptions" :disabled="!form.project || loadingAccounts" label="Project expense category *" placeholder="Type to find a category" required />
							<label class="field-label">Amount ({{ defaults.currency }}) *<input v-model.number="item.amount" type="number" min="0.01" max="999999999" step="0.01" required class="field-input" /></label>
							<label class="field-label sm:col-span-2">Description and business purpose *<textarea v-model.trim="item.description" maxlength="1000" rows="2" required class="field-input"></textarea></label>
						</div>
					</div>
				</div>
				<p class="mt-4 text-right font-semibold">Invoice total: {{ money(invoiceTotal(invoice)) }}</p>
			</section>
			<section class="form-card flex flex-wrap items-center justify-between gap-4">
				<div><p class="text-sm text-muted">Combined submission</p><p class="text-2xl font-semibold">{{ money(total) }}</p><p class="text-sm text-muted">Approval authority is checked against this full amount.</p></div>
				<button type="submit" class="btn-primary" :disabled="submitting || readingFiles || !form.project || !accountOptions.length || total <= 0">{{ submitting ? 'Submitting…' : 'Submit all invoices for review' }}</button>
			</section>
		</form>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import SearchSelect from "../components/SearchSelect.vue";
import { call } from "../lib/frappe";

const API = "volunteering.volunteering.expense_claim_portal.";
const route = useRoute();
let key = 0;
const defaults = ref({ employee_name: "", currency: "INR", expense_date: "", projects: [], own_advances: [], manager_advance: {}, approver: {} });
const blankItem = () => ({ key: ++key, account: "", description: "", amount: null });
const blankInvoice = () => ({ key: ++key, invoice_date: defaults.value.expense_date || "", invoice_number: "", supplier_name: "", receipt_filename: "", receipt_content: "", items: [blankItem()] });
const form = reactive({ project: "", reimbursement_source: "PERSONAL", employee_advance: "", is_emergency: false, emergency_date: "", emergency_reason: "", invoices: [blankInvoice(), blankInvoice()] });
const accountOptions = ref([]);
const loading = ref(true);
const loadingAccounts = ref(false);
const readingFiles = ref(0);
const submitting = ref(false);
const error = ref("");
const result = ref(null);
let accountRequest = 0;
const sources = computed(() => [
	{ value: "PERSONAL", label: "Paid personally", hint: "Reimburse me after approval", disabled: false },
	{ value: "OWN_ADVANCE", label: "Against my advance", hint: defaults.value.own_advances.length ? "Settle a paid advance" : "No paid advance is available", disabled: !defaults.value.own_advances.length },
	{ value: "MANAGER_ADVANCE", label: "Against manager’s advance", hint: defaults.value.manager_advance.available ? `Available from ${defaults.value.manager_advance.manager_name}` : "No manager advance is available", disabled: !defaults.value.manager_advance.available },
]);
const invoiceTotal = (invoice) => invoice.items.reduce((sum, item) => sum + Number(item.amount || 0), 0);
const total = computed(() => form.invoices.reduce((sum, invoice) => sum + invoiceTotal(invoice), 0));
const money = (amount) => new Intl.NumberFormat("en-IN", { style: "currency", currency: defaults.value.currency || "INR", maximumFractionDigits: 2 }).format(Number(amount || 0));

onMounted(async () => {
	try {
		defaults.value = await call(`${API}get_expense_claim_form`);
		form.invoices.forEach((invoice) => { invoice.invoice_date = defaults.value.expense_date; });
		form.emergency_date = defaults.value.expense_date;
		const requested = String(route.query.project || "");
		if (defaults.value.projects.some((project) => project.value === requested)) form.project = requested;
		else if (defaults.value.projects.length === 1) form.project = defaults.value.projects[0].value;
		if (form.project) await projectChanged();
	} catch (e) { error.value = e.message || String(e); }
	finally { loading.value = false; }
});

async function projectChanged() {
	const request = ++accountRequest;
	accountOptions.value = [];
	form.invoices.forEach((invoice) => invoice.items.forEach((item) => { item.account = ""; }));
	if (!form.project) return;
	loadingAccounts.value = true;
	try {
		const options = await call(`${API}get_project_accounts`, { project: form.project });
		if (request !== accountRequest) return;
		accountOptions.value = options;
		if (options.length === 1) form.invoices.forEach((invoice) => invoice.items.forEach((item) => { item.account = options[0].value; }));
	} catch (e) { if (request === accountRequest) error.value = e.message || String(e); }
	finally { if (request === accountRequest) loadingAccounts.value = false; }
}

function addInvoice() {
	if (form.invoices.length >= 10) return;
	const invoice = blankInvoice();
	if (accountOptions.value.length === 1) invoice.items[0].account = accountOptions.value[0].value;
	form.invoices.push(invoice);
}

async function chooseReceipt(event, invoice) {
	const file = event.target.files?.[0];
	invoice.receipt_filename = "";
	invoice.receipt_content = "";
	if (!file) return;
	if (file.size > 5 * 1024 * 1024) { error.value = "Each invoice must be 5 MB or smaller."; event.target.value = ""; return; }
	readingFiles.value += 1;
	try {
		invoice.receipt_content = await new Promise((resolve, reject) => {
			const reader = new FileReader();
			reader.onload = () => resolve(String(reader.result || "").split(",")[1] || "");
			reader.onerror = reject;
			reader.readAsDataURL(file);
		});
		invoice.receipt_filename = file.name;
	} catch (_) { error.value = "The selected invoice could not be read."; event.target.value = ""; }
	finally { readingFiles.value -= 1; }
}

async function submit() {
	if (submitting.value || readingFiles.value) return;
	error.value = "";
	if (form.invoices.some((invoice) => !invoice.receipt_content)) { error.value = "Attach a receipt for every invoice."; return; }
	if (form.reimbursement_source === "MANAGER_ADVANCE" && total.value > Number(defaults.value.manager_advance.maximum_available || 0)) { error.value = "The manager’s current advance does not cover this submission."; return; }
	submitting.value = true;
	try {
		const invoices = form.invoices.map((invoice) => ({
			invoice_date: invoice.invoice_date,
			invoice_number: invoice.invoice_number,
			supplier_name: invoice.supplier_name,
			receipt_filename: invoice.receipt_filename,
			receipt_content: invoice.receipt_content,
			items: invoice.items.map((item) => ({ account: item.account, description: item.description, amount: item.amount })),
		}));
		result.value = await call(`${API}submit_multi_invoice_expense_claim`, { payload: { ...form, invoices } });
		window.scrollTo({ top: 0, behavior: "smooth" });
	} catch (e) { error.value = e.message || String(e); window.scrollTo({ top: 0, behavior: "smooth" }); }
	finally { submitting.value = false; }
}
</script>

<style scoped>
.form-card { @apply rounded-2xl border border-line bg-surface p-4 shadow-soft sm:p-5; }
.field-label { @apply block text-sm font-medium text-ink; }
.field-input { @apply mt-1 block w-full rounded-xl border border-line bg-surface px-3 py-2.5 text-sm text-ink; }
.field-input:focus { outline: 2px solid var(--accent); outline-offset: 2px; }
.choice-card { @apply flex min-h-24 flex-col items-start gap-1 rounded-xl border border-line bg-bg p-4 text-left text-ink transition-colors; }
.choice-card-active { @apply border-accent bg-accent-soft; }
.choice-card:disabled { @apply cursor-not-allowed opacity-50; }
.message-error { @apply rounded-xl border border-bad bg-bad-soft p-4 text-sm text-bad; }
</style>
