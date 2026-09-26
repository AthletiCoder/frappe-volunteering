<template>
	<div class="max-w-5xl mx-auto space-y-5">
		<PageHeader
			title="Chart of Accounts"
			eyebrow="Accounts"
			subtitle="Organise Sevamrita's accounting groups and ledgers without exposing balances to employees."
		>
			<template #actions>
				<button
					v-if="authorized && !showForm"
					type="button"
					class="btn-primary"
					@click="startNew()"
				>
					Add account
				</button>
				<RouterLink to="/home" class="btn-secondary">Back to Home</RouterLink>
			</template>
		</PageHeader>

		<p v-if="error" class="message-error" role="alert">{{ error }}</p>
		<p v-if="message" class="message-success" role="status">{{ message }}</p>
		<p v-if="loading" class="text-muted">Loading Chart of Accounts…</p>

		<template v-else-if="authorized">
			<section class="rounded-2xl border border-line bg-warn-soft p-4 text-sm text-ink">
				<strong
					>Groups organise the chart; ledger accounts receive accounting entries.</strong
				>
				Renaming keeps an account’s history. To split a used account, create the new
				ledgers and disable the old one after Accounts has completed the accounting
				transition.
			</section>

			<section v-if="showForm" class="form-card" aria-labelledby="account-form-heading">
				<div class="flex flex-wrap items-start justify-between gap-3 mb-5">
					<div>
						<h2 id="account-form-heading" class="form-title mb-0">
							{{ formHeading }}
						</h2>
						<p class="form-hint mb-0">
							{{
								form.name ||
								"The account will inherit its root and report type from its parent."
							}}
						</p>
					</div>
					<button
						type="button"
						class="btn-secondary"
						:disabled="saving"
						@click="closeForm"
					>
						Back to chart
					</button>
				</div>

				<div v-if="form.is_root" class="space-y-4">
					<div class="rounded-xl bg-soft p-4 text-sm">
						<p><strong>Root type:</strong> {{ form.root_type }}</p>
						<p><strong>Report:</strong> {{ form.report_type }}</p>
						<p class="text-muted mt-2">
							ERPNext protects root accounts from editing or deletion.
						</p>
					</div>
					<button type="button" class="btn-primary" @click="startNew(form.name)">
						Add child account
					</button>
				</div>

				<form v-else class="space-y-5" @submit.prevent="save">
					<div class="form-grid">
						<label class="field-label sm:col-span-2">
							Account name *
							<input
								v-model.trim="form.account_name"
								required
								maxlength="140"
								class="field-input"
							/>
						</label>
						<label class="field-label">
							Account number
							<input
								v-model.trim="form.account_number"
								maxlength="140"
								class="field-input"
							/>
							<span class="field-help"
								>Optional, but must be unique within Sevamrita.</span
							>
						</label>
						<SearchSelect
							v-model="form.parent_account"
							label="Parent group"
							placeholder="Type to find a parent group"
							empty-text="No matching group is available in Sevamrita's Chart of Accounts."
							selection-error="Choose a parent group from the suggestions."
							:required="true"
							:disabled="saving"
							:options="parentOptions"
						/>
					</div>

					<fieldset class="rounded-xl border border-line p-4">
						<legend class="px-2 font-semibold">Account kind</legend>
						<div class="option-grid">
							<label :class="['choice-card', form.is_group && 'choice-card-active']">
								<input
									v-model="form.is_group"
									type="radio"
									:value="true"
									:disabled="Boolean(form.name)"
								/>
								<span
									><strong>Group</strong
									><small
										>Contains child groups or ledgers; receives no
										postings.</small
									></span
								>
							</label>
							<label
								:class="['choice-card', !form.is_group && 'choice-card-active']"
							>
								<input
									v-model="form.is_group"
									type="radio"
									:value="false"
									:disabled="Boolean(form.name)"
								/>
								<span
									><strong>Ledger</strong
									><small
										>Receives transactions and can be mapped to project
										labels.</small
									></span
								>
							</label>
						</div>
						<p v-if="form.name" class="field-help mt-3">
							The kind of an existing account is fixed here to protect its children
							and postings.
						</p>
					</fieldset>

					<div v-if="!form.is_group" class="form-grid">
						<label class="field-label">
							Account type
							<select v-model="form.account_type" class="field-input">
								<option value="">General ledger</option>
								<option
									v-for="type in workspace.account_types"
									:key="type"
									:value="type"
								>
									{{ type }}
								</option>
							</select>
							<span class="field-help"
								>Helps ERPNext select the account for the correct
								transactions.</span
							>
						</label>
						<label class="field-label">
							Currency
							<select v-model="form.account_currency" class="field-input">
								<option value="">
									Company currency ({{ workspace.company_currency }})
								</option>
								<option
									v-for="currency in workspace.currencies"
									:key="currency"
									:value="currency"
								>
									{{ currency }}
								</option>
							</select>
						</label>
						<label class="field-label">
							Balance restriction
							<select v-model="form.balance_must_be" class="field-input">
								<option value="">No restriction</option>
								<option value="Debit">Must remain Debit</option>
								<option value="Credit">Must remain Credit</option>
							</select>
						</label>
						<label v-if="form.account_type === 'Tax'" class="field-label">
							Tax rate (%)
							<input
								v-model.number="form.tax_rate"
								type="number"
								step="0.01"
								class="field-input"
							/>
						</label>
						<label
							v-if="['Income', 'Expense'].includes(form.root_type)"
							class="flex items-start gap-2 text-sm sm:col-span-2"
						>
							<input v-model="form.include_in_gross" type="checkbox" class="mt-1" />
							<span
								><strong class="block">Include in gross profit</strong
								><span class="text-muted"
									>Use only when this ledger belongs in gross-profit
									reporting.</span
								></span
							>
						</label>
					</div>

					<label class="flex items-start gap-2 text-sm">
						<input v-model="form.disabled" type="checkbox" class="mt-1" />
						<span
							><strong class="block">Disabled</strong
							><span class="text-muted"
								>Keep its history, but prevent new accounting entries.</span
							></span
						>
					</label>

					<div class="flex flex-wrap justify-between gap-3">
						<button
							v-if="form.name"
							type="button"
							class="btn-secondary text-bad"
							:disabled="saving"
							@click="remove"
						>
							Remove unused account
						</button>
						<span v-else></span>
						<div class="flex flex-wrap gap-2">
							<button
								v-if="form.name && form.is_group"
								type="button"
								class="btn-secondary"
								:disabled="saving"
								@click="startNew(form.name)"
							>
								Add child
							</button>
							<button type="submit" class="btn-primary" :disabled="saving">
								{{
									saving
										? "Saving…"
										: form.name
											? "Save account"
											: "Create account"
								}}
							</button>
						</div>
					</div>
					<p v-if="form.name" class="field-help">
						Removal succeeds only for an account with no transactions, children or
						linked records.
					</p>
				</form>
			</section>

			<template v-else>
				<section class="form-card space-y-4">
					<div class="grid gap-3 md:grid-cols-[minmax(0,1fr)_12rem_12rem]">
						<label class="field-label">
							Find an account
							<input
								v-model.trim="search"
								class="field-input"
								placeholder="Name, number or type"
							/>
						</label>
						<label class="field-label">
							Root
							<select v-model="rootFilter" class="field-input">
								<option value="All">All roots</option>
								<option v-for="root in rootTypes" :key="root" :value="root">
									{{ root }}
								</option>
							</select>
						</label>
						<label class="field-label">
							Show
							<select v-model="kindFilter" class="field-input">
								<option value="All">Groups and ledgers</option>
								<option value="Groups">Groups only</option>
								<option value="Ledgers">Ledgers only</option>
								<option value="Disabled">Disabled only</option>
							</select>
						</label>
					</div>
					<p class="text-sm text-muted">
						{{ visibleAccounts.length }} of {{ workspace.accounts.length }} accounts
					</p>
				</section>

				<section v-if="!visibleAccounts.length" class="form-card text-center text-muted">
					No accounts match these filters.
				</section>
				<section v-for="group in groupedAccounts" :key="group.root" class="form-card">
					<div class="flex items-center justify-between gap-3 mb-3">
						<h2 class="form-title mb-0">{{ group.root }}</h2>
						<span class="text-sm text-muted">{{ group.rows.length }}</span>
					</div>
					<div class="account-list">
						<div
							v-for="account in group.rows"
							:key="account.name"
							class="account-row"
							:style="{ '--account-depth': Math.min(account.depth, 6) }"
							:data-account-name="account.name"
							:data-parent-account="account.parent_account"
							:data-account-depth="account.depth"
						>
							<button
								v-if="account.is_group && account.has_children"
								type="button"
								class="account-toggle"
								:aria-label="`${isExpanded(account) ? 'Collapse' : 'Expand'} ${account.account_name}`"
								:aria-expanded="isExpanded(account)"
								@click="toggleAccount(account)"
							>
								<svg
									aria-hidden="true"
									viewBox="0 0 20 20"
									:class="[
										'account-chevron',
										isExpanded(account) && 'account-chevron-open',
									]"
								>
									<path d="m7 4 6 6-6 6" />
								</svg>
							</button>
							<span v-else class="account-leaf" aria-hidden="true">•</span>
							<button
								type="button"
								class="account-open"
								@click="openAccount(account)"
							>
								<span class="account-name">
									<span>
										<strong
											>{{
												account.account_number
													? `${account.account_number} · `
													: ""
											}}{{ account.account_name }}</strong
										>
										<small
											>{{
												account.is_group
													? "Group"
													: account.account_type || "Ledger"
											}}
											· {{ account.name }}</small
										>
									</span>
								</span>
								<span
									:class="['status-pill', account.disabled && 'status-disabled']"
									>{{ account.disabled ? "Disabled" : "Active" }}</span
								>
							</button>
						</div>
					</div>
				</section>
			</template>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import SearchSelect from "../components/SearchSelect.vue";
