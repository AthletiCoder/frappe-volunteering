<template>
	<div>
		<PageHeader
			eyebrow="Money"
			title="Advances"
			subtitle="Request funds for an approved project, then submit bills or return the unused balance."
		>
			<template #actions>
				<button v-if="!showForm" class="btn-primary" type="button" @click="startNew">
					Request an advance
				</button>
				<button class="btn-secondary" type="button" :disabled="loading" @click="loadAll">
					{{ loading ? "Loading…" : "Refresh" }}
				</button>
			</template>
		</PageHeader>

		<p v-if="error" class="message-error" role="alert">{{ error }}</p>
		<section v-if="result" class="message-success mb-5" role="status">
			<p class="font-semibold">Advance {{ result.name }} saved.</p>
			<p class="text-sm mt-1">
				{{
					result.submitted
						? `It is now ${result.workflow_state || "pending approval"}.`
						: "It remains a draft and has not been sent for approval."
				}}
			</p>
		</section>

		<section v-if="showForm" class="space-y-5 mb-8">
			<div class="form-card">
				<div class="flex flex-wrap items-start justify-between gap-3">
					<div>
						<h2 class="text-xl font-semibold text-ink">
							{{ form.name ? `Edit ${form.name}` : "Request an advance" }}
						</h2>
						<p class="text-sm text-muted mt-1">
							Series, employee, company, accounts and approval routing are assigned
							automatically.
						</p>
					</div>
					<button type="button" class="btn-secondary" @click="closeForm">Close</button>
				</div>
			</div>

			<div v-if="defaults.freeze?.frozen" class="message-error">
				<p class="font-semibold">New advance requests are frozen.</p>
				<p class="text-sm mt-1">{{ defaults.freeze.reason }}</p>
			</div>
			<div v-else-if="!defaults.projects.length" class="message-error">
				<p class="font-semibold">You are not currently eligible to request an advance.</p>
				<p class="text-sm mt-1">
					You must be the owner or a listed member of at least one active, approved
					Project.
				</p>
			</div>
			<div v-else-if="!defaults.approved_bank" class="message-error">
				<p class="font-semibold">An approved reimbursement bank account is required.</p>
				<p class="text-sm mt-1">
					<RouterLink class="underline" to="/bank-account"
						>Submit bank details</RouterLink
					>
					and wait for Accounts Manager approval before requesting an advance.
				</p>
			</div>

			<form class="space-y-5" @submit.prevent="save(true)">
				<section class="form-card">
					<h3 class="form-title">Request details</h3>
					<div class="grid gap-4 sm:grid-cols-2 mt-4">
						<SearchSelect
							v-model="form.intended_project"
							:options="defaults.projects"
							label="Intended project *"
							placeholder="Type to find one of your active projects"
							empty-text="No matching active project. You can request an advance only for an approved project that lists you as owner or member."
							selection-error="Choose an eligible project from the suggestions."
							required
						/>
						<label class="field-label">
							Amount ({{ defaults.currency }}) *
							<input
								v-model.number="form.amount"
								type="number"
								min="0.01"
								step="0.01"
								required
								class="field-input"
							/>
							<span class="field-hint"
								>You may request any amount. Approval authority depends on your
								total outstanding advances when the reviewer acts.</span
							>
						</label>
						<label class="field-label">
							Required by *
							<input
								v-model="form.required_by_date"
								type="date"
								:min="defaults.today"
								required
								class="field-input"
							/>
						</label>
						<label class="field-label">
							Expected settlement date *
							<input
								v-model="form.expected_settlement_date"
								type="date"
								:min="form.required_by_date || defaults.today"
								required
								class="field-input"
							/>
						</label>
					</div>
					<label class="field-label mt-4">
						Purpose *
						<textarea
							v-model.trim="form.purpose"
							rows="3"
							maxlength="500"
							required
							class="field-input"
							placeholder="What will the money be used for?"
						></textarea>
					</label>
				</section>

				<section class="form-card">
					<h3 class="form-title">Who will use the advance?</h3>
					<div class="grid gap-3 sm:grid-cols-2 mt-4">
						<label
							class="choice-card"
							:class="{
								selected: form.advance_use === 'My expenses',
							}"
						>
							<input v-model="form.advance_use" type="radio" value="My expenses" />
							<span
								><strong>My expenses</strong
								><small>I will submit the bills myself.</small></span
							>
						</label>
						<label
							class="choice-card"
							:class="{
								selected: form.advance_use === 'Team expenses',
								disabled: !defaults.has_direct_reports,
							}"
						>
							<input
								v-model="form.advance_use"
								type="radio"
								value="Team expenses"
								:disabled="!defaults.has_direct_reports"
							/>
							<span
								><strong>Team expenses</strong
								><small
									>Direct reports may submit eligible bills against my
									advance.</small
								></span
							>
						</label>
					</div>
				</section>

				<section class="form-card">
					<h3 class="form-title">Payment and support</h3>
					<div
						v-if="defaults.approved_bank"
						class="rounded-xl border border-line bg-soft p-3 text-sm mt-4"
					>
						<p class="font-medium text-ink">Approved reimbursement account</p>
						<p class="text-muted mt-1">
							{{ defaults.approved_bank.bank_name }} ·
							{{ defaults.approved_bank.account_number_masked }} ·
							{{ defaults.approved_bank.ifsc }}
						</p>
					</div>
					<div class="grid gap-4 sm:grid-cols-2 mt-4">
						<label class="field-label">
							Estimate / quotation (optional)
							<input
								type="file"
								accept=".pdf,.png,.jpg,.jpeg"
								class="field-input"
								:disabled="readingFile || saving"
								@change="chooseSupport"
							/>
							<span class="field-hint">PDF, PNG or JPEG; maximum 5 MB.</span>
						</label>
						<label class="field-label">
							Additional note (optional)
							<textarea
								v-model.trim="form.additional_note"
								rows="3"
								maxlength="1000"
								class="field-input"
							></textarea>
						</label>
					</div>
					<p v-if="form.support_filename" class="text-xs text-muted mt-2">
						Ready to upload privately: {{ form.support_filename }}
					</p>
				</section>

				<section class="form-card flex flex-wrap justify-between gap-3 items-center">
					<div class="text-sm text-muted">
						<p>
							Reporting manager:
							{{
								defaults.approver?.name ||
								defaults.approver?.user ||
								"Not configured"
							}}
						</p>
						<p>
							Every request starts with your reporting manager. Each reviewer
							escalates to the next person when the live total of this request and
							your other outstanding advances exceeds their approval authority; no
							linked approver is skipped.
						</p>
						<p v-if="defaults.open_advances.length">
							You have
							{{ defaults.open_advances.length }} advance(s) with an open balance.
							You can submit another request; each balance remains tracked until
							settled.
						</p>
					</div>
					<div class="flex flex-wrap gap-2">
						<button
							type="button"
							class="btn-secondary"
							:disabled="!canSave || saving || readingFile"
							@click="save(false)"
						>
							Save draft
						</button>
						<button
							type="submit"
							class="btn-primary"
							:disabled="!canSave || saving || readingFile"
						>
							{{ saving ? "Saving…" : "Submit for approval" }}
						</button>
					</div>
				</section>
			</form>
		</section>

		<ManagerFloatPanel />
		<TeamFloatRequests />

		<h2 class="text-lg font-semibold text-ink mb-3 mt-7">My advances</h2>
		<div
			v-for="adv in advances"
			:key="adv.name"
			:id="`advance-${adv.name}`"
			class="rounded-2xl border border-line bg-surface shadow-soft p-4 mb-4"
		>
			<div class="flex justify-between gap-3 flex-wrap">
				<div>
					<p class="font-semibold text-ink">{{ adv.name }}</p>
					<div class="text-sm text-muted">
						{{ adv.purpose || "—" }} ·
						{{ adv.workflow_state || adv.status }}
					</div>
					<div v-if="adv.intended_project" class="text-xs text-muted mt-1">
						Project: {{ adv.intended_project }}
					</div>
				</div>
				<span
					class="px-2 py-0.5 rounded-full text-xs font-semibold h-fit"
					:class="residualClass(adv.residual_pct)"
				>
					Residual {{ Math.round(adv.residual_pct || 0) }}%
				</span>
			</div>

			<div class="grid grid-cols-2 md:grid-cols-5 gap-2 mt-3">
				<div v-for="stat in stats(adv)" :key="stat.label" class="rounded-xl bg-soft p-2">
					<div class="text-xs text-muted">{{ stat.label }}</div>
					<div class="font-semibold text-ink">{{ stat.value }}</div>
				</div>
			</div>
			<p
				v-if="adv.required_by_date || adv.expected_settlement_date"
				class="text-xs text-muted mt-3"
			>
				Required by: {{ adv.required_by_date || "—" }} · Expected settlement:
				{{ adv.expected_settlement_date || "—" }}
			</p>
			<p v-if="adv.advance_additional_note" class="text-sm text-muted mt-2">
				{{ adv.advance_additional_note }}
			</p>
			<a
				v-if="adv.advance_supporting_document"
				:href="adv.advance_supporting_document"
				class="text-sm text-accent underline mt-2 inline-block"
				target="_blank"
				rel="noopener"
				>View estimate / quotation</a
			>

			<details class="mt-3">
				<summary class="cursor-pointer text-sm font-medium text-ink">
					Linked expense claims
				</summary>
				<div v-if="!(adv.expense_claims || []).length" class="text-sm text-muted mt-2">
					No claims linked yet.
				</div>
				<div
					v-for="claim in adv.expense_claims || []"
					:key="claim.name"
					class="text-sm mt-2"
				>
					<a class="text-accent hover:underline" :href="claim.route">{{ claim.name }}</a>
					<span class="text-muted">
						· {{ formatMoney(claim.allocated_amount) }} · {{ claim.status }}</span
					>
				</div>
			</details>

			<div class="mt-3 flex flex-wrap gap-2">
				<RouterLink
					v-if="Number(adv.paid_amount || 0) > 0 && Number(adv.residual || 0) > 0"
					class="btn-primary text-sm"
					:to="`/expense-claim?reimbursement_source=OWN_ADVANCE&employee_advance=${encodeURIComponent(adv.name)}`"
					>Submit bills</RouterLink
				>
				<button
					v-if="
						adv.docstatus === 0 &&
						['Draft', 'Rejected', '', null].includes(adv.workflow_state)
					"
					type="button"
					class="btn-secondary text-sm"
					@click="editAdvance(adv.name)"
				>
					Edit draft
				</button>
			</div>
			<p
				v-if="Number(adv.paid_amount || 0) > 0 && Number(adv.residual || 0) > 0"
				class="text-xs text-muted mt-3"
			>
				If you will not use the remaining amount, arrange its return with Accounts.
				Accounts will confirm receipt and record it here; your Returned and Residual totals
				will then update.
			</p>
		</div>

		<div v-if="!advances.length && !loading" class="text-center text-muted py-10">
			No advances yet.
		</div>
	</div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { call } from "../lib/frappe";
