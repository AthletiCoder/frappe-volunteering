import { expect, test, type Page } from '@playwright/test';

const sections = [
	{ id: 'my_purchase_requests', label: 'My purchase requests', route: '/volunteering/vendor-purchases' },
	{ id: 'purchase_approvals', label: 'Purchase approvals', route: '/volunteering/purchase-approvals' },
	{ id: 'approved_purchases', label: 'Approved purchases — Accounts', route: '/volunteering/purchase-accounts' },
];
function order(name: string, supplier: string, state: string, overrides = {}) {
	return {
		name, supplier_name: supplier, supplier: 'SUP-QA', project: 'PROJ-QA', project_name: 'Community kitchen',
		owner: 'requester@example.com', pending_approver: 'hybrid@example.com', modified: '2026-10-22 12:00:00',
		workflow_state: state, docstatus: state === 'Approved' ? 1 : 0, status: 'To Receive and Bill',
		transaction_date: '2026-10-22', schedule_date: '2026-10-25', currency: 'INR', grand_total: 1000,
		advance_paid: 0, outstanding_amount: 0, per_received: 0, per_billed: 0, prices_include_tax: true,
		items: [{ name: 'POI-QA', item_name: 'Steel plates', qty: 10, rate: 100, amount: 1000, uom: 'Nos' }],
		receipts: [], invoices: [], payments: [], attachments: [],
		// Deliberately broad fixture: the UI must still respect its page perspective.
		actions: { edit: true, review: true, receive: true, invoice: true, pay: true, transitions: ['Approve', 'Reject'], approval_flags: { can_approve: true } },
		...overrides,
	};
}
const rows = {
	requests: [order('PO-MINE', 'My own supplier', 'Draft')],
	approvals: [order('PO-REVIEW', 'Assigned supplier', 'Pending Approval')],
	accounts: [order('PO-FINANCE', 'Approved supplier', 'Approved'), order('PO-PAID', 'Already paid supplier', 'Approved', { per_received: 100, per_billed: 100 })],
};
async function mockPages(page: Page, accounts = true) {
	const calls: { name: string; payload: any }[] = [];
	let reviewed = false;
	await page.route('**/api/method/**', async route => {
		const name = new URL(route.request().url()).pathname.split('.').pop() || '';
		const payload = route.request().postDataJSON() || {};
		calls.push({ name, payload });
		if (!accounts && payload.view === 'accounts') {
			await route.fulfill({ status: 403, json: { message: 'Accounts access is required for this action.' } });
			return;
		}
		let result: any = {};
		if (name === 'get_home_payload') result = {
			allowed: true, full_name: 'Nikhil Shah', waiting_count: 0, nav: {}, flags: {},
			actions: { purchasing: accounts ? sections : sections.slice(0, 2) },
		};
		if (name === 'get_purchase_workspace') result = {
			view: payload.view, today: '2026-10-22', currency: 'INR',
			orders: payload.view === 'approvals' && reviewed ? [] : rows[payload.view as keyof typeof rows],
			projects: [], suppliers: [], items: [], warehouses: [], expense_accounts: [], payment_accounts: [], modes: [], uoms: [],
			capabilities: { accounts, create: payload.view === 'requests', manage_suppliers: accounts },
			advance_setup: { ready: true },
		};
		if (name === 'get_purchase') result = Object.values(rows).flat().find(row => row.name === payload.name);
		if (name === 'review_purchase') reviewed = true;
		await route.fulfill({ json: { message: result } });
	});
	return calls;
}

test('a mixed-role user switches between three separate lists from the Purchasing menu', async ({ page }) => {
	const calls = await mockPages(page);
	await page.goto(sections[0].route);
	const menu = page.getByRole('navigation', { name: 'Sections', exact: true });
	for (const section of sections) {
		await expect(menu.getByRole('link', { name: section.label, exact: true })).toBeVisible();
	}
	await expect(page.getByRole('heading', { name: sections[0].label, exact: true })).toBeVisible();
	await expect(page.getByRole('heading', { name: 'My own supplier' })).toBeVisible();
	await expect(page.getByRole('heading', { name: 'Assigned supplier' })).toHaveCount(0);
	await expect(page.getByRole('button', { name: 'Create purchase order', exact: true })).toBeVisible();
	for (const [section, supplier] of [[sections[1], 'Assigned supplier'], [sections[2], 'Approved supplier']] as const) {
		await menu.getByRole('link', { name: section.label, exact: true }).click();
		await expect(page.getByRole('heading', { name: section.label, exact: true })).toBeVisible();
		await expect(page.getByRole('heading', { name: supplier, exact: true })).toBeVisible();
		await expect(page.getByRole('heading', { name: 'My own supplier' })).toHaveCount(0);
		await expect(page.getByRole('button', { name: 'Create purchase order', exact: true })).toHaveCount(0);
	}
	expect(calls.filter(call => call.name === 'get_purchase_workspace').map(call => call.payload.view)).toEqual(['requests', 'approvals', 'accounts']);
});

