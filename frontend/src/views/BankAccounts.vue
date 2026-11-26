<template>
	<div class="mx-auto max-w-6xl space-y-5">
		<PageHeader
			title="Reimbursement bank account"
			subtitle="Submit your payment destination. It becomes usable only after Accounts Manager approval."
			eyebrow="Expenses"
		>
			<template #actions>
				<RouterLink to="/home" class="btn-back">Back to Home</RouterLink>
			</template>
		</PageHeader>

		<div v-if="loading" class="grid gap-5 lg:grid-cols-[minmax(0,1fr)_21rem]" aria-busy="true"><p class="sr-only">Loading bank-account details…</p><div class="skeleton h-[32rem] rounded-2xl"></div><div class="skeleton h-72 rounded-2xl"></div></div>
		<div v-if="error" class="message-error" role="alert">{{ error }}</div>
		<template v-if="!loading">
			<div v-if="workspace.can_submit" class="bank-board">
				<!-- The change form: four short steps, all on one page. -->
				<section class="kit-panel min-w-0 overflow-hidden">
					<div class="border-b border-line px-5 py-4 sm:px-6">
						<h2 class="text-lg font-semibold text-ink">{{ workspace.approved ? "Request a bank-account change" : "Submit bank details" }}</h2>
						<p class="mt-1 text-sm text-muted">Your currently approved account remains active while a replacement is being reviewed.</p>
					</div>
					<form @submit.prevent="submitRequest">
						<fieldset class="bank-step">
							<legend class="bank-step__title"><span class="bank-step__num" :class="{ 'bank-step__num--done': form.account_holder_name }">1</span>Account holder</legend>
							<label class="field-label">Account-holder name *<input v-model.trim="form.account_holder_name" required maxlength="160" autocomplete="name" class="field-input" placeholder="Exactly as it appears on the bank record" /></label>
						</fieldset>
						<fieldset class="bank-step">
							<legend class="bank-step__title"><span class="bank-step__num" :class="{ 'bank-step__num--done': form.bank_name && ifscValid }">2</span>Bank details</legend>
							<div class="grid gap-4 sm:grid-cols-2">
								<div class="min-w-0"><label class="field-label">IFSC *<input v-model.trim="form.ifsc" required minlength="11" maxlength="11" class="field-input font-mono uppercase tracking-wider" placeholder="ABCD0123456" autocapitalize="characters" spellcheck="false" /></label>
									<span v-if="form.ifsc && ifscValid" class="field-ok"><Icon name="check" size="sm" />Looks like a valid IFSC</span>
									<span v-else-if="form.ifsc.length === 11" class="field-warn">IFSC is 4 letters, a 0, then 6 letters or digits</span>
									<span v-else class="field-help">11 characters, printed on your cheque book</span>
								</div>
								<label class="field-label">Bank name *<input v-model.trim="form.bank_name" required maxlength="100" autocomplete="organization" class="field-input" placeholder="e.g. State Bank of India" /></label>
								<label class="field-label">Branch<input v-model.trim="form.branch" maxlength="140" class="field-input" placeholder="Optional" /></label>
							</div>
							<div class="mt-4" role="radiogroup" aria-label="Account type *">
								<p class="field-label">Account type *</p>
								<div class="mt-1.5 grid grid-cols-2 gap-2 sm:grid-cols-4">
									<label v-for="type in accountTypes" :key="type" class="choice-card" :class="{ 'choice-card--on': form.account_type === type }">
										<input v-model="form.account_type" type="radio" name="account_type" :value="type" required />
										<span>{{ type }}</span>
									</label>
								</div>
							</div>
						</fieldset>
						<fieldset class="bank-step">
							<legend class="bank-step__title"><span class="bank-step__num" :class="{ 'bank-step__num--done': numbersMatch }">3</span>Account number</legend>
							<div class="grid gap-4 sm:grid-cols-2">
								<label class="field-label">Account number *<input v-model="form.account_number" required maxlength="30" autocomplete="off" inputmode="numeric" class="field-input font-mono tracking-wider" /></label>
								<div class="min-w-0"><label class="field-label">Re-enter account number *<input v-model="form.account_number_confirmation" required maxlength="30" autocomplete="off" inputmode="numeric" class="field-input font-mono tracking-wider" :class="{ 'field-input--bad': confirmMismatch }" /></label>
									<span v-if="numbersMatch" class="field-ok"><Icon name="check" size="sm" />Numbers match</span>
									<span v-else-if="confirmMismatch" class="field-warn">Doesn’t match the account number yet</span>
								</div>
							</div>
							<details class="mt-3 group" :open="Boolean(form.swift)">
								<summary class="inline-flex min-h-8 cursor-pointer items-center gap-1 text-sm font-semibold text-navy-600 hover:text-navy-900">International transfers<Icon name="chevron-down" size="sm" class="transition-transform group-open:rotate-180" /></summary>
								<label class="field-label mt-2 sm:max-w-xs">SWIFT, if applicable<input v-model.trim="form.swift" maxlength="11" class="field-input font-mono uppercase tracking-wider" /></label>
							</details>
						</fieldset>
						<fieldset class="bank-step">
							<legend class="bank-step__title"><span class="bank-step__num" :class="{ 'bank-step__num--done': form.proof_content && form.ownership_confirmed }">4</span>Proof and confirmation</legend>
							<div class="min-w-0"><label class="field-label">Cancelled cheque or bank proof *<input ref="proofInput" type="file" required :disabled="readingProof || saving" accept=".pdf,.png,.jpg,.jpeg" class="mt-1.5" @change="chooseProof" /></label>
								<span v-if="readingProof" class="field-help">Reading the file…</span>
								<span v-else-if="form.proof_filename" class="field-ok"><Icon name="check" size="sm" />{{ form.proof_filename }} is ready</span>
								<span class="field-help">PDF, PNG or JPEG, maximum 5 MB. Drop it on the box or choose a file. Visible only to you and Accounts Managers.</span>
							</div>
							<label class="confirm-row mt-4"><input v-model="form.ownership_confirmed" type="checkbox" required class="mt-0.5" /><span>I confirm this account belongs to me and the bank proof shows the correct account details.</span></label>
						</fieldset>
						<div class="flex flex-wrap items-center justify-between gap-3 border-t border-line bg-soft/60 px-5 py-4 sm:px-6">
							<p class="text-xs text-muted">{{ hasPending ? "One request is already with Accounts." : "Accounts usually review within a few working days." }}</p>
							<button type="submit" class="btn-primary min-h-11" :disabled="saving || readingProof || hasPending">{{ saving ? "Submitting…" : hasPending ? "Awaiting Accounts Manager review" : "Submit for approval" }}</button>
						</div>
					</form>
					<p v-if="success" class="message-success mx-5 mb-5 sm:mx-6" role="status">{{ success }}</p>
				</section>

				<!-- Context rail -->
				<aside class="min-w-0 space-y-5">
					<section class="kit-panel p-5">
						<h2 class="text-base font-semibold text-ink">Your approved reimbursement account</h2>
						<template v-if="workspace.approved">
							<div class="bank-card mt-4">
								<div class="flex items-start justify-between gap-3"><span class="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/60">{{ workspace.approved.account_type }}</span><Icon name="bank" class="text-marigold" /></div>
								<p class="mt-5 font-mono text-lg tracking-[0.14em]">{{ workspace.approved.account_number_masked }}</p>
								<div class="mt-4 flex items-end justify-between gap-3 text-xs"><div class="min-w-0"><p class="text-white/55">Holder</p><p class="truncate font-semibold">{{ workspace.approved.account_holder_name }}</p></div><div class="text-right"><p class="text-white/55">IFSC</p><p class="font-semibold tracking-wide">{{ workspace.approved.ifsc }}</p></div></div>
							</div>
							<dl class="mt-4 grid grid-cols-2 gap-3 text-sm">
								<div><dt class="text-xs text-muted">Bank</dt><dd class="mt-0.5 font-medium text-ink">{{ workspace.approved.bank_name }}</dd></div>
								<div><dt class="text-xs text-muted">Approved on</dt><dd class="mt-0.5 font-medium text-ink">{{ formatDate(workspace.approved.reviewed_on) }}</dd></div>
							</dl>
						</template>
						<div v-else class="mt-3 rounded-xl bg-warn-soft p-3 text-sm text-ink">No approved account is available. Invoice generation and bank reimbursement will remain unavailable until an Accounts Manager approves one.</div>
					</section>
					<section class="kit-panel p-5">
						<h2 class="text-base font-semibold text-ink">What happens next</h2>
						<ol class="timeline mt-4">
							<li class="timeline__item"><span class="timeline__dot timeline__dot--on">1</span><div><p class="text-sm font-semibold text-ink">You submit the details</p><p class="text-xs text-muted">With a cancelled cheque or bank letter.</p></div></li>
							<li class="timeline__item"><span class="timeline__dot" :class="{ 'timeline__dot--on': hasPending }">2</span><div><p class="text-sm font-semibold text-ink">Accounts checks the proof</p><p class="text-xs text-muted">Your current account stays active meanwhile.</p></div></li>
							<li class="timeline__item"><span class="timeline__dot">3</span><div><p class="text-sm font-semibold text-ink">The new account goes live</p><p class="text-xs text-muted">Used for reimbursements and invoices.</p></div></li>
						</ol>
					</section>
					<section v-if="workspace.requests?.length" class="kit-panel p-5">
						<h2 class="text-base font-semibold text-ink">Your request history</h2>
						<ul class="mt-3 divide-y divide-line">
							<li v-for="request in workspace.requests" :key="request.name" class="py-3 text-sm first:pt-0 last:pb-0">
								<div class="flex flex-wrap items-start justify-between gap-2"><strong class="min-w-0 break-words">{{ request.bank_name }} · {{ request.account_number_masked }}</strong><span class="status-pill" :class="statusTone(request.request_status)">{{ request.request_status }}</span></div>
								<p class="mt-1 text-xs text-muted">{{ request.name }} · submitted {{ formatDate(request.creation) }}</p>
								<p v-if="request.review_comments" class="mt-1 text-xs text-ink-2">Accounts Manager: {{ request.review_comments }}</p>
								<a v-if="request.proof_url" :href="request.proof_url" target="_blank" rel="noopener" class="mt-1.5 inline-flex text-xs font-semibold text-navy-600 hover:text-navy-900">View private bank proof</a>
							</li>
						</ul>
					</section>
				</aside>
			</div>
			<section v-else-if="workspace.requests?.length" class="form-card">
				<h2 class="form-title">Your request history</h2>
				<ul class="divide-y divide-line"><li v-for="request in workspace.requests" :key="request.name" class="py-3 text-sm"><strong>{{ request.bank_name }} · {{ request.account_number_masked }}</strong> <span class="status-pill">{{ request.request_status }}</span></li></ul>
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
import Icon from "../components/Icon.vue";
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

