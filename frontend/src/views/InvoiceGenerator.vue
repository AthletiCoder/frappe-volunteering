<template>
	<div class="max-w-5xl mx-auto">
		<PageHeader
			title="Prepare an invoice"
			subtitle="Prepare GST or non-GST documents for supplier or volunteer signature."
			eyebrow="Expenses"
		>
			<template #actions>
				<RouterLink to="/home" class="btn-secondary">Back to Home</RouterLink>
			</template>
		</PageHeader>

		<div v-if="loading" class="text-muted">Loading company details…</div>
		<form v-else class="space-y-5" @submit.prevent="generate">
			<section class="form-card">
				<h2 class="form-title">Invoice type</h2>
				<div class="grid sm:grid-cols-2 gap-3">
					<button
						v-for="option in invoiceTypes"
						:key="option.value"
						type="button"
						:class="[
							'choice-card',
							form.invoice_type === option.value ? 'choice-card-active' : '',
						]"
						@click="form.invoice_type = option.value"
					>
						<span class="font-semibold">{{ option.label }}</span>
						<span class="text-sm text-muted">{{ option.hint }}</span>
					</button>
				</div>
			</section>

			<section class="form-card">
				<h2 class="form-title">Invoice details</h2>
				<div class="form-grid">
					<label class="field-label"
						>Invoice number<input
							aria-label="Invoice number"
							aria-describedby="invoice-number-help"
							:value="
								result?.invoice_number || 'Assigned automatically on generation'
							"
							readonly
							class="field-input"
						/><span id="invoice-number-help" class="block text-xs text-muted mt-1"
							>Format: INV-YYYY-000001. Shared across all employees and invoice
							types, using the generation year.</span
						></label
					>
					<label class="field-label"
						>Invoice date *<input
							v-model="form.invoice_date"
							type="date"
							required
							class="field-input"
					/></label>
				</div>
			</section>

			<details class="form-card">
				<summary class="cursor-pointer text-lg font-semibold text-ink">
					Optional fields (if available)
				</summary>
				<p class="mt-3 mb-3 text-sm text-muted">
					Fill these only if the supplier or purchase documents provide them. Otherwise,
					leave them blank.
				</p>
				<div class="form-grid">
					<label class="field-label"
						>Buyer order number<input
							v-model.trim="form.buyer_order_number"
							maxlength="100"
							class="field-input"
					/></label>
					<label class="field-label"
						>Buyer order date<input
							v-model="form.buyer_order_date"
							type="date"
							class="field-input"
					/></label>
					<label class="field-label"
						>Supplier reference<input
							v-model.trim="form.supplier_reference"
							maxlength="140"
							class="field-input"
					/></label>
					<label class="field-label"
						>Dispatch document number<input
							v-model.trim="form.dispatch_document_number"
							maxlength="100"
							class="field-input"
					/></label>
					<label class="field-label"
						>Delivery note date<input
							v-model="form.delivery_note_date"
							type="date"
							class="field-input"
					/></label>
				</div>
			</details>

			<section class="form-card">
				<h2 class="form-title">Signature</h2>
				<div class="form-grid">
					<label class="field-label"
						>Who will sign? *<select
							aria-label="Who will sign? *"
							v-model="form.signer_type"
							required
							class="field-input"
						>
							<option value="SUPPLIER">Supplier / authorised representative</option>
							<option value="VOLUNTEER">Volunteer (me)</option>
						</select></label
					>
					<label v-if="!isVolunteer" class="field-label"
						>Supplier signatory name<input
							v-model.trim="form.authorised_signatory"
							maxlength="120"
							class="field-input"
					/></label>
					<label v-else class="field-label"
						>Volunteer name<input
							:value="form.volunteer.name"
							readonly
							class="field-input"
					/></label>
				</div>
				<p v-if="isVolunteer" class="mt-3 text-sm text-muted">
					You will sign an expense statement confirming your own expense details, not on
					behalf of the supplier. Attach the signed statement and available original
					bills to your claim. Receipt review and approval are still required.
					<span v-if="isGst"
						>This does not replace a supplier-issued GST tax invoice.</span
					>
				</p>
			</section>

			<section class="form-card">
				<h2 class="form-title">Supplier</h2>
				<p class="form-hint">
					Enter the supplier’s legal details, not the employee’s details.
				</p>
				<div class="form-grid">
					<label class="field-label sm:col-span-2"
						>Legal name *<input
							v-model.trim="form.supplier.name"
							required
							maxlength="160"
							class="field-input"
					/></label>
					<label class="field-label sm:col-span-2"
						>Address *<textarea
							v-model.trim="form.supplier.address"
							required
							maxlength="600"
							rows="3"
							class="field-input"
						></textarea>
					</label>
					<label class="field-label"
						>State *<input
							v-model.trim="form.supplier.state"
							required
							maxlength="100"
							class="field-input"
					/></label>
					<label class="field-label"
						>PIN code<input
							v-model.trim="form.supplier.pin_code"
							maxlength="12"
							inputmode="numeric"
							class="field-input"
					/></label>
					<label v-if="isGst" class="field-label"
						>GSTIN *<input
							v-model.trim="form.supplier.gstin"
							required
							maxlength="15"
							class="field-input uppercase"
							placeholder="22AAAAA0000A1Z5"
					/></label>
					<label v-else class="field-label"
						>PAN (optional)<input
							v-model.trim="form.supplier.pan"
							maxlength="10"
							class="field-input uppercase"
							placeholder="ABCDE1234F"
					/></label>
				</div>
			</section>

			<section class="form-card">
				<h2 class="form-title">Consignee and buyer</h2>
				<p class="form-hint">
					Buyer means the organisation purchasing the goods or services—normally
					Sevamrita Foundation, not the volunteer paying on its behalf. Consignee means
					the recipient of the goods. Select the relevant Sevamrita office instead of
					typing the company address manually.
				</p>
				<div v-if="officeAddresses.length" class="space-y-3">
					<label class="field-label"
						>Consignee office address *<select
							aria-label="Consignee office address *"
							v-model="form.consignee_address_name"
							required
							class="field-input"
							@change="applyOfficeAddress('consignee')"
						>
							<option
								v-for="address in officeAddresses"
								:key="address.name"
								:value="address.name"
							>
								{{ address.label }}
							</option>
						</select></label
					>
					<PartyFields v-model="form.consignee" :gst-required="false" readonly />
				</div>
				<div v-else class="rounded-xl border border-bad bg-bad-soft p-4 text-sm text-bad">
					No active Sevamrita office address is available. Ask an Accounts Manager to add
					one before generating an invoice.
				</div>
				<label class="mt-4 flex items-start gap-2 text-sm text-ink">
					<input
						v-model="form.buyer_same_as_consignee"
						type="checkbox"
						class="mt-0.5"
						@change="buyerSameChanged"
					/>
					Buyer is the same as consignee
				</label>
				<div v-if="!form.buyer_same_as_consignee" class="mt-5 pt-5 border-t border-line">
					<h3 class="font-semibold text-ink mb-3">Buyer details</h3>
					<label class="field-label"
						>Buyer office address *<select
							aria-label="Buyer office address *"
							v-model="form.buyer_address_name"
							required
							class="field-input"
							@change="applyOfficeAddress('buyer')"
						>
							<option
								v-for="address in officeAddresses"
								:key="address.name"
								:value="address.name"
							>
								{{ address.label }}
							</option>
						</select></label
					>
					<PartyFields v-model="form.buyer" :gst-required="false" readonly />
				</div>
			</section>

			<section class="form-card">
				<div class="flex items-center justify-between gap-3 mb-3">
					<div>
						<h2 class="form-title mb-0">Items</h2>
						<p class="form-hint">Enter HSN/SAC if available.</p>
					</div>
					<button
						type="button"
						class="btn-secondary"
						:disabled="form.items.length >= 20"
						@click="addItem"
					>
						Add item
					</button>
				</div>
				<div class="space-y-3">
					<div
						v-for="(item, index) in form.items"
						:key="item.key"
						class="rounded-xl border border-line bg-bg p-3"
					>
						<div class="flex items-center justify-between mb-2">
							<span class="text-sm font-semibold">Item {{ index + 1 }}</span
							><button
								v-if="form.items.length > 1"
								type="button"
								class="text-sm text-bad"
								@click="removeItem(index)"
							>
								Remove
							</button>
						</div>
						<div class="grid sm:grid-cols-12 gap-3">
							<label class="field-label sm:col-span-4"
								>Description *<input
									v-model.trim="item.description"
									required
									maxlength="300"
									class="field-input"
							/></label>
							<label class="field-label sm:col-span-2"
								>HSN/SAC (optional)<input
									v-model.trim="item.hsn_sac"
									maxlength="30"
									class="field-input"
							/></label>
							<label class="field-label sm:col-span-2"
								>Unit *<input
									v-model.trim="item.unit"
									required
									maxlength="20"
									class="field-input"
									placeholder="Nos, kg, hours…"
							/></label>
							<label class="field-label sm:col-span-2"
								>Quantity *<input
									v-model.number="item.quantity"
									required
									type="number"
									min="0.001"
									step="0.001"
									class="field-input"
							/></label>
							<label class="field-label sm:col-span-2"
								>Rate (INR) *<input
									v-model.number="item.rate"
									required
									type="number"
									min="0.01"
									step="0.01"
									class="field-input"
							/></label>
						</div>
						<p class="mt-2 text-right text-sm font-semibold">
							Amount: {{ money(itemAmount(item)) }}
						</p>
					</div>
				</div>
			</section>

			<section class="form-card">
				<h2 class="form-title">Charges and tax</h2>
				<div class="form-grid">
					<label class="field-label"
						>Transportation charges<input
							v-model.number="form.transportation_charges"
							type="number"
							min="0"
							step="0.01"
							class="field-input"
					/></label>
					<label class="field-label"
						>Other charges<input
							v-model.number="form.other_charges"
							type="number"
							min="0"
							step="0.01"
							class="field-input"
					/></label>
					<label v-if="isGst" class="field-label"
						>GST type *<select v-model="form.tax_mode" required class="field-input">
							<option value="CGST_SGST">Intra-state: CGST + SGST</option>
							<option value="IGST">Inter-state: IGST</option>
						</select></label
					>
					<label v-if="isGst" class="field-label"
						>GST rate *<select
							v-model.number="form.gst_rate"
							required
							class="field-input"
						>
							<option :value="0">0%</option>
							<option :value="5">5%</option>
							<option :value="12">12%</option>
							<option :value="18">18%</option>
							<option :value="28">28%</option>
						</select></label
					>
					<label v-if="isGst" class="field-label"
						>Place of supply *<input
							v-model.trim="form.place_of_supply"
							required
							maxlength="100"
							class="field-input"
					/></label>
					<label v-if="isGst" class="field-label flex items-center gap-2 mt-6"
						><input v-model="form.reverse_charge" type="checkbox" /> Tax payable on
						reverse charge</label
					>
				</div>
				<div
					class="mt-4 ml-auto max-w-sm rounded-xl border border-line overflow-hidden text-sm"
				>
					<div class="total-row">
						<span>Taxable total</span><strong>{{ money(taxableTotal) }}</strong>
					</div>
					<div v-if="isGst" class="total-row">
						<span>GST</span><strong>{{ money(gstAmount) }}</strong>
					</div>
					<div class="total-row bg-soft text-base">
						<span>Grand total</span><strong>{{ money(grandTotal) }}</strong>
					</div>
				</div>
			</section>

			<section class="form-card">
				<h2 class="form-title">Approved reimbursement remittance details</h2>
				<p class="form-hint">
					These are your employee reimbursement details—not the supplier's bank account.
					The full approved account number is included in the downloaded PDF and Word
					document. Bank details cannot be changed here.
				</p>
				<div v-if="approvedBank" class="grid sm:grid-cols-2 gap-3 text-sm">
					<p>
						<span class="block text-muted">Account holder</span
						><strong>{{ approvedBank.account_name }}</strong>
					</p>
					<p>
						<span class="block text-muted">Bank</span
						><strong>{{ approvedBank.bank_name }}</strong>
					</p>
					<p>
						<span class="block text-muted">Account number</span
						><strong>{{ approvedBank.account_number_masked }}</strong>
					</p>
					<p>
						<span class="block text-muted">IFSC</span
						><strong>{{ approvedBank.ifsc }}</strong>
					</p>
				</div>
				<p v-else class="rounded-xl bg-warn-soft p-3 text-sm">
					Submit your bank details and get Accounts Manager approval before generating an
					invoice.
				</p>
				<RouterLink
					to="/bank-account"
					class="inline-block mt-3 text-sm font-semibold text-accent"
					>Manage my reimbursement bank account</RouterLink
				>
			</section>

			<div
				v-if="error"
				class="rounded-xl border border-bad bg-bad-soft p-3 text-sm text-bad"
			>
				{{ error }}
			</div>
			<div v-if="result" class="rounded-2xl border border-ok bg-ok-soft p-4">
				<p class="font-semibold text-ink">Document files are ready</p>
				<p class="text-sm text-ink mt-1">
					Invoice number: <strong>{{ result.invoice_number }}</strong>
				</p>
				<p class="text-sm text-muted mt-1">{{ result.notice }}</p>
				<div class="flex flex-wrap gap-2 mt-3">
					<button
						v-if="result.pdf"
						type="button"
						class="btn-primary"
						@click="download(result.pdf)"
					>
						Download PDF
					</button>
					<button
						v-if="result.docx"
						type="button"
						class="btn-secondary"
						@click="download(result.docx)"
					>
						Download Word document
					</button>
				</div>
			</div>

			<div class="flex flex-wrap gap-3 justify-end pb-4">
				<button
					type="submit"
					name="output_format"
					value="pdf"
					class="btn-primary px-5 py-2.5"
					:disabled="generating || !approvedBank || !officeAddresses.length"
				>
					{{ generating === "pdf" ? "Generating PDF…" : "Generate PDF" }}
				</button>
				<button
					type="submit"
					name="output_format"
					value="docx"
					class="btn-secondary px-5 py-2.5"
					:disabled="generating || !approvedBank || !officeAddresses.length"
				>
					{{ generating === "docx" ? "Generating Word…" : "Generate Word" }}
				</button>
			</div>
		</form>
	</div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import { call } from "../lib/frappe";

