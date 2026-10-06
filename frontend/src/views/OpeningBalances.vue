<template>
	<div class="opening-page mx-auto max-w-5xl space-y-6 pb-10">
		<PageHeader
			title="Opening balances"
			eyebrow="Accounts"
			subtitle="Record the balance of each ledger at the beginning of the financial year."
		>
			<template #actions>
				<RouterLink to="/chart-of-accounts" class="btn-secondary"
					>Chart of Accounts</RouterLink
				>
			</template>
		</PageHeader>
		<p v-if="error" class="message-error" role="alert">{{ error }}</p>
		<p v-if="message" class="message-success" role="status">{{ message }}</p>
		<p v-if="loading" class="text-muted">Loading opening balances…</p>
		<template v-else-if="workspace">
			<section class="form-card overview-card">
				<div class="section-heading">
					<div><p class="eyebrow">Starting point</p><h2 class="form-title">Begin with the opening position</h2></div>
					<p class="form-hint">Enter April–September transactions separately with their actual dates. Do not include them in these starting amounts.</p>
				</div>
				<div class="summary-grid">
					<div class="summary-tile"><span>Financial year opens</span><strong>{{ dateLabel(workspace.default_opening_date) }}</strong></div>
					<div class="summary-tile"><span>Temporary Opening balance</span><strong>{{ money(Math.abs(workspace.temporary_balance)) }}</strong><small>{{ Number(workspace.temporary_balance) < 0 ? "Credit" : "Debit" }} remaining</small></div>
				</div>
				<details class="explanation"><summary>What is Temporary Opening?</summary><p>It balances each provisional starting amount and should reach zero once all verified opening balances are entered. It is not a donation or fund balance.</p></details>
			</section>
			<form class="form-card entry-card" @submit.prevent="record">
				<div class="section-heading">
					<div><p class="eyebrow">New entry</p><h2 class="form-title">Record a starting balance</h2></div>
					<p class="form-hint">Enter one ledger at a time. For a payable or receivable, choose the employee, supplier or customer too.</p>
				</div>
				<div class="opening-fields">
					<div class="account-field"><SearchSelect
						v-model="form.account"
						label="Ledger account *"
						:options="accountOptions"
						placeholder="Search bank, asset, payable or fund ledgers"
						:required="true"
						:disabled="saving"
					/><span class="field-help">Only active balance-sheet ledgers are listed.</span></div>
					<label class="field-label"
						>Opening date *<input
							v-model="form.opening_date"
							type="date"
							required
							:max="workspace.today"
							class="field-input"
					/><span class="field-help">First day of the relevant financial year.</span></label>
					<label class="field-label"
						>Amount ({{ workspace.currency }}) *<input
							v-model="form.amount"
							type="number"
							min="0.01"
							step="0.01"
							required
							class="field-input"
							placeholder="0.00"
					/><span class="field-help">Enter a positive amount.</span></label>
					<fieldset class="balance-field"><legend>Which side of the ledger? *</legend>
						<div class="side-options">
							<label class="side-option" :class="{ selected: form.side === 'Debit' }"><input v-model="form.side" type="radio" name="opening-side" value="Debit" required /><span><strong>Debit</strong><small>Usually bank balances and other assets</small></span></label>
							<label class="side-option" :class="{ selected: form.side === 'Credit' }"><input v-model="form.side" type="radio" name="opening-side" value="Credit" required /><span><strong>Credit</strong><small>Usually amounts owed and fund balances</small></span></label>
						</div>
					</fieldset>
					<template v-if="partyRequired">
						<label class="field-label"
							>Party type *<select
								v-model="form.party_type"
								required
								class="field-input"
							>
								<option value="">Choose a type</option>
								<option
									v-for="type in allowedPartyTypes"
									:key="type"
									:value="type"
								>
									{{ type }}
								</option>
							</select></label
						>
						<SearchSelect
							v-model="form.party"
							:label="`${form.party_type || 'Party'} *`"
							:options="partyOptions"
							:required="true"
							:disabled="saving || !form.party_type"
							placeholder="Type to find an existing party"
							empty-text="No party found. Create their record first."
						/>
					</template>
					<label class="field-label source-field"
						>Source reference *<input
							v-model.trim="form.source_reference"
							required
							maxlength="240"
							class="field-input"
							placeholder="For example, Axis statement opening balance on 1 April"
						/><span class="field-help"
							>Identify the statement or approved closing records supporting this
							amount.</span
						></label
					>
				</div>
				<div v-if="selectedAccount && Number(form.amount) > 0" class="posting-preview" aria-live="polite">
					<div class="preview-heading"><strong>Posting preview</strong><span>This is the entry that will be created</span></div>
					<div class="preview-row"><span>{{ form.side }}</span><span>{{ selectedAccount.account_name }}</span><strong>{{ money(form.amount) }}</strong></div>
					<div class="preview-row"><span>{{ form.side === "Debit" ? "Credit" : "Debit" }}</span><span>Temporary Opening</span><strong>{{ money(form.amount) }}</strong></div>
				</div>
				<div class="submit-area"><label class="checkbox-row"><input v-model="confirmed" type="checkbox" required /><span>I checked the amount and date against the source record. I understand posting changes the ledger.</span></label>
					<button type="submit" class="btn-primary" :disabled="saving">
						{{ saving ? "Posting…" : "Post opening balance" }}
					</button>
				</div>
			</form>
			<section class="form-card">
				<h2 class="form-title">Opening amounts recorded here</h2>
				<p class="form-hint">
					To correct a submitted amount, make a traceable accounting correction; do not
					enter it a second time.
				</p>
				<p v-if="!workspace.history.length" class="text-muted mt-4">
					No opening amounts have been entered through Home yet.
				</p>
				<div
					v-for="entry in workspace.history"
					:key="entry.name"
					class="mt-3 rounded-xl border border-line p-4"
				>
					<div class="flex flex-wrap items-start justify-between gap-2">
						<div>
							<strong>{{ entry.rows?.[0]?.account || entry.name }}</strong>
							<p v-if="entry.rows?.[0]?.party" class="text-sm text-muted">
								{{ entry.rows[0].party_type }} · {{ entry.rows[0].party }}
							</p>
						</div>
						<span class="text-sm text-muted"
							>{{ dateLabel(entry.posting_date) }} · {{ entry.name }}</span
						>
					</div>
					<p class="mt-2 text-sm">
						{{ entry.rows?.[0]?.debit_in_account_currency ? "Debit" : "Credit" }}
						{{
							money(
								entry.rows?.[0]?.debit_in_account_currency ||
									entry.rows?.[0]?.credit_in_account_currency ||
									0,
							)
						}}
					</p>
				</div>
			</section>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import SearchSelect from "../components/SearchSelect.vue";
