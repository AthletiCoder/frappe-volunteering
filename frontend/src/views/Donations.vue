<template>
	<div class="donations-page mx-auto max-w-5xl space-y-6 pb-10">
		<PageHeader title="Donations" eyebrow="Accounts" subtitle="Record donations and issue signed receipts when ready.">
			<template #actions><RouterLink to="/home" class="btn-secondary">Back to Home</RouterLink></template>
		</PageHeader>
		<p v-if="error" class="message-error" role="alert">{{ error }}</p>
		<p v-if="message" class="message-success" role="status">{{ message }} <a v-if="issuedPdf" :href="issuedPdf" target="_blank" rel="noopener" class="text-accent underline">Open private PDF</a></p>
		<p v-if="loading" class="text-muted">Loading donation workspace…</p>
		<template v-else-if="workspace">
			<div class="flex flex-wrap gap-2" role="group" aria-label="Donations views">
				<button v-for="[id, label] in views" :key="id" type="button" :class="view === id ? 'btn-primary' : 'btn-secondary'" :aria-pressed="view === id" :disabled="busy || listLoading" @click="openView(id)">{{ label }}</button>
			</div>
			<div v-if="view === 'record'" class="intro-note">
				<strong>Before you begin</strong>
				<p>Record money already received. For cheques, wait until the funds clear. You can issue the receipt later from the donations list.</p>
			</div>

			<form v-if="view === 'record'" class="space-y-6" @submit.prevent="register">
				<section class="form-card">
					<div class="section-heading"><span class="step-number">1</span><div><h2 class="form-title">Donor details</h2><p class="form-hint">Choose a previous donor or enter a new name. Their details can be reused next time.</p></div></div>
					<label class="field-label">Donor name <span class="required">*</span><input v-model="donorChoice" list="donor-suggestions" required class="field-input" placeholder="Type a name or choose a saved donor" @input="chooseDonor" /></label>
					<datalist id="donor-suggestions"><option v-for="donor in availableDonors" :key="donor.name" :value="donorOption(donor)">{{ donor.address }}</option></datalist>
					<div v-if="form.donor" class="saved-donor-note">Saved donor selected · {{ form.donor }} <button type="button" class="text-accent underline" @click="newDonor">Use a new donor</button></div>
					<div class="form-grid mt-5">
						<label class="field-label">Donor type<select v-model="form.donor_type" class="field-input"><option>Individual</option><option>Organisation</option></select></label>
						<label class="field-label">PAN <span class="required">*</span><input v-model.trim="form.pan" required maxlength="10" minlength="10" class="field-input uppercase" placeholder="ABCDE1234F" /></label>
						<label class="field-label full-width">Full postal address <span class="required">*</span><textarea v-model.trim="form.address" required maxlength="600" rows="3" class="field-input" placeholder="Street, city, state and PIN code" /></label>
						<label class="field-label">Phone number<input v-model.trim="form.mobile_number" maxlength="40" class="field-input" placeholder="Optional" /></label>
						<label class="field-label">Email<input v-model.trim="form.email" type="email" maxlength="140" class="field-input" placeholder="Optional" /></label>
					</div>
					<div v-if="form.donor" class="section-footer"><button type="button" class="btn-secondary" :disabled="busy" @click="saveDonor">Save donor changes</button><p class="field-help">Save corrections before recording. Earlier entries stay unchanged.</p></div>
				</section>

				<section class="form-card">
					<div class="section-heading"><span class="step-number">2</span><div><h2 class="form-title">Donation and payment</h2><p class="form-hint">Enter the amount, the date money arrived and how it was received.</p></div></div>
					<div class="form-grid">
						<label class="field-label">Amount received (INR) <span class="required">*</span><input v-model="form.amount" required type="number" min="0.01" step="0.01" class="field-input" placeholder="0.00" /></label>
						<label class="field-label">Date received <span class="required">*</span><input v-model="form.received_on" required type="date" :max="workspace.today" class="field-input" /></label>
						<label class="field-label">Payment method <span class="required">*</span><select v-model="form.payment_method" required class="field-input"><option value="">Choose a method</option><option v-for="method in methods" :key="method">{{ method }}</option></select></label>
						<label v-if="form.payment_method !== 'Cash'" class="field-label full-width">Cheque / transaction reference <span class="required">*</span><input v-model.trim="form.payment_reference" required maxlength="140" class="field-input" placeholder="For example, UPI ID, IMPS/NEFT reference or cheque number" /></label>
					</div>
					<label v-if="form.payment_method === 'Cheque'" class="checkbox-row mt-5"><input v-model="form.cheque_cleared" required type="checkbox" /><span>I confirm this cheque has cleared and the money was received.</span></label>
				</section>

				<section class="form-card">
					<div class="section-heading"><span class="step-number">3</span><div><h2 class="form-title">Accounting</h2><p class="form-hint">Choose where the money arrived. New entries are credited to General Donations.</p></div></div>
					<div class="form-grid">
						<label class="field-label">Money received into <span class="required">*</span><select v-model="form.received_into_account" required class="field-input"><option value="">Choose a cash or bank ledger</option><option v-for="account in receivedOptions" :key="account.name" :value="account.name">{{ account.account_name }} · {{ account.account_type }}</option></select></label>
						<label class="field-label">Donation credit ledger<input :value="creditLedger?.account_name || 'Required ledger not configured'" readonly class="field-input" /></label>
					</div>
					<p v-if="!creditLedger" class="warning-note mt-4">The General Donations income ledger is unavailable. Ask Accounts to configure it before recording this donation.</p>
				</section>

				<section class="form-card">
					<div class="section-heading"><span class="step-number">4</span><div><h2 class="form-title">Review and record</h2><p class="form-hint">Check the details before posting the Journal Entry.</p></div></div>
					<div v-if="form.payment_method === 'Cash'" class="signature-panel"><div><strong>Cash donor signature</strong><p class="field-help">The donor signs on screen. Changing the donation details afterward requires a new signature.</p></div><button type="button" class="btn-secondary" @click="openSignature('donor')">{{ form.donor_signature_data ? 'Sign again' : 'Ask donor to sign' }}</button><img v-if="form.donor_signature_data" :src="form.donor_signature_data" alt="Cash donor signature" class="signature-preview" /></div>
					<div class="issue-panel"><p>You don’t need an authorised signatory to record this donation.</p><button type="submit" class="btn-primary" :disabled="busy || !creditLedger">{{ busy ? 'Recording…' : 'Record donation' }}</button></div>
				</section>
			</form>

			<section v-if="view === 'list'" class="form-card">
				<div class="flex flex-wrap items-end justify-between gap-4 pb-4">
					<div><h2 class="form-title">Recorded donations</h2><p class="form-hint mb-0">Review donations and issue receipts for pending entries.</p></div>
					<label class="field-label">Receipt status<select v-model="filter" class="field-input" :disabled="busy || listLoading" @change="loadList(1)"><option value="all">All donations</option><option value="pending">Pending receipt</option><option value="issued">Receipt issued</option></select></label>
				</div>
				<p v-if="listLoading" class="text-muted" role="status">Loading donations…</p>
				<p v-else-if="!list.rows.length" class="text-muted">No donations match this view.</p>
				<article v-for="row in listLoading ? [] : list.rows" :key="row.name" class="border-t border-line">
					<div class="history-row">
						<div>
							<strong>{{ row.full_name }}</strong>
							<span>{{ row.received_on }}<template v-if="row.payment_method"> · {{ row.payment_method }}</template></span>
							<span v-if="row.journal_entry">{{ row.journal_entry }}</span>
						</div>
						<div>
							<strong>{{ formatAmount(row.amount) }}</strong>
							<a v-if="row.receipt_file" :href="row.receipt_file" target="_blank" rel="noopener" class="text-accent underline">Open PDF · {{ row.receipt_number }}</a>
							<template v-else-if="row.receipt_status === 'pending'">
								<span class="font-medium">Pending receipt</span>
								<button type="button" class="btn-secondary" :aria-expanded="issuing === row.name" :disabled="busy" @click="toggleIssue(row.name)">{{ issuing === row.name ? 'Close receipt options' : 'Issue receipt' }}</button>
							</template>
							<span v-else>{{ row.donation_purpose === 'CSR' ? 'Historical CSR · no receipt expected' : 'Receipt unavailable' }}</span>
						</div>
					</div>
					<form v-if="issuing === row.name" class="intro-note mb-4 space-y-4" @submit.prevent="issueReceipt(row)">
						<p v-if="!workspace.signatories.length">Register an authorised signature in <button type="button" class="text-accent underline" @click="openView('setup')">Receipt setup</button> to issue this receipt.</p>
						<template v-else>
							<label class="field-label">Authorised Sevamrita signatory <span class="required">*</span><select v-model="issue.signatory" required class="field-input"><option value="">Choose a registered signatory</option><option v-for="person in workspace.signatories" :key="person.name" :value="person.name">{{ person.signatory_name }} · {{ person.designation }}</option></select></label>
							<label class="checkbox-row"><input v-model="issue.want80g" type="checkbox" /><span>Include verified 80G registration on this acknowledgement</span></label>
							<div class="flex justify-end"><button type="submit" class="btn-primary" :disabled="busy || !issue.signatory">Issue signed PDF</button></div>
						</template>
					</form>
				</article>
				<div v-if="!listLoading && (list.page > 1 || list.has_more)" class="section-footer">
					<button type="button" class="btn-secondary" :disabled="list.page <= 1 || busy || listLoading" @click="loadList(list.page - 1)">Previous</button>
					<span class="text-sm text-muted">Page {{ list.page }}</span>
					<button type="button" class="btn-secondary" :disabled="!list.has_more || busy || listLoading" @click="loadList(list.page + 1)">Next</button>
				</div>
			</section>

			<section v-if="view === 'setup'" class="space-y-4 pt-2"><div><h2 class="text-lg font-semibold text-ink">Receipt setup</h2><p class="text-sm text-muted">Occasional settings for receipt identity and authorised signatures.</p></div>
				<details class="form-card setup-card"><summary>Receipt identity and registration</summary><p class="form-hint mt-4">Use verified organisation records. The 80G line appears only when a valid registration is configured and selected for a donation.</p><form class="form-grid mt-5" @submit.prevent="saveSettings"><label class="field-label">Organisation name <span class="required">*</span><input v-model.trim="settings.organisation_name" required class="field-input" maxlength="160" /></label><label class="field-label">Contact email <span class="required">*</span><input v-model.trim="settings.contact_email" required type="email" class="field-input" maxlength="140" /></label><label class="field-label full-width">Registered office address <span class="required">*</span><textarea v-model.trim="settings.registered_address" required class="field-input" rows="3" maxlength="600" /></label><label class="field-label">CIN<input v-model.trim="settings.cin" class="field-input" maxlength="40" /></label><label class="field-label">Organisation PAN<input v-model.trim="settings.organisation_pan" class="field-input uppercase" maxlength="10" /></label><label class="field-label">80G registration number<input v-model.trim="settings.eighty_g_number" class="field-input" maxlength="80" /></label><label class="field-label">80G valid until<input v-model="settings.eighty_g_valid_until" type="date" class="field-input" /></label><div class="full-width section-footer"><button type="submit" class="btn-secondary" :disabled="busy">Save receipt details</button></div></form></details>
				<details class="form-card setup-card"><summary>Register an authorised signature</summary><p class="form-hint mt-4">Only register a signature with the signatory's authority. Issued receipts keep a copy of the signature used at the time.</p><div class="form-grid mt-5"><label class="field-label">Signatory name <span class="required">*</span><input v-model.trim="newSignatory.name" class="field-input" maxlength="140" /></label><label class="field-label">Designation<input v-model.trim="newSignatory.designation" class="field-input" maxlength="140" /></label></div><div class="section-footer"><button type="button" class="btn-secondary" @click="openSignature('signatory')">Draw signature</button><span v-if="newSignatory.signature" class="text-sm text-ok">Signature captured</span><button type="button" class="btn-primary" :disabled="busy || !newSignatory.name || !newSignatory.signature" @click="saveSignatory">Save signatory</button></div></details>
			</section>
		</template>
		<div v-if="signatureOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" role="dialog" aria-modal="true" aria-label="Draw signature"><div class="w-full max-w-2xl rounded-2xl bg-surface p-5"><h2 class="form-title">{{ signatureTarget === 'donor' ? 'Donor signature' : 'Authorised representative signature' }}</h2><p class="form-hint">Use a finger, stylus or mouse on the white panel.</p><canvas ref="canvas" class="mt-3 h-56 w-full touch-none rounded-xl border border-line bg-white" @pointerdown="startStroke" @pointermove="drawStroke" @pointerup="stopStroke" @pointercancel="stopStroke"></canvas><div class="mt-4 flex flex-wrap justify-end gap-2"><button type="button" class="btn-secondary" @click="clearCanvas">Clear</button><button type="button" class="btn-secondary" @click="signatureOpen = false">Cancel</button><button type="button" class="btn-primary" @click="acceptSignature">Use signature</button></div><p v-if="signatureError" class="mt-2 text-sm text-bad">{{ signatureError }}</p></div></div>
	</div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import { call } from "../lib/frappe";