const invoiceTypes = [
	{
		value: "NON_GST",
		label: "Non-GST invoice",
		hint: "For a bill without GST charges",
	},
	{ value: "GST", label: "GST tax invoice", hint: "For a GST-registered supplier" },
];
const blankParty = () => ({ name: "", address: "", state: "", pin_code: "", gstin: "", pan: "" });
let itemKey = 1;
const blankItem = () => ({
	key: itemKey++,
	description: "",
	hsn_sac: "",
	unit: "Nos",
	quantity: 1,
	rate: 0,
});
const form = reactive({
	invoice_type: "NON_GST",
	signer_type: "SUPPLIER",
	volunteer: { name: "", employee: "" },
	invoice_date: "",
	buyer_order_number: "",
	buyer_order_date: "",
	supplier_reference: "",
	dispatch_document_number: "",
	delivery_note_date: "",
	supplier: blankParty(),
	consignee_address_name: "",
	consignee: blankParty(),
	buyer_same_as_consignee: true,
	buyer_address_name: "",
	buyer: blankParty(),
	items: [blankItem()],
	transportation_charges: 0,
	other_charges: 0,
	tax_mode: "CGST_SGST",
	gst_rate: 18,
	place_of_supply: "",
	reverse_charge: false,
	authorised_signatory: "",
});
const loading = ref(true);
const generating = ref(null);
const generationReference = ref(null);
const generatedSnapshot = ref("");
const error = ref("");
const result = ref(null);
const approvedBank = ref(null);
const officeAddresses = ref([]);
const isGst = computed(() => form.invoice_type === "GST");
const isVolunteer = computed(() => form.signer_type === "VOLUNTEER");
const itemsTotal = computed(() => form.items.reduce((sum, item) => sum + itemAmount(item), 0));
const taxableTotal = computed(
	() =>
		itemsTotal.value +
		Number(form.transportation_charges || 0) +
		Number(form.other_charges || 0),
);
const gstAmount = computed(() =>
	isGst.value ? (taxableTotal.value * Number(form.gst_rate || 0)) / 100 : 0,
);
const grandTotal = computed(() => taxableTotal.value + gstAmount.value);

