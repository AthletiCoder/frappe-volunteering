<template>
	<div class="purchase-page mx-auto max-w-6xl space-y-6 pb-8">
		<PageHeader :title="order?.name || (editing ? 'New purchase order' : pageInfo.title)" :eyebrow="order || editing ? pageInfo.title : 'Purchasing'" :subtitle="order ? `${order.supplier_name} · ${order.project_name}` : pageInfo.subtitle">
			<template #actions>
				<button v-if="order || editing" class="btn-secondary" @click="goList">{{ pageInfo.title }}</button>
				<button v-else-if="workspaceView === 'requests' && workspace?.capabilities.create" class="btn-primary" @click="newOrder">Create purchase order</button>
			</template>
		</PageHeader>
		<p v-if="error" class="notice error" role="alert">{{ error }}</p>
		<p v-if="message" class="notice success" role="status">{{ message }}</p>
		<p v-if="loading" class="text-muted" role="status">Loading purchases…</p>
		<template v-if="workspace && !loading">
			<section v-if="workspaceView === 'accounts' && !workspace.advance_setup?.ready && workspace.capabilities.accounts" class="notice setup">
				<div><strong>Supplier advance accounting</strong><p class="mt-1">Enable the Vendor Advances asset ledger to track payments made before a supplier’s bill arrives.</p></div>
				<button v-if="workspace.advance_setup?.can_configure" class="btn-secondary mt-3" :disabled="saving" @click="enableAdvances">Enable supplier advances</button>
				<p v-else class="mt-2">An Accounts Manager can enable this here.</p>
			</section>

			<template v-if="!order && !editing">
				<section class="grid gap-3 sm:grid-cols-3">
					<div v-for="card in summaryCards" :key="card.label" class="summary"><span>{{ card.label }}</span><strong>{{ card.value }}</strong></div>
				</section>
				<section class="panel space-y-5">
					<div class="grid gap-4 sm:grid-cols-[1fr_15rem]">
						<label class="field-label">Find a purchase<input v-model="search" class="field-input" placeholder="Order, supplier or project" type="search" /></label>
						<label class="field-label">Show<select v-model="filter" class="field-input"><option v-for="option in filterOptions" :key="option.value" :value="option.value">{{ option.label }}</option></select></label>
					</div>
					<p v-if="!visibleOrders.length" class="empty">{{ pageInfo.empty }}</p>
					<button v-for="row in visibleOrders" :key="row.name" class="purchase-row" @click="openOrder(row.name)">
						<div class="min-w-0"><span class="text-xs text-muted">{{ row.name }} · {{ dateLabel(row.transaction_date) }}</span><h2 class="mt-1 font-semibold">{{ row.supplier_name }}</h2><p class="mt-1 text-sm text-muted">{{ row.project }} · {{ row.workflow_state }}</p></div>
						<div class="text-right"><strong>{{ money(row.grand_total) }}</strong><p class="mt-2 text-xs text-muted">{{ Math.round(row.per_received || 0) }}% received · {{ Math.round(row.per_billed || 0) }}% billed</p><span class="mt-2 block text-sm font-medium text-accent">Open purchase →</span></div>
					</button>
				</section>
			</template>

			<form v-if="editing" class="space-y-5" @submit.prevent="saveOrder(true)">
				<section class="panel"><h2 class="section-title">Supplier and project</h2><div class="fields mt-5">
					<SearchSelect v-model="form.supplier" label="Supplier *" :options="supplierOptions" placeholder="Find a registered supplier" empty-text="No matching supplier. An Accounts Manager can register one below." selection-error="Choose a registered supplier." :required="true" />
					<SearchSelect v-model="form.project" label="Project *" :options="workspace.projects" placeholder="Choose an active project" empty-text="No eligible active project is available." selection-error="Choose a project from the list." :required="true" />
					<label class="field-label">Order date *<input v-model="form.transaction_date" class="field-input" type="date" :max="workspace.today" required /></label>
					<label class="field-label">Expected delivery *<input v-model="form.schedule_date" class="field-input" type="date" required /></label>
					<label class="field-label sm:col-span-2">Purpose and order instructions<textarea v-model="form.terms" class="field-input" rows="3" placeholder="What is being purchased, where it should be delivered, and any agreed terms." /></label>
				</div></section>
				<section class="panel space-y-5"><div class="flex items-center justify-between gap-3"><h2 class="section-title">Items to purchase</h2><button type="button" class="btn-secondary" @click="form.items.push(blankItem())">Add item</button></div>
					<article v-for="(item, index) in form.items" :key="index" class="item-card space-y-4">
						<div class="flex items-center justify-between"><strong>Item {{ index + 1 }}</strong><button v-if="form.items.length > 1" type="button" class="text-sm text-bad" @click="form.items.splice(index, 1)">Remove item</button></div>
						<div class="fields"><SearchSelect v-model="item.item_code" label="Purchase item *" :options="itemOptions" placeholder="Search materials or services" empty-text="No matching item. An Accounts Manager can add one below." selection-error="Choose a purchase item from the list." :required="true" />
							<label class="field-label">Description<input v-model="item.description" class="field-input" placeholder="Specification or description" /></label>
							<label class="field-label">Quantity *<input v-model.number="item.qty" class="field-input" type="number" min="0.001" step="any" required /><small class="field-help">Unit: {{ itemMaster(item.item_code)?.stock_uom || 'Select an item' }}</small></label>
							<label class="field-label">{{ legacyTaxes ? 'Unit rate (INR) *' : 'Unit price including taxes (INR) *' }}<input v-model.number="item.rate" class="field-input" type="number" min="0.01" step="0.01" required /></label>
							<SearchSelect v-if="itemMaster(item.item_code)?.is_stock_item" v-model="item.warehouse" label="Receiving warehouse *" :options="warehouseOptions" placeholder="Choose a warehouse" empty-text="No eligible receiving warehouse is configured." selection-error="Choose a receiving warehouse." :required="true" />
						</div><p class="text-right font-semibold">{{ money(Number(item.qty || 0) * Number(item.rate || 0)) }}</p>
					</article>
					<div class="total"><span>{{ legacyTaxes ? 'Items total before existing taxes' : 'Total including taxes' }}</span><strong>{{ money(itemsTotal) }}</strong></div>
					<p class="field-help">{{ legacyTaxes ? 'This older draft keeps its existing tax configuration. No tax template can be added or changed here.' : 'Enter the final quoted prices, including any supplier taxes. No additional tax is added. Accounts may optionally record the included tax breakup with the supplier bill.' }}</p>
					<label class="field-label">Quotation or supporting document (optional)<input class="upload" type="file" accept=".pdf,.png,.jpg,.jpeg" @change="pickFile($event, 'order')" /><span v-if="proofs.order" class="field-help">{{ proofs.order.file_name }}</span></label>
				</section>
				<div class="action-bar"><button type="button" class="btn-secondary" :disabled="saving" @click="saveOrder(false)">Save draft</button><button type="submit" class="btn-primary" :disabled="saving">{{ saving ? 'Saving…' : 'Submit purchase for approval' }}</button></div>
			</form>

			<template v-else-if="order">
				<section class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
					<div class="summary"><span>Order total</span><strong>{{ money(order.grand_total) }}</strong><small>{{ order.workflow_state }}</small></div>
					<div class="summary"><span>Total paid</span><strong>{{ money(totalPaid) }}</strong><small>{{ order.payments.length }} recorded payments</small></div>
					<div class="summary"><span>Advance applied to bills</span><strong>{{ money(totalApplied) }}</strong><small>Included in total paid</small></div>
					<div class="summary"><span>Outstanding billed amount</span><strong>{{ money(totalOutstanding) }}</strong><small>{{ order.invoices.length }} supplier bills</small></div>
				</section>
				<section class="panel space-y-5">
					<div class="flex flex-wrap justify-between gap-3"><h2 class="section-title">Order and delivery</h2><span class="status-pill">{{ order.status }}</span></div>
					<div class="fields text-sm"><p><span class="text-muted">Ordered:</span> {{ dateLabel(order.transaction_date) }}</p><p><span class="text-muted">Expected:</span> {{ dateLabel(order.schedule_date) }}</p><p><span class="text-muted">Requested by:</span> {{ order.owner }}</p><p><span class="text-muted">Assigned approver:</span> {{ order.pending_approver || '—' }}</p></div>
					<div v-for="item in order.items" :key="item.name" class="item-card"><div class="flex flex-wrap justify-between gap-3"><div><strong>{{ item.item_name }}</strong><p class="mt-1 text-sm text-muted" v-text="plain(item.description)" /></div><strong>{{ money(item.amount) }}</strong></div><p class="mt-3 text-sm">{{ item.qty }} {{ item.uom }} × {{ money(item.rate) }} · {{ item.received_qty || 0 }} received</p></div>
					<p v-if="order.terms" class="whitespace-pre-wrap text-sm text-muted">{{ plain(order.terms) }}</p>
					<div class="total"><span>{{ legacyTaxes ? `Existing taxes ${money(order.tax_amount)}` : 'Total including taxes' }}</span><strong>{{ money(order.grand_total) }}</strong></div>
					<div class="flex flex-wrap gap-3">
						<button v-if="workspaceView === 'requests' && order.actions.edit" class="btn-secondary" @click="editOrder">Edit order</button>
						<button v-if="workspaceView !== 'approvals' && order.actions.receive" class="btn-primary" @click="startReceive">Record goods received</button>
						<button v-if="workspaceView === 'accounts' && order.actions.invoice" class="btn-primary" @click="startInvoice">Record supplier bill</button>
						<button v-if="workspaceView === 'accounts' && order.actions.pay && canPayAdvance" class="btn-secondary" @click="startPayment('')">Record supplier advance</button>
						<button v-if="workspaceView === 'accounts' && order.actions.pay && totalOutstanding > 0" class="btn-primary" @click="startPayment(order.invoices.find(row => Number(row.outstanding_amount) > 0).name)">Record bill payment</button>
					</div>
				</section>

				<form v-if="action === 'receive'" class="panel space-y-5" @submit.prevent="receiveGoods">
					<div class="flex items-center justify-between"><h2 class="section-title">Goods received</h2><button type="button" class="text-sm text-muted" @click="action = ''">Close</button></div>
					<div class="fields"><label class="field-label">Date received *<input v-model="delivery.posting_date" class="field-input" type="date" :max="workspace.today" required /></label><label class="field-label">Delivery note number<input v-model="delivery.delivery_note" class="field-input" /></label></div>
					<div v-for="row in delivery.items" :key="row.order_item" class="item-card fields items-center"><div><strong>{{ row.label }}</strong><p class="field-help">{{ row.maximum }} still to receive</p></div><label class="field-label">Quantity received now<input v-model.number="row.qty" class="field-input" type="number" min="0" :max="row.maximum" step="any" required /></label></div>
					<label class="field-label">Delivery proof (optional)<input type="file" class="upload" accept=".pdf,.png,.jpg,.jpeg" @change="pickFile($event, 'receive')" /></label>
					<div class="action-bar"><button class="btn-primary" :disabled="saving">{{ saving ? 'Recording…' : 'Confirm goods received' }}</button></div>
				</form>

				<form v-if="action === 'invoice'" class="panel space-y-5" @submit.prevent="recordBill">
					<div class="flex items-center justify-between"><h2 class="section-title">Supplier bill and account allocation</h2><button type="button" class="text-sm text-muted" @click="action = ''">Close</button></div>
					<p class="field-help">Record the full bill for this delivery. Advances paid against this order are applied automatically. The bill date determines the expense accounting date.</p>
					<label class="field-label">Goods receipt *<select v-model="bill.receipt" class="field-input" required @change="chooseReceipt"><option value="">Choose a delivery</option><option v-for="receipt in unbilledReceipts" :key="receipt.name" :value="receipt.name">{{ receipt.name }} · {{ dateLabel(receipt.posting_date) }}</option></select></label>
					<div class="fields"><label class="field-label">Supplier invoice number *<input v-model="bill.bill_no" class="field-input" required maxlength="140" /></label><label class="field-label">Invoice date *<input v-model="bill.bill_date" class="field-input" type="date" :max="workspace.today" required /></label><label class="field-label">Payment due date *<input v-model="bill.due_date" class="field-input" type="date" required /></label></div>
					<div v-for="row in bill.items" :key="row.receipt_item" class="item-card"><div class="flex flex-wrap justify-between gap-3"><strong>{{ row.label }}</strong><strong>{{ money(row.amount) }}</strong></div><p class="mt-2 text-sm text-muted">{{ row.qty }} × {{ money(row.rate) }}</p><SearchSelect v-model="row.expense_account" class="mt-4" label="Expense ledger *" :options="expenseOptions" :required="true" /></div>
					<section v-if="!legacyTaxes && workspace.capabilities.accounts" class="item-card space-y-5">
						<label class="flex items-start gap-3 text-sm font-semibold"><input v-model="bill.record_tax_breakup" type="checkbox" class="mt-1" /><span>Record included tax breakup (optional)</span></label>
						<p class="field-help">Accounts reference only. Sevamrita is not GST registered: all included taxes remain part of the purchase cost. This does not claim GST credit or increase the bill total.</p>
						<template v-if="bill.record_tax_breakup">
							<fieldset v-for="row in bill.items" :key="row.receipt_item" class="min-w-0 space-y-4 rounded-xl border border-line bg-surface p-4">
								<legend class="px-1 text-sm font-semibold">{{ row.label }} — {{ money(row.amount) }} including taxes</legend>
								<div class="fields"><label v-for="field in purchaseTaxFields" :key="field.key" class="field-label">{{ field.label }}<input v-model="row.tax_breakup[field.key]" class="field-input" type="number" min="0" :max="row.amount" step="0.01" inputmode="decimal" /></label></div>
								<p class="field-help">Value before included taxes: <strong>{{ money(purchaseTaxSummary([row]).base_total) }}</strong> · Included taxes: {{ money(purchaseTaxSummary([row]).tax_total) }}</p>
							</fieldset>
							<p v-if="billTaxSummary.error" class="notice error" role="alert">{{ billTaxSummary.error }}</p>
							<div v-else class="total"><span>Value before taxes {{ money(billTaxSummary.base_total) }} + included taxes {{ money(billTaxSummary.tax_total) }}</span><strong>Total unchanged: {{ money(billTaxSummary.gross_total) }}</strong></div>
						</template>
					</section>
					<div class="total"><span>Full bill total for this delivery</span><strong>{{ money(order.receipts.find(row => row.name === bill.receipt)?.grand_total) }}</strong></div>
					<p class="field-help">Unused advance available from this order: {{ money(Math.max(0, Number(order.advance_paid || 0) - totalApplied)) }}</p>
					<label class="field-label">Supplier bill *<input type="file" class="upload" accept=".pdf,.png,.jpg,.jpeg" required @change="pickFile($event, 'invoice')" /></label>
					<div class="action-bar"><button class="btn-primary" :disabled="saving || (bill.record_tax_breakup && !!billTaxSummary.error)">{{ saving ? 'Posting…' : 'Post supplier bill and apply advances' }}</button></div>
				</form>

				<form v-if="action === 'payment'" class="panel space-y-5" @submit.prevent="payVendor">
					<div class="flex items-center justify-between"><h2 class="section-title">{{ payment.invoice ? 'Record supplier bill payment' : 'Record supplier advance' }}</h2><button type="button" class="text-sm text-muted" @click="action = ''">Close</button></div>
					<div class="fields"><label v-if="payment.invoice" class="field-label">Supplier bill<select v-model="payment.invoice" class="field-input" @change="updatePaymentAmount"><option v-for="invoice in order.invoices.filter(row => Number(row.outstanding_amount) > 0)" :key="invoice.name" :value="invoice.name">{{ invoice.bill_no }} · {{ money(invoice.outstanding_amount) }} remaining</option></select></label><SearchSelect v-model="payment.paid_from" label="Pay from *" :options="paymentOptions" placeholder="Choose a bank or cash ledger" empty-text="No matching bank or cash ledger is available." selection-error="Choose a bank or cash ledger." :required="true" />
						<label class="field-label">Amount (INR) *<input v-model.number="payment.amount" class="field-input" type="number" min="0.01" :max="paymentMaximum" step="0.01" required /><small class="field-help">Maximum {{ money(paymentMaximum) }}</small></label>
						<label class="field-label">Payment posting date *<input v-model="payment.posting_date" class="field-input" type="date" :max="workspace.today" required /></label>
						<label class="field-label">Mode of payment<select v-model="payment.mode_of_payment" class="field-input"><option value="">Not specified</option><option v-for="mode in availableModes" :key="mode.name" :value="mode.name">{{ mode.name }}</option></select></label>
						<template v-if="paymentBank"><label class="field-label">Bank transaction reference *<input v-model="payment.reference_no" class="field-input" required /></label><label class="field-label">Transaction reference date *<input v-model="payment.reference_date" class="field-input" type="date" :max="workspace.today" required /></label></template>
					</div>
					<p v-if="paymentAccount?.account_type === 'Cash'" class="field-help">Cash payments are limited to {{ money(workspace.cash_payment_limit) }} under the current accounts settings.</p>
					<label class="flex items-start gap-3 text-sm"><input v-model="paymentConfirmed" class="mt-1" type="checkbox" required /><span>I confirm this money has been paid to the supplier.</span></label>
					<div class="action-bar"><button class="btn-primary" :disabled="saving || !paymentConfirmed">{{ saving ? 'Recording…' : 'Record payment' }}</button></div>
				</form>

				<section v-if="order.receipts.length" class="panel space-y-4"><h2 class="section-title">Delivery history</h2><article v-for="receipt in order.receipts" :key="receipt.name" class="item-card"><strong>{{ receipt.name }}</strong><p class="mt-1 text-sm text-muted">{{ dateLabel(receipt.posting_date) }}</p><p v-for="item in receipt.items" :key="item.name" class="mt-2 text-sm">{{ item.item_name }} · {{ item.qty }} received</p></article></section>
				<section v-if="order.invoices.length" class="panel space-y-4"><h2 class="section-title">Supplier bills</h2><article v-for="invoice in order.invoices" :key="invoice.name" class="item-card"><div class="flex flex-wrap justify-between gap-3"><div><strong>{{ invoice.bill_no }}</strong><p class="mt-1 text-sm text-muted">{{ invoice.name }} · {{ dateLabel(invoice.bill_date) }}</p></div><strong>{{ money(invoice.grand_total) }}</strong></div><div class="mt-4 fields text-sm"><p>Advance applied: {{ money(invoice.total_advance) }}</p><p>Still payable: <strong>{{ money(invoice.outstanding_amount) }}</strong></p></div>
					<details v-if="workspace.capabilities.accounts && invoice.tax_breakup" class="mt-5 rounded-xl border border-line bg-surface p-4"><summary class="cursor-pointer text-sm font-semibold">Included tax breakup — Accounts record</summary><p class="field-help">{{ invoice.tax_breakup.treatment }}. No GST credit is claimed.</p><div v-for="(row, index) in invoice.tax_breakup.items" :key="index" class="mt-4 space-y-2 border-t border-line pt-4 text-sm"><strong>{{ row.item_name }}</strong><div class="fields"><p>Value before taxes: {{ money(row.base_amount) }}</p><p>Tax-inclusive cost: {{ money(row.gross_amount) }}</p><p v-for="field in purchaseTaxFields" :key="field.key">{{ field.label }}: {{ money(row[field.key]) }}</p></div></div><p class="field-help">Recorded by {{ invoice.tax_breakup.recorded_by }} · {{ dateLabel(invoice.tax_breakup.recorded_on) }}</p></details>
				</article></section>
				<section v-if="order.payments.length" class="panel space-y-4"><h2 class="section-title">Payment history</h2><article v-for="entry in order.payments" :key="entry.name" class="item-card"><div class="flex flex-wrap justify-between gap-3"><div><strong>{{ entry.name }}</strong><p class="mt-1 text-sm text-muted">{{ dateLabel(entry.posting_date) }} · {{ entry.reference_no || 'Cash' }}</p><p class="mt-1 text-xs text-muted">{{ entry.paid_from }}</p></div><strong>{{ money(entry.paid_amount) }}</strong></div></article></section>
				<section v-if="order.attachments.length" class="panel space-y-3"><h2 class="section-title">Supporting documents</h2><a v-for="file in order.attachments" :key="file.file_url" :href="file.file_url" class="block break-words text-sm text-accent underline" target="_blank" rel="noopener">{{ file.file_name }} <span class="text-muted">· {{ file.attached_to_name }}</span></a></section>

				<section v-if="workspaceView === 'approvals' && order.actions.review" class="panel space-y-5"><h2 class="section-title">Review purchase order</h2><p class="field-help">{{ order.actions.approval_flags.can_approve ? 'This order is within your current approval authority.' : 'A higher authority is required for approval.' }}</p><label class="field-label">Review notes<textarea v-model="reviewNote" class="field-input" rows="3" /></label><div class="action-bar"><button v-if="order.actions.transitions.includes('Reject')" class="btn-secondary" :disabled="saving" @click="review('Reject')">Reject order</button><button v-if="order.actions.approval_flags.can_escalate" class="btn-secondary" :disabled="saving" @click="review('Escalate')">Escalate</button><button v-if="order.actions.transitions.includes('Approve')" class="btn-primary" :disabled="saving" @click="review('Approve')">Approve purchase order</button></div></section>
			</template>

			<details v-if="workspaceView === 'accounts' && workspace.capabilities.manage_suppliers && !order" class="panel"><summary class="cursor-pointer font-semibold">Add a supplier or purchase item</summary><div class="mt-5 fields items-start"><form class="space-y-4" @submit.prevent="createMaster('supplier')"><h2 class="section-title">Register a supplier</h2><label v-for="field in ['name', 'phone', 'address', 'pan', 'gstin']" :key="field" class="field-label">{{ { name: 'Supplier name *', phone: 'Phone *', address: 'Address *', pan: 'PAN *', gstin: 'GSTIN (if registered)' }[field] }}<input v-model="supplier[field]" class="field-input" :required="field !== 'gstin'" /></label><button class="btn-secondary" :disabled="saving">Save supplier</button></form><form class="space-y-4" @submit.prevent="createMaster('item')"><h2 class="section-title">Add a consumption or service item</h2><p class="field-help">For materials consumed by the project or services purchased.</p><label class="field-label">Item name *<input v-model="masterItem.name" class="field-input" required /></label><SearchSelect v-model="masterItem.uom" label="Unit of measure *" :options="(workspace.uoms || []).map(value => ({ value, label: value }))" :required="true" /><button class="btn-secondary" :disabled="saving">Save purchase item</button></form></div></details>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import PageHeader from '../components/PageHeader.vue';