const api = "volunteering.volunteering.donation_portal";
const methods = ["Online", "Bank Transfer", "UPI", "Cheque", "Cash"];
const workspace = ref(null), loading = ref(true), busy = ref(false), error = ref(""), message = ref("");
const views = [["list", "Donations list"], ["record", "Record a donation"], ["setup", "Receipt setup"]];
const view = ref("list"), filter = ref("all"), listLoading = ref(false);
const list = ref({ rows: [], page: 1, has_more: false });
const issuing = ref(""), issuedPdf = ref("");
const issue = reactive({ signatory: "", want80g: false });
const formatAmount = (value) => Number(value).toLocaleString("en-IN", { style: "currency", currency: "INR" });
const settings = reactive({ organisation_name: "", registered_address: "", contact_email: "", cin: "", organisation_pan: "", eighty_g_number: "", eighty_g_valid_until: "" });
const newSignatory = reactive({ name: "", designation: "", signature: "" });
const form = reactive({ donor: "", donor_name: "", donor_type: "Individual", address: "", pan: "", mobile_number: "", email: "", amount: "", received_on: "", payment_method: "Online", payment_reference: "", received_into_account: "", donation_account: "", donor_signature_data: "", donor_signature_proof: "", cheque_cleared: false });
const donorChoice = ref("");
const signatureOpen = ref(false), signatureTarget = ref(""), signatureError = ref(""), canvas = ref(null);
let drawing = false, hasInk = false, requestKey = crypto.randomUUID();
const receivedOptions = computed(() => workspace.value?.accounts?.received_into || []);
const creditLedger = computed(() => workspace.value?.accounts?.donation_credit_by_type?.General || null);
const availableDonors = computed(() => workspace.value?.donors || []);
function donorOption(donor) { return `${donor.donor_name} · ${donor.name}`; }
function chooseDonor() {
	const donor = availableDonors.value.find((row) => donorOption(row) === donorChoice.value);
	form.donor = donor?.name || "";
	form.donor_name = donor?.donor_name || donorChoice.value;
	for (const field of ["donor_type", "address", "pan", "mobile_number", "email"]) form[field] = donor?.[field] || (field === "donor_type" ? "Individual" : "");
}
function newDonor() { donorChoice.value = ""; chooseDonor(); }
function openView(next) {
	view.value = next;
	error.value = "";
	issuing.value = "";
	if (next === "list") loadList(1);
}
function toggleIssue(name) {
	error.value = "";
	issuing.value = issuing.value === name ? "" : name;
	Object.assign(issue, { signatory: "", want80g: false });
}
async function loadList(page) {
	const status = filter.value;
	issuing.value = "";
	listLoading.value = true;
	try {
		const result = await call(`${api}.get_donation_list`, { receipt_status: status, page });
		list.value = result;
	} catch (e) { error.value = e.message || String(e); }
	finally { listLoading.value = false; }
}
async function issueReceipt(row) {
	if (busy.value) return;
	busy.value = true;
	error.value = ""; message.value = ""; issuedPdf.value = "";
	try {
		const result = await call(`${api}.issue_donation_receipt`, { donation: row.name, signatory: issue.signatory, want_80g: Number(issue.want80g) });
		message.value = `Receipt ${result.receipt_number} issued.`;
		issuedPdf.value = result.receipt_file;
		await loadList(1);
	} catch (e) { error.value = e.message || String(e); }
	finally { busy.value = false; }
}
function applyWorkspace(data) {
	workspace.value = data;
	Object.assign(settings, data.settings);
	if (!form.received_on) form.received_on = data.today;
	form.donation_account = data.accounts?.donation_credit_by_type?.General?.name || "";
}
async function load() { loading.value = true; error.value = ""; try { applyWorkspace(await call(`${api}.get_donation_workspace`)); await loadList(1); } catch (e) { error.value = e.message || String(e); } finally { loading.value = false; } }
async function saveSettings() { busy.value = true; error.value = ""; try { applyWorkspace(await call(`${api}.save_donation_receipt_settings`, { details: { ...settings } })); issuedPdf.value = ""; message.value = "Receipt identity saved."; } catch (e) { error.value = e.message; } finally { busy.value = false; } }
async function saveSignatory() { busy.value = true; error.value = ""; try { applyWorkspace(await call(`${api}.save_donation_signatory`, { name: newSignatory.name, designation: newSignatory.designation, signature_data: newSignatory.signature })); issuedPdf.value = ""; message.value = "Authorised signature registered."; Object.assign(newSignatory, { name: "", designation: "", signature: "" }); } catch (e) { error.value = e.message; } finally { busy.value = false; } }
async function saveDonor() { busy.value = true; error.value = ""; try { const updated = await call(`${api}.update_donation_donor`, { donor: form.donor, details: { donor_name: form.donor_name, donor_type: form.donor_type, address: form.address, pan: form.pan, mobile_number: form.mobile_number, email: form.email } }); applyWorkspace(updated); const donor = updated.donors.find((row) => row.name === form.donor); donorChoice.value = donorOption(donor); issuedPdf.value = ""; message.value = "Donor details saved for future donations."; } catch (e) { error.value = e.message; } finally { busy.value = false; } }
async function register() {
	if (busy.value) return;
	error.value = ""; message.value = ""; issuedPdf.value = "";
	if (!creditLedger.value) { error.value = "The General Donations ledger is not configured."; return; }
	if (form.payment_method === "Cash" && !form.donor_signature_data) { error.value = "Ask the cash donor to sign on screen."; return; }
	busy.value = true;
	try {
		const recorded = await call(`${api}.register_donation`, { details: { ...form, request_key: requestKey } });
		message.value = `Donation recorded · Journal Entry ${recorded.journal_entry}. Receipt pending.`;
		requestKey = crypto.randomUUID();
		Object.assign(form, { donor: "", donor_name: "", donor_type: "Individual", address: "", pan: "", mobile_number: "", email: "", amount: "", received_on: workspace.value.today, payment_method: "Online", payment_reference: "", received_into_account: "", donor_signature_data: "", donor_signature_proof: "", cheque_cleared: false });
		donorChoice.value = "";
		filter.value = "pending";
		view.value = "list";
		await loadList(1);
		applyWorkspace(await call(`${api}.get_donation_workspace`));
	} catch (e) { error.value = e.message || String(e); }
	finally { busy.value = false; }
}
async function openSignature(target) { signatureTarget.value = target; signatureError.value = ""; signatureOpen.value = true; await nextTick(); const element = canvas.value; const scale = Math.min(devicePixelRatio || 1, 2); const rect = element.getBoundingClientRect(); element.width = Math.round(rect.width * scale); element.height = Math.round(rect.height * scale); const ctx = element.getContext("2d"); ctx.setTransform(scale, 0, 0, scale, 0, 0); ctx.fillStyle = "white"; ctx.fillRect(0, 0, rect.width, rect.height); ctx.strokeStyle = "#111827"; ctx.lineWidth = 2.5; ctx.lineCap = "round"; ctx.lineJoin = "round"; hasInk = false; }
function point(event) { const rect = canvas.value.getBoundingClientRect(); return { x: event.clientX - rect.left, y: event.clientY - rect.top }; }
function startStroke(event) { event.preventDefault(); drawing = true; hasInk = true; canvas.value.setPointerCapture?.(event.pointerId); const p = point(event); const ctx = canvas.value.getContext("2d"); ctx.beginPath(); ctx.moveTo(p.x, p.y); }
function drawStroke(event) { if (!drawing) return; event.preventDefault(); const p = point(event); const ctx = canvas.value.getContext("2d"); ctx.lineTo(p.x, p.y); ctx.stroke(); }
function stopStroke() { drawing = false; }
function clearCanvas() { const rect = canvas.value.getBoundingClientRect(); const ctx = canvas.value.getContext("2d"); ctx.fillStyle = "white"; ctx.fillRect(0, 0, rect.width, rect.height); hasInk = false; }
async function acceptSignature() {
	if (!hasInk) { signatureError.value = "Draw a signature first."; return; }
	const data = canvas.value.toDataURL("image/png");
	if (signatureTarget.value === "donor") {
		try {
			const bound = await call(`${api}.bind_donation_donor_signature`, { details: { ...form, donor_signature_data: data, request_key: requestKey } });
			form.donor_signature_data = data;
			form.donor_signature_proof = bound.proof;
		} catch (e) { signatureError.value = e.message || String(e); return; }
	} else newSignatory.signature = data;
	signatureOpen.value = false;
}
watch(() => [form.donor, form.donor_name, form.donor_type, form.address, form.pan, form.mobile_number, form.email, form.amount, form.received_on, form.payment_method, form.payment_reference, form.cheque_cleared, form.received_into_account, form.donation_account], () => { if (form.donor_signature_data) { form.donor_signature_data = ""; form.donor_signature_proof = ""; message.value = "Donation details changed after signing. Ask the donor to sign again."; } });
watch(() => form.payment_method, (method) => { if (method === "Cash") form.payment_reference = ""; else form.cheque_cleared = false; });
onMounted(load);
</script>