const PartyFields = defineComponent({
	name: "PartyFields",
	props: {
		modelValue: { type: Object, required: true },
		gstRequired: { type: Boolean, default: false },
		readonly: { type: Boolean, default: false },
	},
	emits: ["update:modelValue"],
	setup(props, { emit }) {
		const update = (key, value) =>
			emit("update:modelValue", { ...props.modelValue, [key]: value });
		const field = (key, label, options = {}) =>
			h("label", { class: options.wide ? "field-label sm:col-span-2" : "field-label" }, [
				label,
				h(options.multiline ? "textarea" : "input", {
					class: "field-input",
					value: props.modelValue[key],
					required: options.required,
					readonly: props.readonly,
					maxlength: options.maxlength,
					rows: options.multiline ? 3 : undefined,
					onInput: (event) => update(key, event.target.value),
				}),
			]);
		return () =>
			h("div", { class: "form-grid" }, [
				field("name", "Name *", { wide: true, required: true, maxlength: 160 }),
				field("address", "Address *", {
					wide: true,
					required: true,
					maxlength: 600,
					multiline: true,
				}),
				field("state", "State *", { required: true, maxlength: 100 }),
				field("pin_code", "PIN code", { maxlength: 12 }),
				field("gstin", props.gstRequired ? "GSTIN *" : "GSTIN", {
					required: props.gstRequired,
					maxlength: 15,
				}),
			]);
	},
});

