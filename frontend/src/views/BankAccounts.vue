<template>
	<div class="max-w-5xl mx-auto space-y-5">
		<PageHeader
			title="Reimbursement bank account"
			subtitle="Submit your payment destination. It becomes usable only after Accounts Manager approval."
			eyebrow="Expenses"
		>
			<template #actions>
				<RouterLink to="/home" class="btn-secondary">Back to Home</RouterLink>
			</template>
		</PageHeader>

		<div v-if="loading" class="text-muted">Loading bank-account details…</div>
		<div
			v-if="error"
			class="rounded-xl border border-bad bg-bad-soft p-4 text-sm text-bad"
			role="alert"
		>
			{{ error }}
		</div>
		<template v-if="!loading">
			<section v-if="workspace.can_submit" class="form-card">
				<h2 class="form-title">Your approved reimbursement account</h2>
				<div v-if="workspace.approved" class="grid sm:grid-cols-3 gap-3 text-sm">
					<div>
						<span class="field-caption">Account holder</span
						><strong>{{ workspace.approved.account_holder_name }}</strong>
					</div>
					<div>
						<span class="field-caption">Bank</span
						><strong>{{ workspace.approved.bank_name }}</strong>
					</div>
					<div>
						<span class="field-caption">Account number</span
						><strong>{{ workspace.approved.account_number_masked }}</strong>
					</div>
					<div>
						<span class="field-caption">IFSC</span
						><strong>{{ workspace.approved.ifsc }}</strong>
					</div>
					<div>
						<span class="field-caption">Account type</span
						><strong>{{ workspace.approved.account_type }}</strong>
					</div>
					<div>
						<span class="field-caption">Approved on</span
						><strong>{{ formatDate(workspace.approved.reviewed_on) }}</strong>
					</div>
				</div>
				<div v-else class="rounded-xl bg-warn-soft p-3 text-sm text-ink">
					No approved account is available. Invoice generation and bank reimbursement
					will remain unavailable until an Accounts Manager approves one.
				</div>
			</section>

			<section v-if="workspace.can_submit" class="form-card">
				<h2 class="form-title">
					{{
						workspace.approved
							? "Request a bank-account change"
							: "Submit bank details"
					}}
				</h2>
				<p class="form-hint">
					Your currently approved account remains active while a replacement is being
					reviewed.
				</p>
				<form class="form-grid" @submit.prevent="submitRequest">
					<label class="field-label sm:col-span-2"
						>Account-holder name *<input
							v-model.trim="form.account_holder_name"
							required
							maxlength="160"
							autocomplete="name"
							class="field-input"
					/></label>
					<label class="field-label"
						>Bank name *<input
							v-model.trim="form.bank_name"
							required
							maxlength="100"
							autocomplete="organization"
							class="field-input"
					/></label>
					<label class="field-label"
						>Branch<input
							v-model.trim="form.branch"
							maxlength="140"
							class="field-input"
					/></label>
					<label class="field-label"
						>Account type *<select
							v-model="form.account_type"
							required
							class="field-input"
						>
							<option>Savings</option>
							<option>Current</option>
							<option>Salary</option>
							<option>Other</option>
						</select></label
					>
					<label class="field-label"
						>IFSC *<input
							v-model.trim="form.ifsc"
							required
							minlength="11"
							maxlength="11"
							class="field-input uppercase"
							placeholder="ABCD0123456"
					/></label>
					<label class="field-label"
						>Account number *<input
							v-model="form.account_number"
							required
							maxlength="30"
							autocomplete="off"
							class="field-input"
					/></label>
					<label class="field-label"
						>Re-enter account number *<input
							v-model="form.account_number_confirmation"
							required
							maxlength="30"
							autocomplete="off"
							class="field-input"
					/></label>
					<label class="field-label"
						>SWIFT, if applicable<input
							v-model.trim="form.swift"
							maxlength="11"
							class="field-input uppercase"
					/></label>
					<label class="field-label sm:col-span-2"
						>Cancelled cheque or bank proof *<input
							ref="proofInput"
							type="file"
							required
							:disabled="readingProof || saving"
							accept=".pdf,.png,.jpg,.jpeg"
							class="field-input"
							@change="chooseProof"
						/><span class="block text-xs text-muted mt-1"
							>PDF, PNG or JPEG, maximum 5 MB. Visible only to you and Accounts
							Managers.</span
						></label
					>
					<label class="sm:col-span-2 flex items-start gap-2 text-sm"
						><input
							v-model="form.ownership_confirmed"
							type="checkbox"
							required
							class="mt-1"
						/>I confirm this account belongs to me and the bank proof shows the correct
						account details.</label
					>
					<div class="sm:col-span-2 flex justify-end">
						<button
							type="submit"
							class="btn-primary"
							:disabled="saving || readingProof || hasPending"
						>
							{{
								saving
									? "Submitting…"
									: hasPending
										? "Awaiting Accounts Manager review"
										: "Submit for approval"
							}}
						</button>
					</div>
				</form>
				<p
					v-if="success"
					class="mt-3 rounded-xl bg-ok-soft p-3 text-sm text-ink"
					role="status"
				>
					{{ success }}
				</p>
			</section>

			<section v-if="workspace.requests?.length" class="form-card">
				<h2 class="form-title">Your request history</h2>
				<div class="divide-y divide-line">
					<div
						v-for="request in workspace.requests"
						:key="request.name"
						class="py-3 first:pt-0 last:pb-0 text-sm"
					>
						<div class="flex flex-wrap justify-between gap-2">
							<strong
								>{{ request.bank_name }} ·
								{{ request.account_number_masked }}</strong
							><span class="status-pill">{{ request.request_status }}</span>
						</div>
						<p class="text-muted mt-1">
							{{ request.name }} · submitted {{ formatDate(request.creation) }}
						</p>
						<p v-if="request.review_comments" class="mt-1">
							Accounts Manager: {{ request.review_comments }}
						</p>
						<a
							v-if="request.proof_url"
							:href="request.proof_url"
							target="_blank"
							rel="noopener"
							class="inline-block mt-2 text-accent font-semibold"
							>View private bank proof</a
						>
					</div>
				</div>
			</section>

			<section v-if="workspace.can_review" class="form-card">
				<div class="flex flex-wrap items-center justify-between gap-2 mb-3">
					<div>
						<h2 class="form-title mb-0">Accounts Manager review queue</h2>
						<p class="form-hint mb-0">
							Only Accounts Managers can make these decisions.
						</p>
					</div>
					<span class="status-pill"
						>{{ workspace.pending_requests.length }} pending</span
					>
				</div>
				<div v-if="!workspace.pending_requests.length" class="text-sm text-muted">
					No bank details are awaiting approval.
				</div>
				<div v-else class="space-y-4">
					<article
						v-for="request in workspace.pending_requests"
						:key="request.name"
						class="rounded-xl border border-line bg-bg p-4"
					>
						<div class="flex flex-wrap justify-between gap-2">
							<div>
								<strong>{{ request.employee_name }}</strong>
								<p class="text-xs text-muted">
									{{ request.employee }} · {{ request.name }}
								</p>
							</div>
							<span class="status-pill">Pending Approval</span>
						</div>
						<div class="grid sm:grid-cols-3 gap-3 text-sm mt-4">
							<div>
								<span class="field-caption">Account holder</span
								><strong>{{ request.account_holder_name }}</strong>
							</div>
							<div>
								<span class="field-caption">Bank and branch</span
								><strong
									>{{ request.bank_name
									}}<template v-if="request.branch">
										· {{ request.branch }}</template
									></strong
								>
							</div>
							<div>
								<span class="field-caption">Account number</span
								><strong class="break-all">{{ request.account_number }}</strong>
							</div>
							<div>
								<span class="field-caption">IFSC</span
								><strong>{{ request.ifsc }}</strong>
							</div>
							<div>
								<span class="field-caption">Account type</span
								><strong>{{ request.account_type }}</strong>
							</div>
							<div v-if="request.swift">
								<span class="field-caption">SWIFT</span
								><strong>{{ request.swift }}</strong>
							</div>
						</div>
						<a
							v-if="request.proof_url"
							:href="request.proof_url"
							target="_blank"
							rel="noopener"
							class="inline-block mt-3 text-sm text-accent font-semibold"
							>View private bank proof</a
						>
						<label class="field-label mt-4"
							>Review comments<textarea
								v-model.trim="comments[request.name]"
								rows="2"
								maxlength="500"
								class="field-input"
							></textarea>
						</label>
						<div class="flex flex-wrap justify-end gap-2 mt-3">
							<button
								type="button"
								class="btn-secondary"
								:disabled="reviewing"
								@click="review(request, 'return')"
							>
								Return for correction
							</button>
							<button
								type="button"
								class="btn-secondary text-bad"
								:disabled="reviewing"
								@click="review(request, 'reject')"
							>
								Reject
							</button>
							<button
								type="button"
								class="btn-primary"
								:disabled="reviewing"
								@click="review(request, 'approve')"
							>
								Approve account
							</button>
						</div>
					</article>
				</div>
			</section>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import { call } from "../lib/frappe";