import SearchSelect from '../components/SearchSelect.vue';
import { call } from '../lib/frappe';
import { loadHomePayload } from '../lib/home';
import { purchaseTaxFields, purchaseTaxSummary } from '../lib/purchaseTaxBreakup';

const props = defineProps({ workspaceView: { type: String, default: 'requests' } });
const API = 'volunteering.volunteering.vendor_purchases.';
const route = useRoute(), router = useRouter();
const pageInfo = computed(() => ({
	requests: { title: 'My purchase requests', path: '/vendor-purchases', subtitle: 'Raise a purchase request and track the orders you submitted. Approval and Accounts work have separate pages.', empty: 'No purchase requests match. Create a purchase order to begin.' },
	approvals: { title: 'Purchase approvals', path: '/purchase-approvals', subtitle: 'Review only the pending purchase requests assigned to you. This is separate from your own requests and Accounts processing.', empty: 'No pending purchase requests are assigned to you that match this search.' },
	accounts: { title: 'Approved purchases — Accounts', path: '/purchase-accounts', subtitle: 'Process approved purchase orders: supplier advances, deliveries, supplier bills and final payments.', empty: 'No approved purchase orders match these filters.' },
}[props.workspaceView]));
const workspace = ref(null), order = ref(null), loading = ref(true), saving = ref(false);
const error = ref(''), message = ref(''), editing = ref(false), action = ref(''), filter = ref(''), search = ref(''), reviewNote = ref('');
const key = () => crypto.randomUUID();
const blankItem = () => ({ item_code: '', description: '', qty: 1, rate: '', warehouse: '', expense_account: '' });
const blankOrder = () => ({ request_key: key(), supplier: '', project: '', transaction_date: workspace.value?.today || '', schedule_date: workspace.value?.today || '', terms: '', items: [blankItem()] });
const form = reactive(blankOrder()), delivery = reactive({}), bill = reactive({}), payment = reactive({});
const proofs = reactive({ order: null, receive: null, invoice: null });
const paymentConfirmed = ref(false);
const supplier = reactive({ name: '', phone: '', address: '', pan: '', gstin: '' }), masterItem = reactive({ name: '', uom: 'Nos' });
const supplierOptions = computed(() => (workspace.value?.suppliers || []).map(row => ({ value: row.name, label: row.supplier_name })));
const itemOptions = computed(() => (workspace.value?.items || []).map(row => ({ value: row.name, label: row.item_name, description: `${row.stock_uom} · ${row.is_stock_item ? 'Stock item' : 'Consumption / service'}` })));
const expenseOptions = computed(() => (workspace.value?.expense_accounts || []).map(row => ({ value: row.name, label: row.account_name })));
const warehouseOptions = computed(() => (workspace.value?.warehouses || []).map(row => ({ value: row.name, label: row.warehouse_name })));
const paymentOptions = computed(() => (workspace.value?.payment_accounts || []).map(row => ({ value: row.name, label: row.account_name, description: row.account_type })));
const itemMaster = code => workspace.value?.items.find(row => row.name === code);
const itemsTotal = computed(() => form.items.reduce((sum, row) => sum + Number(row.qty || 0) * Number(row.rate || 0), 0));
const legacyTaxes = computed(() => !!order.value && order.value.prices_include_tax === false);
const billTaxSummary = computed(() => purchaseTaxSummary(bill.items));
const filterOptions = computed(() => props.workspaceView === 'requests'
	? [{ value: '', label: 'All my requests' }, ...['Draft', 'Pending Approval', 'Approved', 'Rejected'].map(value => ({ value, label: value }))]
	: props.workspaceView === 'approvals' ? [{ value: '', label: 'Awaiting my approval' }]
		: [{ value: '', label: 'All approved orders' }, ...['Awaiting delivery', 'Awaiting bill', 'Awaiting payment', 'Received and billed'].map(value => ({ value, label: value }))]);