import { call } from "../lib/frappe";

const api = "volunteering.volunteering.opening_balances_portal.";
const workspace = ref(null),
	loading = ref(true),
	saving = ref(false),
	error = ref(""),
	message = ref(""),
	confirmed = ref(false);
const form = reactive({
	account: "",
	opening_date: "",
	amount: "",
	side: "Debit",
	party_type: "",
	party: "",
	source_reference: "",
});
const partyOptions = ref([]);
const accountOptions = computed(() =>
	(workspace.value?.accounts || []).map((row) => ({
		value: row.name,
		label: `${row.account_name} · ${row.name}`,
		description: row.root_type,
	})),
);
const selectedAccount = computed(() =>
	(workspace.value?.accounts || []).find((row) => row.name === form.account),
);
const partyRequired = computed(() =>
	["Payable", "Receivable"].includes(selectedAccount.value?.account_type),
);
const allowedPartyTypes = computed(() =>
	selectedAccount.value?.account_type === "Payable"
		? ["Employee", "Supplier"]
		: ["Customer", "Employee"],
);
function money(value) {
	return new Intl.NumberFormat("en-IN", {
		style: "currency",
		currency: workspace.value?.currency || "INR",
	}).format(Number(value || 0));
}
function dateLabel(value) {
	if (!value) return "";
	const [year, month, day] = String(value).slice(0, 10).split("-");
	return `${day}/${month}/${year}`;
}
async function load() {
	loading.value = true;
	error.value = "";
	try {
		workspace.value = await call(api + "get_opening_balances");
		if (!form.opening_date) form.opening_date = workspace.value.default_opening_date;
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		loading.value = false;
	}
}
watch(
	() => form.account,
	() => {
		form.party_type = "";
		form.party = "";
		partyOptions.value = [];
		form.side = selectedAccount.value?.root_type === "Asset" ? "Debit" : "Credit";
	},
);
watch(
	() => form.party_type,
	async (type) => {
		form.party = "";
		partyOptions.value = [];
		if (!type) return;
		try {
			partyOptions.value = await call(api + "get_opening_parties", { party_type: type });
		} catch (e) {
			error.value = e.message || String(e);
		}
	},
);
async function record() {
	error.value = "";
	message.value = "";
	if (!confirmed.value) {
		error.value = "Confirm the source amount before posting.";
		return;
	}
	saving.value = true;
	try {
		const result = await call(api + "record_opening_balance", { details: { ...form } });
		workspace.value = result.workspace;
		message.value = `Opening balance posted as ${result.journal_entry}.`;
		form.account = "";
		form.amount = "";
		form.party_type = "";
		form.party = "";
		form.source_reference = "";
		confirmed.value = false;
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		saving.value = false;
	}
}
onMounted(load);
</script>

