<template>
	<div class="mx-auto max-w-6xl">
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
		<div v-if="submissionStatus && !result" class="form-card mb-4" role="status"><p>{{ submissionStatus }}</p><button v-if="!submitting && submission?.pending?.args" type="button" class="btn-secondary mt-3" @click="retrySavedSubmission">Retry saved submission</button></div>
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
			<div class="flex gap-3"><button type="button" class="btn-primary" @click="startAnother">Submit another set of invoices</button><RouterLink to="/home" class="btn-secondary inline-flex">Return Home</RouterLink></div>
		</section>
		<form v-else class="form-layout" @submit.prevent="submit">
			<div class="min-w-0 space-y-5">
			<section class="form-card">
				<h2 class="step-title"><span class="step-num" :class="{ 'step-num--done': form.project }" aria-hidden="true">1</span>Claim context</h2>
				<div class="mb-4 flex flex-wrap gap-2">
					<span class="person-chip"><Avatar :name="defaults.employee_name" size="sm" /><span class="min-w-0"><span class="block text-[11px] text-muted">Employee</span><span class="block truncate text-sm font-semibold text-ink">{{ defaults.employee_name || "—" }}</span></span></span>
					<span class="person-chip"><Avatar :name="defaults.approver?.name || '?'" size="sm" tone="slate" /><span class="min-w-0"><span class="block text-[11px] text-muted">Reporting manager</span><span class="block truncate text-sm font-semibold text-ink">{{ defaults.approver?.name || "Not configured" }}</span></span></span>
				</div>
				<div class="grid gap-4 sm:grid-cols-2">
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
				<h2 class="step-title !mb-2"><span class="step-num step-num--done" aria-hidden="true">2</span>How were these paid?</h2>
				<p class="text-sm text-muted mb-4">All invoices in this submission must use the same payment source and project.</p>
				<div class="grid gap-3 sm:grid-cols-3">
					<button v-for="source in sources" :key="source.value" type="button" :disabled="source.disabled"
						:class="['option-card', form.reimbursement_source === source.value ? 'option-card--on' : '']" :aria-pressed="form.reimbursement_source === source.value"
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
				<div><h2 class="step-title !mb-0"><span class="step-num" :class="{ 'step-num--done': total > 0 }" aria-hidden="true">3</span>Invoices</h2><p class="text-sm text-muted mt-1">One date and one private receipt per invoice; add the billed items below it.</p></div>
				<button type="button" class="btn-secondary" :disabled="form.invoices.length >= 10" @click="addInvoice">+ Add invoice</button>
			</div>
			<section v-for="(invoice, invoiceIndex) in form.invoices" :key="invoice.key" class="form-card">
				<div class="flex items-center justify-between gap-3 mb-4">
					<h3 class="flex items-center gap-2.5 text-lg font-semibold"><span class="item-badge" aria-hidden="true">{{ invoiceIndex + 1 }}</span>Invoice {{ invoiceIndex + 1 }}</h3>
					<button v-if="form.invoices.length > 2" type="button" class="text-sm font-medium text-bad" @click="form.invoices.splice(invoiceIndex, 1)">Remove invoice</button>
				</div>
				<div class="grid gap-4 sm:grid-cols-2">
					<label class="field-label">Date shown on invoice *<input v-model="invoice.invoice_date" type="date" :max="defaults.expense_date" required class="field-input" /></label>
					<label class="field-label">Invoice number<input v-model.trim="invoice.invoice_number" maxlength="100" class="field-input" /></label>
					<label class="field-label sm:col-span-2">Supplier / payee<input v-model.trim="invoice.supplier_name" maxlength="160" class="field-input" /></label>
					<label class="field-label sm:col-span-2">Invoice or bill (PDF, PNG or JPEG; max 5 MB) *
						<input type="file" accept=".pdf,.png,.jpg,.jpeg" :required="!invoice.receipt_content" class="field-input" :disabled="readingFiles || submitting" @change="chooseReceipt($event, invoice)" />
					</label>
				</div>
				<p v-if="invoice.receipt_filename" class="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-ok"><Icon name="check" size="sm" />Ready to upload privately: {{ invoice.receipt_filename }}</p>
				<div class="mt-5 space-y-3">
					<div class="flex items-center justify-between gap-3"><h4 class="font-semibold">Items on this invoice</h4><button type="button" class="btn-secondary" :disabled="invoice.items.length >= 10" @click="invoice.items.push(blankItem())">+ Add item</button></div>
					<div v-for="(item, itemIndex) in invoice.items" :key="item.key" class="rounded-xl border border-line bg-soft/50 p-4">
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
			</div>
			<aside class="form-rail space-y-4">
				<section class="summary-card" aria-label="Submission summary">
					<p class="eyebrow">Combined submission</p>
					<p class="summary-total">{{ money(total) }}</p>
					<dl class="summary-list">
						<div v-for="(invoice, index) in form.invoices" :key="invoice.key"><dt>Invoice {{ index + 1 }}<template v-if="invoice.receipt_filename || invoice.receipt_content"> ✓</template></dt><dd>{{ money(invoiceTotal(invoice)) }}</dd></div>
					</dl>
					<p class="mt-3 text-xs text-muted">Approval authority is checked against this full amount.</p>
					<button type="submit" class="btn-primary mt-4 min-h-11 w-full" :disabled="submitting || readingFiles || !form.project || !accountOptions.length || total <= 0">{{ submitting ? 'Submitting…' : 'Submit all invoices for review' }}</button>
				</section>
				<section class="summary-card">
					<p class="text-sm font-semibold text-ink">What happens next</p>
					<ol class="next-steps mt-3">
						<li><span class="next-steps__dot">1</span><span>Each invoice becomes its own claim</span></li>
						<li><span class="next-steps__dot">2</span><span>Receipt review, then reporting-manager approval</span></li>
						<li><span class="next-steps__dot">3</span><span>Posted in the financial year of each invoice date</span></li>
					</ol>
				</section>
			</aside>
		</form>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import Avatar from "../components/Avatar.vue";