const summaryCards = computed(() => {
	const orders = workspace.value?.orders || [];
	if (props.workspaceView === 'requests') return [{ label: 'My requests', value: orders.length }, { label: 'Awaiting approval', value: orders.filter(row => row.workflow_state === 'Pending Approval').length }, { label: 'Drafts and rejected requests', value: orders.filter(row => ['Draft', 'Rejected'].includes(row.workflow_state)).length }];
	if (props.workspaceView === 'approvals') return [{ label: 'Assigned to me', value: orders.length }, { label: 'Total requested', value: money(orders.reduce((sum, row) => sum + Number(row.grand_total || 0), 0)) }, { label: 'Projects', value: new Set(orders.map(row => row.project)).size }];
	return [{ label: 'Approved orders', value: orders.length }, { label: 'Awaiting delivery', value: orders.filter(row => Number(row.per_received || 0) < 100).length }, { label: 'Bills awaiting payment', value: orders.filter(row => Number(row.outstanding_amount) > 0).length }];
});
const matchesFilter = row => !filter.value || (filter.value === 'Awaiting payment' ? Number(row.outstanding_amount) > 0
	: filter.value === 'Awaiting delivery' ? Number(row.per_received || 0) < 100
		: filter.value === 'Awaiting bill' ? Number(row.per_received || 0) > Number(row.per_billed || 0)
			: filter.value === 'Received and billed' ? Number(row.per_received) >= 100 && Number(row.per_billed) >= 100 : row.workflow_state === filter.value);
