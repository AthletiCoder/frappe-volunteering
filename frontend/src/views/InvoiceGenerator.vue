<template>
	<div :class="embedded ? '' : 'max-w-5xl mx-auto'">
		<PageHeader
			v-if="!embedded"
			title="Prepare an invoice"
			subtitle="Prepare GST or non-GST documents with a volunteer reimbursement declaration."
			eyebrow="Expenses"
		>
			<template #actions>
				<RouterLink to="/home" class="btn-secondary">Back to Home</RouterLink>
			</template>
		</PageHeader>

		<div v-if="loading" class="text-muted">Loading company details…</div>
		<component
			:is="embedded ? 'div' : 'form'"
			v-else
			class="space-y-5"
			@submit.prevent="generate"
		>
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
				<h2 class="form-title">Supplier</h2>
				<p class="form-hint">
					Enter the supplier’s legal details, not the employee’s details.
				</p>
				<label v-if="vendorAddresses.length" class="field-label block mb-3"
					>Frequent vendor address<select
						v-model="selectedVendorAddress"
						aria-label="Frequent vendor address"
						class="field-input"
						@change="applyVendorAddress"
					>
						<option value="">Enter a new vendor address</option>
						<option
							v-for="vendor in vendorAddresses"
							:key="vendor.name"
							:value="vendor.name"
						>
							{{ vendor.label }}
						</option>
					</select>
					<span class="block text-xs text-muted mt-1"
						>Supplier addresses and any bank details used with them are saved privately
						for your next invoice.</span
					></label
				>
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
				<h2 class="form-title">Supplier bank details (optional)</h2>
				<p class="form-hint">
					Use the supplier’s account—not the employee reimbursement account. Leave all
					fields blank when remittance details are not needed; the invoice will omit this
					section completely.
				</p>
				<div class="form-grid">
					<label class="field-label"
						>Account holder name<input
							v-model.trim="form.bank.account_name"
							maxlength="160"
							class="field-input"
					/></label>
					<label class="field-label"
						>Bank name<input
							v-model.trim="form.bank.bank_name"
							maxlength="140"
							class="field-input"
					/></label>
					<label class="field-label"
						>Account number<input
							v-model.trim="form.bank.account_number"
							maxlength="50"
							inputmode="numeric"
							class="field-input"
					/></label>
					<label class="field-label"
						>IFSC<input
							v-model.trim="form.bank.ifsc"
							maxlength="20"
							class="field-input uppercase"
					/></label>
					<label class="field-label"
						>Branch<input
							v-model.trim="form.bank.branch"
							maxlength="140"
							class="field-input"
					/></label>
					<label class="field-label"
						>SWIFT code<input
							v-model.trim="form.bank.swift"
							maxlength="20"
							class="field-input uppercase"
					/></label>
					<label class="field-label sm:col-span-2"
						>UPI ID<input
							v-model.trim="form.bank.upi_id"
							maxlength="100"
							class="field-input"
					/></label>
				</div>
			</section>

			<section class="form-card">
				<h2 class="form-title">Sevamrita office</h2>
				<div v-if="officeAddresses.length" class="space-y-3">
					<label class="field-label"
						>Office address *<select
							aria-label="Office address *"
							v-model="form.consignee_address_name"
							required
							class="field-input"
							@change="applyOfficeAddress"
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
					<address class="rounded-xl bg-soft p-3 text-sm not-italic text-ink">
						<strong class="block">{{ form.consignee.name }}</strong>
						{{ form.consignee.address }}<br />
						{{ form.consignee.state }} {{ form.consignee.pin_code }}
					</address>
				</div>
				<div v-else class="rounded-xl border border-bad bg-bad-soft p-4 text-sm text-bad">
					No active Sevamrita office address is available. Ask an Accounts Manager to add
					one before generating an invoice.
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
							<label class="field-label sm:col-span-5"
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
								>Quantity *<input
									v-model.number="item.quantity"
									required
									type="number"
									min="0.001"
									step="0.001"
									class="field-input"
							/></label>
							<label class="field-label sm:col-span-3"
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
						>GST amount<input
							v-model.number="form.gst_amount"
							type="number"
							min="0"
							step="0.01"
							required
							class="field-input"
					/></label>
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
				<h2 class="form-title">Volunteer declaration and signature</h2>
				<p class="form-hint">
					I confirm that I paid the amount shown above and request reimbursement to my
					bank account.
				</p>
				<div class="form-grid">
					<label class="field-label"
						>Volunteer name<input
							:value="form.volunteer.name"
							readonly
							class="field-input"
					/></label>
				</div>
				<div class="mt-4 rounded-xl border border-line bg-bg p-3">
					<div class="flex flex-wrap items-center justify-between gap-3">
						<div>
							<p class="font-medium text-ink">Volunteer signature *</p>
							<p class="text-xs text-muted">
								Required for every invoice. Reuse your saved signature or sign freshly.
							</p>
							<p v-if="savedVolunteerSignature" class="text-xs text-ok mt-1">
								A saved signature is available for reuse.
							</p>
						</div>
						<div class="flex flex-wrap gap-2">
							<button
								v-if="savedVolunteerSignature"
								type="button"
								class="btn-secondary"
								@click="useSavedVolunteerSignature"
							>
								Use saved signature
							</button>
							<button
								type="button"
								class="btn-secondary"
								@click="openSignature('volunteer')"
							>
								Sign freshly
							</button>
						</div>
					</div>
					<img
						v-if="form.volunteer_signature_data"
						:src="form.volunteer_signature_data"
						alt="Volunteer signature preview"
						class="signature-preview mt-3"
					/>
					<p v-if="volunteerSignatureSource" class="text-xs text-muted mt-2">
						{{ volunteerSignatureSource === "saved" ? "Using saved signature" : "Using fresh signature" }}
					</p>
				</div>

				<div class="mt-4 rounded-xl border border-line bg-bg p-3">
					<label class="flex items-start gap-3 text-sm font-medium text-ink">
						<input v-model="form.vendor_will_sign" type="checkbox" class="mt-1" />
						<span>
							Vendor will also sign this invoice
							<span class="block text-xs font-normal text-muted"
								>Optional. If left unchecked, no vendor declaration or signature block
								will appear in the invoice.</span
							>
						</span>
					</label>
					<div v-if="form.vendor_will_sign" class="mt-4 space-y-3">
						<label class="field-label"
							>Vendor signatory name (optional)<input
								v-model.trim="form.authorised_signatory"
								maxlength="120"
								class="field-input"
						/></label>
						<div class="flex flex-wrap gap-2">
							<button
								type="button"
								class="btn-secondary"
								@click="openSignature('vendor')"
							>
								{{ form.vendor_signature_data ? "Sign freshly again" : "Vendor sign on screen" }}
							</button>
						</div>
						<img
							v-if="form.vendor_signature_data"
							:src="form.vendor_signature_data"
							alt="Vendor signature preview"
							class="signature-preview"
						/>
					</div>
				</div>
			</section>

			<div
				v-if="error"
				class="rounded-xl border border-bad bg-bad-soft p-3 text-sm text-bad"
			>
				{{ error }}
			</div>
			<div v-if="result && !embedded" class="rounded-2xl border border-ok bg-ok-soft p-4">
				<p class="font-semibold text-ink">Document files are ready</p>
				<p class="text-sm text-ink mt-1">
					Invoice number: <strong>{{ result.invoice_number }}</strong>
				</p>
				<p v-if="result.notice" class="text-sm text-muted mt-1">{{ result.notice }}</p>
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

			<div v-if="!embedded" class="flex flex-wrap gap-3 justify-end pb-4">
				<button
					type="submit"
					name="output_format"
					value="pdf"
					class="btn-primary px-5 py-2.5"
					:disabled="generating || !officeAddresses.length"
				>
					{{ generating === "pdf" ? "Generating PDF…" : "Generate PDF" }}
				</button>
				<button
					type="submit"
					name="output_format"
					value="docx"
					class="btn-secondary px-5 py-2.5"
					:disabled="generating || !officeAddresses.length"
				>
					{{ generating === "docx" ? "Generating Word…" : "Generate Word" }}
				</button>
			</div>
		</component>
		<div
			v-if="signatureOpen"
			class="signature-modal"
			role="dialog"
			aria-modal="true"
			aria-labelledby="signature-dialog-title"
		>
			<div class="signature-dialog">
				<h2 id="signature-dialog-title" class="form-title">
					{{ activeSignatureKind === "vendor" ? "Vendor sign on screen" : "Volunteer sign on screen" }}
				</h2>
				<p class="form-hint">
					Use a finger, stylus or mouse. The white panel is the signature area.
				</p>
				<canvas
					ref="signatureCanvas"
					class="signature-canvas"
					@pointerdown="startSignature"
					@pointermove="drawSignature"
					@pointerup="stopSignature"
					@pointercancel="stopSignature"
					@pointerleave="stopSignature"
				></canvas>
				<p v-if="signatureError" class="text-sm text-bad mt-2">{{ signatureError }}</p>
				<div class="flex flex-wrap justify-end gap-2 mt-4">
					<button type="button" class="btn-secondary" @click="clearSignatureCanvas">
						Clear
					</button>
					<button type="button" class="btn-secondary" @click="closeSignature">
						Cancel
					</button>
					<button type="button" class="btn-primary" @click="saveSignature">
						Use this signature
					</button>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import { call } from "../lib/frappe";

