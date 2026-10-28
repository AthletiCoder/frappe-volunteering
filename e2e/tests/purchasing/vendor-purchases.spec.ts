import { expect, test, type Page } from '@playwright/test';

const today = '2026-10-21';
function workspace(accounts = false, orders: any[] = []) {
	return {
		today, currency: 'INR', orders,
		projects: [{ value: 'PROJ-QA', label: 'Pune community kitchen' }],
		suppliers: [{ name: 'SUP-QA', supplier_name: 'Shree Ganesh Kitchen Supplies' }],
		items: [{ name: 'STEEL-PLATE', item_name: 'Steel plates', stock_uom: 'Nos', is_stock_item: 0 }],
		warehouses: [], tax_templates: [], uoms: ['Nos'],
		expense_accounts: accounts ? [{ name: 'Programme Materials - SF', account_name: 'Programme Materials' }] : [],
		payment_accounts: accounts ? [{ name: 'SF Axis Bank - SF', account_name: 'SF Axis Bank', account_type: 'Bank' }] : [],
		modes: [], capabilities: { accounts, create: true, manage_suppliers: accounts },
		advance_setup: { ready: true, can_configure: accounts },
	};
}
function purchase(accounts = false) {
	return {
		name: 'PUR-ORD-QA', modified: '2026-10-21 12:00:00', supplier: 'SUP-QA', supplier_name: 'Shree Ganesh Kitchen Supplies',
		project: 'PROJ-QA', project_name: 'Pune community kitchen', owner: 'arjun@example.com', pending_approver: 'vikram@example.com',
		docstatus: 1, workflow_state: 'Approved', status: 'To Receive and Bill', transaction_date: today, schedule_date: today,
		currency: 'INR', net_total: 1000, tax_amount: 0, grand_total: 1000, advance_paid: 0,
		prices_include_tax: true,
		items: [{ name: 'POI-1', item_code: 'STEEL-PLATE', item_name: 'Steel plates', description: 'Stainless steel dinner plates', qty: 10, uom: 'Nos', rate: 100, amount: 1000, received_qty: 0 }],
		receipts: [] as any[], invoices: [] as any[], payments: [] as any[], attachments: [] as any[],
		actions: { edit: false, review: false, transitions: [] as string[], approval_flags: {}, receive: true, invoice: false, pay: accounts },
	};
}
async function choose(page: Page, label: string, value: string) {
	await page.getByRole('combobox', { name: label, exact: true }).fill(value);
	await page.getByRole('listbox', { name: label, exact: true }).getByRole('option').first().click();
}
async function mock(page: Page, data: any, current: any, onCall?: (name: string, payload: any) => any) {
	await page.route('**/api/method/**', async route => {
		const name = new URL(route.request().url()).pathname.split('.').pop() || '';
		const payload = route.request().postDataJSON() || {};
		let result: any = {};
		if (name === 'get_home_payload') result = { allowed: true, full_name: 'Arjun Sharma', waiting_count: 0, nav: {}, flags: {}, actions: { purchasing: [{ id: 'vendor_purchases', label: 'Vendor purchases', route: '/volunteering/vendor-purchases' }] } };
		else if (name === 'get_purchase_workspace') result = data;
		else if (name === 'get_purchase') result = current;
		else if (onCall) result = onCall(name, payload) || {};
		await route.fulfill({ json: { message: result } });
	});
}