import { formatMoney } from "../lib/money";
import PageHeader from "../components/PageHeader.vue";
import SearchSelect from "../components/SearchSelect.vue";
import ManagerFloatPanel from "../components/ManagerFloatPanel.vue";
import TeamFloatRequests from "../components/TeamFloatRequests.vue";

const API = "volunteering.volunteering.advance_portal.";
const route = useRoute();
const router = useRouter();
const advances = ref([]);
const defaults = ref({
	projects: [],
	approved_bank: null,
	freeze: { frozen: false },
	open_advances: [],
	approver: {},
	currency: "INR",
	today: "",
	has_direct_reports: false,
});
const showForm = ref(false);
const loading = ref(false);
const saving = ref(false);
const readingFile = ref(false);
const error = ref("");
const result = ref(null);
const blankForm = () => ({
	name: "",
	intended_project: "",
	amount: null,
	purpose: "",
	required_by_date: defaults.value.today || "",
	expected_settlement_date: defaults.value.today || "",
	advance_use: "My expenses",
	additional_note: "",
	support_filename: "",
	support_content: "",
});
const form = reactive(blankForm());
const canSave = computed(
	() =>
		!defaults.value.freeze?.frozen &&
		defaults.value.projects.length > 0 &&
		Boolean(defaults.value.approved_bank),
);