const API = "volunteering.volunteering.employee_bank_accounts.";
const loading = ref(true);
const saving = ref(false);
const reviewing = ref(false);
const error = ref("");
const success = ref("");
const workspace = ref({
	can_submit: false,
	can_review: false,
	requests: [],
	pending_requests: [],
});
const comments = reactive({});
const proofInput = ref(null);
const readingProof = ref(false);
const form = reactive({
	account_holder_name: "",
	bank_name: "",
	branch: "",
	account_type: "Savings",
	account_number: "",
	account_number_confirmation: "",
	ifsc: "",
	swift: "",
	proof_filename: "",
	proof_content: "",
	ownership_confirmed: false,
});

const hasPending = computed(() =>
	workspace.value.requests?.some((row) => row.request_status === "Pending Approval"),
);

async function load() {
	loading.value = true;
	error.value = "";
	try {
		workspace.value = await call(API + "get_bank_account_workspace");
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		loading.value = false;
	}
}

async function submitRequest() {
	saving.value = true;
	error.value = "";
	success.value = "";
	try {
		if (readingProof.value || !form.proof_content)
			throw new Error("Choose a bank proof and wait for it to finish loading.");
		await call(API + "submit_bank_account_request", { details: form });
		success.value =
			"Bank details submitted. Your approved account, if any, remains active until this request is approved.";
		form.account_number = form.account_number_confirmation = "";
		form.proof_filename = form.proof_content = "";
		form.ownership_confirmed = false;
		if (proofInput.value) proofInput.value.value = "";
		await load();
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		saving.value = false;
	}
}