const props = defineProps({
	embedded: { type: Boolean, default: false },
	seed: { type: Object, default: null },
});
const emit = defineEmits(["total-change"]);
const embedded = computed(() => props.embedded);

const invoiceTypes = [
	{
		value: "NON_GST",
		label: "Non-GST invoice",
		hint: "For a bill without GST charges",
	},
	{ value: "GST", label: "GST tax invoice", hint: "For a GST-registered supplier" },
];
const blankParty = () => ({ name: "", address: "", state: "", pin_code: "", gstin: "", pan: "" });
const blankBank = () => ({
	account_name: "",
	bank_name: "",
	account_number: "",
	ifsc: "",
	branch: "",
	swift: "",
	upi_id: "",
});
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
	volunteer: { name: "", employee: "" },
	invoice_date: "",
	buyer_order_number: "",
	buyer_order_date: "",
	supplier_reference: "",
	dispatch_document_number: "",
	delivery_note_date: "",
	supplier: blankParty(),
	bank: blankBank(),
	consignee_address_name: "",
	consignee: blankParty(),
	items: [blankItem()],
	transportation_charges: 0,
	other_charges: 0,
	gst_amount: 0,
	vendor_will_sign: false,
	authorised_signatory: "",
	volunteer_signature_data: "",
	vendor_signature_data: "",
});
const loading = ref(true);
const generating = ref(null);
const generationReference = ref(null);
const generatedSnapshot = ref("");
const error = ref("");
const result = ref(null);
const officeAddresses = ref([]);
const vendorAddresses = ref([]);
const selectedVendorAddress = ref("");
const savedVolunteerSignature = ref("");
const volunteerSignatureSource = ref("");
const signatureOpen = ref(false);
const signatureCanvas = ref(null);
const signatureError = ref("");
const activeSignatureKind = ref("volunteer");
let signing = false;
let signatureHasInk = false;
const isGst = computed(() => form.invoice_type === "GST");
const itemsTotal = computed(() => form.items.reduce((sum, item) => sum + itemAmount(item), 0));
const taxableTotal = computed(
	() =>
		itemsTotal.value +
		Number(form.transportation_charges || 0) +
		Number(form.other_charges || 0),
);
const gstAmount = computed(() => (isGst.value ? Number(form.gst_amount || 0) : 0));
const grandTotal = computed(() => taxableTotal.value + gstAmount.value);