function resetForm() {
	Object.assign(form, blankForm());
	if (defaults.value.projects.length === 1)
		form.intended_project = defaults.value.projects[0].value;
}

function startNew() {
	result.value = null;
	resetForm();
	showForm.value = true;
	router.replace({ path: "/advances", query: { new: "1" } });
	window.scrollTo({ top: 0, behavior: "smooth" });
}

function closeForm() {
	showForm.value = false;
	error.value = "";
	router.replace({ path: "/advances" });
}

function residualClass(pct) {
	if ((pct || 0) > 10) return "bg-bad-soft text-bad";
	if ((pct || 0) > 0) return "bg-warn-soft text-warn";
	return "bg-ok-soft text-ok";
}

function stats(adv) {
	return [
		{ label: "Requested", value: formatMoney(adv.advance_amount) },
		{ label: "Paid", value: formatMoney(adv.paid_amount) },
		{ label: "Claimed", value: formatMoney(adv.claimed_amount) },
		{ label: "Returned", value: formatMoney(adv.return_amount) },
		{ label: "Residual", value: formatMoney(adv.residual) },
	];
}

async function chooseSupport(event) {
	const file = event.target.files?.[0];
	form.support_filename = "";
	form.support_content = "";
	if (!file) return;
	if (file.size > 5 * 1024 * 1024) {
		error.value = "The supporting document must be 5 MB or smaller.";
		event.target.value = "";
		return;
	}
	readingFile.value = true;
	try {
		form.support_filename = file.name;
		form.support_content = await new Promise((resolve, reject) => {
			const reader = new FileReader();
			reader.onload = () => resolve(String(reader.result || "").split(",")[1] || "");
			reader.onerror = reject;
			reader.readAsDataURL(file);
		});
	} catch (_) {
		error.value = "The selected supporting document could not be read.";
	} finally {
		readingFile.value = false;
	}
}

