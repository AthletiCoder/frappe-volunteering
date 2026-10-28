import { expect, test, type Page } from '@playwright/test';
import { loginViaAPI } from '../../helpers/auth';
import { chooseSearch, expectNoDesk, portalCall, qaReceipt, requireLocalRegression } from '../../helpers/portal-regression';

const api = 'volunteering.volunteering.vendor_purchases.';
const password = process.env.E2E_PURCHASE_PASSWORD || 'PurchaseDemo!26';
async function login(page: Page, role: string, path: string) {
	await loginViaAPI(page.request, `demo.purchase.${role}@sevamrita.local`, password);
	await page.goto(path);
	await expectNoDesk(page);
}

test('real Home purchase: request → assigned approval → supplier advance → delivery → bill → final payment', async ({ page, browser, baseURL }, testInfo) => {
	test.setTimeout(240_000);
	requireLocalRegression(baseURL);
	const ref = `QA-HOME-PURCHASE-${Date.now()}`;
	await login(page, 'employee', '/volunteering/vendor-purchases?new=1');
	await chooseSearch(page, 'Supplier *', 'Demo Annapurna Kitchen');
	await chooseSearch(page, 'Project *', 'Purchasing Demo - Pune Community Kitchen');
	await chooseSearch(page, 'Purchase item *', 'Demo Steel Dining Plate');
	await page.getByRole('spinbutton', { name: /^Quantity/ }).fill('10');
	await page.getByLabel('Unit price including taxes (INR) *', { exact: true }).fill('180');
	await page.getByLabel('Purpose and order instructions').fill(`${ref}: fictional supplies; no actual purchase or bank transfer.`);
	const submitted = page.waitForResponse(response => response.url().includes('save_purchase'));
	await page.getByRole('button', { name: 'Submit purchase for approval', exact: true }).click();
	const submittedResponse = await submitted;
	expect(submittedResponse.status(), await submittedResponse.text()).toBe(200);
	const order = (await submittedResponse.json()).message;
	expect(order.grand_total).toBe(1800);
	expect(order.workflow_state).toBe('Pending Approval');
	expect(order.pending_approver).toBe('demo.purchase.manager@sevamrita.local');
	await expect(page.getByRole('heading', { name: order.name, exact: true })).toBeVisible();
	await expect(page.getByRole('button', { name: 'Record supplier advance', exact: true })).toHaveCount(0);
	const managerContext = await browser.newContext({ baseURL });
	const accountsContext = await browser.newContext({ baseURL });
	try {
		const accounts = await accountsContext.newPage();
		await login(accounts, 'accounts', '/volunteering/purchase-accounts');
		const pendingAccounts = await portalCall(accounts, `${api}get_purchase_workspace`, { view: 'accounts' });
		expect(pendingAccounts.orders.some((row: any) => row.name === order.name)).toBe(false);
		const personal = await portalCall(accounts, `${api}get_purchase_workspace`, { view: 'requests' });
		expect(personal.orders.some((row: any) => row.name === order.name)).toBe(false);
		const manager = await managerContext.newPage();
		await login(manager, 'manager', `/volunteering/purchase-approvals?order=${order.name}`);
		await manager.getByLabel('Review notes').fill('QA: checked the fictional quotation and quantities.');
		await manager.getByRole('button', { name: 'Approve purchase order', exact: true }).click();
		await expect(manager).toHaveURL(/\/purchase-approvals$/);
		await expect(manager.getByRole('status')).toContainText('Approve');
		expect((await portalCall(manager, `${api}get_purchase_workspace`, { view: 'approvals' })).orders.some((row: any) => row.name === order.name)).toBe(false);

		await accounts.goto(`/volunteering/purchase-accounts?order=${order.name}`);
		await accounts.getByRole('button', { name: 'Record supplier advance', exact: true }).click();
		await chooseSearch(accounts, 'Pay from *', 'Demo Purchasing Bank');
		await accounts.getByRole('spinbutton', { name: /^Amount \(INR\)/ }).fill('600');
		await accounts.getByLabel('Bank transaction reference *', { exact: true }).fill(`${ref}-ADVANCE`);
		await accounts.getByRole('checkbox', { name: 'I confirm this money has been paid to the supplier.' }).check();
		await accounts.getByRole('button', { name: 'Record payment', exact: true }).click();
		await expect(accounts.getByRole('status')).toContainText('Supplier payment recorded');
		await page.reload();
		await page.getByRole('button', { name: 'Record goods received', exact: true }).click();
		await page.getByRole('button', { name: 'Confirm goods received', exact: true }).click();
		await expect(page.getByRole('status')).toContainText('Goods receipt recorded');

		await accounts.reload();
		await accounts.getByRole('button', { name: 'Record supplier bill', exact: true }).click();
		await accounts.getByLabel('Supplier invoice number *', { exact: true }).fill(ref);
		await chooseSearch(accounts, 'Expense ledger *', 'Kitchen Utensils and Small Equipment');
		await accounts.getByLabel('Supplier bill *', { exact: true }).setInputFiles(qaReceipt(`${ref} total INR 1800`));
		await accounts.getByRole('button', { name: 'Post supplier bill and apply advances', exact: true }).click();
		await expect(accounts.getByRole('status')).toContainText('Supplier bill posted');
		let result = await portalCall(accounts, `${api}get_purchase`, { name: order.name, view: 'accounts' });
		expect(result.invoices).toHaveLength(1);
		expect(result.invoices[0].grand_total).toBe(1800);
		expect(result.invoices[0].total_advance).toBe(600);
		expect(result.invoices[0].outstanding_amount).toBe(1200);
		const bill = result.attachments.find((row: any) => row.attached_to_name === result.invoices[0].name);
		expect(bill?.file_url).toMatch(/^\/private\/files\//);
		const download = await accounts.request.get(bill.file_url);
		expect(download.status()).toBe(200);
		expect((await download.body()).subarray(0, 4).toString()).toBe('%PDF');
		await accounts.getByRole('button', { name: 'Record bill payment', exact: true }).click();
		await expect(accounts.getByRole('spinbutton', { name: /^Amount \(INR\)/ })).toHaveValue('1200');
		await chooseSearch(accounts, 'Pay from *', 'Demo Purchasing Bank');
		await accounts.getByLabel('Bank transaction reference *', { exact: true }).fill(`${ref}-FINAL`);
		await accounts.getByRole('checkbox', { name: 'I confirm this money has been paid to the supplier.' }).check();
		await accounts.getByRole('button', { name: 'Record payment', exact: true }).click();
		await expect(accounts.getByRole('status')).toContainText('Supplier payment recorded');
		await expect(accounts.getByRole('button', { name: 'Record bill payment', exact: true })).toHaveCount(0);
		result = await portalCall(accounts, `${api}get_purchase`, { name: order.name, view: 'accounts' });
		expect(result.invoices[0].outstanding_amount).toBe(0);
		expect(result.payments).toHaveLength(2);
		expect(result.payments.reduce((sum: number, row: any) => sum + Number(row.paid_amount), 0)).toBe(1800);
		await page.reload();
		await expect(page.getByRole('heading', { name: 'Supplier bills', exact: true })).toBeVisible();
		await expect(page.getByRole('button', { name: 'Record bill payment', exact: true })).toHaveCount(0);
		await testInfo.attach('purchase-accounting-result', { body: JSON.stringify(result, null, 2), contentType: 'application/json' });
	} finally {
		await managerContext.close();
		await accountsContext.close();
	}
});

test('employee cannot inspect the Accounts processing page or another requester’s purchase', async ({ page, baseURL }) => {
	requireLocalRegression(baseURL);
	await login(page, 'employee', '/volunteering/purchase-accounts');
	await expect(page.getByRole('alert')).toContainText('Accounts access is required');
	await expect(page.getByRole('button', { name: 'Record supplier advance', exact: true })).toHaveCount(0);
	await page.goto('/volunteering/purchase-approvals');
	await expect(page.getByRole('heading', { name: 'Purchase approvals', exact: true })).toBeVisible();
	await expect(page.locator('.purchase-row')).toHaveCount(0);
});