<style scoped>
.form-card {
	@apply rounded-2xl border border-line bg-surface p-5 shadow-soft sm:p-7;
}
.form-title {
	@apply m-0 text-xl font-semibold leading-tight text-ink;
}
.form-hint {
	@apply mt-1 text-sm leading-relaxed text-muted;
}
.form-grid {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 1.35rem 1.5rem;
}
.full-width {
	grid-column: 1 / -1;
}
.field-label {
	@apply block text-sm font-medium leading-snug text-ink;
}
.field-input {
	@apply mt-2 block w-full rounded-xl border border-line bg-bg px-3 py-3 text-base font-normal text-ink;
	min-width: 0;
	min-height: 3rem;
}
textarea.field-input {
	min-height: 6rem;
	resize: vertical;
}
.field-input:focus {
	@apply border-accent outline-none ring-2 ring-accent;
}
.field-help {
	@apply block text-xs leading-relaxed text-muted;
}
.required {
	@apply text-bad;
}
.section-heading {
	display: flex;
	align-items: flex-start;
	gap: 1rem;
	margin-bottom: 1.6rem;
}
.step-number {
	@apply flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent-soft text-sm font-semibold text-accent;
}
.intro-note {
	@apply rounded-2xl border border-line border-l-4 border-l-accent bg-surface px-5 py-4 text-sm leading-relaxed text-ink;
}
.intro-note p {
	@apply mt-1 text-muted;
}
.saved-donor-note {
	@apply mt-3 rounded-xl bg-accent-soft px-4 py-3 text-sm text-ink;
}
.saved-donor-note button {
	@apply ml-2;
}
.section-footer {
	@apply mt-6 flex flex-wrap items-center gap-3 border-t border-line pt-5;
}
.checkbox-row {
	@apply flex items-start gap-3 rounded-xl border border-line bg-bg px-4 py-4 text-sm leading-relaxed text-ink;
}
.checkbox-row input {
	@apply mt-1 h-4 w-4 shrink-0;
}
.checkbox-row small {
	@apply mt-1 block text-xs text-muted;
}
.warning-note {
	@apply rounded-xl border border-warn bg-warn-soft px-4 py-3 text-sm text-warn;
}
.signature-panel {
	@apply flex flex-wrap items-center gap-4 rounded-xl border border-line bg-bg p-4;
}
.signature-panel > div {
	flex: 1 1 16rem;
}
.signature-preview {
	@apply max-h-20 max-w-60 rounded-lg border border-line bg-white p-1;
}
.issue-panel {
	@apply flex flex-wrap items-center justify-between gap-4 border-t border-line pt-6 text-sm leading-relaxed text-muted;
}
.issue-panel p {
	flex: 1 1 20rem;
}
.history-row {
	@apply flex flex-wrap justify-between gap-4 py-4 text-sm;
}
.history-row > div {
	@apply flex flex-col gap-1;
}
.history-row > div:last-child {
	@apply items-start sm:items-end;
}
.history-row span {
	@apply text-muted;
}
.setup-card summary {
	@apply cursor-pointer text-base font-semibold text-ink;
}
.setup-card[open] summary {
	@apply border-b border-line pb-4;
}
.message-error {
	@apply rounded-xl border border-bad bg-bad-soft p-4 text-sm text-bad;
}
.message-success {
	@apply rounded-xl border border-ok bg-ok-soft p-4 text-sm text-ink;
}
@media (max-width: 640px) {
	.form-grid {
		grid-template-columns: minmax(0, 1fr);
		gap: 1.15rem;
	}
	.form-card {
		padding: 1.25rem;
	}
	.issue-panel button {
		width: 100%;
	}
}
</style>