const visibleOrders = computed(() => (workspace.value?.orders || []).filter(row => matchesFilter(row) && `${row.name} ${row.supplier_name} ${row.project}`.toLowerCase().includes(search.value.toLowerCase())));
const totalPaid = computed(() => (order.value?.payments || []).reduce((sum, row) => sum + Number(row.paid_amount || 0), 0));
const totalApplied = computed(() => (order.value?.invoices || []).reduce((sum, row) => sum + Number(row.total_advance || 0), 0));
const totalOutstanding = computed(() => (order.value?.invoices || []).reduce((sum, row) => sum + Number(row.outstanding_amount || 0), 0));
const canPayAdvance = computed(() => workspace.value?.advance_setup?.ready && !order.value?.invoices.length && Number(order.value?.advance_paid || 0) < Number(order.value?.grand_total || 0));
const unbilledReceipts = computed(() => (order.value?.receipts || []).filter(row => row.items.some(item => Number(item.billed_amt || 0) + 0.005 < Number(item.amount))));
const paymentAccount = computed(() => workspace.value?.payment_accounts.find(row => row.name === payment.paid_from));
const paymentBank = computed(() => paymentAccount.value?.account_type === 'Bank');
const availableModes = computed(() => (workspace.value?.modes || []).filter(row => row.type === paymentAccount.value?.account_type));
const paymentMaximum = computed(() => payment.invoice ? Number(order.value?.invoices.find(row => row.name === payment.invoice)?.outstanding_amount || 0) : Number(order.value?.grand_total || 0) - Number(order.value?.advance_paid || 0));
const money = amount => new Intl.NumberFormat('en-IN', { style: 'currency', currency: workspace.value?.currency || 'INR' }).format(Number(amount || 0));
const dateLabel = date => date ? String(date).slice(0, 10).split('-').reverse().join('/') : '—';
const plain = html => String(html || '').replace(/<[^>]*>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>');

async function load() {
	loading.value = true; error.value = ''; action.value = '';
	try {
		// Clear the previous perspective before awaiting a restricted page, so a
		// denied route never leaves another page's orders or actions on screen.
		workspace.value = null; order.value = null; editing.value = false;
		if (route.query.new === '1' && props.workspaceView !== 'requests') { await router.replace({ path: '/vendor-purchases', query: { new: '1', project: route.query.project } }); return; }
		workspace.value = await call(`${API}get_purchase_workspace`, { view: props.workspaceView });
		filter.value = props.workspaceView === 'accounts' && route.query.view === 'payments' ? 'Awaiting payment' : '';
		order.value = route.query.order ? await readOrder(route.query.order) : null;
		editing.value = route.query.new === '1' && workspace.value.capabilities.create;
		if (route.query.new === '1' && !editing.value) throw new Error('Your account cannot raise purchase orders. You can still view your purchase history.');
		if (editing.value) {
			const project = workspace.value.projects.some(row => row.value === route.query.project) ? route.query.project : '';
			Object.assign(form, blankOrder(), { project });
		}
	} catch (e) { error.value = e.message; } finally { loading.value = false; }
}
const readOrder = name => call(`${API}get_purchase`, { name, view: props.workspaceView });
function goList() { return router.push(pageInfo.value.path); }
function openOrder(name) { router.push({ path: pageInfo.value.path, query: { order: name } }); }
function newOrder() { router.push({ path: '/vendor-purchases', query: { new: '1' } }); }
function editOrder() {
	Object.assign(form, { ...blankOrder(), supplier: order.value.supplier, project: order.value.project, transaction_date: order.value.transaction_date, schedule_date: order.value.schedule_date, terms: plain(order.value.terms), items: order.value.items.map(row => ({ item_code: row.item_code, description: plain(row.description), qty: row.qty, rate: row.rate, warehouse: row.warehouse || '', expense_account: row.expense_account || '' })) });
	editing.value = true;
}
async function run(task, success) {
	if (saving.value) return;
	saving.value = true; error.value = ''; message.value = '';
	try { await task(); message.value = success; await loadHomePayload().catch(() => {}); } catch (e) { error.value = e.message; } finally { saving.value = false; }
}
async function saveOrder(submit) {
	await run(async () => {
		const result = await call(`${API}save_purchase`, { details: { ...form, proof: proofs.order }, name: order.value?.name || null, modified: order.value?.modified || null, submit: submit ? 1 : 0 });
		order.value = await readOrder(result.name); editing.value = false; proofs.order = null;
		await router.replace({ path: '/vendor-purchases', query: { order: result.name } });
	}, submit ? 'Purchase submitted for approval.' : 'Purchase draft saved.');
}
async function enableAdvances() { await run(async () => { workspace.value.advance_setup = await call(`${API}configure_vendor_advances`); }, 'Supplier advance accounting is ready.'); }
async function review(decision) {
	await run(async () => { await call(`${API}review_purchase`, { name: order.value.name, modified: order.value.modified, action: decision, reason: reviewNote.value }); await goList(); }, `Purchase decision recorded: ${decision}.`);
}
function startReceive() {
	action.value = 'receive'; proofs.receive = null;
	Object.assign(delivery, { request_key: key(), posting_date: workspace.value.today, delivery_note: '', items: order.value.items.filter(row => Number(row.qty) > Number(row.received_qty || 0)).map(row => ({ order_item: row.name, label: row.item_name, qty: Number(row.qty) - Number(row.received_qty || 0), maximum: Number(row.qty) - Number(row.received_qty || 0) })) });
}
async function receiveGoods() {
	await run(async () => { const name = order.value.name; await call(`${API}record_goods_received`, { name, details: { request_key: delivery.request_key, posting_date: delivery.posting_date, delivery_note: delivery.delivery_note, items: delivery.items.map(({ order_item, qty }) => ({ order_item, qty })), proof: proofs.receive } }); order.value = await readOrder(name); action.value = ''; }, 'Goods receipt recorded.');
}
function startInvoice() { action.value = 'invoice'; proofs.invoice = null; Object.assign(bill, { request_key: key(), receipt: unbilledReceipts.value[0]?.name || '', bill_no: '', bill_date: workspace.value.today, due_date: workspace.value.today, record_tax_breakup: false, items: [] }); chooseReceipt(); }
function chooseReceipt() { const receipt = order.value.receipts.find(row => row.name === bill.receipt); bill.items = (receipt?.items || []).filter(row => Number(row.billed_amt || 0) + 0.005 < Number(row.amount)).map(row => ({ receipt_item: row.name, label: row.item_name, qty: row.qty, rate: row.rate, amount: row.amount, expense_account: row.expense_account || '', tax_breakup: { cgst: '', sgst: '', igst: '', other_tax: '' } })); }
async function recordBill() {
	if (bill.record_tax_breakup && billTaxSummary.value.error) { error.value = billTaxSummary.value.error; return; }
	const details = { request_key: bill.request_key, receipt: bill.receipt, bill_no: bill.bill_no, bill_date: bill.bill_date, due_date: bill.due_date, items: bill.items.map(({ receipt_item, expense_account }) => ({ receipt_item, expense_account })), proof: proofs.invoice };
	if (bill.record_tax_breakup) details.tax_breakup = billTaxSummary.value.items.map(({ receipt_item, cgst, sgst, igst, other_tax }) => ({ receipt_item, cgst, sgst, igst, other_tax }));
	await run(async () => { const name = order.value.name; await call(`${API}record_supplier_invoice`, { name, details }); order.value = await readOrder(name); action.value = ''; }, 'Supplier bill posted and available order advances applied.');
}
function startPayment(invoice) { action.value = 'payment'; paymentConfirmed.value = false; Object.assign(payment, { request_key: key(), invoice, paid_from: '', amount: '', posting_date: workspace.value.today, reference_no: '', reference_date: workspace.value.today, mode_of_payment: '' }); updatePaymentAmount(); }
function updatePaymentAmount() { payment.amount = paymentMaximum.value; }
async function payVendor() { await run(async () => { const name = order.value.name; await call(`${API}record_vendor_payment`, { name, details: { ...payment } }); order.value = await readOrder(name); action.value = ''; }, 'Supplier payment recorded.'); }
async function createMaster(kind) { await run(async () => { await call(`${API}create_purchase_master`, { kind, details: kind === 'supplier' ? { ...supplier } : { ...masterItem } }); workspace.value = await call(`${API}get_purchase_workspace`, { view: props.workspaceView }); }, `${kind === 'supplier' ? 'Supplier' : 'Purchase item'} saved.`); }
async function pickFile(event, target) {
	proofs[target] = null;
	const file = event.target.files?.[0]; if (!file) return;
	if (!/\.(pdf|png|jpe?g)$/i.test(file.name) || file.size > 5 * 1024 * 1024) { error.value = 'Choose a PDF, PNG or JPEG file up to 5 MB.'; event.target.value = ''; return; }
	try { const content = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(',')[1]); reader.onerror = reject; reader.readAsDataURL(file); }); proofs[target] = { file_name: file.name, content }; } catch { error.value = 'The document could not be read.'; }
}
watch(() => payment.paid_from, () => { payment.mode_of_payment = ''; });
watch(() => route.fullPath, load);
onMounted(load);
</script>