test('employee creates and submits a Home purchase order with the selected project and supplier', async ({ page }) => {
	const data = workspace();
	const current = purchase();
	let submitted: any;
	current.workflow_state = 'Pending Approval'; current.docstatus = 0;
	current.actions.receive = false;
	await mock(page, data, current, (name, payload) => {
		if (name === 'save_purchase') { submitted = payload; return current; }
	});
	await page.goto('/volunteering/vendor-purchases');
	await page.getByRole('button', { name: 'Create purchase order', exact: true }).click();
	await choose(page, 'Supplier *', 'Ganesh');
	await choose(page, 'Project *', 'Pune');
	await choose(page, 'Purchase item *', 'Steel');
	await page.getByRole('spinbutton', { name: /^Quantity/ }).fill('10');
	await page.getByLabel('Unit price including taxes (INR) *', { exact: true }).fill('100');
	await expect(page.getByLabel('Purchase tax template', { exact: true })).toHaveCount(0);
	await expect(page.getByRole('checkbox', { name: 'Record included tax breakup (optional)' })).toHaveCount(0);
	await page.getByLabel('Purpose and order instructions').fill('Plates for the community meal programme');
	await page.getByRole('button', { name: 'Submit purchase for approval', exact: true }).click();
	await expect(page.getByRole('heading', { name: 'PUR-ORD-QA', exact: true })).toBeVisible();
	expect(submitted.submit).toBe(1);
	expect(submitted.details.project).toBe('PROJ-QA');
	expect(submitted.details.items[0].qty).toBe(10);
	expect(submitted.details).not.toHaveProperty('taxes_and_charges');
	await expect(page.getByRole('button', { name: 'Record supplier advance', exact: true })).toHaveCount(0);
});

test('assigned manager reviews at the bottom of the purchase detail', async ({ page }) => {
	const current = purchase();
	current.docstatus = 0; current.workflow_state = 'Pending Approval';
	current.actions.review = true; current.actions.receive = false;
	current.actions.transitions = ['Approve', 'Reject'];
	current.actions.approval_flags = { can_approve: true };
	let reviewed: any;
	await mock(page, workspace(false, [current]), current, (name, payload) => {
		if (name === 'review_purchase') { reviewed = payload; current.workflow_state = 'Approved'; current.actions.review = false; return current; }
	});
	await page.goto('/volunteering/purchase-approvals?order=PUR-ORD-QA');
	await page.getByLabel('Review notes').fill('Quantities and supplier quotation checked.');
	await page.getByRole('button', { name: 'Approve purchase order', exact: true }).click();
	await expect(page.getByRole('status')).toContainText('Approve');
	expect(reviewed.action).toBe('Approve');
	expect(reviewed.modified).toBe('2026-10-21 12:00:00');
});