import { call } from "../lib/frappe";

const service = "volunteering.volunteering.chart_of_accounts_portal.";
const workspace = reactive({
	company: "",
	company_currency: "INR",
	accounts: [],
	parent_accounts: [],
	account_types: [],
	currencies: [],
});
const loading = ref(true);
const saving = ref(false);
const authorized = ref(false);
const showForm = ref(false);
const search = ref("");
const rootFilter = ref("All");
const kindFilter = ref("All");
const error = ref("");
const message = ref("");
const expandedAccounts = ref(new Set());

const blankForm = () => ({
	name: "",
	modified: "",
	account_name: "",
	account_number: "",
	parent_account: "",
	is_group: false,
	is_root: false,
	root_type: "",
	report_type: "",
	account_type: "",
	account_currency: "",
	disabled: false,
	tax_rate: 0,
	balance_must_be: "",
	include_in_gross: false,
});
const form = reactive(blankForm());

function setWorkspace(data) {
	Object.assign(workspace, data || {});
}
function resetForm(values = {}) {
	Object.assign(form, blankForm(), values, {
		is_group: Boolean(values.is_group),
		is_root: Boolean(values.is_root),
		disabled: Boolean(values.disabled),
		include_in_gross: Boolean(values.include_in_gross),
	});
}
function parentRoot(parent) {
	return workspace.parent_accounts.find((row) => row.name === parent)?.root_type || "";
}
function startNew(parent = "") {
	error.value = "";
	message.value = "";
	resetForm({
		parent_account: parent,
		root_type: parentRoot(parent),
		account_currency: workspace.company_currency,
	});
	showForm.value = true;
	window.scrollTo({ top: 0, behavior: "smooth" });
}
function openAccount(account) {
	error.value = "";
	message.value = "";
	resetForm(account);
	showForm.value = true;
	window.scrollTo({ top: 0, behavior: "smooth" });
}
function closeForm() {
	showForm.value = false;
	expandedAccounts.value = new Set();
	resetForm();
	error.value = "";
}
function toggleAccount(account) {
	if (!account.is_group || !account.has_children) return;
	const expanded = new Set(expandedAccounts.value);
	if (expanded.has(account.name)) expanded.delete(account.name);
	else expanded.add(account.name);
	expandedAccounts.value = expanded;
}
function isExpanded(account) {
	return expandedAccounts.value.has(account.name);
}

