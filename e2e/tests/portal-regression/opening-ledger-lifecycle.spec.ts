import { expect, test, type Page } from '@playwright/test';
import { loginViaAPI } from '../../helpers/auth';
import { PERSONAS } from '../../helpers/personas';
import { chooseSearch, portalCall, qaReceipt, requireLocalRegression } from '../../helpers/portal-regression';

async function createLedger(page: Page, label: string) {
	await page.goto('/volunteering/chart-of-accounts');
	await page.getByRole('button', { name: 'Add account', exact: true }).click();
	await page.getByLabel('Account name *', { exact: true }).fill(label);
	await chooseSearch(page, 'Parent group', 'Current Assets');
	const saved = page.waitForResponse(response => response.url().includes('save_account'));
	await page.getByRole('button', { name: 'Create account', exact: true }).click();
	const response = await saved;
	expect(response.status(), await response.text()).toBe(200);
	await expect(page.getByRole('status')).toContainText('Chart of Accounts updated');
	return (await response.json()).message.saved_account;
}
test.beforeEach(({ baseURL }) => requireLocalRegression(baseURL));

test('opening balance with private proof appears in the dated ledger and cannot be posted twice', async ({ page }) => {
	test.setTimeout(120_000);
	await loginViaAPI(page.request, PERSONAS.accounts.email, PERSONAS.accounts.password);
	const label = `QA Opening Proof ${Date.now()}`;
	const account = await createLedger(page, label);
	await page.goto('/volunteering/opening-balances');
	await chooseSearch(page, 'Ledger account *', label);
	await page.getByRole('spinbutton', { name: /Amount \(.*\) \*/ }).fill('123.45');
	await page.getByRole('textbox', { name: /^Source reference/ }).fill('QA ONLY: fictional opening statement');
	const date = await page.getByLabel(/^Opening date \*/).inputValue();
	await page.getByLabel('Proof documents (optional)', { exact: true }).setInputFiles(qaReceipt('QA ONLY opening balance INR 123.45'));
	await page.getByRole('checkbox', { name: /I checked the amount and date/ }).check();
	const posted = page.waitForResponse(response => response.url().includes('record_opening_balance'));
	await page.getByRole('button', { name: 'Post opening balance', exact: true }).click();
	const response = await posted;
	expect(response.status(), await response.text()).toBe(200);
	const result = (await response.json()).message;
	await expect(page.getByRole('status')).toContainText('Opening balance posted as');
	const ledger = await portalCall(page, 'volunteering.volunteering.chart_of_accounts_portal.get_account_ledger', { account, from_date: date, to_date: date });
	expect(ledger.entry_count).toBe(1);
	expect(ledger.total_debit).toBe(123.45);
	expect(ledger.closing_balance).toBe(123.45);
	expect(ledger.entries[0].voucher_no).toBe(result.journal_entry);
	const files = await portalCall(page, 'frappe.client.get_list', { doctype: 'File', filters: { attached_to_doctype: 'Journal Entry', attached_to_name: result.journal_entry }, fields: ['file_url', 'is_private'] });
	expect(files).toHaveLength(1);
	expect(files[0].is_private).toBe(1);
	expect((await page.request.get(files[0].file_url)).status()).toBe(200);
	await page.goto('/volunteering/chart-of-accounts');
	await page.getByLabel('Find an account').fill(label);
	await page.getByRole('button', { name: new RegExp(`^View ledger for ${label}`) }).click();
	await page.getByLabel('From posting date', { exact: true }).fill(date);
	await page.getByLabel('To posting date', { exact: true }).fill(date);
	await page.getByRole('button', { name: 'Show entries', exact: true }).click();
	await expect(page.locator('.ledger-summary')).toContainText('123.45');
	await expect(page.locator('.ledger-table')).toContainText(result.journal_entry);
	await page.goto('/volunteering/opening-balances');
	await chooseSearch(page, 'Ledger account *', label);
	await page.getByRole('spinbutton', { name: /Amount \(.*\) \*/ }).fill('123.45');
	await page.getByRole('textbox', { name: /^Source reference/ }).fill('Duplicate attempt must fail');
	await page.getByRole('checkbox', { name: /I checked the amount and date/ }).check();
	await page.getByRole('button', { name: 'Post opening balance', exact: true }).click();
	await expect(page.getByRole('alert')).toContainText(/already|existing/i);
	expect((await portalCall(page, 'volunteering.volunteering.chart_of_accounts_portal.get_account_ledger', { account, from_date: date, to_date: date })).entry_count).toBe(1);
});

test('Accounts Manager can disable and remove an unused ledger through Home', async ({ page }) => {
	await loginViaAPI(page.request, PERSONAS.accounts.email, PERSONAS.accounts.password);
	const label = `QA Unused Ledger ${Date.now()}`;
	await createLedger(page, label);
	// ERPNext blocks ledger renames for five minutes after any GL write. That
	// quiet-window guard is retained; account disabling does not rename it.
	await page.getByRole('checkbox', { name: /^Disabled/ }).check();
	await page.getByRole('button', { name: 'Save account', exact: true }).click();
	await expect(page.getByRole('status')).toContainText('Chart of Accounts updated');
	page.once('dialog', dialog => dialog.accept());
	await page.getByRole('button', { name: 'Remove unused account', exact: true }).click();
	await expect(page.getByRole('status')).toContainText('Unused account removed');
	const chart = await portalCall(page, 'volunteering.volunteering.chart_of_accounts_portal.get_chart_of_accounts');
	expect(chart.accounts.some((row: any) => row.account_name.startsWith(label))).toBe(false);
});
