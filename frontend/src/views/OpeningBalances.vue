<template>
	<div class="mx-auto max-w-6xl space-y-5 pb-10">
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
			<div class="grid gap-3 sm:grid-cols-2">
				<StatTile label="Financial year opens" :value="dateLabel(workspace.default_opening_date)" icon="calendar-check" />
				<StatTile
					label="Temporary Opening balance"
					:value="money(Math.abs(workspace.temporary_balance))"
					:hint="`${Number(workspace.temporary_balance) < 0 ? 'Credit' : 'Debit'} remaining · should reach zero`"
					icon="coins"
					:attention="Math.abs(Number(workspace.temporary_balance)) > 0"
				/>
			</div>

			<div class="form-layout">
				<form class="kit-panel step-panel min-w-0" @submit.prevent="record">
					<div class="border-b border-line px-5 py-4 sm:px-6">
						<h2 class="font-display text-lg font-semibold text-ink">Record a starting balance</h2>
						<p class="mt-1 text-sm text-muted">Enter one ledger at a time. For a payable or receivable, choose the employee, supplier or customer too.</p>
					</div>
					<fieldset class="form-step">
						<legend class="form-step__title"><span aria-hidden="true" class="step-num" :class="{ 'step-num--done': form.account && Number(form.amount) > 0 && form.side }">1</span>Ledger and amount</legend>
						<div class="form-step__grid">
							<div class="min-w-0 sm:col-span-2"><SearchSelect
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
									class="field-input tabular-nums"
									placeholder="0.00"
							/><span class="field-help">Enter a positive amount.</span></label>
							<fieldset class="min-w-0 sm:col-span-2"><legend class="field-label mb-2">Which side of the ledger? *</legend>
								<div class="grid gap-3 sm:grid-cols-2">
									<label class="check-card"><input v-model="form.side" type="radio" name="opening-side" value="Debit" required /><span><strong>Debit</strong><small>Usually bank balances and other assets</small></span></label>
									<label class="check-card"><input v-model="form.side" type="radio" name="opening-side" value="Credit" required /><span><strong>Credit</strong><small>Usually amounts owed and fund balances</small></span></label>
								</div>
							</fieldset>
						</div>
					</fieldset>
					<fieldset v-if="partyRequired" class="form-step">
						<legend class="form-step__title"><span aria-hidden="true" class="step-num" :class="{ 'step-num--done': form.party_type && form.party }">2</span>Party</legend>
						<div class="form-step__grid">
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
						</div>
					</fieldset>
					<fieldset class="form-step">
						<legend class="form-step__title"><span aria-hidden="true" class="step-num" :class="{ 'step-num--done': form.source_reference }">{{ partyRequired ? 3 : 2 }}</span>Evidence</legend>
						<label class="field-label"
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
						<div class="mt-4">
							<label class="field-label" for="opening-proof">Proof documents (optional)</label>
							<p class="field-help">Attach up to three files, 5 MB each. PDF, PNG, JPEG, DOCX, XLSX or CSV. They are stored privately with the opening entry.</p>
							<input id="opening-proof" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx,.csv" class="mt-2 block w-full" :disabled="saving" @change="chooseProof" />
							<ul v-if="proofFiles.length" class="mt-3 grid gap-2">
								<li v-for="(file, index) in proofFiles" :key="`${file.name}-${index}`" class="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line px-3 py-2 text-sm [overflow-wrap:anywhere]">
									<span>{{ file.name }} <small class="text-muted">({{ (file.size / 1024 / 1024).toFixed(2) }} MB)</small></span>
									<button type="button" class="link-arrow" :disabled="saving" :aria-label="`Remove ${file.name}`" @click="removeProof(index)">Remove</button>
								</li>
							</ul>
						</div>
					</fieldset>
					<div class="form-step__foot">
						<label class="flex min-w-0 flex-1 basis-72 cursor-pointer items-start gap-2.5 text-[13px] leading-relaxed text-ink"><input v-model="confirmed" type="checkbox" required class="mt-0.5" /><span>I checked the amount and date against the source record. I understand posting changes the ledger.</span></label>
						<button type="submit" class="btn-primary" :disabled="saving">
							{{ saving ? "Posting…" : "Post opening balance" }}
						</button>
					</div>
				</form>

				<aside class="form-rail min-w-0 space-y-4">
					<div class="summary-card">
						<p class="eyebrow">Posting preview</p>
						<div v-if="selectedAccount && Number(form.amount) > 0" class="posting-preview mt-3" aria-live="polite">
							<p class="text-xs text-muted">This is the entry that will be created</p>
							<div class="preview-row"><span class="pill pill--info">{{ form.side }}</span><span>{{ selectedAccount.account_name }}</span><strong>{{ money(form.amount) }}</strong></div>
							<div class="preview-row"><span class="pill pill--muted">{{ form.side === "Debit" ? "Credit" : "Debit" }}</span><span>Temporary Opening</span><strong>{{ money(form.amount) }}</strong></div>
						</div>
						<p v-else class="mt-2 text-sm text-muted">Choose a ledger and enter an amount to see the two lines that will be posted.</p>
					</div>
					<div class="rounded-2xl bg-accent-soft p-4 text-sm leading-relaxed text-muted">
						<strong class="block text-ink">Begin with the opening position</strong>
						Enter April–September transactions separately with their actual dates. Do not include them in these starting amounts.
						<details class="mt-3 border-t border-line pt-3"><summary class="cursor-pointer font-semibold text-navy-900">What is Temporary Opening?</summary><p class="mt-2">It balances each provisional starting amount and should reach zero once all verified opening balances are entered. It is not a donation or fund balance.</p></details>
					</div>
				</aside>
			</div>

			<section class="kit-panel overflow-hidden" aria-labelledby="opening-history-title">
				<header class="border-b border-line px-5 py-4 sm:px-6">
					<h2 id="opening-history-title" class="font-display text-base font-semibold text-ink">Opening amounts recorded here</h2>
					<p class="mt-1 text-sm text-muted">
						To correct a submitted amount, make a traceable accounting correction; do not
						enter it a second time.
					</p>
				</header>
				<p v-if="!workspace.history.length" class="px-5 py-8 text-center text-sm text-muted">
					No opening amounts have been entered through Home yet.
				</p>
				<div
					v-for="entry in workspace.history"
					:key="entry.name"
					class="history-row"
				>
					<div class="min-w-0">
						<strong class="block truncate text-sm text-ink">{{ entry.rows?.[0]?.account || entry.name }}</strong>
						<p v-if="entry.rows?.[0]?.party" class="truncate text-xs text-muted">
							{{ entry.rows[0].party_type }} · {{ entry.rows[0].party }}
						</p>
						<p class="text-xs text-muted">{{ dateLabel(entry.posting_date) }} · {{ entry.name }}</p>
						<div v-if="entry.attachments?.length" class="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs">
							<span class="text-muted">Proof documents</span>
							<a v-for="file in entry.attachments" :key="file.file_url" :href="file.file_url" target="_blank" rel="noopener noreferrer" class="text-navy-900 underline [overflow-wrap:anywhere]">{{ file.file_name }}</a>
						</div>
					</div>
					<p class="shrink-0 text-right text-sm">
						<span :class="pillClass(entry.rows?.[0]?.debit_in_account_currency ? 'info' : 'muted')">{{ entry.rows?.[0]?.debit_in_account_currency ? "Debit" : "Credit" }}</span>
						<strong class="mt-1 block tabular-nums text-ink">{{
							money(
								entry.rows?.[0]?.debit_in_account_currency ||
									entry.rows?.[0]?.credit_in_account_currency ||
									0,
							)
						}}</strong>
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
import StatTile from "../components/StatTile.vue";
import { pillClass } from "../lib/tones.js";
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
const proofFiles = ref([]);
const MAX_PROOF_FILES = 3;
const MAX_PROOF_BYTES = 5 * 1024 * 1024;
const PROOF_TYPES = /\.(pdf|png|jpe?g|docx|xlsx|csv)$/i;
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
function chooseProof(event) {
	const files = Array.from(event.target.files || []);
	event.target.value = "";
	if (!files.length) return;
	if (proofFiles.value.length + files.length > MAX_PROOF_FILES) {
		error.value = "Attach no more than three proof documents.";
		return;
	}
	if (files.some((file) => !PROOF_TYPES.test(file.name) || !file.size || file.size > MAX_PROOF_BYTES)) {
		error.value = "Choose PDF, PNG, JPEG, DOCX, XLSX or CSV files, each no larger than 5 MB.";
		return;
	}
	error.value = "";
	proofFiles.value = [...proofFiles.value, ...files];
}
function removeProof(index) {
	proofFiles.value = proofFiles.value.filter((_, fileIndex) => fileIndex !== index);
}
function readProof(file) {
	return new Promise((resolve, reject) => {
		const reader = new FileReader();
		reader.onload = () => resolve(String(reader.result || "").split(",")[1] || "");
		reader.onerror = () => reject(new Error(`Could not read ${file.name}.`));
		reader.readAsDataURL(file);
	});
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
		const attachments = await Promise.all(proofFiles.value.map(async (file) => ({
			file_name: file.name,
			content: await readProof(file),
		})));
		const result = await call(api + "record_opening_balance", { details: { ...form, attachments } });
		workspace.value = result.workspace;
		message.value = `Opening balance posted as ${result.journal_entry}.`;
		form.account = "";
		form.amount = "";
		form.party_type = "";
		form.party = "";
		form.source_reference = "";
		proofFiles.value = [];
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
.posting-preview { display: grid; gap: 0.5rem; }
.preview-row { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 0.625rem; border-radius: 12px; background: var(--soft); padding: 0.625rem 0.75rem; font-size: 0.8125rem; }
.preview-row span:nth-child(2) { overflow-wrap: anywhere; color: var(--ink); }
.preview-row strong { white-space: nowrap; font-variant-numeric: tabular-nums; color: var(--ink); }
.history-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; padding: 0.875rem 1.25rem; }
@media (min-width: 640px) { .history-row { padding: 0.875rem 1.5rem; } }
.history-row + .history-row { border-top: 1px solid var(--line); }
</style>