watch(grandTotal, (value) => emit("total-change", Number(value || 0)), { immediate: true });

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

function applyOfficeAddress() {
	const selected = officeAddresses.value.find(
		(address) => address.name === form.consignee_address_name,
	);
	if (!selected) return;
	Object.assign(form.consignee, selected.party);
}

function applyVendorAddress() {
	if (!selectedVendorAddress.value) {
		Object.assign(form.supplier, blankParty());
		Object.assign(form.bank, blankBank());
		return;
	}
	const selected = vendorAddresses.value.find(
		(vendor) => vendor.name === selectedVendorAddress.value,
	);
	if (selected) {
		Object.assign(form.supplier, blankParty(), selected.party);
		Object.assign(form.bank, blankBank(), selected.bank || {});
	}
}

function rememberGeneratedVendor(vendor) {
	if (!vendor?.name) return;
	const index = vendorAddresses.value.findIndex((row) => row.name === vendor.name);
	if (index === -1) vendorAddresses.value.unshift(vendor);
	else vendorAddresses.value.splice(index, 1, vendor);
	selectedVendorAddress.value = vendor.name;
}

function canvasPoint(event) {
	const rect = signatureCanvas.value.getBoundingClientRect();
	return { x: event.clientX - rect.left, y: event.clientY - rect.top };
}
async function openSignature(kind) {
	activeSignatureKind.value = kind === "vendor" ? "vendor" : "volunteer";
	signatureOpen.value = true;
	signatureError.value = "";
	await nextTick();
	const canvas = signatureCanvas.value;
	const rect = canvas.getBoundingClientRect();
	const scale = Math.min(window.devicePixelRatio || 1, 2);
	canvas.width = Math.round(rect.width * scale);
	canvas.height = Math.round(rect.height * scale);
	const context = canvas.getContext("2d");
	context.setTransform(scale, 0, 0, scale, 0, 0);
	context.fillStyle = "white";
	context.fillRect(0, 0, rect.width, rect.height);
	context.strokeStyle = "#111827";
	context.lineWidth = 2.4;
	context.lineCap = "round";
	context.lineJoin = "round";
	signatureHasInk = false;
}
function startSignature(event) {
	event.preventDefault();
	signing = true;
	signatureHasInk = true;
	signatureCanvas.value.setPointerCapture?.(event.pointerId);
	const point = canvasPoint(event);
	const context = signatureCanvas.value.getContext("2d");
	context.beginPath();
	context.moveTo(point.x, point.y);
}
function drawSignature(event) {
	if (!signing) return;
	event.preventDefault();
	const point = canvasPoint(event);
	const context = signatureCanvas.value.getContext("2d");
	context.lineTo(point.x, point.y);
	context.stroke();
}
function stopSignature() {
	signing = false;
}
function clearSignatureCanvas() {
	const canvas = signatureCanvas.value;
	const rect = canvas.getBoundingClientRect();
	const context = canvas.getContext("2d");
	context.fillStyle = "white";
	context.fillRect(0, 0, rect.width, rect.height);
	context.beginPath();
	signatureHasInk = false;
	signatureError.value = "";
}
function saveSignature() {
	if (!signatureHasInk) {
		signatureError.value = "Draw a signature before using it.";
		return;
	}
	const value = signatureCanvas.value.toDataURL("image/png");
	if (activeSignatureKind.value === "vendor") {
		form.vendor_signature_data = value;
	} else {
		form.volunteer_signature_data = value;
		volunteerSignatureSource.value = "fresh";
	}
	signatureOpen.value = false;
}
function closeSignature() {
	signatureOpen.value = false;
	signing = false;
}
function useSavedVolunteerSignature() {
	if (!savedVolunteerSignature.value) return;
	form.volunteer_signature_data = savedVolunteerSignature.value;
	volunteerSignatureSource.value = "saved";
}