import Icon from "../components/Icon.vue";
import SearchSelect from "../components/SearchSelect.vue";
import { call } from "../lib/frappe";
import { ExpenseSubmission } from "../lib/expenseSubmission";

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
const result = ref(null), submissionStatus = ref("");
let submission;
async function startAnother() {
    await submission?.reset(); result.value = null; error.value = "";
    form.invoices = [blankInvoice(), blankInvoice()];
    if (accountOptions.value.length === 1) form.invoices.forEach(invoice => invoice.items[0].account = accountOptions.value[0].value);
}
async function retrySavedSubmission() {
    if (submitting.value || !submission?.pending) return;
    submitting.value = true; error.value = "";
    try { result.value = await submission.retry(); } catch (e) { error.value = e.message; }
    finally { submitting.value = false; }
}
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
        submission = new ExpenseSubmission({ slot: defaults.value.employee + ":multiple", call, status: value => submissionStatus.value = value });
        result.value = await submission.restore();
        if (!result.value && submission.pending?.draft) {
            Object.assign(form, submission.pending.draft);
            key = Math.max(key, ...form.invoices.flatMap(invoice => [invoice.key, ...invoice.items.map(item => item.key)])) + 1;
            accountOptions.value = await call(`${API}get_project_accounts`, { project: form.project });
            submissionStatus.value ||= "Your previous submission is saved on this device. Retry it safely below.";
        }
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
		result.value = await submission.submit(`${API}submit_multi_invoice_expense_claim`, { payload: { ...form, invoices } }, JSON.parse(JSON.stringify(form)));
		window.scrollTo({ top: 0, behavior: "smooth" });
	} catch (e) { error.value = e.message || String(e); window.scrollTo({ top: 0, behavior: "smooth" }); }
	finally { submitting.value = false; }
}
</script>

<style scoped>
.person-chip { @apply flex min-w-0 max-w-full items-center gap-2.5 rounded-xl border border-line bg-soft py-1.5 pl-1.5 pr-3.5; }
.item-badge { @apply inline-flex h-6 w-6 items-center justify-center rounded-full bg-navy-900 text-[11px] font-bold text-white; }
.choice-card { @apply flex min-h-24 flex-col items-start gap-1 rounded-xl border border-line bg-bg p-4 text-left text-ink transition-colors; }
.choice-card:disabled { @apply cursor-not-allowed opacity-50; }
</style>