const formHeading = computed(() =>
	form.is_root ? form.account_name : form.name ? `Edit ${form.account_name}` : "Add account",
);
const parentOptions = computed(() =>
	workspace.parent_accounts
		.filter((row) => row.name !== form.name)
		.map((row) => ({
			value: row.name,
			label: row.label,
			description: `${row.root_type}${row.disabled ? " · Disabled" : ""}`,
		})),
);
const rootTypes = computed(() => [
	...new Set(workspace.accounts.map((row) => row.root_type).filter(Boolean)),
]);
function matchesFilters(row) {
	const query = search.value.toLowerCase();
	if (rootFilter.value !== "All" && row.root_type !== rootFilter.value) return false;
	if (kindFilter.value === "Groups" && !row.is_group) return false;
	if (kindFilter.value === "Ledgers" && row.is_group) return false;
	if (kindFilter.value === "Disabled" && !row.disabled) return false;
	return (
		!query ||
		[row.account_name, row.account_number, row.name, row.account_type].some((value) =>
			String(value || "")
				.toLowerCase()
				.includes(query),
		)
	);
}
const filterTree = computed(() => Boolean(search.value || kindFilter.value !== "All"));
const matchedAccounts = computed(() => workspace.accounts.filter(matchesFilters));
const relevantAccountNames = computed(() => {
	if (!filterTree.value) return new Set(workspace.accounts.map((row) => row.name));
	const byName = new Map(workspace.accounts.map((row) => [row.name, row]));
	const relevant = new Set(matchedAccounts.value.map((row) => row.name));
	for (const row of matchedAccounts.value) {
		let parent = row.parent_account;
		while (parent && byName.has(parent)) {
			relevant.add(parent);
			parent = byName.get(parent).parent_account;
		}
	}
	return relevant;
});
const visibleAccounts = computed(() => {
	const byName = new Map(workspace.accounts.map((row) => [row.name, row]));
	return workspace.accounts.filter((row) => {
		if (rootFilter.value !== "All" && row.root_type !== rootFilter.value) return false;
		if (!relevantAccountNames.value.has(row.name)) return false;
		if (!filterTree.value && !matchesFilters(row)) return false;
		let parent = row.parent_account;
		while (parent && byName.has(parent)) {
			if (!expandedAccounts.value.has(parent)) return false;
			parent = byName.get(parent).parent_account;
		}
		return true;
	});
});
const groupedAccounts = computed(() =>
	rootTypes.value
		.map((root) => ({
			root,
			rows: visibleAccounts.value.filter((row) => row.root_type === root),
		}))
		.filter((group) => group.rows.length),
);