test('Accounts records advance, delivery, full bill, then its remaining payment in Home', async ({ page }) => {
	const current = purchase(true);
	let paid = 0, received = false, billed = false;
	await mock(page, workspace(true, [current]), current, (name, payload) => {
		if (name === 'record_vendor_payment') {
			expect(payload.details.amount).toBe(500);
			expect(payload.details.reference_no).toContain('QA-BANK');
			paid += 1;
			current.payments.push({ name: `PAY-QA-${paid}`, posting_date: today, paid_amount: 500, reference_no: payload.details.reference_no, paid_from: 'SF Axis Bank' });
			if (!payload.details.invoice) current.advance_paid = 500;
			else current.invoices[0].outstanding_amount = 0;
			return current;
		}
		if (name === 'record_goods_received') {
			expect(payload.details.items[0].qty).toBe(10); received = true;
			current.items[0].received_qty = 10; current.actions.receive = false; current.actions.invoice = true;
			current.receipts.push({ name: 'PR-QA', posting_date: today, grand_total: 1000, items: [{ name: 'PRI-QA', item_name: 'Steel plates', qty: 10, amount: 1000, rate: 100, billed_amt: 0 }] });
			return current;
		}
		if (name === 'record_supplier_invoice') {
			expect(payload.details.bill_no).toBe('GANESH-101');
			expect(payload.details.items[0].expense_account).toBe('Programme Materials - SF');
			expect(payload.details.proof.file_name).toBe('supplier-bill.png'); billed = true;
			expect(payload.details).not.toHaveProperty('tax_breakup');
			current.actions.invoice = false;
			current.invoices.push({ name: 'PI-QA', bill_no: 'GANESH-101', bill_date: today, grand_total: 1000, total_advance: 500, outstanding_amount: 500 });
			return current;
		}
	});
	await page.goto('/volunteering/purchase-accounts?order=PUR-ORD-QA');
	await page.getByRole('button', { name: 'Record supplier advance', exact: true }).click();
	await choose(page, 'Pay from *', 'Axis');
	await page.getByLabel('Amount (INR) *').fill('500');
	await page.getByLabel('Bank transaction reference *').fill('QA-BANK-ADVANCE');
	await page.getByRole('checkbox', { name: 'I confirm this money has been paid to the supplier.' }).check();
	await page.getByRole('button', { name: 'Record payment', exact: true }).click();
	await expect(page.getByRole('heading', { name: 'Payment history', exact: true })).toBeVisible();
	await page.getByRole('button', { name: 'Record goods received', exact: true }).click();
	await page.getByRole('button', { name: 'Confirm goods received', exact: true }).click();
	await expect(page.getByRole('heading', { name: 'Delivery history', exact: true })).toBeVisible();
	await page.getByRole('button', { name: 'Record supplier bill', exact: true }).click();
	await page.getByLabel('Supplier invoice number *').fill('GANESH-101');
	await choose(page, 'Expense ledger *', 'Programme');
	await page.getByLabel('Supplier bill *', { exact: true }).setInputFiles({ name: 'supplier-bill.png', mimeType: 'image/png', buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZlVAAAAAASUVORK5CYII=', 'base64') });
	await page.getByRole('button', { name: 'Post supplier bill and apply advances', exact: true }).click();
	await expect(page.getByRole('heading', { name: 'Supplier bills', exact: true })).toBeVisible();
	await page.getByRole('button', { name: 'Record bill payment', exact: true }).click();
	await choose(page, 'Pay from *', 'Axis');
	await page.getByLabel('Bank transaction reference *').fill('QA-BANK-FINAL');
	await page.getByRole('checkbox', { name: 'I confirm this money has been paid to the supplier.' }).check();
	await page.getByRole('button', { name: 'Record payment', exact: true }).click();
	await expect(page.getByRole('button', { name: 'Record bill payment', exact: true })).toHaveCount(0);
	expect(paid).toBe(2); expect(received).toBe(true); expect(billed).toBe(true);
});

test('Accounts optionally records included taxes without increasing the bill total', async ({ page }) => {
	const current = purchase(true);
	current.grand_total = 1180; current.net_total = 1180;
	current.items[0].amount = 1180; current.items[0].rate = 118; current.items[0].received_qty = 10;
	current.actions.receive = false; current.actions.invoice = true;
	current.receipts.push({ name: 'PR-TAX', posting_date: today, grand_total: 1180, items: [{ name: 'PRI-TAX', item_name: 'Steel plates', qty: 10, amount: 1180, rate: 118, billed_amt: 0 }] });
	let submitted: any;
	await mock(page, workspace(true), current, (name, payload) => {
		if (name === 'record_supplier_invoice') {
			submitted = payload.details;
			current.actions.invoice = false;
			current.invoices.push({ name: 'PI-TAX', bill_no: 'TAX-INCLUSIVE-01', bill_date: today, grand_total: 1180, total_advance: 0, outstanding_amount: 1180,
				tax_breakup: { treatment: 'Non-recoverable tax included in purchase cost', gross_total: 1180, base_total: 1000, tax_total: 180, recorded_by: 'accounts@example.com', recorded_on: today, items: [{ item_name: 'Steel plates', gross_amount: 1180, base_amount: 1000, cgst: 90, sgst: 90, igst: 0, other_tax: 0 }] } });
			return current;
		}
	});
	await page.goto('/volunteering/purchase-accounts?order=PUR-ORD-QA');
	await page.getByRole('button', { name: 'Record supplier bill', exact: true }).click();
	await expect(page.getByLabel('CGST included (INR)', { exact: true })).toHaveCount(0);
	await page.getByRole('checkbox', { name: 'Record included tax breakup (optional)' }).check();
	await page.getByLabel('CGST included (INR)', { exact: true }).fill('90');
	await page.getByLabel('SGST / UTGST included (INR)', { exact: true }).fill('90');
	await expect(page.getByText('Total unchanged: ₹1,180.00', { exact: true })).toBeVisible();
	await page.screenshot({ path: 'output/qa/accounts-included-tax-breakup.png', fullPage: true });
	await page.getByLabel('Supplier invoice number *', { exact: true }).fill('TAX-INCLUSIVE-01');
	await choose(page, 'Expense ledger *', 'Programme');
	await page.getByLabel('Supplier bill *', { exact: true }).setInputFiles({ name: 'inclusive-bill.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 demo UI fixture') });
	await page.getByRole('button', { name: 'Post supplier bill and apply advances', exact: true }).click();
	await expect(page.getByRole('heading', { name: 'Supplier bills', exact: true })).toBeVisible();
	expect(submitted.tax_breakup).toEqual([{ receipt_item: 'PRI-TAX', cgst: 90, sgst: 90, igst: 0, other_tax: 0 }]);
	expect(submitted).not.toHaveProperty('record_tax_breakup');
	await page.getByText('Included tax breakup — Accounts record', { exact: true }).click();
	await expect(page.getByText('Tax-inclusive cost: ₹1,180.00', { exact: true })).toBeVisible();
});

test('Accounts breakup rejects excessive tax, and unchecking omits it from the bill', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 844 });
	const current = purchase(true);
	current.actions.invoice = true;
	current.receipts.push({ name: 'PR-TAX', posting_date: today, grand_total: 1000, items: [{ name: 'PRI-TAX', item_name: 'Steel plates', qty: 10, amount: 1000, rate: 100, billed_amt: 0 }] });
	let submitted: any;
	await mock(page, workspace(true), current, (name, payload) => { if (name === 'record_supplier_invoice') { submitted = payload.details; return current; } });
	await page.goto('/volunteering/purchase-accounts?order=PUR-ORD-QA');
	await page.getByRole('button', { name: 'Record supplier bill', exact: true }).click();
	await page.getByRole('checkbox', { name: 'Record included tax breakup (optional)' }).check();
	await page.getByLabel('CGST included (INR)', { exact: true }).fill('700');
	await page.getByLabel('SGST / UTGST included (INR)', { exact: true }).fill('700');
	await expect(page.getByRole('alert')).toContainText('Included taxes cannot exceed');
	await expect(page.getByRole('button', { name: 'Post supplier bill and apply advances', exact: true })).toBeDisabled();
	expect(await page.locator('.purchase-page').evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
	await page.getByRole('checkbox', { name: 'Record included tax breakup (optional)' }).uncheck();
	await page.getByLabel('Supplier invoice number *', { exact: true }).fill('GROSS-ONLY');
	await choose(page, 'Expense ledger *', 'Programme');
	await page.getByLabel('Supplier bill *', { exact: true }).setInputFiles({ name: 'bill.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 demo UI fixture') });
	await page.getByRole('button', { name: 'Post supplier bill and apply advances', exact: true }).click();
	await expect(page.getByRole('status')).toContainText('Supplier bill posted');
	expect(submitted).not.toHaveProperty('tax_breakup');
});

test('purchase details and entry fields fit a narrow phone screen', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 844 });
	await mock(page, workspace(true), purchase(true));
	await page.goto('/volunteering/purchase-accounts?order=PUR-ORD-QA');
	await expect(page.getByRole('heading', { name: 'Order and delivery', exact: true })).toBeVisible();
	await page.getByRole('button', { name: 'Record supplier advance', exact: true }).click();
	await expect(page.getByLabel('Amount (INR) *')).toBeVisible();
	expect(await page.locator('.purchase-page').evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
	await page.screenshot({ path: 'output/qa/vendor-purchases-mobile.png', fullPage: true });
});