async function chooseProof(event) {
	form.proof_filename = form.proof_content = "";
	error.value = "";
	const file = event.target.files?.[0];
	if (!file) return;
	if (file.size > 5 * 1024 * 1024 || !/\.(pdf|png|jpe?g)$/i.test(file.name)) {
		error.value = "Choose a PDF, PNG or JPEG bank proof smaller than 5 MB.";
		event.target.value = "";
		return;
	}
	readingProof.value = true;
	try {
		const encoded = await new Promise((resolve, reject) => {
			const reader = new FileReader();
			reader.onload = () => resolve(String(reader.result).split(",")[1]);
			reader.onerror = () =>
				reject(new Error("Could not read the bank proof. Please choose it again."));
			reader.readAsDataURL(file);
		});
		form.proof_filename = file.name;
		form.proof_content = encoded;
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		readingProof.value = false;
	}
}

async function review(request, action) {
	reviewing.value = true;
	error.value = "";
	try {
		await call(API + "review_bank_account_request", {
			request: request.name,
			action,
			modified: request.modified,
			comments: comments[request.name] || "",
		});
		delete comments[request.name];
		await load();
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		reviewing.value = false;
	}
}

function formatDate(value) {
	if (!value) return "—";
	return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(
		new Date(value),
	);
}

onMounted(load);
</script>

<style scoped>
.form-card {
	@apply rounded-2xl border border-line bg-surface p-4 sm:p-5 shadow-soft;
}
.form-title {
	@apply text-lg font-semibold text-ink mb-3;
}
.form-hint {
	@apply text-sm text-muted -mt-2 mb-3;
}
.form-grid {
	@apply grid sm:grid-cols-2 gap-3;
}
.field-label {
	@apply block text-sm font-medium text-ink;
}
.field-input {
	@apply mt-1 w-full rounded-xl border border-line bg-bg px-3 py-2 text-ink font-normal;
}
.field-input:focus {
	@apply outline-none ring-2 ring-accent border-accent;
}
.field-caption {
	@apply block text-xs text-muted mb-0.5;
}
.status-pill {
	@apply self-start rounded-full bg-soft px-2.5 py-1 text-xs font-semibold text-ink;
}
button:disabled {
	@apply opacity-60 cursor-not-allowed;
}
</style>