onMounted(async () => {
	try {
		const defaults = await call(
			"volunteering.volunteering.invoice_generator.get_invoice_generator_defaults",
		);
		officeAddresses.value = defaults.office_addresses || [];
		vendorAddresses.value = defaults.vendor_addresses || [];
		savedVolunteerSignature.value = defaults.saved_volunteer_signature || "";
		Object.assign(form.volunteer, defaults.volunteer || {});
		form.invoice_date = defaults.invoice_date || "";
		form.consignee_address_name = defaults.default_office_address || "";
		Object.assign(form.consignee, defaults.consignee || {});
		applySeed(props.seed);
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		loading.value = false;
	}
});

watch(
	() => props.seed,
	(seed) => {
		if (!loading.value) applySeed(seed);
	},
	{ deep: true },
);

watch(
	() => form.vendor_will_sign,
	(enabled) => {
		if (!enabled) {
			form.authorised_signatory = "";
			form.vendor_signature_data = "";
		}
	},
);

function applySeed(seed) {
	if (!seed) return;
	if (seed.expense_date && !form.invoice_date) form.invoice_date = seed.expense_date;
	if (seed.description && !form.items[0]?.description) {
		form.items[0].description = seed.description;
	}
}

function getSubmissionPayload() {
	if (loading.value) throw new Error("Invoice details are still loading.");
	if (!officeAddresses.value.length) {
		throw new Error("A Sevamrita office address is required before submitting this invoice.");
	}
	if (!form.volunteer_signature_data) {
		throw new Error("Add the volunteer signature before submitting this invoice.");
	}
	if (form.vendor_will_sign && !form.vendor_signature_data) {
		throw new Error("Ask the vendor to sign on screen, or turn off vendor signing.");
	}
	return JSON.parse(JSON.stringify(form));
}

defineExpose({ getSubmissionPayload });

async function generate(event) {
	if (generating.value) return;
	const outputFormat = event?.submitter?.value === "docx" ? "docx" : "pdf";
	const snapshot = JSON.stringify(form);
	const reference = snapshot === generatedSnapshot.value ? generationReference.value : null;
	error.value = "";
	generating.value = outputFormat;
	try {
		getSubmissionPayload();
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
		savedVolunteerSignature.value = form.volunteer_signature_data;
		volunteerSignatureSource.value = "saved";
		rememberGeneratedVendor(generated.vendor_address);
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
.signature-preview {
	display: block;
	width: min(100%, 30rem);
	height: 8rem;
	object-fit: contain;
	object-position: left center;
	background: white;
	border: 1px solid var(--line);
	border-radius: 0.75rem;
}
.signature-modal {
	@apply fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4;
}
.signature-dialog {
	@apply w-full max-w-3xl rounded-2xl border border-line bg-surface p-4 sm:p-6 shadow-xl;
}
.signature-canvas {
	display: block;
	width: 100%;
	height: min(34vh, 15rem);
	background: white;
	border: 2px solid var(--line);
	border-radius: 0.75rem;
	touch-action: none;
	cursor: crosshair;
}
button:disabled {
	@apply opacity-60 cursor-not-allowed;
}
</style>