watch(
	() => form.parent_account,
	(parent) => {
		if (!form.is_root) form.root_type = parentRoot(parent);
	},
);
watch([search, rootFilter, kindFilter], () => {
	if (!filterTree.value) {
		expandedAccounts.value = new Set();
		return;
	}
	const byName = new Map(workspace.accounts.map((row) => [row.name, row]));
	const expanded = new Set();
	for (const row of matchedAccounts.value) {
		let parent = row.parent_account;
		while (parent && byName.has(parent)) {
			expanded.add(parent);
			parent = byName.get(parent).parent_account;
		}
	}
	expandedAccounts.value = expanded;
});

async function save() {
	saving.value = true;
	error.value = "";
	message.value = "";
	try {
		const data = await call(service + "save_account", {
			account: form.name || null,
			expected_modified: form.modified || null,
			details: {
				account_name: form.account_name,
				account_number: form.account_number,
				parent_account: form.parent_account,
				is_group: form.is_group ? 1 : 0,
				account_type: form.account_type,
				account_currency: form.account_currency,
				disabled: form.disabled ? 1 : 0,
				tax_rate: form.tax_rate || 0,
				balance_must_be: form.balance_must_be,
				include_in_gross: form.include_in_gross ? 1 : 0,
			},
		});
		setWorkspace(data);
		const saved = workspace.accounts.find((row) => row.name === data.saved_account);
		if (saved) resetForm(saved);
		message.value = "Chart of Accounts updated.";
	} catch (err) {
		error.value = err.message || "Unable to save this account.";
	} finally {
		saving.value = false;
	}
}
async function remove() {
	if (!form.name || saving.value) return;
	if (!window.confirm(`Remove ${form.account_name}? Only an unused account can be removed.`))
		return;
	saving.value = true;
	error.value = "";
	message.value = "";
	try {
		setWorkspace(
			await call(service + "delete_account", {
				account: form.name,
				expected_modified: form.modified,
			}),
		);
		showForm.value = false;
		resetForm();
		message.value = "Unused account removed from the Chart of Accounts.";
	} catch (err) {
		error.value = err.message || "This account cannot be removed.";
	} finally {
		saving.value = false;
	}
}