<style scoped>
.opening-page { min-width: 0; }
.form-card { padding: 1.75rem; border: 1px solid var(--line); border-radius: 1.25rem; background: var(--surface); box-shadow: var(--shadow-soft); }
.section-heading { display: flex; align-items: start; justify-content: space-between; gap: 1.5rem; margin-bottom: 1.5rem; }
.section-heading > div { min-width: 0; flex: 1 1 auto; }
.section-heading > .form-hint { flex: 0 1 21rem; }
.eyebrow { margin: 0 0 .35rem; color: var(--accent); font-size: .7rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.form-title { margin: 0; color: var(--ink); font-size: 1.25rem; font-weight: 700; line-height: 1.3; }
.form-hint { margin: 0; color: var(--muted); font-size: .875rem; line-height: 1.55; }
.summary-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .75rem; }
.summary-tile { display: flex; flex-direction: column; gap: .25rem; min-width: 0; padding: 1.1rem 1.25rem; border-radius: .9rem; background: var(--soft); }
.summary-tile span { color: var(--muted); font-size: .8rem; }
.summary-tile strong { color: var(--ink); font-size: 1.2rem; line-height: 1.35; }
.summary-tile small { color: var(--muted); font-size: .75rem; }
.explanation { margin-top: 1.25rem; padding-top: 1rem; border-top: 1px solid var(--line); color: var(--muted); font-size: .83rem; line-height: 1.55; }
.explanation summary { width: fit-content; color: var(--accent); font-weight: 600; cursor: pointer; }
.explanation p { max-width: 46rem; margin: .65rem 0 0; }
.opening-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1.35rem 1.25rem; min-width: 0; padding: 0; border: 0; background: transparent; }
.account-field, .source-field, .balance-field { grid-column: 1 / -1; min-width: 0; }
.field-label { display: flex; flex-direction: column; align-items: stretch; min-width: 0; color: var(--ink); font-size: .875rem; font-weight: 600; line-height: 1.4; }
.field-input, .opening-page :deep(.search-input) { display: block; width: 100%; min-width: 0; min-height: 3rem; margin-top: .55rem; padding: .7rem .85rem; border: 1px solid var(--line); border-radius: .75rem; background: var(--surface); color: var(--ink); font-size: .925rem; font-weight: 400; line-height: 1.4; }
.opening-page :deep(.search-input) { margin-top: 0; }
.field-input:focus-visible, .opening-page :deep(.search-input:focus-visible) { outline: 2px solid var(--accent); outline-offset: 1px; }
.field-help { display: block; margin-top: .45rem; color: var(--muted); font-size: .76rem; font-weight: 400; line-height: 1.45; }
.opening-page :deep(.search-select > label) { display: block; color: var(--ink); font-size: .875rem; font-weight: 600; }
.opening-page :deep(.search-select > div) { margin-top: .55rem; }
.balance-field { margin: 0; padding: 0; border: 0; }
.balance-field legend { margin-bottom: .7rem; padding: 0; color: var(--ink); font-size: .875rem; font-weight: 600; }
.side-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .75rem; }
.side-option { display: flex; align-items: start; gap: .75rem; min-width: 0; padding: .95rem 1rem; border: 1px solid var(--line); border-radius: .875rem; background: var(--surface); cursor: pointer; }
.side-option.selected { border-color: var(--accent); background: var(--accent-soft); }
.side-option input { width: 1rem; height: 1rem; margin: .18rem 0 0; flex: none; accent-color: var(--accent); }
.side-option span { display: flex; flex-direction: column; gap: .2rem; min-width: 0; }
.side-option strong { color: var(--ink); font-size: .9rem; }
.side-option small { color: var(--muted); font-size: .76rem; line-height: 1.4; }
.posting-preview { overflow: hidden; margin-top: 1.5rem; border: 1px solid var(--line); border-radius: .875rem; background: var(--soft); }
.preview-heading { display: flex; flex-wrap: wrap; justify-content: space-between; gap: .25rem 1rem; padding: .85rem 1rem; border-bottom: 1px solid var(--line); }
.preview-heading strong { font-size: .875rem; }
.preview-heading span { color: var(--muted); font-size: .76rem; }
.preview-row { display: grid; grid-template-columns: 4.5rem minmax(0, 1fr) auto; align-items: baseline; gap: .75rem; padding: .7rem 1rem; font-size: .85rem; }
.preview-row + .preview-row { border-top: 1px solid var(--line); }
.preview-row span:first-child { color: var(--muted); font-weight: 600; }
.preview-row span:nth-child(2) { overflow-wrap: anywhere; }
.preview-row strong { white-space: nowrap; font-size: .9rem; }
.submit-area { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 1.25rem; margin-top: 1.5rem; padding-top: 1.5rem; border-top: 1px solid var(--line); }
.checkbox-row { display: flex; align-items: start; gap: .7rem; max-width: 35rem; color: var(--ink); font-size: .8rem; font-weight: 400; line-height: 1.5; cursor: pointer; }
.checkbox-row input { width: 1rem; height: 1rem; margin-top: .13rem; flex: none; accent-color: var(--accent); }
.submit-area .btn-primary { min-height: 2.8rem; padding: .7rem 1.15rem; white-space: nowrap; }
.submit-area .btn-primary:disabled { opacity: .6; cursor: wait; }
.message-error, .message-success { margin: 0; padding: .9rem 1rem; border: 1px solid; border-radius: .85rem; font-size: .875rem; }
.message-error { border-color: var(--bad); background: var(--bad-soft); color: var(--bad); }
.message-success { border-color: var(--ok); background: var(--ok-soft); color: var(--ink); }
@media (max-width: 640px) {
	.form-card { padding: 1.2rem; }
	.section-heading { display: block; margin-bottom: 1.2rem; }
	.section-heading > .form-hint { margin-top: .5rem; }
	.summary-grid, .opening-fields, .side-options { grid-template-columns: minmax(0, 1fr); }
	.account-field, .source-field, .balance-field { grid-column: auto; }
	.preview-row { grid-template-columns: 3.5rem minmax(0, 1fr); gap: .25rem .5rem; }
	.preview-row strong { grid-column: 2; }
	.submit-area .btn-primary { width: 100%; }
}
</style>