test('personal detail has no approval, bill or payment actions even for an Accounts approver', async ({ page }) => {
	const calls = await mockPages(page);
	await page.goto('/volunteering/vendor-purchases?order=PO-MINE');
	await expect(page.getByRole('heading', { name: 'PO-MINE', exact: true })).toBeVisible();
	await expect(page.getByRole('button', { name: 'Edit order', exact: true })).toBeVisible();
	for (const label of ['Approve purchase order', 'Record supplier bill', 'Record supplier advance', 'Record bill payment'])
		await expect(page.getByRole('button', { name: label, exact: true })).toHaveCount(0);
	expect(calls.find(call => call.name === 'get_purchase')?.payload).toEqual({ name: 'PO-MINE', view: 'requests' });
});

test('approval detail only reviews the request and returns to the pending queue after a decision', async ({ page }) => {
	const calls = await mockPages(page);
	await page.goto('/volunteering/purchase-approvals?order=PO-REVIEW');
	await expect(page.getByRole('heading', { name: 'PO-REVIEW', exact: true })).toBeVisible();
	for (const label of ['Edit order', 'Record goods received', 'Record supplier bill', 'Record supplier advance'])
		await expect(page.getByRole('button', { name: label, exact: true })).toHaveCount(0);
	await page.getByLabel('Review notes').fill('Quotation and quantity checked.');
	await page.getByRole('button', { name: 'Approve purchase order', exact: true }).click();
	await expect(page).toHaveURL(/\/purchase-approvals$/);
	await expect(page.getByText('No pending purchase requests are assigned to you that match this search.', { exact: true })).toBeVisible();
	expect(calls.find(call => call.name === 'get_purchase')?.payload.view).toBe('approvals');
	expect(calls.find(call => call.name === 'review_purchase')?.payload.action).toBe('Approve');
});

test('Accounts detail processes approved purchases without requester or approval controls', async ({ page }) => {
	const calls = await mockPages(page);
	await page.goto('/volunteering/purchase-accounts?order=PO-FINANCE');
	await expect(page.getByRole('heading', { name: 'PO-FINANCE', exact: true })).toBeVisible();
	await expect(page.getByRole('button', { name: 'Record supplier advance', exact: true })).toBeVisible();
	await expect(page.getByRole('button', { name: 'Record supplier bill', exact: true })).toBeVisible();
	await expect(page.getByRole('button', { name: 'Edit order', exact: true })).toHaveCount(0);
	await expect(page.getByRole('button', { name: 'Approve purchase order', exact: true })).toHaveCount(0);
	expect(calls.find(call => call.name === 'get_purchase')?.payload.view).toBe('accounts');
});

test('an employee opening the restricted Accounts URL gets no list or processing buttons', async ({ page }) => {
	await mockPages(page, false);
	await page.goto('/volunteering/purchase-accounts');
	await expect(page.getByRole('alert')).toBeVisible();
	await expect(page.getByRole('heading', { name: 'Approved supplier' })).toHaveCount(0);
	await expect(page.getByRole('button', { name: 'Create purchase order', exact: true })).toHaveCount(0);
});

test('all three list layouts fit a phone and the old payments link redirects to Accounts', async ({ page }) => {
	await mockPages(page);
	await page.setViewportSize({ width: 390, height: 844 });
	for (const section of sections) {
		await page.goto(section.route);
		await expect(page.getByRole('heading', { name: section.label, exact: true })).toBeVisible();
		expect(await page.locator('.purchase-page').evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
	}
	await page.goto('/volunteering/vendor-purchases?view=payments');
	await expect(page).toHaveURL(/\/purchase-accounts\?view=payments$/);
	await expect(page.getByRole('combobox', { name: 'Show', exact: true })).toHaveValue('Awaiting payment');
	await expect(page.getByRole('heading', { name: 'Already paid supplier' })).toHaveCount(0);
});