function itemAmount(item) {
	return Number(item.quantity || 0) * Number(item.rate || 0);
}
function money(value) {
	return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(
		Number(value || 0),
	);
}
function addItem() {
	if (form.items.length < 20) form.items.push(blankItem());
}
function removeItem(index) {
	if (form.items.length > 1) form.items.splice(index, 1);
}

function applyOfficeAddress(target) {
	const field = target === "buyer" ? "buyer_address_name" : "consignee_address_name";
	const selected = officeAddresses.value.find((address) => address.name === form[field]);
	if (!selected) return;
	Object.assign(form[target], selected.party);
	if (target === "consignee") {
		form.place_of_supply = selected.party.state || "";
		if (form.buyer_same_as_consignee) {
			form.buyer_address_name = selected.name;
			Object.assign(form.buyer, selected.party);
		}
	}
}

function buyerSameChanged() {
	if (form.buyer_same_as_consignee) {
		form.buyer_address_name = form.consignee_address_name;
		Object.assign(form.buyer, form.consignee);
	} else if (!form.buyer_address_name) {
		form.buyer_address_name =
			form.consignee_address_name || officeAddresses.value[0]?.name || "";
		applyOfficeAddress("buyer");
	}
}

onMounted(async () => {
	try {
		const defaults = await call(
			"volunteering.volunteering.invoice_generator.get_invoice_generator_defaults",
		);
		approvedBank.value = defaults.remittance_bank || null;
		officeAddresses.value = defaults.office_addresses || [];
		Object.assign(form.volunteer, defaults.volunteer || {});
		form.invoice_date = defaults.invoice_date || "";
		form.consignee_address_name = defaults.default_office_address || "";
		form.buyer_address_name = defaults.default_office_address || "";
		Object.assign(form.consignee, defaults.consignee || {});
		Object.assign(form.buyer, defaults.consignee || {});
		form.place_of_supply = defaults.consignee?.state || "";
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		loading.value = false;
	}
});