const accountTypes = ["Savings", "Current", "Salary", "Other"];
const ifscValid = computed(() => /^[A-Z]{4}0[A-Z0-9]{6}$/.test(String(form.ifsc || "").toUpperCase()));
const numbersMatch = computed(() => Boolean(form.account_number) && form.account_number === form.account_number_confirmation);
const confirmMismatch = computed(() => Boolean(form.account_number_confirmation) && !numbersMatch.value && (form.account_number_confirmation.length >= form.account_number.length || !form.account_number.startsWith(form.account_number_confirmation)));
function statusTone(status) {
	if (status === "Approved") return "bg-ok-soft text-ok";
	if (status === "Pending Approval") return "bg-warn-soft text-warn";
	if (status === "Rejected") return "bg-bad-soft text-bad";
	return "";
}
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
.bank-board { display: grid; gap: 1.25rem; align-items: start; }
@media (min-width: 1024px) { .bank-board { grid-template-columns: minmax(0, 1fr) 21rem; gap: 1.5rem; } .bank-board > aside { position: sticky; top: 5.5rem; } }
.bank-step { min-width: 0; padding: 1.25rem; border-bottom: 1px solid var(--line); }
@media (min-width: 640px) { .bank-step { padding: 1.375rem 1.5rem; } }
.bank-step:last-of-type { border-bottom: 0; }
.bank-step__title { float: left; width: 100%; padding: 0; display: flex; align-items: center; gap: 0.625rem; margin-bottom: 0.875rem; font-family: theme("fontFamily.display"); font-size: 0.9375rem; font-weight: 600; color: var(--ink); }
.bank-step__title + * { clear: both; }
.bank-step__num { display: inline-flex; width: 1.625rem; height: 1.625rem; align-items: center; justify-content: center; border-radius: 999px; background: var(--navy-50); color: var(--navy-900); font-family: theme("fontFamily.sans"); font-size: 0.75rem; font-weight: 700; transition: background-color var(--dur) ease, color var(--dur) ease; }
.bank-step__num--done { background: var(--ok); color: #fff; }
.field-ok { margin-top: 0.375rem; display: flex; align-items: center; gap: 0.3rem; font-size: 0.75rem; font-weight: 500; color: var(--ok); }
.field-warn { margin-top: 0.375rem; display: block; font-size: 0.75rem; font-weight: 500; color: var(--warn); }
.field-input--bad { border-color: color-mix(in srgb, var(--warn) 60%, var(--line-strong)); }
.choice-card { position: relative; display: flex; min-height: 2.75rem; cursor: pointer; align-items: center; gap: 0.5rem; padding: 0.5rem 0.75rem; border: 1px solid var(--line-strong); border-radius: 12px; background: var(--surface); font-size: 0.875rem; font-weight: 600; color: var(--ink-2); transition: border-color var(--dur-fast) ease, background-color var(--dur-fast) ease, box-shadow var(--dur-fast) ease; }
.choice-card:hover { border-color: var(--navy-200); background: var(--navy-50); }
.choice-card--on, .choice-card--on:hover { border-color: var(--navy-900); background: var(--accent-soft); color: var(--navy-900); box-shadow: inset 0 0 0 1px var(--navy-900); }
.confirm-row { display: flex; align-items: flex-start; gap: 0.75rem; padding: 0.875rem 1rem; border: 1px solid var(--line); border-radius: 12px; background: var(--soft); font-size: 0.875rem; color: var(--ink); cursor: pointer; }
.bank-card { position: relative; overflow: hidden; border-radius: 16px; padding: 1.125rem 1.25rem; color: #fff; background: radial-gradient(120% 140% at 100% 0%, rgb(242 181 68 / 0.22), transparent 50%), linear-gradient(135deg, var(--navy-900), var(--navy-600)); box-shadow: 0 14px 30px -18px rgb(5 34 77 / 0.7); }
.timeline { display: grid; gap: 0.875rem; }
.timeline__item { position: relative; display: flex; gap: 0.75rem; }
.timeline__item:not(:last-child)::after { content: ""; position: absolute; left: 0.75rem; top: 1.75rem; bottom: -0.875rem; width: 2px; background: var(--line); transform: translateX(-1px); }
.timeline__dot { display: inline-flex; width: 1.5rem; height: 1.5rem; flex-shrink: 0; align-items: center; justify-content: center; border-radius: 999px; background: var(--soft); color: var(--muted); font-size: 0.6875rem; font-weight: 700; box-shadow: inset 0 0 0 1px var(--line-strong); }
.timeline__dot--on { background: var(--navy-900); color: #fff; box-shadow: none; }
.text-ink-2 { color: var(--ink-2); }
.field-caption { @apply block text-xs text-muted mb-0.5; }
.status-pill { @apply self-start rounded-full bg-soft px-2.5 py-1 text-xs font-semibold text-ink; }
button:disabled { @apply opacity-60 cursor-not-allowed; }
</style>