<style scoped>
.panel { @apply rounded-2xl border border-line bg-surface p-4 shadow-soft sm:p-6; }
.section-title { @apply text-lg font-semibold text-ink; }
.fields { @apply grid gap-5 sm:grid-cols-2; }
.field-label { @apply block min-w-0 text-sm font-medium text-ink; }
.field-input { @apply mt-2 block min-h-11 w-full min-w-0 rounded-xl border border-line bg-surface px-3 py-2.5 text-base font-normal text-ink; }
.field-help { @apply mt-2 block text-sm font-normal leading-relaxed text-muted; }
.summary { @apply min-w-0 rounded-2xl border border-line bg-surface p-5; }
.summary span { @apply block text-sm text-muted; }.summary strong { @apply mt-2 block text-xl font-bold text-ink; }.summary small { @apply mt-2 block text-xs text-muted; }
.purchase-row { @apply flex w-full flex-wrap items-start justify-between gap-4 rounded-xl border border-line p-4 text-left transition-colors hover:border-accent hover:bg-accent-soft; }
.item-card { @apply min-w-0 rounded-xl border border-line bg-bg p-4; }
.total { @apply flex flex-wrap items-center justify-between gap-3 rounded-xl bg-accent-soft p-4 text-sm; }
.action-bar { @apply flex flex-wrap justify-end gap-3; }.action-bar button { @apply w-full sm:w-auto; }
.notice { @apply rounded-xl border p-4 text-sm leading-relaxed; }.error { @apply border-bad bg-bad-soft text-bad; }.success { @apply border-ok bg-ok-soft text-ink; }.setup { @apply border-line bg-accent-soft text-ink; }
.status-pill { @apply rounded-full bg-accent-soft px-3 py-1 text-xs font-semibold text-accent; }
.upload { @apply mt-2 block w-full min-w-0 rounded-xl border border-line bg-bg p-3 text-sm font-normal; }
.empty { @apply rounded-xl bg-bg p-6 text-center text-sm text-muted; }
</style>