async function generate(event) {
	if (generating.value) return;
	const outputFormat = event?.submitter?.value === "docx" ? "docx" : "pdf";
	const snapshot = JSON.stringify(form);
	const reference = snapshot === generatedSnapshot.value ? generationReference.value : null;
	error.value = "";
	generating.value = outputFormat;
	try {
		const generated = await call(
			"volunteering.volunteering.invoice_generator.generate_invoice_documents",
			{ payload: form, output_format: outputFormat, generation_reference: reference },
		);
		result.value =
			result.value?.invoice_number === generated.invoice_number
				? { ...result.value, ...generated }
				: generated;
		generationReference.value = generated.generation_reference;
		generatedSnapshot.value = snapshot;
		download(generated[outputFormat]);
		window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
	} catch (e) {
		generationReference.value = null;
		generatedSnapshot.value = "";
		error.value = e.message || String(e);
	} finally {
		generating.value = null;
	}
}

function download(file) {
	const bytes = Uint8Array.from(atob(file.content_base64), (char) => char.charCodeAt(0));
	const blob = new Blob([bytes], { type: file.content_type });
	const url = URL.createObjectURL(blob);
	const link = document.createElement("a");
	link.href = url;
	link.download = file.filename;
	document.body.appendChild(link);
	link.click();
	link.remove();
	setTimeout(() => URL.revokeObjectURL(url), 1000);
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
.choice-card {
	@apply text-left rounded-xl border border-line bg-bg p-4 flex flex-col gap-1 transition-colors;
}
.choice-card-active {
	@apply border-accent bg-accent-soft;
}
.total-row {
	@apply flex items-center justify-between gap-4 px-3 py-2 border-b border-line last:border-b-0;
}
button:disabled {
	@apply opacity-60 cursor-not-allowed;
}
</style>