onMounted(async () => {
	try {
		setWorkspace(await call(service + "get_chart_of_accounts"));
		authorized.value = true;
	} catch (err) {
		error.value =
			err.message || "Only Accounts Managers and Administrator can access this page.";
	} finally {
		loading.value = false;
	}
});
</script>

<style scoped>
.form-card {
	@apply rounded-2xl border border-line bg-surface p-4 sm:p-5 shadow-soft;
}
.form-title {
	@apply text-lg font-semibold text-ink mb-3;
}
.form-hint {
	@apply text-sm text-muted mb-4;
}
.form-grid {
	@apply grid gap-3 sm:grid-cols-2;
}
.field-label {
	@apply block text-sm font-medium text-ink;
}
.field-input {
	@apply mt-1 w-full rounded-xl border border-line bg-bg px-3 py-2 text-ink font-normal;
}
.field-input:focus-visible {
	@apply outline-none ring-2 ring-accent border-accent;
}
.field-help {
	@apply block text-xs text-muted mt-1;
}
.message-error {
	@apply rounded-xl border border-bad bg-bad-soft p-3 text-sm text-bad;
}
.message-success {
	@apply rounded-xl border border-ok bg-ok-soft p-3 text-sm text-ink;
}
.choice-card {
	@apply flex cursor-pointer items-start gap-3 rounded-xl border border-line bg-bg p-3;
}
.choice-card-active {
	@apply border-accent bg-accent-soft;
}
.choice-card span,
.choice-card strong,
.choice-card small {
	@apply block min-w-0;
}
.choice-card small {
	@apply text-xs text-muted mt-0.5;
}
.option-grid {
	@apply grid gap-2 sm:grid-cols-2;
}
button:disabled {
	@apply cursor-not-allowed opacity-60;
}
.account-list {
	display: grid;
	gap: 0.4rem;
}
.account-row {
	display: flex;
	min-height: 3.5rem;
	width: 100%;
	align-items: center;
	justify-content: flex-start;
	gap: 0.75rem;
	border: 1px solid var(--line);
	border-radius: 0.75rem;
	background: var(--surface);
	padding: 0.65rem 0.75rem 0.65rem calc(0.75rem + var(--account-depth) * 1rem);
}
.account-row:hover {
	background: var(--accent-soft);
}
.account-toggle,
.account-leaf {
	display: inline-flex;
	height: 2rem;
	width: 2rem;
	flex: none;
	align-items: center;
	justify-content: center;
	border-radius: 0.5rem;
}
.account-toggle:hover,
.account-toggle:focus-visible {
	background: var(--surface);
	outline: 2px solid var(--accent);
	outline-offset: 1px;
}
.account-chevron {
	height: 1rem;
	width: 1rem;
	fill: none;
	stroke: currentColor;
	stroke-width: 2;
	stroke-linecap: round;
	stroke-linejoin: round;
	transition: transform 150ms ease;
}
.account-chevron-open {
	transform: rotate(90deg);
}
.account-leaf {
	font-size: 1rem;
}
.account-open {
	display: flex;
	min-width: 0;
	flex: 1;
	align-items: center;
	justify-content: space-between;
	gap: 0.75rem;
	border-radius: 0.5rem;
	padding: 0.15rem;
	text-align: left;
}
.account-open:focus-visible {
	outline: 2px solid var(--accent);
	outline-offset: 2px;
}
.account-name {
	display: flex;
	min-width: 0;
	align-items: flex-start;
	gap: 0.55rem;
}
.account-name strong,
.account-name small {
	display: block;
	overflow-wrap: anywhere;
}
.account-name small {
	margin-top: 0.15rem;
	color: var(--muted);
	font-size: 0.75rem;
}
.status-pill {
	flex: none;
	border-radius: 999px;
	background: var(--ok-soft);
	padding: 0.2rem 0.55rem;
	font-size: 0.75rem;
}
.status-disabled {
	background: var(--soft);
	color: var(--muted);
}
@media (max-width: 480px) {
	.account-row {
		padding-left: calc(0.65rem + min(var(--account-depth), 3) * 0.55rem);
	}
}
</style>