async function save(submitRequest) {
	if (!canSave.value || saving.value) return;
	saving.value = true;
	error.value = "";
	result.value = null;
	try {
		result.value = await call(`${API}save_advance_request`, {
			payload: { ...form },
			submit_request: submitRequest ? 1 : 0,
		});
		showForm.value = false;
		await router.replace({ path: "/advances" });
		await loadAll(false);
		window.scrollTo({ top: 0, behavior: "smooth" });
	} catch (e) {
		error.value = e.message || String(e);
		window.scrollTo({ top: 0, behavior: "smooth" });
	} finally {
		saving.value = false;
	}
}

async function editAdvance(name) {
	error.value = "";
	try {
		const data = await call(`${API}get_advance_detail`, { name });
		if (
			data.docstatus !== 0 ||
			!["Draft", "Rejected", "", null].includes(data.workflow_state)
		) {
			showForm.value = false;
			await nextTick();
			document
				.getElementById(`advance-${name}`)
				?.scrollIntoView({ behavior: "smooth", block: "start" });
			return;
		}
		Object.assign(form, {
			name: data.name,
			intended_project: data.intended_project || "",
			amount: data.advance_amount,
			purpose: data.purpose || "",
			required_by_date: data.required_by_date || defaults.value.today,
			expected_settlement_date: data.expected_settlement_date || defaults.value.today,
			advance_use: data.advance_use || "My expenses",
			additional_note: data.advance_additional_note || "",
			support_filename: "",
			support_content: "",
		});
		showForm.value = true;
		window.scrollTo({ top: 0, behavior: "smooth" });
	} catch (e) {
		error.value = e.message || String(e);
	}
}

async function loadAll(setLoading = true) {
	if (setLoading) loading.value = true;
	error.value = "";
	try {
		const [formData, listData] = await Promise.all([
			call(`${API}get_advance_request_form`),
			call(`${API}get_my_advances`),
		]);
		defaults.value = formData;
		advances.value = listData?.advances || [];
		if (route.query.new === "1" && !showForm.value) {
			resetForm();
			showForm.value = true;
		}
		if (route.params.name) await editAdvance(route.params.name);
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		loading.value = false;
	}
}

onMounted(loadAll);
</script>

<style scoped>
.form-card {
	@apply rounded-2xl border border-line bg-surface p-4 sm:p-5 shadow-soft;
}
.form-title {
	@apply text-lg font-semibold text-ink;
}
.field-label {
	@apply block text-sm font-medium text-ink;
}
.field-input {
	@apply mt-1 block w-full rounded-xl border border-line bg-surface px-3 py-2.5 text-sm text-ink;
}
.field-hint {
	@apply mt-1 block text-xs text-muted;
}
.field-input:focus-visible {
	outline: 2px solid var(--accent);
	outline-offset: 2px;
}
.choice-card {
	@apply flex cursor-pointer gap-3 rounded-xl border border-line bg-surface p-4;
}
.choice-card.selected {
	background: var(--accent-soft);
	border-color: var(--accent);
}
.choice-card.disabled {
	@apply cursor-not-allowed opacity-50;
}
.choice-card strong,
.choice-card small {
	@apply block;
}
.choice-card small {
	@apply mt-1 text-sm text-muted;
}
.message-error,
.message-success {
	@apply rounded-xl p-4;
}
.message-error {
	@apply bg-bad-soft text-bad mb-5;
}
.message-success {
	@apply bg-ok-soft text-ok;
}
</style>
